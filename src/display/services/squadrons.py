"""
The rules of squadrons (see display/models/squadron.py): who may manage the members, how people are invited and join,
and who may share a contest with a squadron. Shared by the REST actions; the audience a squadron gives a contest is
decided in display/services/contest_visibility.py.
"""

import datetime
import secrets

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.exceptions import ValidationError

from display.models import Contest, MyUser, Squadron, SquadronContestShare, SquadronInvitation, SquadronMembership


# More open invitations than this is not a squadron being built up but an address list being used
MAX_PENDING_INVITATIONS = 50
# ... and a person cannot send out more than this a day across all their squadrons, whatever happens to the invitations
MAX_INVITATIONS_PER_USER_PER_DAY = 100


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
        pending = SquadronInvitation.objects.filter(squadron=squadron, status=SquadronInvitation.PENDING)
        if pending.filter(email=email).exists():
            raise ValidationError("They have already been invited.")
        if pending.count() >= MAX_PENDING_INVITATIONS:
            raise ValidationError(
                f"There are already {MAX_PENDING_INVITATIONS} invitations waiting for an answer. "
                "Cancel some, or share the invite link instead."
            )
        since = timezone.now() - datetime.timedelta(days=1)
        sent_today = SquadronInvitation.objects.filter(invited_by=acting_user, created_at__gte=since).count()
        if sent_today >= MAX_INVITATIONS_PER_USER_PER_DAY:
            raise ValidationError(
                "You have sent too many invitations today. Try again tomorrow, or share the invite link instead."
            )
        # Inviting the same address again soon after (a cancelled invitation, say) is not mailed again
        mailed_lately = SquadronInvitation.objects.filter(
            squadron=squadron, email=email, created_at__gte=since
        ).exists()
        invitation = SquadronInvitation.objects.create(
            squadron=squadron, email=email, role=role, invited_by=acting_user
        )
        if not mailed_lately:
            transaction.on_commit(lambda: _queue_invitation_email(invitation.pk))
        return invitation


def _queue_invitation_email(invitation_pk: int) -> None:
    from display.tasks import send_squadron_invitation_email_task

    send_squadron_invitation_email_task.delay(invitation_pk)


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


def enable_invite_link(squadron: Squadron, acting_user: MyUser) -> str:
    """Switch the invite link on, or give it a new address (the old one stops working). Returns the token."""
    require_admin(squadron, acting_user)
    squadron.invite_token = secrets.token_urlsafe(24)
    squadron.save(update_fields=["invite_token"])
    return squadron.invite_token


def disable_invite_link(squadron: Squadron, acting_user: MyUser) -> None:
    require_admin(squadron, acting_user)
    squadron.invite_token = None
    squadron.save(update_fields=["invite_token"])


def squadron_for_invite_token(token: str) -> Squadron:
    """The squadron an invite link is for. A link that is off, or never existed, is not found."""
    squadron = Squadron.objects.filter(invite_token=token).first() if token else None
    if squadron is None:
        raise NotFound("This invite link does not work any more.")
    return squadron


def join_by_invite_link(token: str, user: MyUser) -> SquadronMembership:
    """Opening the link and pressing Join is the acceptance: the user joins as a member."""
    squadron = squadron_for_invite_token(token)
    with transaction.atomic():
        membership, _created = SquadronMembership.objects.get_or_create(
            squadron=squadron, user=user, defaults={"role": SquadronMembership.MEMBER}
        )
        # An invitation to be a member is answered by joining. One to be an admin stays open: accepting it promotes
        SquadronInvitation.objects.filter(
            squadron=squadron,
            email=user.email.strip().lower(),
            status=SquadronInvitation.PENDING,
            role=SquadronMembership.MEMBER,
        ).update(status=SquadronInvitation.ACCEPTED, responded_at=timezone.now())
    return membership


def prepare_account_deletion(user: MyUser) -> None:
    """
    What a squadron needs before a member's account goes: a squadron the user is the only admin of is handed to the member
    who has been in it longest (so it still has somebody who can manage it), or deleted if nobody else is in it. The
    invitations still waiting for an answer at the user's address are removed. The memberships themselves go with the user.
    """
    with transaction.atomic():
        # Every squadron the user is in is locked, not only those they are an admin of: two members deleting their accounts
        # at the same time could otherwise promote one of them while the other goes, leaving the squadron without an admin.
        # The caller must delete the user inside the same transaction, so the locks are held until the memberships are gone.
        # Locked in one order, so two deletions cannot deadlock; the roles are read again under the locks.
        squadron_ids = list(
            SquadronMembership.objects.filter(user=user).order_by("squadron_id").values_list("squadron_id", flat=True)
        )
        for squadron in Squadron.objects.select_for_update().filter(pk__in=squadron_ids).order_by("pk"):
            memberships = list(squadron.memberships.select_for_update().order_by("joined_at", "pk"))
            mine = next((m for m in memberships if m.user_id == user.pk), None)
            if mine is None or mine.role != SquadronMembership.ADMIN:
                continue
            others = [m for m in memberships if m.user_id != user.pk]
            if any(m.role == SquadronMembership.ADMIN for m in others):
                continue
            if not others:
                squadron.delete()
            else:
                successor = others[0]
                successor.role = SquadronMembership.ADMIN
                successor.save(update_fields=["role"])
        SquadronInvitation.objects.filter(email=user.email.strip().lower(), status=SquadronInvitation.PENDING).delete()


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
