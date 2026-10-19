"""
The rules of squadrons (see display/models/squadron.py): who may manage the members, how people are invited and join,
and who may share a contest with a squadron. Shared by the REST actions; the audience a squadron gives a contest is
decided in display/services/contest_visibility.py.
"""

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from rest_framework.exceptions import ValidationError

from display.models import Contest, MyUser, Squadron, SquadronContestShare, SquadronInvitation, SquadronMembership


def create_squadron(user: MyUser, name: str, description: str = "") -> Squadron:
    name = (name or "").strip()
    if not name:
        raise ValidationError("A squadron needs a name.")
    with transaction.atomic():
        squadron = Squadron.objects.create(name=name, description=description or "", created_by=user)
        SquadronMembership.objects.create(squadron=squadron, user=user, role=SquadronMembership.ADMIN)
    return squadron


def membership_of(squadron: Squadron, user: MyUser) -> SquadronMembership | None:
    if user is None or not user.is_authenticated:
        return None
    return SquadronMembership.objects.filter(squadron=squadron, user=user).first()


def is_admin(squadron: Squadron, user: MyUser) -> bool:
    membership = membership_of(squadron, user)
    return membership is not None and membership.role == SquadronMembership.ADMIN


def require_admin(squadron: Squadron, user: MyUser) -> None:
    if not is_admin(squadron, user):
        raise PermissionDenied("Only an admin of the squadron may do that.")


def _invitee_email(identifier: str) -> str:
    """Digits are a user id (what the people search gives), anything else an e-mail address."""
    identifier = str(identifier or "").strip()
    if identifier.isdigit():
        user = MyUser.objects.filter(pk=int(identifier)).first()
        if user is None:
            raise ValidationError("User not found")
        return user.email.lower()
    try:
        validate_email(identifier)
    except DjangoValidationError:
        raise ValidationError("That is not an e-mail address.")
    return identifier.lower()


def invite(squadron: Squadron, acting_user: MyUser, identifier: str, role: str = SquadronMembership.MEMBER):
    """Invite somebody, by user id or e-mail address, to join as [role]. They have to accept."""
    require_admin(squadron, acting_user)
    if role not in dict(SquadronMembership.ROLES):
        raise ValidationError("Unknown role.")
    email = _invitee_email(identifier)
    with transaction.atomic():
        # The lock on the squadron makes the check for an earlier invitation safe against a double click
        Squadron.objects.select_for_update().get(pk=squadron.pk)
        if SquadronMembership.objects.filter(squadron=squadron, user__email__iexact=email).exists():
            raise ValidationError("They are already in the squadron.")
        if SquadronInvitation.objects.filter(
            squadron=squadron, email=email, status=SquadronInvitation.PENDING
        ).exists():
            raise ValidationError("They have already been invited.")
        return SquadronInvitation.objects.create(squadron=squadron, email=email, role=role, invited_by=acting_user)


def pending_invitations_for(user: MyUser):
    if user is None or not user.is_authenticated:
        return SquadronInvitation.objects.none()
    return SquadronInvitation.objects.filter(
        email=user.email.strip().lower(), status=SquadronInvitation.PENDING
    ).select_related("squadron", "invited_by")


def _own_pending_invitation(invitation: SquadronInvitation, user: MyUser) -> None:
    if invitation.email != user.email.strip().lower() or invitation.status != SquadronInvitation.PENDING:
        raise PermissionDenied("This invitation is not open to you.")


def accept_invitation(invitation: SquadronInvitation, user: MyUser) -> SquadronMembership:
    with transaction.atomic():
        invitation = SquadronInvitation.objects.select_for_update().get(pk=invitation.pk)
        _own_pending_invitation(invitation, user)
        membership, created = SquadronMembership.objects.get_or_create(
            squadron=invitation.squadron, user=user, defaults={"role": invitation.role}
        )
        if not created and invitation.role == SquadronMembership.ADMIN:
            membership.role = SquadronMembership.ADMIN
            membership.save(update_fields=["role"])
        invitation.status = SquadronInvitation.ACCEPTED
        invitation.responded_at = timezone.now()
        invitation.save(update_fields=["status", "responded_at"])
    return membership


def decline_invitation(invitation: SquadronInvitation, user: MyUser) -> None:
    _own_pending_invitation(invitation, user)
    invitation.status = SquadronInvitation.DECLINED
    invitation.responded_at = timezone.now()
    invitation.save(update_fields=["status", "responded_at"])


