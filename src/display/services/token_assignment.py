from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from display.models import ContestTokenAssignment, UserTokenGrant, ContestUsageLedger, Contestant


def _backfill_historical_usage_for_existing_contest(contest):
    started_contestants = Contestant.objects.filter(
        navigation_task__contest=contest,
        contestanttrack__calculator_started=True,
    ).select_related("navigation_task", "team__crew").distinct()
    owner_person_id = None
    if contest.created_by_id:
        try:
            owner_person_id = contest.created_by.person.id
        except Exception:
            owner_person_id = None
    for contestant in started_contestants:
        if owner_person_id is not None and contestant.team.crew.member1_id == owner_person_id:
            continue
        pilot = contestant.team.crew.member1
        ContestUsageLedger.objects.get_or_create(
            contest=contest,
            pilot=pilot,
            kind=ContestUsageLedger.CONTEST_PILOT_STARTED,
            defaults={
                "navigation_task": contestant.navigation_task,
                "team": contestant.team,
                "contestant": contestant,
            },
        )
        ContestUsageLedger.objects.get_or_create(
            contest=contest,
            navigation_task=contestant.navigation_task,
            pilot=pilot,
            kind=ContestUsageLedger.TASK_PILOT_STARTED,
            defaults={
                "team": contestant.team,
                "contestant": contestant,
            },
        )


def ensure_token_assignment_active_for_guest_start(contest):
    assignment = ContestTokenAssignment.objects.select_for_update().select_related("token_type").filter(contest=contest).first()
    if assignment is None:
        return None
    now = timezone.now()
    if assignment.expires_at is not None and assignment.expires_at <= now:
        raise ValidationError("This contest token has expired. The contest is now in archive mode until a new token or annual pass is applied.")
    if assignment.activated_at is None:
        assignment.activated_at = now
        if assignment.token_type.validity_days is not None:
            assignment.expires_at = now + timezone.timedelta(days=assignment.token_type.validity_days)
        assignment.save(update_fields=["activated_at", "expires_at"])
    return assignment


@transaction.atomic
def revert_token_assignment_for_support(assignment, acting_user):
    token_grant = UserTokenGrant.objects.select_for_update().get(pk=assignment.token_grant_id)
    token_grant.quantity_consumed = max(token_grant.quantity_consumed - 1, 0)
    token_grant.full_clean()
    token_grant.save(update_fields=["quantity_consumed", "updated_at"])
    assignment.delete()
    return token_grant


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
    existing_assignment.activated_at = None
    existing_assignment.expires_at = None
    existing_assignment.save(update_fields=["token_grant", "token_type", "assigned_by", "activated_at", "expires_at"])
    return existing_assignment
