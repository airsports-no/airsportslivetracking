"""
Who may do what with a series, as for a contest (display/services/contest_permissions.py): "view" sees a private series,
"change" runs it (settings, legs, and giving others access at any level) and "delete" may also delete it.
"""

from guardian.shortcuts import assign_perm, get_user_perms, get_users_with_perms, remove_perm
from rest_framework.exceptions import ValidationError

from display.models import MyUser, Series
from display.services.people_search import user_identities

SERIES_PERMISSION_MAP = {
    "nothing": [],
    "view": ["view_series"],
    "change": ["view_series", "change_series"],
    "delete": ["view_series", "change_series", "delete_series"],
}


def level_of(codenames) -> str:
    if "delete_series" in codenames:
        return "delete"
    if "change_series" in codenames:
        return "change"
    if "view_series" in codenames:
        return "view"
    return "nothing"


def get_series_permission_level(series: Series, user: MyUser) -> str:
    return level_of(get_user_perms(user, series))


def list_series_permission_grants(series: Series) -> list[dict]:
    users_and_permissions = get_users_with_perms(series, attach_perms=True)
    identities = user_identities(users_and_permissions)
    # Never the raw e-mail address, as for contests
    return [
        {"user_id": user.pk, **identities[user.pk], "level": level_of(codenames)}
        for user, codenames in users_and_permissions.items()
    ]


def set_series_permission_level(series: Series, user: MyUser, level: str, acting_user: MyUser) -> None:
    if user.pk == acting_user.pk and "change_series" not in SERIES_PERMISSION_MAP[level]:
        raise ValidationError("You cannot remove your own management permissions for this series.")
    for permission in SERIES_PERMISSION_MAP["delete"]:
        remove_perm(f"display.{permission}", user, series)
    for permission in SERIES_PERMISSION_MAP[level]:
        assign_perm(f"display.{permission}", user, series)


def remove_series_permission_grant(series: Series, user: MyUser, acting_user: MyUser) -> None:
    if user.pk == acting_user.pk:
        raise ValidationError("You cannot remove your own permissions for this series.")
    for permission in SERIES_PERMISSION_MAP["delete"]:
        remove_perm(f"display.{permission}", user, series)
