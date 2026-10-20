"""
Who may see a contest and its navigation tasks, in one place.

A contest is either public, open to anybody, or private. A private contest, and a private task in any contest, is only
open to the contest's audience: the people with a view grant on the contest, and the members of the squadrons it is shared
with. Every manager has a view grant too. Being in the audience means seeing the contest as a spectator does and taking
part in it, never managing it: screens only organisers need check change_contest instead.
"""

from django.contrib.auth.models import AnonymousUser
from django.db.models import Q, QuerySet
from guardian.shortcuts import get_objects_for_user

from display.models import Contest, MyUser, NavigationTask


def _is_authenticated(user) -> bool:
    return user is not None and user.is_authenticated


def audience_contests(user: MyUser | AnonymousUser | None) -> QuerySet[Contest]:
    """
    The contests [user] is in the audience of, whatever their visibility: those they have a view grant on and those
    shared with a squadron they are a member of. Superusers are in every audience.
    """
    if not _is_authenticated(user):
        return Contest.objects.none()
    granted = get_objects_for_user(user, "display.view_contest", klass=Contest, accept_global_perms=False)
    if user.is_superuser:
        return granted
    return Contest.objects.filter(Q(pk__in=granted.values("pk")) | Q(pk__in=squadron_contests(user).values("pk")))


def squadron_contests(user: MyUser | AnonymousUser | None) -> QuerySet[Contest]:
    """The contests shared with a squadron [user] is a member of."""
    if not _is_authenticated(user):
        return Contest.objects.none()
    return Contest.objects.filter(shared_with_squadrons__memberships__user=user)


def is_contest_audience(user: MyUser | AnonymousUser | None, contest: Contest) -> bool:
    if not _is_authenticated(user):
        return False
    return user.has_perm("display.view_contest", contest) or squadron_contests(user).filter(pk=contest.pk).exists()


def can_view_contest(user: MyUser | AnonymousUser | None, contest: Contest) -> bool:
    """A public contest is open to anybody; a private one only to its audience."""
    return contest.is_public or is_contest_audience(user, contest)


def visible_contests(user: MyUser | AnonymousUser | None) -> QuerySet[Contest]:
    """The contests [user] may open: the public ones and those of the audiences they are in."""
    return Contest.objects.filter(Q(is_public=True) | Q(pk__in=audience_contests(user).values("pk")))


def is_navigation_task_public(navigation_task: NavigationTask) -> bool:
    return navigation_task.is_public and navigation_task.contest.is_public


def can_view_navigation_task(user: MyUser | AnonymousUser | None, navigation_task: NavigationTask) -> bool:
    """A task open to anybody when it and its contest are public, otherwise only to the contest's audience."""
    return is_navigation_task_public(navigation_task) or is_contest_audience(user, navigation_task.contest)


def visible_navigation_tasks_q(user: MyUser | AnonymousUser | None, prefix: str = "") -> Q:
    """
    The filter for the navigation tasks [user] may open, for a queryset of NavigationTask ([prefix] empty) or of a model
    that refers to one ([prefix] the path to it, e.g. "navigation_task__").
    """
    public = Q(**{f"{prefix}is_public": True, f"{prefix}contest__is_public": True})
    return public | Q(**{f"{prefix}contest__in": audience_contests(user).values("pk")})
