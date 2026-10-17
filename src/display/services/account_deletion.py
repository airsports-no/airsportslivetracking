"""
Self-service account deletion for the mobile apps (required by the App Store and Google Play).

Policy matches the superuser tool (``delete_user_and_person`` in views.py) and ``Person``'s docstring: the login
(``MyUser``) is deleted, the ``Person`` is deleted, or anonymized when teams still reference it (Crew uses PROTECT so
historic results stay intact). The Firebase account is deleted as well, otherwise the same person could keep signing in
and silently get a fresh profile.

Organizers can delete their account like anybody else; only staff and superusers (the platform administrators) are
refused. The contests a user manages are never deleted: other pilots' results depend on them. Deleting the login removes
the user's object permissions (django-guardian, cascade) and empties ``Contest.created_by`` (SET_NULL; every consumer
handles that), so the contest keeps its routes, tasks, teams and scores. A contest that nobody else can manage afterwards is
reported to support by e-mail and in the log so it can be given a new manager.

The one thing that stops the login row from being deleted is a token the user bought that a contest still runs on
(``ContestTokenAssignment.token_grant`` is PROTECT: the contest's access tier depends on it). Then the login is kept as an
anonymous, deactivated tombstone instead: no name, no e-mail, no password, no permissions, no group; the user cannot sign in
and the contest keeps its tier.

Everything that can be rolled back is one database transaction together with the Firebase deletion: if the Firebase
account cannot be deleted, nothing is changed and the user is told to try again.
"""

import datetime
import logging
from dataclasses import dataclass, field
from typing import Optional

from django.core.mail import send_mail
from django.db import models, transaction
from django.db.models import ProtectedError
from guardian.shortcuts import get_objects_for_user, get_users_with_perms

from display.models import Contest, ContestTokenAssignment, MyUser, Person, UserTokenGrant, UserUploadedMap
from live_tracking_map.settings import SUPPORT_EMAIL

logger = logging.getLogger(__name__)

ADMINISTRATOR_REFUSAL = "Staff and administrator accounts must be deleted by support. Contact support@airsports.no."


class AccountDeletionBlocked(Exception):
    """The account cannot be deleted by the user themself; ``str(exception)`` is safe to show to them."""


class AccountDeletionFailed(Exception):
    """Nothing was changed because a step failed; ``str(exception)`` is safe to show to them (try again later)."""


@dataclass(frozen=True)
class OrphanedContest:
    """A contest that nobody but staff can manage after the deletion."""

    id: int
    name: str
    running: bool


@dataclass(frozen=True)
class AccountDeletionResult:
    user_deleted: bool
    person_deleted: bool
    person_anonymized: bool
    firebase_deleted: bool
    # The login row was kept as an anonymous tombstone because a contest runs on a token the user bought.
    user_anonymized: bool = False
    contests_kept: int = 0
    contests_without_manager: tuple[OrphanedContest, ...] = field(default_factory=tuple)


def blocked_reason(user) -> Optional[str]:
    """Only the platform administrators own the system and have to go through support; organizers can delete."""
    if user.is_superuser or user.is_staff:
        return ADMINISTRATOR_REFUSAL
    return None


def _delete_firebase_user(email: str) -> bool:
    try:
        from firebase_admin import auth as firebase_auth

        from display.auth_backends import FirebaseMigrationBackend

        FirebaseMigrationBackend()._initialize_firebase()
        try:
            record = firebase_auth.get_user_by_email(email)
        except firebase_auth.UserNotFoundError:
            return True  # nothing to delete
        firebase_auth.delete_user(record.uid)
        return True
    except Exception:
        logger.exception("Failed deleting the Firebase account for a deleted user")
        return False


def _managed_contests(user: MyUser) -> list[Contest]:
    """The contests the user can change (guardian object permission) or created."""
    managed = {
        contest.pk: contest
        for contest in get_objects_for_user(user, "display.change_contest", klass=Contest, accept_global_perms=False)
    }
    for contest in Contest.objects.filter(created_by=user):
        managed.setdefault(contest.pk, contest)
    return list(managed.values())


def _contests_left_without_manager(
    user: MyUser, contests: list[Contest], now: datetime.datetime
) -> list[OrphanedContest]:
    orphaned = []
    for contest in contests:
        others = get_users_with_perms(
            contest, only_with_perms_in=["change_contest"], with_superusers=False, with_group_users=False
        ).exclude(pk=user.pk)
        if not others.exists():
            orphaned.append(OrphanedContest(contest.pk, contest.name, contest.start_time <= now <= contest.finish_time))
    return orphaned


def _anonymize_person(person: Person):
    person.first_name = "Unknown"
    person.last_name = "Unknown"
    person.email = f"internal_{person.pk}@airsports.no"
    person.phone = None
    person.picture = None
    person.biography = ""
    person.app_aircraft_registration = ""
    person.save()


