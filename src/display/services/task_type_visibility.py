from __future__ import annotations

from django.conf import settings

from display.models import AccessGrant, ClubManagerMembership, UserEntitlementGrant, UserTokenGrant
from display.utilities.task_type_group_definitions import (
    CIMA_TASK_TYPE_GROUP,
    LEGACY_TASK_TYPE_GROUP,
    get_all_fine_task_type_groups,
    get_fine_task_type_group,
    get_task_type_group,
)

# Includes both coarse groups ("legacy", "cima") and every namespaced fine
# group ("cima:<subtype>"), so "grant everything" cases (superuser, the
# visibility gate being off) cover fine-grained grants too.
ALL_TASK_TYPE_GROUPS = get_all_fine_task_type_groups()


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

    entitlement_grants = UserEntitlementGrant.objects.filter(
        user=user, kind=UserEntitlementGrant.KIND_TASK_TYPE_GROUP, is_active=True
    )
    for grant in entitlement_grants:
        if grant.is_active_now:
            groups.add(grant.value)

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
    visible_groups = get_visible_task_type_groups_for_user(user)
    # A fine-grained grant (e.g. "cima:circle") should still surface the CIMA
    # section in the task-type picker; enforcement at save-time narrows to the
    # exact subtype regardless.
    return any(group == CIMA_TASK_TYPE_GROUP or group.startswith(f"{CIMA_TASK_TYPE_GROUP}:") for group in visible_groups)


def can_user_see_task_subtype(user, task_type: str | None = None, task_subtype: str | None = None) -> bool:
    """Whether this specific task subtype should be shown in task-creation UI
    (route editor wizard, Django task wizards). Legacy subtypes are always
    visible. CIMA subtypes require the coarse "cima" group OR the exact
    "cima:<subtype>" fine group in the user's visible set - mirroring the
    coarse-or-fine acceptance capacity_enforcement.py uses at save time, so
    what a user can see matches what they can actually create. user=None
    means "no user context" (e.g. building choices outside a request) and is
    treated as unrestricted, matching this module's existing convention.
    """
    coarse_group = get_task_type_group(task_type=task_type, task_subtype=task_subtype)
    if coarse_group != CIMA_TASK_TYPE_GROUP or user is None:
        return True
    fine_group = get_fine_task_type_group(task_type=task_type, task_subtype=task_subtype)
    visible_groups = get_visible_task_type_groups_for_user(user)
    return coarse_group in visible_groups or fine_group in visible_groups
