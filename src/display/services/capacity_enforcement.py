from rest_framework.exceptions import ValidationError

from display.models import ContestUsageLedger
from display.services.access_resolver import resolve_contest_access


def _should_enforce(resolution) -> bool:
    return resolution.enforcement_mode == "enforce"


def _is_owner_team(contest, team) -> bool:
    if not contest.created_by_id or team is None:
        return False
    owner_person = contest.created_by.person
    return team.crew.member1_id == owner_person.id


def _guest_team_has_contest_slot(contest, team) -> bool:
    return ContestUsageLedger.objects.filter(
        contest=contest,
        team=team,
        kind=ContestUsageLedger.CONTEST_TEAM_STARTED,
    ).exists()


def _guest_team_has_task_slot(contest, navigation_task, team) -> bool:
    return ContestUsageLedger.objects.filter(
        contest=contest,
        navigation_task=navigation_task,
        team=team,
        kind=ContestUsageLedger.TASK_TEAM_STARTED,
    ).exists()


def assert_can_add_navigation_task(contest):
    resolution = resolve_contest_access(contest)
    if _should_enforce(resolution) and resolution.task_limit is not None and resolution.tasks_used >= resolution.task_limit:
        raise ValidationError("Navigation task limit reached for this contest")
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
    resolution = resolve_contest_access(contest)
    if _is_owner_team(contest, team):
        return resolution
    if _guest_team_has_task_slot(contest, contestant.navigation_task, team):
        return resolution
    if _should_enforce(resolution) and resolution.contestant_limit is not None and resolution.contestants_used >= resolution.contestant_limit and not _guest_team_has_contest_slot(contest, team):
        raise ValidationError("Free sandbox covers the contest owner only. Inviting additional pilots requires a token or club pass.")
    return resolution