def _retire_login(my_user: MyUser):
    """
    Everything a deletion of the login would do, except deleting the row itself (a contest runs on a token the user bought).
    The row stays as an anonymous, deactivated tombstone that nobody can sign in with.
    """
    for relation in MyUser._meta.related_objects:
        if not (relation.one_to_many or relation.one_to_one):
            continue
        if relation.on_delete is not models.CASCADE or relation.related_model is UserTokenGrant:
            continue
        relation.related_model.objects.filter(**{relation.field.name: my_user}).delete()
    # Tokens that no contest uses go; the ones a contest runs on stay with the (anonymous) row
    UserTokenGrant.objects.filter(user=my_user, contesttokenassignment__isnull=True).delete()
    my_user.groups.clear()
    my_user.user_permissions.clear()
    my_user.email = f"deleted_{my_user.pk}@airsports.no"
    my_user.username = f"deleted_{my_user.pk}"
    my_user.first_name = ""
    my_user.last_name = ""
    my_user.is_active = False
    my_user.is_staff = False
    my_user.is_superuser = False
    my_user.set_unusable_password()
    my_user.save()


def _uploaded_map_files(my_user: MyUser) -> list[tuple]:
    files = []
    for uploaded_map in UserUploadedMap.objects.filter(user=my_user):
        for stored in (uploaded_map.map_file, uploaded_map.thumbnail):
            if stored:
                files.append((stored.storage, stored.name))
    return files


def _remove_stored_files(files: list[tuple]):
    for storage, name in files:
        try:
            storage.delete(name)
        except Exception:
            logger.exception(f"Failed removing the stored file {name} of a deleted account")


def _tell_support_about_contests(orphaned: list[OrphanedContest]):
    lines = [
        f"- contest {contest.id}: {contest.name}" + ("  (RUNNING NOW)" if contest.running else "")
        for contest in orphaned
    ]
    logger.warning("Organizer account deleted, contests without a manager: %s", ", ".join(str(c.id) for c in orphaned))
    try:
        send_mail(
            "Organizer account deleted: contests need a manager",
            "An organizer deleted their account. Their contests and results are kept, but nobody except staff can manage "
            "these contests now. Give them a new manager (Django admin or the contest's permissions):\n\n"
            + "\n".join(lines),
            None,  # Should default to system from email
            recipient_list=[SUPPORT_EMAIL],
        )
    except Exception:
        logger.exception("Failed sending the contests-without-manager notice to support")


def delete_account(email: str) -> AccountDeletionResult:
    my_user = MyUser.objects.filter(email=email).first()
    now = datetime.datetime.now(datetime.timezone.utc)
    user_deleted = False
    user_anonymized = False
    person_deleted = False
    person_anonymized = False
    contests: list[Contest] = []
    orphaned: list[OrphanedContest] = []
    files: list[tuple] = []

    with transaction.atomic():
        if my_user is not None:
            contests = _managed_contests(my_user)
            orphaned = _contests_left_without_manager(my_user, contests, now)
            files = _uploaded_map_files(my_user)
            if ContestTokenAssignment.objects.filter(token_grant__user=my_user).exists():
                _retire_login(my_user)
                user_anonymized = True
            else:
                try:
                    my_user.delete()
                except ProtectedError as e:
                    raise AccountDeletionBlocked(
                        "Something unexpected still depends on this account, so it was not deleted and nothing was "
                        "changed. Contact support@airsports.no."
                    ) from e
                user_deleted = True

        for person in Person.objects.filter(email=email):
            try:
                with transaction.atomic():
                    person.delete()
                person_deleted = True
            except ProtectedError:
                _anonymize_person(person)
                person_anonymized = True

        # Last, so that a failure rolls everything above back: otherwise the person could keep signing in with the
        # Firebase account and silently get a fresh profile.
        if not _delete_firebase_user(email):
            raise AccountDeletionFailed(
                "Your account could not be deleted right now and nothing was changed. Try again later."
            )

    _remove_stored_files(files)
    if orphaned:
        _tell_support_about_contests(orphaned)
    if my_user is not None:
        try:
            # The tombstone no longer has the address: the deletion e-mail goes to the address the account had
            my_user.email = email
            my_user.send_deletion_email()
        except Exception:
            logger.exception("Failed sending the account deletion e-mail")
    return AccountDeletionResult(
        user_deleted=user_deleted,
        person_deleted=person_deleted,
        person_anonymized=person_anonymized,
        firebase_deleted=True,
        user_anonymized=user_anonymized,
        contests_kept=len(contests),
        contests_without_manager=tuple(orphaned),
    )
