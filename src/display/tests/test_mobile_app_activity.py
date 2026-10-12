import datetime
import uuid
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from display.models import MobileAppActivity, Person
from display.models.my_user import MyUser
from display.services.mobile_app_activity import connected_apps


def unique(prefix):
    return f"{prefix}{uuid.uuid4().hex[:8]}"


class TestRecordingAppActivity(TestCase):
    """The cache that throttles the writes outlasts a test run, so every test uses a version string nobody used before."""

    def setUp(self):
        self.user = MyUser.objects.create(username=unique("u"), email=f"{unique('p')}@example.com", first_name="Pi", last_name="Lot")
        Person.objects.create(first_name="Pi", last_name="Lot", email=self.user.email)
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.version = unique("v")

    def get(self, **headers):
        return self.client.get("/api/v1/userprofile/retrieve_profile/", **headers)

    def app_headers(self, platform="android", build="100"):
        return {"HTTP_X_APP_PLATFORM": platform, "HTTP_X_APP_VERSION": self.version, "HTTP_X_APP_BUILD": build}

    def test_notes_the_version_the_app_reports(self):
        self.assertEqual(self.get(**self.app_headers()).status_code, 200)
        row = MobileAppActivity.objects.get(user=self.user)
        self.assertEqual((row.platform, row.app_version, row.app_build), ("android", self.version, "100"))

    def test_writes_at_most_once_a_minute_but_notes_a_new_version_at_once(self):
        self.get(**self.app_headers())
        first = MobileAppActivity.objects.get(user=self.user).last_seen
        self.get(**self.app_headers())
        self.assertEqual(MobileAppActivity.objects.get(user=self.user).last_seen, first)
        self.get(**self.app_headers(build="101"))
        self.assertEqual(MobileAppActivity.objects.get(user=self.user).app_build, "101")
        self.assertEqual(MobileAppActivity.objects.filter(user=self.user).count(), 1)

    def test_ignores_requests_that_do_not_come_from_the_app(self):
        self.get()
        self.get(HTTP_X_APP_PLATFORM="windows", HTTP_X_APP_VERSION=self.version)
        self.assertFalse(MobileAppActivity.objects.exists())

    def test_a_failure_to_record_never_breaks_the_request(self):
        with patch("display.services.mobile_app_activity.record_app_activity", side_effect=RuntimeError("boom")):
            self.assertEqual(self.get(**self.app_headers()).status_code, 200)


class TestAdminMobileApps(TestCase):
    def setUp(self):
        self.admin = MyUser.objects.create(username=unique("a"), email=f"{unique('a')}@example.com", is_superuser=True, is_staff=True)
        self.pilot = MyUser.objects.create(username=unique("p"), email=f"{unique('p')}@example.com", first_name="Pi", last_name="Lot")
        self.client = APIClient()

    def seen(self, user, platform, version, build, minutes_ago):
        return MobileAppActivity.objects.create(
            user=user, platform=platform, app_version=version, app_build=build,
            last_seen=timezone.now() - datetime.timedelta(minutes=minutes_ago),
        )

    def test_lists_the_apps_seen_in_the_window_with_a_count_per_version(self):
        other = MyUser.objects.create(username=unique("o"), email=f"{unique('o')}@example.com")
        old = MyUser.objects.create(username=unique("x"), email=f"{unique('x')}@example.com")
        self.seen(self.pilot, "android", "2.0.0", "100", 2)
        self.seen(other, "ios", "2.0.0", "100", 5)
        self.seen(old, "android", "1.9.0", "90", 120)
        result = connected_apps(15)
        self.assertEqual(result["total"], 2)
        self.assertEqual([u["email"] for u in result["users"]], [self.pilot.email, other.email])
        self.assertEqual({(v["platform"], v["app_version"], v["users"]) for v in result["by_version"]}, {("android", "2.0.0", 1), ("ios", "2.0.0", 1)})
        self.assertEqual(connected_apps(24 * 60)["total"], 3)

    def test_includes_the_last_known_position_when_the_tracking_stream_has_one(self):
        from display.services.received_positions import note_position_received

        person = Person.objects.create(first_name="Pi", last_name="Lot", email=self.pilot.email)
        device = person.app_tracking_id  # generated when the person is created
        self.assertTrue(device)
        no_position = MyUser.objects.create(username=unique("n"), email=f"{unique('n')}@example.com")
        self.seen(self.pilot, "android", "2.0.0", "100", 1)
        self.seen(no_position, "ios", "2.0.0", "100", 2)
        note_position_received(device, timezone.now(), 59.9139, 10.7522)
        users = {u["email"]: u for u in connected_apps(15)["users"]}
        self.assertEqual((users[self.pilot.email]["position"]["latitude"], users[self.pilot.email]["position"]["longitude"]), (59.9139, 10.7522))
        self.assertIsNone(users[no_position.email]["position"])

    def test_coordinates_are_refreshed_at_most_every_few_seconds(self):
        from display.services.received_positions import last_received_coordinates, note_position_received

        device = f"d{uuid.uuid4().hex[:20]}"
        start = timezone.now()
        note_position_received(device, start, 1.0, 1.0)
        note_position_received(device, start + datetime.timedelta(seconds=1), 2.0, 2.0)  # too soon: kept as it was
        self.assertEqual(last_received_coordinates(device)["latitude"], 1.0)
        note_position_received(device, start + datetime.timedelta(seconds=6), 3.0, 3.0)
        self.assertEqual(last_received_coordinates(device)["latitude"], 3.0)
        self.assertIsNone(last_received_coordinates("nobody-" + uuid.uuid4().hex[:8]))

    def test_only_a_site_admin_may_see_it(self):
        self.seen(self.pilot, "android", "2.0.0", "100", 1)
        self.client.force_authenticate(self.pilot)
        self.assertEqual(self.client.get("/api/v1/admin/mobile-apps/").status_code, 403)
        self.client.force_authenticate(self.admin)
        response = self.client.get("/api/v1/admin/mobile-apps/?minutes=15")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["users"][0]["name"], "Pi Lot")
        self.assertEqual(self.client.get("/api/v1/admin/mobile-apps/?minutes=0").status_code, 400)
        self.assertEqual(self.client.get("/api/v1/admin/mobile-apps/?minutes=abc").status_code, 400)
