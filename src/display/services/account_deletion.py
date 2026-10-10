"""
Self-service account deletion for the mobile apps (required by the App Store and Google Play).

Policy matches the superuser tool (``delete_user_and_person`` in views.py) and ``Person``'s docstring: the login
(``MyUser``) is deleted, the ``Person`` is deleted, or anonymized when teams still reference it (Crew uses PROTECT so
historic results stay intact). The Firebase account is deleted as well, otherwise the same person could keep signing in
and silently get a fresh profile.
"""

import logging
from dataclasses import dataclass
from typing import Optional

from django.db.models import ProtectedError

from display.models import MyUser, Person

logger = logging.getLogger(__name__)


class AccountDeletionBlocked(Exception):
    """The account cannot be deleted by the user themself; ``str(exception)`` is safe to show to them."""


@dataclass(frozen=True)
class AccountDeletionResult:
    user_deleted: bool
    person_deleted: bool
    person_anonymized: bool
    firebase_deleted: bool


def blocked_reason(user) -> Optional[str]:
    """Organizer and staff accounts own contests and permissions, so support must handle those deletions."""
    if user.is_superuser or user.is_staff or user.has_perm("display.add_contest"):
        return "Organizer and staff accounts must be deleted by support. Contact support@airsports.no."
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


def delete_account(email: str) -> AccountDeletionResult:
    my_user = MyUser.objects.filter(email=email).first()
    user_deleted = False
    if my_user is not None:
        try:
            my_user.delete()
        except ProtectedError as e:
            raise AccountDeletionBlocked(
                "This account is still referenced by other data and must be deleted by support. "
                "Contact support@airsports.no."
            ) from e
        user_deleted = True

    person_deleted = False
    person_anonymized = False
    for person in Person.objects.filter(email=email):
        try:
            person.delete()
            person_deleted = True
        except ProtectedError:
            person.first_name = "Unknown"
            person.last_name = "Unknown"
            person.email = f"internal_{person.pk}@airsports.no"
            person.phone = None
            person.picture = None
            person.biography = ""
            person.app_aircraft_registration = ""
            person.is_public = False
            person.save()
            person_anonymized = True

    firebase_deleted = _delete_firebase_user(email)
    if my_user is not None:
        my_user.send_deletion_email()
    return AccountDeletionResult(user_deleted, person_deleted, person_anonymized, firebase_deleted)
