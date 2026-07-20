from django.core.exceptions import ValidationError
from django.db import transaction

from display.models import ContestTokenAssignment, UserTokenGrant, ContestUsageLedger, Contestant


def _backfill_historical_usage_for_existing_contest(contest):
    started_contestants = Contestant.objects.filter(
        navigation_task__contest=contest,
        contestanttrack__calculator_started=True,
    ).select_related("navigation_task").distinct()
    for contestant in started_contestants:
        ContestUsageLedger.objects.get_or_create(
            contest=contest,
            contestant=contestant,
            kind=ContestUsageLedger.CONTESTANT_STARTED,
            defaults={"navigation_task": contestant.navigation_task},
        )
    started_tasks = contest.navigationtask_set.filter(
        contestant__contestanttrack__calculator_started=True
    ).distinct()
    for task in started_tasks:
        ContestUsageLedger.objects.get_or_create(
            contest=contest,
            navigation_task=task,
            kind=ContestUsageLedger.TASK_STARTED,
        )


@transaction.atomic
def assign_token_to_contest(contest, acting_user, token_grant_id: int):
    token_grant = UserTokenGrant.objects.select_for_update().select_related("token_type").get(pk=token_grant_id)

    if token_grant.user_id != acting_user.id:
        raise ValidationError("You cannot assign tokens that belong to another user")
    if not token_grant.has_available_tokens:
        raise ValidationError("This token grant has no remaining tokens")
    if ContestTokenAssignment.objects.filter(contest=contest).exists():
        raise ValidationError("This contest already has a token assigned")

    token_grant.quantity_consumed += 1
    token_grant.full_clean()
    token_grant.save(update_fields=["quantity_consumed", "updated_at"])

    _backfill_historical_usage_for_existing_contest(contest)
    assignment = ContestTokenAssignment.objects.create(
        contest=contest,
        token_grant=token_grant,
        token_type=token_grant.token_type,
        assigned_by=acting_user,
    )
    return assignment


@transaction.atomic
def replace_token_for_contest(contest, acting_user, token_grant_id: int):
    existing_assignment = ContestTokenAssignment.objects.select_for_update().filter(contest=contest).first()
    if existing_assignment is None:
        raise ValidationError("This contest does not have an assigned token to replace")
    if existing_assignment.token_grant_id == token_grant_id:
        raise ValidationError("This contest is already using the selected token grant")

    new_token_grant = UserTokenGrant.objects.select_for_update().select_related("token_type").get(pk=token_grant_id)
    if new_token_grant.user_id != acting_user.id:
        raise ValidationError("You cannot assign tokens that belong to another user")
    if not new_token_grant.has_available_tokens:
        raise ValidationError("This token grant has no remaining tokens")

    new_token_grant.quantity_consumed += 1
    new_token_grant.full_clean()
    new_token_grant.save(update_fields=["quantity_consumed", "updated_at"])

    existing_assignment.token_grant = new_token_grant
    existing_assignment.token_type = new_token_grant.token_type
    existing_assignment.assigned_by = acting_user
    existing_assignment.save(update_fields=["token_grant", "token_type", "assigned_by"])
    return existing_assignment
