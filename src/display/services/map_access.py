"""Who may open a navigation task's live tracking map; mirrors the API permission classes for tasks."""

from display.models import Contestant, NavigationTask
from display.services.contest_visibility import can_view_navigation_task


def can_view_task_map(user, task: NavigationTask) -> bool:
    """
    Same rule as NavigationTaskPublicPermissions / NavigationTaskContestPermissions for GET: the task and its contest are
    both public, or the user is in the contest's audience.
    """
    return can_view_navigation_task(user, task)


def map_path_for(contestant: Contestant) -> str:
    """The competition map for the contestant's task with this contestant selected (the web page's contestantIds)."""
    task = contestant.navigation_task
    return f"/competition-map/{task.contest_id}/{task.pk}?contestantIds={contestant.pk}"
