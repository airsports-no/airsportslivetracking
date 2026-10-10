"""Who may open a navigation task's live tracking map; mirrors the API permission classes for tasks."""

from display.models import Contestant, NavigationTask


def can_view_task_map(user, task: NavigationTask) -> bool:
    """
    Same rule as NavigationTaskPublicPermissions / NavigationTaskContestPermissions for GET: the task and its contest are
    both public, or the user has been given view permission on the contest (organizers, club managers, ...).
    """
    if task.is_public and task.contest.is_public:
        return True
    return bool(user is not None and user.is_authenticated and user.has_perm("view_contest", task.contest))


def map_path_for(contestant: Contestant) -> str:
    """The competition map for the contestant's task with this contestant selected (the web page's contestantIds)."""
    task = contestant.navigation_task
    return f"/competition-map/{task.contest_id}/{task.pk}?contestantIds={contestant.pk}"
