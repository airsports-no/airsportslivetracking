from rest_framework.exceptions import ValidationError

from display.services.access_resolver import resolve_contest_access


def _should_enforce(resolution) -> bool:
    return resolution.enforcement_mode == "enforce"



def assert_can_add_navigation_task(contest):
    resolution = resolve_contest_access(contest)
    if _should_enforce(resolution) and resolution.task_limit is not None and resolution.tasks_used >= resolution.task_limit:
        raise ValidationError("Navigation task limit reached for this contest")
    return resolution



def assert_can_register_team(contest):
    resolution = resolve_contest_access(contest)
    if _should_enforce(resolution) and resolution.contestant_limit is not None and resolution.contestants_used >= resolution.contestant_limit:
        raise ValidationError("Contestant limit reached for this contest")
    return resolution



def assert_can_self_register_contestant(navigation_task, contest_team):
    return assert_can_register_team(navigation_task.contest)
