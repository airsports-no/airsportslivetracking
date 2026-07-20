from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.urls import reverse
from rest_framework.test import APITestCase

from display.models import Contest


class TestContestCreateAtomicity(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create(email="atomic-create@example.com")
        self.user.user_permissions.add(Permission.objects.get(codename="add_contest"))
        self.client.force_login(self.user)

    @patch("display.views.assign_token_to_contest", side_effect=ValidationError("boom"))
    def test_contest_not_created_when_initial_token_assignment_fails(self, _mock_assign):
        response = self.client.post(
            reverse("contest_create"),
            data={
                "name": "AtomicContest",
                "time_zone": "Europe/Oslo",
                "start_time": "2026-10-01T09:00",
                "finish_time": "2026-10-01T17:00",
                "location": "60, 11",
                "initial_token_grant": 999,
                "summary_score_sorting_direction": "asc",
                "autosum_scores": True,
            },
            follow=False,
        )

        self.assertFalse(Contest.objects.filter(name="AtomicContest").exists())
