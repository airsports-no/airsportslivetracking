"""
Who may see a contest and its navigation tasks, in one place.

A contest is public (listed), unlisted (public, but only reachable by its link) or private. A private contest, and a
private task in any contest, is only open to the contest's audience: the people with a view grant on the contest. Every
manager has a view grant too. Being in the audience means seeing the contest as a spectator does and taking part in it,
never managing it: screens only organisers need check change_contest instead.
"""

from django.contrib.auth.models import AnonymousUser
from django.db.models import Q, QuerySet
from guardian.shortcuts import get_objects_for_user

from display.models import Contest, MyUser, NavigationTask


def _is_authenticated(user) -> bool:
    return user is not None and user.is_authenticated


def audience_contests(user: MyUser | AnonymousUser | None) -> QuerySet[Contest]:
    """The contests [user] is in the audience of, whatever their visibility. Superusers are in every audience."""
    if not _is_authenticated(user):
        return Contest.objects.none()
    return get_objects_for_user(user, "display.view_contest", klass=Contest, accept_global_perms=False)


def is_contest_audience(user: MyUser | AnonymousUser | None, contest: Contest) -> bool:
    return _is_authenticated(user) and user.has_perm("display.view_contest", contest)


def can_view_contest(user: MyUser | AnonymousUser | None, contest: Contest) -> bool:
    """A public or unlisted contest is open to anybody with the link; a private one only to its audience."""
    return contest.is_public or is_contest_audience(user, contest)


def visible_contests(user: MyUser | AnonymousUser | None, listed_only: bool = False) -> QuerySet[Contest]:
    """
    The contests [user] may open. With [listed_only] an unlisted contest only counts for its audience, which is what
    lists and dashboards show: nobody else should find it without the link.
    """
    public = Q(is_public=True, is_featured=True) if listed_only else Q(is_public=True)
    return Contest.objects.filter(public | Q(pk__in=audience_contests(user).values("pk")))


def is_navigation_task_public(navigation_task: NavigationTask) -> bool:
    return navigation_task.is_public and navigation_task.contest.is_public


def can_view_navigation_task(user: MyUser | AnonymousUser | None, navigation_task: NavigationTask) -> bool:
    """A task open to anybody when it and its contest are public or unlisted, otherwise only to the contest's audience."""
    return is_navigation_task_public(navigation_task) or is_contest_audience(user, navigation_task.contest)


def visible_navigation_tasks_q(user: MyUser | AnonymousUser | None, prefix: str = "", listed_only: bool = False) -> Q:
    """
    The filter for the navigation tasks [user] may open, for a queryset of NavigationTask ([prefix] empty) or of a model
    that refers to one ([prefix] the path to it, e.g. "navigation_task__"). [listed_only] as in visible_contests.
    """
    public = {f"{prefix}is_public": True, f"{prefix}contest__is_public": True}
    if listed_only:
        public[f"{prefix}is_featured"] = True
    return Q(**public) | Q(**{f"{prefix}contest__in": audience_contests(user).values("pk")})
