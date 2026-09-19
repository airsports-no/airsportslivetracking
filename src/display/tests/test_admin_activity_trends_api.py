import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from display.default_scorecards.create_scorecards import create_scorecards
from display.models import Contest, NavigationTask, Route, Scorecard


class TestAdminActivityTrendsApi(TestCase):
    def setUp(self):
        create_scorecards()
        self.superuser = get_user_model().objects.create(email="admin-trends-super@example.com", is_superuser=True)
        self.regular_user = get_user_model().objects.create(email="admin-trends-regular@example.com")
        self.scorecard = Scorecard.get_originals().get(shortcut_name="FAI Precision")

    def test_non_superuser_is_rejected(self):
        client = APIClient()
        client.force_authenticate(self.regular_user)
        response = client.get("/api/v1/admin/activity-trends/")
        self.assertEqual(403, response.status_code)

    def test_contests_and_tasks_are_counted_in_the_same_bucket(self):
        now = datetime.datetime.now(datetime.timezone.utc).replace(hour=10, minute=0, second=0, microsecond=0)
        contest = Contest.objects.create(
            name="Trend contest",
            time_zone="Europe/Oslo",
            start_time=now,
            finish_time=now + datetime.timedelta(hours=8),
            location="60.0,11.0",
        )
        NavigationTask.objects.create(
            name="Trend task 1",
            contest=contest,
            route=Route.objects.create(name="Trend route 1", waypoints=[], takeoff_gates=[], landing_gates=[]),
            original_scorecard=self.scorecard,
            start_time=now,
            finish_time=contest.finish_time,
        )
        NavigationTask.objects.create(
            name="Trend task 2",
            contest=contest,
            route=Route.objects.create(name="Trend route 2", waypoints=[], takeoff_gates=[], landing_gates=[]),
            original_scorecard=self.scorecard,
            start_time=now,
            finish_time=contest.finish_time,
        )

        client = APIClient()
        client.force_authenticate(self.superuser)
        response = client.get("/api/v1/admin/activity-trends/", {"days": 1, "bin": "day"})

        self.assertEqual(200, response.status_code, response.content)
        payload = response.json()
        self.assertEqual(1, len(payload["series"]))
        self.assertEqual(1, payload["series"][0]["contests"])
        self.assertEqual(2, payload["series"][0]["tasks"])

    def test_invalid_bin_is_rejected_cleanly(self):
        client = APIClient()
        client.force_authenticate(self.superuser)
        response = client.get("/api/v1/admin/activity-trends/", {"bin": "decade"})
        self.assertEqual(400, response.status_code)
