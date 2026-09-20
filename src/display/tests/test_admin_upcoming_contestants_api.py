import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from display.default_scorecards.create_scorecards import create_scorecards
from display.models import Aeroplane, Contest, Contestant, Crew, NavigationTask, Person, Route, Scorecard, Team


class TestAdminUpcomingContestantsApi(TestCase):
    def setUp(self):
        create_scorecards()
        self.superuser = get_user_model().objects.create(email="admin-upcoming-super@example.com", is_superuser=True)
        self.regular_user = get_user_model().objects.create(email="admin-upcoming-regular@example.com")
        self.scorecard = Scorecard.get_originals().get(shortcut_name="FAI Precision")
        self.contest = Contest.objects.create(
            name="Admin Upcoming Contest",
            time_zone="Europe/Oslo",
            start_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 9, 1, 20, 0, tzinfo=datetime.timezone.utc),
            location="60.0,11.0",
        )
        self.navigation_task = NavigationTask.objects.create(
            name="Admin Upcoming Task",
            contest=self.contest,
            route=Route.objects.create(name="Upcoming Route", waypoints=[], takeoff_gates=[], landing_gates=[]),
            original_scorecard=self.scorecard,
            start_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 9, 1, 20, 0, tzinfo=datetime.timezone.utc),
            wind_speed=0,
            wind_direction=0,
            minutes_to_starting_point=5,
            minutes_to_landing=5,
        )

    def _make_contestant(self, number, takeoff_time):
        team = Team.objects.create(
            crew=Crew.objects.create(member1=Person.objects.create(first_name="P", last_name=str(number), email=f"upcoming-{number}@example.com")),
            aeroplane=Aeroplane.objects.create(registration=f"LN-UP{number}"),
        )
        return Contestant.objects.create(
            navigation_task=self.navigation_task,
            team=team,
            contestant_number=number,
            takeoff_time=takeoff_time,
            tracker_start_time=takeoff_time - datetime.timedelta(minutes=10),
            finished_by_time=takeoff_time + datetime.timedelta(hours=2),
            air_speed=70,
            minutes_to_starting_point=5,
            wind_speed=0,
            wind_direction=0,
        )

    def test_non_superuser_is_rejected(self):
        client = APIClient()
        client.force_authenticate(self.regular_user)
        response = client.get("/api/v1/admin/upcoming-contestants/")
        self.assertEqual(403, response.status_code)

    def test_only_future_contestants_within_the_horizon_are_returned(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        past = self._make_contestant(1, now - datetime.timedelta(days=1))
        soon = self._make_contestant(2, now + datetime.timedelta(days=2))
        far_future = self._make_contestant(3, now + datetime.timedelta(days=40))

        client = APIClient()
        client.force_authenticate(self.superuser)
        response = client.get("/api/v1/admin/upcoming-contestants/", {"days": 14})

        self.assertEqual(200, response.status_code, response.content)
        returned_ids = {row["id"] for row in response.json()}
        self.assertNotIn(past.pk, returned_ids)
        self.assertIn(soon.pk, returned_ids)
        self.assertNotIn(far_future.pk, returned_ids)

    def test_results_are_sorted_by_takeoff_time(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        later = self._make_contestant(1, now + datetime.timedelta(days=5))
        earlier = self._make_contestant(2, now + datetime.timedelta(days=1))

        client = APIClient()
        client.force_authenticate(self.superuser)
        response = client.get("/api/v1/admin/upcoming-contestants/", {"days": 14})

        self.assertEqual(200, response.status_code, response.content)
        ids_in_order = [row["id"] for row in response.json()]
        self.assertEqual([earlier.pk, later.pk], ids_in_order)

    def test_invalid_days_is_rejected_cleanly(self):
        client = APIClient()
        client.force_authenticate(self.superuser)
        response = client.get("/api/v1/admin/upcoming-contestants/", {"days": 999})
        self.assertEqual(400, response.status_code)
