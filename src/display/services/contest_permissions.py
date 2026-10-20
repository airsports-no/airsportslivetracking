"""
Contest per-user permission management, extracted from the classic views (display/views.py:
list_contest_permissions, add_user_contest_permissions, change_user_contest_permissions,
delete_user_contest_permissions) so the REST actions used by the SPA and the legacy views can
share one implementation until the legacy views are deleted.
"""

from guardian.shortcuts import assign_perm, get_user_perms, get_users_with_perms, remove_perm
from rest_framework.exceptions import PermissionDenied, ValidationError

from display.models import Contest, MyUser
from display.services.people_search import user_identities

CONTEST_PERMISSION_LEVELS = ("nothing", "view", "change", "delete")

CONTEST_PERMISSION_MAP = {
    "nothing": [],
    "view": ["view_contest"],
    "change": ["view_contest", "change_contest", "add_contest"],
    "delete": ["view_contest", "change_contest", "add_contest", "delete_contest"],
}


def map_contest_permissions_to_permission_name(permission_codenames) -> str:
    if "delete_contest" in permission_codenames:
        return "delete"
    elif "change_contest" in permission_codenames:
        return "change"
    elif "view_contest" in permission_codenames:
        return "view"
    else:
        return "nothing"


def require_grant_allowed(target: MyUser, current_level: str, new_level: str, acting_can_delete: bool, noun: str) -> None:
    """
    The rules for giving somebody a level on a contest or series ([noun]), shared by both:
    - Only an organiser (in the contest manager group, with the right to create contests) can be given "change" or "delete";
      anybody else can only be given "view".
    - "delete" is the owner's level: giving it, or changing or removing the access of somebody who has it, takes "delete"
      yourself.
    """
    if new_level in ("change", "delete") and not target.has_perm("display.add_contest"):
        raise ValidationError(
            f"Only an organiser can be given more than view access to a {noun}. They can become an organiser themselves "
            "with the Become an Organizer button."
        )
    if (new_level == "delete" or current_level == "delete") and not acting_can_delete:
        raise PermissionDenied(f"Only somebody who may delete the {noun} can give or take away that right.")


def list_contest_permission_grants(contest: Contest) -> list[dict]:
    users_and_permissions = get_users_with_perms(contest, attach_perms=True)
    identities = user_identities(users_and_permissions)
    # Never the raw email: grants may be made by searching a name, and a manager should not learn
    # the address of everyone they (or a co-manager) have granted access to.
    return [
        {
            "user_id": user.pk,
            **identities[user.pk],
            "level": map_contest_permissions_to_permission_name(codenames),
        }
        for user, codenames in users_and_permissions.items()
    ]


def resolve_permission_target_user(identifier: str) -> MyUser:
    """Digits -> pk, else email - same lookup ClubManagerMembershipCreateSerializer.validate_user_id uses."""
    if isinstance(identifier, str) and identifier.strip().isdigit():
        user = MyUser.objects.filter(pk=int(identifier.strip())).first()
    else:
        user = MyUser.objects.filter(email__iexact=str(identifier).strip()).first()
    if user is None:
        raise ValidationError("User not found")
    return user


def set_contest_permission_level(contest: Contest, user: MyUser, level: str, acting_user: MyUser) -> None:
    # Same self-lockout protection as remove_contest_permission_grant, but for the PUT path:
    # dropping your own level to something without change_contest is equivalent to removing
    # yourself, just one step at a time.
    if user.pk == acting_user.pk and "change_contest" not in CONTEST_PERMISSION_MAP[level]:
        raise ValidationError("You cannot remove your own management permissions for this contest.")
    require_grant_allowed(
        user,
        get_contest_permission_level(contest, user),
        level,
        acting_user.has_perm("display.delete_contest", contest),
        "contest",
    )
    for permission in CONTEST_PERMISSION_MAP["delete"]:
        remove_perm(f"display.{permission}", user, contest)
    for permission in CONTEST_PERMISSION_MAP[level]:
        assign_perm(f"display.{permission}", user, contest)


def remove_contest_permission_grant(contest: Contest, user: MyUser, acting_user: MyUser) -> None:
    if user.pk == acting_user.pk:
        raise ValidationError("You cannot remove your own permissions for this contest.")
    require_grant_allowed(
        user,
        get_contest_permission_level(contest, user),
        "nothing",
        acting_user.has_perm("display.delete_contest", contest),
        "contest",
    )
    for permission in CONTEST_PERMISSION_MAP["delete"]:
        remove_perm(f"display.{permission}", user, contest)


def get_contest_permission_level(contest: Contest, user: MyUser) -> str:
    return map_contest_permissions_to_permission_name(get_user_perms(user, contest))
