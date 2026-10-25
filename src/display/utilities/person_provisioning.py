"""
The local profile (MyUser and Person) of someone who has signed up with Firebase. It is made when they first sign in,
which needs a verified email address, not when the signup form is submitted: a form submitted by a bot then leaves
nothing behind but an unverified Firebase account.
"""

import logging
from typing import Tuple

logger = logging.getLogger(__name__)


def split_display_name(display_name) -> Tuple[str, str]:
    """
    First and last name from a Firebase display name, which the signup form writes as "first last": the last word is
    the last name, whatever comes before it the first name ("Mary Ann Smith" is Mary Ann, Smith). One word is a first
    name only. Nothing gives empty names.
    """
    parts = (display_name or "").split()
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return " ".join(parts[:-1]), parts[-1]


def ensure_person(user) -> None:
    """
    A user without a Person gets one, with the user's names. Never blocks the sign-in: creating a Person registers a
    tracker with Traccar, and the profile is created on its first use anyway if this fails.
    """
    from display.models import Person

    try:
        Person.objects.get_or_create(
            email=user.email,
            defaults={"first_name": user.first_name or "", "last_name": user.last_name or ""},
        )
    except Exception:
        logger.exception("Could not create the person profile for %s at sign-in", user.email)