def revoke_invitation(invitation: SquadronInvitation, acting_user: MyUser) -> None:
    require_admin(invitation.squadron, acting_user)
    if invitation.status != SquadronInvitation.PENDING:
        raise ValidationError("The invitation is no longer open.")
    invitation.status = SquadronInvitation.REVOKED
    invitation.responded_at = timezone.now()
    invitation.save(update_fields=["status", "responded_at"])


def _would_leave_without_admin(squadron: Squadron, membership: SquadronMembership) -> bool:
    return membership.role == SquadronMembership.ADMIN and squadron.admin_count <= 1


def change_role(squadron: Squadron, acting_user: MyUser, membership: SquadronMembership, role: str) -> None:
    require_admin(squadron, acting_user)
    if role not in dict(SquadronMembership.ROLES):
        raise ValidationError("Unknown role.")
    with transaction.atomic():
        Squadron.objects.select_for_update().get(pk=squadron.pk)
        if role != SquadronMembership.ADMIN and _would_leave_without_admin(squadron, membership):
            raise ValidationError("A squadron needs at least one admin. Make somebody else an admin first.")
        membership.role = role
        membership.save(update_fields=["role"])


def remove_member(squadron: Squadron, acting_user: MyUser, membership: SquadronMembership) -> None:
    """An admin removes a member, or a member leaves (their own membership). The last admin cannot go."""
    if membership.user_id != acting_user.pk:
        require_admin(squadron, acting_user)
    with transaction.atomic():
        Squadron.objects.select_for_update().get(pk=squadron.pk)
        if _would_leave_without_admin(squadron, membership):
            raise ValidationError(
                "A squadron needs at least one admin. Make somebody else an admin first, or delete the squadron."
            )
        membership.delete()


def delete_squadron(squadron: Squadron, acting_user: MyUser) -> None:
    require_admin(squadron, acting_user)
    squadron.delete()


def share_contest(contest: Contest, squadron: Squadron, acting_user: MyUser) -> SquadronContestShare:
    """Any member of the squadron who may change the contest can share it with the squadron."""
    if not acting_user.has_perm("display.change_contest", contest):
        raise PermissionDenied("Only somebody who manages the contest may share it.")
    if membership_of(squadron, acting_user) is None:
        raise PermissionDenied("You can only share a contest with a squadron you are a member of.")
    share, _created = SquadronContestShare.objects.get_or_create(
        squadron=squadron, contest=contest, defaults={"shared_by": acting_user}
    )
    return share


def can_stop_sharing(share: SquadronContestShare, user: MyUser) -> bool:
    """
    An admin of the squadron may stop sharing anything. A member only what they shared themselves. Whoever manages the
    contest also controls who it is shared with, so can always take it back.
    """
    if is_admin(share.squadron, user):
        return True
    if share.shared_by_id is not None and share.shared_by_id == user.pk and membership_of(share.squadron, user):
        return True
    return user.has_perm("display.change_contest", share.contest)


def unshare_contest(contest: Contest, squadron: Squadron, acting_user: MyUser) -> None:
    share = SquadronContestShare.objects.filter(squadron=squadron, contest=contest).first()
    if share is None:
        return
    if not can_stop_sharing(share, acting_user):
        raise PermissionDenied("You can only stop sharing contests you shared yourself. An admin can stop any.")
    share.delete()


def shareable_contests(squadron: Squadron, user: MyUser):
    """The contests [user] could share with the squadron: those they manage that it does not have yet."""
    from guardian.shortcuts import get_objects_for_user

    managed = get_objects_for_user(
        user, "display.change_contest", klass=Contest, accept_global_perms=False, with_superuser=False
    )
    return managed.exclude(shared_with_squadrons=squadron).order_by("-start_time")


def contest_access_through_squadrons(user: MyUser) -> list[dict]:
    """
    The contests [user] can open because of the squadrons they are in, each with every squadron that gives the access
    (a contest shared with two of their squadrons appears once, with both).
    """
    shares = (
        SquadronContestShare.objects.filter(squadron__memberships__user=user)
        .select_related("contest", "squadron")
        .order_by("-contest__start_time", "squadron__name")
    )
    by_contest: dict[int, dict] = {}
    for share in shares:
        entry = by_contest.setdefault(
            share.contest_id,
            {
                "id": share.contest_id,
                "name": share.contest.name,
                "start_time": share.contest.start_time,
                "finish_time": share.contest.finish_time,
                "squadrons": [],
            },
        )
        entry["squadrons"].append({"id": share.squadron_id, "name": share.squadron.name})
    return list(by_contest.values())
