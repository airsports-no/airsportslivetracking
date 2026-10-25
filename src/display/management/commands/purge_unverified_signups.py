"""
Removes the accounts a bot made through the signup form: Firebase accounts whose email was never verified, with the
display name the bot used, together with the local user and person made for them before signup stopped making them.

Nothing is deleted without --execute. An account is only removed if it is unverified, still has only the password
provider, was created more than --older-than-hours ago and has not signed in since its signup (the signup's own
token request, a second after creation, does not count). Its local rows (if any) must have no data of their own:
no sign-in, not staff, no crew, no profile details, nothing else that would go with them.

    python3 manage.py purge_unverified_signups --display-name "Test User"             # what would be removed
    python3 manage.py purge_unverified_signups --display-name "Test User" --execute    # remove it
"""

import datetime

from django.contrib.admin.utils import NestedObjects
from django.core.management.base import BaseCommand
from django.db import DEFAULT_DB_ALIAS

from display.models import MyUser, Person


def mask(email: str) -> str:
    local, _, domain = (email or "").partition("@")
    return f"{local[:2]}***@{domain}"


# The signup form signs the new account in once, on the server, to get the token that sends the verification email:
# a sign-in this soon after creation is that, not the person using the account.
SIGNUP_SIGN_IN_SECONDS = 120

# A profile with anything filled in beyond the names is somebody's: none of it is set by the signup form.
PROFILE_FIELDS = ("phone", "biography", "picture", "country", "app_aircraft_registration")


def has_profile_data(person) -> bool:
    return any(getattr(person, field, None) for field in PROFILE_FIELDS)


def own_data(instance) -> list:
    """The kinds of data (besides the row itself and plain join rows) that would be deleted with this row."""
    collector = NestedObjects(using=DEFAULT_DB_ALIAS)
    collector.collect([instance])
    # Something that refers to it and stops its deletion (a crew, for a person) is data of its own too: the collector
    # notes those in .protected instead of raising.
    protected = {type(obj)._meta.label for obj in collector.protected}
    return sorted(
        protected
        | {
            model._meta.label
            for model, objects in collector.model_objs.items()
            if model is not type(instance) and not model._meta.auto_created and objects
        }
    )


class Command(BaseCommand):
    help = "Remove unverified Firebase accounts made by a bot (by display name), and their empty local rows."

    def add_arguments(self, parser):
        parser.add_argument("--display-name", required=True, help='The display name the bot used, e.g. "Test User".')
        parser.add_argument("--older-than-hours", type=float, default=24.0)
        parser.add_argument("--limit", type=int, default=500, help="At most this many accounts in one run.")
        parser.add_argument("--execute", action="store_true", help="Delete (the default only lists what would go).")

    def handle(self, *args, **options):
        from firebase_admin import auth

        from display.auth_backends import FirebaseMigrationBackend

        FirebaseMigrationBackend()._initialize_firebase()
        name = options["display_name"].strip()
        cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=options["older_than_hours"])
        execute = options["execute"]
        removed = skipped = 0
        reasons = {}

        def skip(reason):
            nonlocal skipped
            skipped += 1
            reasons[reason] = reasons.get(reason, 0) + 1

        for firebase_user in auth.list_users().iterate_all():
            if firebase_user.display_name != name or firebase_user.email_verified:
                continue
            created = datetime.datetime.fromtimestamp(firebase_user.user_metadata.creation_timestamp / 1000, datetime.timezone.utc)
            if created > cutoff:
                skip("newer than the limit")
                continue
            last_sign_in = firebase_user.user_metadata.last_sign_in_timestamp
            if last_sign_in and (last_sign_in - firebase_user.user_metadata.creation_timestamp) / 1000 > SIGNUP_SIGN_IN_SECONDS:
                skip("has signed in")
                continue
            if {provider.provider_id for provider in firebase_user.provider_data} - {"password"}:
                skip("has another provider")
                continue
            email = firebase_user.email or ""
            user = MyUser.objects.filter(email__iexact=email).first() if email else None
            person = Person.objects.filter(email__iexact=email).first() if email else None
            if user and (user.last_login or user.is_staff or user.is_superuser):
                skip("local user has signed in or is staff")
                continue
            if user and own_data(user) or person and (own_data(person) or has_profile_data(person)):
                skip("local rows have data of their own")
                continue
            if removed >= options["limit"]:
                skip("over the limit of this run")
                continue
            removed += 1
            self.stdout.write(f"{'Removing' if execute else 'Would remove'} {mask(email)} (created {created:%Y-%m-%d %H:%M})")
            if execute:
                auth.delete_user(firebase_user.uid)
                if person:
                    person.delete()
                if user:
                    user.delete()
        self.stdout.write(
            f"{'Removed' if execute else 'Would remove'} {removed}; left alone {skipped}"
            + (f" ({', '.join(f'{count} {reason}' for reason, count in reasons.items())})" if reasons else "")
            + ("" if execute else ". Nothing was deleted: add --execute to do it.")
        )
