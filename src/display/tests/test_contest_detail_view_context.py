from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory

from display.models import AccessGrant, Club, Contest, UserEntitlementGrant
from display.serialisers import ContestSerialiser
from display.utilities.task_type_group_definitions import CIMA_TASK_TYPE_GROUP


class TestContestAccessStatusSerializationWithTaskGroups(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create(email="serializer@example.com")
        self.club = Club.objects.create(name="Serializer Club")
        self.contest = Contest.objects.create(
            name="Serializer Contest",
            time_zone="Europe/Oslo",
            start_time="2026-05-01T09:00:00+00:00",
            finish_time="2026-05-01T17:00:00+00:00",
            location="60.0,11.0",
            created_by=self.user,
            organizing_club=self.club,
        )
        self.request = APIRequestFactory().get("/")
        self.request.user = self.user

    def test_contest_serializer_emits_task_type_group_access_status(self):
        AccessGrant.objects.create(
            club=self.club,
            status=AccessGrant.ACTIVE,
            contestant_limit=None,
            task_type_groups=[CIMA_TASK_TYPE_GROUP],
        )
        data = ContestSerialiser(self.contest, context={"request": self.request}).data

        self.assertIn(CIMA_TASK_TYPE_GROUP, data["access_status"]["allowed_task_type_groups"])
        self.assertIn("legacy", data["access_status"]["allowed_task_type_groups"])
        self.assertEqual([CIMA_TASK_TYPE_GROUP], data["access_status"]["package_task_type_groups"])
        self.assertIn("legacy", data["access_status"]["free_task_type_groups"])

    def test_contest_serializer_merges_viewers_personal_entitlement_grant(self):
        """Regression test: a beta tester's personal cima:circle grant must
        show up in this contest's access_status even though the contest
        itself has no club/token grant at all (still on the free tier)."""
        UserEntitlementGrant.objects.create(
            user=self.user,
            kind=UserEntitlementGrant.KIND_TASK_TYPE_GROUP,
            value="cima:circle",
        )

        data = ContestSerialiser(self.contest, context={"request": self.request}).data

        self.assertEqual("free", data["access_status"]["tier_code"])
        self.assertIn("cima:circle", data["access_status"]["allowed_task_type_groups"])
        self.assertIn("legacy", data["access_status"]["allowed_task_type_groups"])
