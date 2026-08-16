from __future__ import annotations

from django.conf import settings

from display.models import AccessGrant, ClubManagerMembership, UserTokenGrant
from display.utilities.task_type_group_definitions import CIMA_TASK_TYPE_GROUP, LEGACY_TASK_TYPE_GROUP

ALL_TASK_TYPE_GROUPS = [LEGACY_TASK_TYPE_GROUP, CIMA_TASK_TYPE_GROUP]


def gate_cima_task_visibility() -> bool:
    return bool(getattr(settings, "GATE_CIMA_TASK_VISIBILITY", False))


def get_user_granted_task_type_groups(user) -> list[str]:
    """Task-type groups this user actually holds a grant for: superuser status,
    an active token grant, or membership managing a club with an active
    access grant. Unlike get_visible_task_type_groups_for_user, this never
    falls back to "everything" just because the global visibility gate is
    off - it's meant for enforcement (does this user's own grant justify an
    action), not for deciding what to show in a dropdown.
    """
    groups: set[str] = set()

    if getattr(user, "is_superuser", False):
        groups.update(ALL_TASK_TYPE_GROUPS)
        return sorted(groups)

    if not getattr(user, "is_authenticated", False):
        return sorted(groups)

    token_grants = UserTokenGrant.objects.filter(user=user, token_type__is_active=True).select_related("token_type")
    for grant in token_grants:
        if grant.quantity_remaining > 0:
            groups.update(grant.token_type.task_type_groups or [])

    club_ids = ClubManagerMembership.objects.filter(user=user, is_active=True).values_list("club_id", flat=True)
    for grant in AccessGrant.objects.filter(club_id__in=club_ids).order_by("-created_at"):
        if grant.is_active:
            groups.update(grant.task_type_groups or [])

    return sorted(groups)


def get_visible_task_type_groups_for_user(user) -> list[str]:
    if not gate_cima_task_visibility():
        return list(ALL_TASK_TYPE_GROUPS)

    configured_free = getattr(settings, "DEFAULT_FREE_TASK_TYPE_GROUPS", None)
    groups = set(configured_free if configured_free is not None else [LEGACY_TASK_TYPE_GROUP])

    if CIMA_TASK_TYPE_GROUP in groups:
        return sorted(groups)

    groups.update(get_user_granted_task_type_groups(user))
    return sorted(groups)


def can_user_see_cima_task_types(user) -> bool:
    return CIMA_TASK_TYPE_GROUP in get_visible_task_type_groups_for_user(user)
