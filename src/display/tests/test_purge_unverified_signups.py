"""purge_unverified_signups: bot signups are removed only when it is certain nobody used them, and only on request."""

import datetime
from io import StringIO
from unittest.mock import MagicMock, patch

from django.core.management import call_command
from django.test import TestCase

from display.models import Crew, MyUser, Person
from utilities.mock_utilities import TraccarMock

NOW = datetime.datetime.now(datetime.timezone.utc)


def firebase_user(email, name="Test User", verified=False, hours_old=48, signed_in=False, providers=("password",)):
    user = MagicMock()
    user.uid = f"uid-{email}"
    user.email = email
    user.display_name = name
    user.email_verified = verified
    user.user_metadata.creation_timestamp = int((NOW - datetime.timedelta(hours=hours_old)).timestamp() * 1000)
    user.user_metadata.last_sign_in_timestamp = int(NOW.timestamp() * 1000) if signed_in else 0
    user.provider_data = [MagicMock(provider_id=provider) for provider in providers]
    return user


@patch("display.signals.get_traccar_instance", return_value=TraccarMock)
class TestPurgeUnverifiedSignups(TestCase):
    def run_command(self, users, *args):
        out = StringIO()
        with (
            patch("display.auth_backends.FirebaseMigrationBackend._initialize_firebase"),
            patch("firebase_admin.auth.list_users") as list_users,
            patch("firebase_admin.auth.delete_user") as delete_user,
        ):
            list_users.return_value.iterate_all.return_value = users
            call_command("purge_unverified_signups", "--display-name", "Test User", *args, stdout=out)
        return out.getvalue(), delete_user

    def make_rows(self, email):
        MyUser.objects.create_user(username=email, email=email)
        return Person.objects.create(first_name="Test", last_name="User", email=email)

    def test_by_default_nothing_is_deleted(self, _traccar):
        self.make_rows("bot@example.com")
        output, delete_user = self.run_command([firebase_user("bot@example.com")])
        delete_user.assert_not_called()
        self.assertTrue(MyUser.objects.filter(email="bot@example.com").exists())
        self.assertIn("Would remove 1", output)
        self.assertIn("bo***@example.com", output)

    def test_execute_removes_the_firebase_account_and_the_local_rows(self, _traccar):
        self.make_rows("bot@example.com")
        output, delete_user = self.run_command([firebase_user("bot@example.com")], "--execute")
        delete_user.assert_called_once_with("uid-bot@example.com")
        self.assertFalse(MyUser.objects.filter(email="bot@example.com").exists())
        self.assertFalse(Person.objects.filter(email="bot@example.com").exists())
        self.assertIn("Removed 1", output)

    def test_a_firebase_account_without_local_rows_is_removed_too(self, _traccar):
        _, delete_user = self.run_command([firebase_user("fresh@example.com")], "--execute")
        delete_user.assert_called_once()

    def test_accounts_that_may_be_real_are_left_alone(self, _traccar):
        keep = [
            firebase_user("verified@example.com", verified=True),
            firebase_user("other-name@example.com", name="Jane Doe"),
            firebase_user("new@example.com", hours_old=2),
            firebase_user("signed-in@example.com", signed_in=True),
            firebase_user("google@example.com", providers=("password", "google.com")),
        ]
        _, delete_user = self.run_command(keep, "--execute")
        delete_user.assert_not_called()

    def test_a_local_user_who_has_signed_in_or_has_a_crew_is_left_alone(self, _traccar):
        self.make_rows("used@example.com")
        MyUser.objects.filter(email="used@example.com").update(last_login=NOW)
        crewed = self.make_rows("crewed@example.com")
        Crew.objects.create(member1=crewed)
        _, delete_user = self.run_command(
            [firebase_user("used@example.com"), firebase_user("crewed@example.com")], "--execute"
        )
        delete_user.assert_not_called()
        self.assertTrue(Person.objects.filter(email="used@example.com").exists())
        self.assertTrue(Person.objects.filter(email="crewed@example.com").exists())
