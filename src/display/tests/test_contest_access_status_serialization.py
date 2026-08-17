from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory

from display.models import Contest, Club
from display.serialisers import ContestSerialiser


class TestContestAccessStatusSerialization(TestCase):
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

    @patch("display.serialisers.resolve_contest_access")
    @patch("display.serialisers.AvailableTokenGrantSerializer")
    @patch("display.serialisers.UserTokenGrant")
    def test_contest_serializer_emits_access_status(self, mock_token_model, mock_token_serializer, mock_resolve):
        mock_resolve.return_value = type(
            "Resolution",
            (),
            {
                "tier_code": "annual_club_pass",
                "tier_label": "Annual Club Pass",
                "source_type": "club_pass",
                "source_id": 7,
                "contestant_limit": None,
                "contestants_used": 2,
                "enforcement_mode": "audit",
                "token_grant_id": None,
                "token_type_id": None,
                "package_contestant_limit": None,
                "free_contestant_limit": None,
                "contestant_limit_uses_free_default": False,
                "uses_more_advantageous_free_limits": False,
                "allowed_task_type_groups": ["legacy", "cima"],
                "package_task_type_groups": ["cima"],
                "free_task_type_groups": ["legacy"],
            },
        )()
        mock_token_model.objects.filter.return_value.select_related.return_value.order_by.return_value = []
        mock_token_serializer.return_value.data = []

        data = ContestSerialiser(self.contest, context={"request": self.request}).data

        self.assertEqual("annual_club_pass", data["access_status"]["tier_code"])
        self.assertEqual("Annual Club Pass", data["access_status"]["tier_label"])
        self.assertEqual("club_pass", data["access_status"]["source_type"])
        self.assertEqual(2, data["access_status"]["contestants_used"])
        self.assertEqual(["legacy", "cima"], data["access_status"]["allowed_task_type_groups"])
        self.assertEqual(["cima"], data["access_status"]["package_task_type_groups"])
        self.assertEqual(["legacy"], data["access_status"]["free_task_type_groups"])
        mock_resolve.assert_called_once_with(self.contest, user=self.user)
