from rest_framework.exceptions import ValidationError
from django.utils import timezone

from display.models import ContestUsageLedger
from display.services.access_resolver import resolve_contest_access
from display.services.token_assignment import ensure_token_assignment_active_for_guest_start


def _should_enforce(resolution) -> bool:
    return resolution.enforcement_mode == "enforce"


def _is_owner_team(contest, team) -> bool:
    if not contest.created_by_id or team is None:
        return False
    owner_person = contest.created_by.person
    return team.crew.member1_id == owner_person.id


def _guest_pilot_has_contest_slot(contest, pilot) -> bool:
    return ContestUsageLedger.objects.filter(
        contest=contest,
        pilot=pilot,
        kind=ContestUsageLedger.CONTEST_PILOT_STARTED,
    ).exists()


def _guest_pilot_has_task_slot(contest, navigation_task, pilot) -> bool:
    return ContestUsageLedger.objects.filter(
        contest=contest,
        navigation_task=navigation_task,
        pilot=pilot,
        kind=ContestUsageLedger.TASK_PILOT_STARTED,
    ).exists()


def assert_can_add_navigation_task(contest):
    resolution = resolve_contest_access(contest)
    token_assignment = getattr(contest, "contesttokenassignment", None)
    if token_assignment is not None and token_assignment.expires_at is not None and token_assignment.expires_at <= timezone.now():
        raise ValidationError("This contest token has expired. The contest is now in archive mode until a new token or annual pass is applied.")
    return resolution


def assert_can_register_team(contest, team=None):
    resolution = resolve_contest_access(contest)
    if _is_owner_team(contest, team):
        return resolution
    if _should_enforce(resolution) and resolution.contestant_limit is not None and resolution.contestants_used >= resolution.contestant_limit:
        raise ValidationError("Free sandbox covers the contest owner only. Inviting additional pilots requires a token or club pass.")
    return resolution


def assert_can_self_register_contestant(navigation_task, contest_team):
    return assert_can_register_team(navigation_task.contest, contest_team.team)


def assert_can_start_contestant(contestant):
    contest = contestant.navigation_task.contest
    team = contestant.team
    pilot = team.crew.member1
    navigation_task = contestant.navigation_task
    resolution = resolve_contest_access(contest)
    if _is_owner_team(contest, team):
        return resolution
    ensure_token_assignment_active_for_guest_start(contest)
    if _guest_pilot_has_task_slot(contest, navigation_task, pilot):
        return resolution
    task_started_pilots = ContestUsageLedger.objects.filter(
        contest=contest,
        navigation_task=navigation_task,
        kind=ContestUsageLedger.TASK_PILOT_STARTED,
    ).count()
    if _should_enforce(resolution) and resolution.contestant_limit is not None:
        if task_started_pilots >= resolution.contestant_limit:
            raise ValidationError("Free sandbox covers the contest owner only. Inviting additional pilots requires a token or club pass.")
        if resolution.contestants_used >= resolution.contestant_limit and not _guest_pilot_has_contest_slot(contest, pilot):
            raise ValidationError("Free sandbox covers the contest owner only. Inviting additional pilots requires a token or club pass.")
    return resolution
