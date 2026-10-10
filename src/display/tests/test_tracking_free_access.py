import datetime
from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from display.models import MyUser, Person, UserEntitlementGrant
from display.services.tracking_access import SOURCE_GRANT, SOURCE_STAFF, free_tracking_access
from utilities.mock_utilities import TraccarMock

NOW = datetime.datetime.now(datetime.timezone.utc)
HOUR = datetime.timedelta(hours=1)


def grant(user, kind=UserEntitlementGrant.KIND_APP_TRACKING, **kwargs):
    return UserEntitlementGrant.objects.create(user=user, kind=kind, value=kwargs.pop("value", "free"), **kwargs)


class TestFreeTrackingAccess(TestCase):
    def setUp(self):
        self.user = MyUser.objects.create(username="pilot", email="pilot@example.com")

    def test_ordinary_users_have_none(self):
        self.assertIsNone(free_tracking_access(self.user))

    def test_anonymous_and_missing_users_have_none(self):
        from django.contrib.auth.models import AnonymousUser

        self.assertIsNone(free_tracking_access(AnonymousUser()))
        self.assertIsNone(free_tracking_access(None))

    def test_staff_and_superusers_always_do(self):
        self.user.is_staff = True
        self.assertEqual(free_tracking_access(self.user).source, SOURCE_STAFF)
        self.user.is_staff, self.user.is_superuser = False, True
        self.assertEqual(free_tracking_access(self.user).source, SOURCE_STAFF)

    def test_an_active_grant_without_expiry_gives_access(self):
        grant(self.user)
        access = free_tracking_access(self.user)
        self.assertEqual((access.source, access.expires_at), (SOURCE_GRANT, None))

    def test_a_grant_stops_at_its_expiry(self):
        g = grant(self.user, expires_at=NOW + HOUR)
        self.assertEqual(free_tracking_access(self.user).expires_at, g.expires_at)
        UserEntitlementGrant.objects.update(expires_at=NOW - HOUR)
        self.assertIsNone(free_tracking_access(self.user))

    def test_a_deactivated_grant_is_ignored(self):
        grant(self.user, is_active=False)
        self.assertIsNone(free_tracking_access(self.user))

    def test_other_kinds_of_grants_do_not_count(self):
        grant(self.user, kind=UserEntitlementGrant.KIND_TASK_TYPE_GROUP, value="cima")
        self.assertIsNone(free_tracking_access(self.user))

    def test_other_peoples_grants_do_not_count(self):
        other = MyUser.objects.create(username="other", email="other@example.com")
        grant(other)
        self.assertIsNone(free_tracking_access(self.user))

    def test_the_longest_lasting_grant_is_reported(self):
        grant(self.user, value="short", expires_at=NOW + HOUR)
        grant(self.user, value="forever")
        self.assertIsNone(free_tracking_access(self.user).expires_at)


class TestFreeAccessOnTheOwnProfile(TestCase):
    URL = "/api/v1/userprofile/retrieve_profile/"

    def setUp(self):
        patcher = patch("display.signals.get_traccar_instance", return_value=TraccarMock)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.user = MyUser.objects.create(username="pilot", email="pilot@example.com")
        Person.objects.create(first_name="Pi", last_name="Lot", email="pilot@example.com", validated=True)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_the_profile_says_null_for_an_ordinary_pilot(self):
        self.assertIsNone(self.client.get(self.URL).json()["tracking_free_access"])

    def test_the_profile_reports_a_grant_with_its_expiry(self):
        g = grant(self.user, expires_at=NOW + HOUR)
        body = self.client.get(self.URL).json()["tracking_free_access"]
        self.assertEqual(body["source"], "grant")
        self.assertIsNotNone(body["expires_at"])

    def test_staff_are_reported_as_such(self):
        self.user.is_staff = True
        self.user.save()
        self.assertEqual(self.client.get(self.URL).json()["tracking_free_access"]["source"], "staff")

    def test_updating_the_profile_returns_the_flag_too(self):
        grant(self.user)
        response = self.client.patch("/api/v1/userprofile/partial_update_profile/", {"biography": "Hi"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["tracking_free_access"]["source"], "grant")

    def test_the_email_match_ignores_case(self):
        from types import SimpleNamespace

        from display.serialisers import OwnPersonSerialiser

        grant(self.user)
        person = Person.objects.get(email="pilot@example.com")
        person.email = "Pilot@Example.com"
        data = OwnPersonSerialiser(person, context={"request": SimpleNamespace(user=self.user)}).data
        self.assertEqual(data["tracking_free_access"]["source"], "grant")
        stranger = MyUser.objects.create(username="stranger", email="stranger@example.com")
        data = OwnPersonSerialiser(person, context={"request": SimpleNamespace(user=stranger)}).data
        self.assertIsNone(data["tracking_free_access"])

    def test_other_profile_serialisers_do_not_carry_the_field(self):
        from display.serialisers import PersonSerialiser

        self.assertNotIn("tracking_free_access", PersonSerialiser().fields)
