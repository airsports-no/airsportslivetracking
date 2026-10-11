import datetime
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from display.models import MobileDevice, Person


class SendTestPushCommandTest(TestCase):
    def setUp(self):
        self.person = Person.objects.create(first_name="Pi", last_name="Lot", email="pilot@example.com")
        self.device = MobileDevice.objects.create(person=self.person, platform="android", push_token="tok-abc", app_version="55")

    def run_command(self, email="PILOT@example.com", **kwargs):
        out = StringIO()
        call_command("send_test_push", email, stdout=out, **kwargs)
        return out.getvalue()

    def test_sends_to_every_registered_phone_of_the_person_whatever_the_case_of_the_email(self):
        MobileDevice.objects.create(person=self.person, platform="ios", push_token="tok-def", app_version="204")
        with patch("display.management.commands.send_test_push._send_one", return_value=True) as send:
            output = self.run_command()
        self.assertEqual(send.call_count, 2)
        self.assertEqual({call.args[0].push_token for call in send.call_args_list}, {"tok-abc", "tok-def"})
        self.assertIn("Reached 2 of 2", output)

    def test_title_and_body_can_be_given(self):
        with patch("display.management.commands.send_test_push._send_one", return_value=True) as send:
            self.run_command(title="Hello", body="World")
        self.assertEqual(send.call_args.args[1:3], ("Hello", "World"))

    def test_no_registered_phone_is_explained(self):
        with self.assertRaisesMessage(CommandError, "No phone is registered"):
            self.run_command(email="nobody@example.com")

    def test_a_dead_token_or_failure_is_reported_and_is_an_error_when_nothing_is_reached(self):
        with patch("display.management.commands.send_test_push._send_one", side_effect=RuntimeError("boom")):
            with self.assertRaisesMessage(CommandError, "No phone was reached"):
                self.run_command()

    @override_settings(PUSH_NOTIFICATIONS_ENABLED=False)
    def test_says_when_the_automatic_pushes_are_switched_off_but_still_sends(self):
        with patch("display.management.commands.send_test_push._send_one", return_value=True) as send:
            output = self.run_command()
        self.assertEqual(send.call_count, 1)
        self.assertIn("PUSH_NOTIFICATIONS_ENABLED is off", output)


class MobileDeviceAdminTest(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(email="admin@example.com", password="x")
        self.client.force_login(self.admin)
        person = Person.objects.create(first_name="Pi", last_name="Lot", email="pilot@example.com")
        self.device = MobileDevice.objects.create(person=person, platform="android", push_token="tok-abcdefghijklmnop", app_version="55")

    def test_the_list_shows_the_devices_with_a_shortened_token(self):
        response = self.client.get("/admin/display/mobiledevice/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "pilot@example.com")
        self.assertContains(response, "tok-abcdefgh...")
        self.assertNotContains(response, "tok-abcdefghijklmnop")

    def test_the_detail_page_shows_the_full_token_read_only(self):
        response = self.client.get(f"/admin/display/mobiledevice/{self.device.pk}/change/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "tok-abcdefghijklmnop")
        self.assertNotContains(response, "<input type=\"text\" name=\"push_token\"")
        self.assertNotContains(response, "name=\"_save\"")

    def test_nothing_can_be_added_changed_or_deleted(self):
        self.assertEqual(self.client.get("/admin/display/mobiledevice/add/").status_code, 403)
        response = self.client.post(f"/admin/display/mobiledevice/{self.device.pk}/change/", {"app_version": "1"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.client.get(f"/admin/display/mobiledevice/{self.device.pk}/delete/").status_code, 403)
        self.device.refresh_from_db()
        self.assertEqual(self.device.app_version, "55")

    def test_the_notification_log_lists_too(self):
        self.assertEqual(self.client.get("/admin/display/pushnotificationlog/").status_code, 200)
