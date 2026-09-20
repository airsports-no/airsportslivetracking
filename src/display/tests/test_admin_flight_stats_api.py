import datetime

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from display.default_scorecards.create_scorecards import create_scorecards
from display.models import Aeroplane, Contest, Contestant, ContestantTrack, Crew, NavigationTask, Person, Route, Scorecard, Team


class TestAdminFlightStatsApi(TestCase):
    def setUp(self):
        # AdminFlightStatsViewSet caches its response by (days, bin) - clear so a stale cached
        # response from another test using the same params isn't served here (the cache doesn't
        # roll back with the DB transaction the way everything else in this test does).
        cache.clear()
        create_scorecards()
        self.superuser = get_user_model().objects.create(email="admin-flight-stats-super@example.com", is_superuser=True)
        self.regular_user = get_user_model().objects.create(email="admin-flight-stats-regular@example.com")
        self.scorecard = Scorecard.get_originals().get(shortcut_name="FAI Precision")
        self.contest = Contest.objects.create(
            name="Admin Flight Stats Contest",
            time_zone="Europe/Oslo",
            start_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 8, 1, 20, 0, tzinfo=datetime.timezone.utc),
            location="60.0,11.0",
        )
        self.navigation_task = NavigationTask.objects.create(
            name="Admin Flight Stats Task",
            contest=self.contest,
            route=Route.objects.create(name="Stats Route", waypoints=[], takeoff_gates=[], landing_gates=[]),
            original_scorecard=self.scorecard,
            start_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 8, 1, 20, 0, tzinfo=datetime.timezone.utc),
            wind_speed=0,
            wind_direction=0,
            minutes_to_starting_point=5,
            minutes_to_landing=5,
        )

    def _make_contestant(self, number, member1_email, takeoff_time, calculator_started, passed_start, passed_finish, member2=None):
        team = Team.objects.create(
            crew=Crew.objects.create(
                member1=Person.objects.create(first_name="P", last_name=str(number), email=member1_email),
                member2=member2,
            ),
            aeroplane=Aeroplane.objects.create(registration=f"LN-{number}"),
        )
        contestant = Contestant.objects.create(
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
        ContestantTrack.objects.filter(contestant=contestant).update(
            calculator_started=calculator_started,
            # "Crossed the starting line" is read from current_state, not passed_starting_gate -
            # see the comment in admin_flight_stats.build_admin_flight_stats for why.
            current_state="Flying" if passed_start else "Waiting...",
            passed_finish_gate=passed_finish,
        )
        return contestant

    def test_non_superuser_is_rejected(self):
        client = APIClient()
        client.force_authenticate(self.regular_user)
        response = client.get("/api/v1/admin/flight-stats/")
        self.assertEqual(403, response.status_code)

    def test_unauthenticated_is_rejected(self):
        client = APIClient()
        response = client.get("/api/v1/admin/flight-stats/")
        self.assertIn(response.status_code, (401, 403))

    def test_only_calculator_started_contestants_are_counted_and_split_by_status(self):
        now = datetime.datetime.now(datetime.timezone.utc).replace(minute=0, second=0, microsecond=0)
        # Not calculator_started at all - must be excluded entirely.
        self._make_contestant(1, "p1@example.com", now, calculator_started=False, passed_start=False, passed_finish=False)
        # calculator_started, hasn't crossed the starting line yet.
        self._make_contestant(2, "p2@example.com", now, calculator_started=True, passed_start=False, passed_finish=False)
        # Crossed start, not finish.
        self._make_contestant(3, "p3@example.com", now, calculator_started=True, passed_start=True, passed_finish=False)
        # Crossed both.
        self._make_contestant(4, "p4@example.com", now, calculator_started=True, passed_start=True, passed_finish=True)

        client = APIClient()
        client.force_authenticate(self.superuser)
        response = client.get("/api/v1/admin/flight-stats/", {"days": 1, "bin": "day"})

        self.assertEqual(200, response.status_code, response.content)
        payload = response.json()
        self.assertEqual(1, len(payload["series"]))
        bucket = payload["series"][0]
        self.assertEqual(1, bucket["awaiting_start"])
        self.assertEqual(1, bucket["flying"])
        self.assertEqual(1, bucket["finished"])
        # The non-started contestant contributed 0 to every category, not 1 to any of them.
        self.assertEqual(3, bucket["awaiting_start"] + bucket["flying"] + bucket["finished"])

    def test_a_contestant_stuck_mid_flight_state_is_finished_once_its_window_has_passed(self):
        # Regression: current_state is set live by the calculator and simply stops updating once
        # it's no longer running - it is never retroactively corrected. A contestant who went
        # off-track, crashed the calculator, or flew a task with no real finish gate could get
        # stuck showing "Flying" forever, including weeks after the contest actually ended.
        weeks_ago = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(weeks=3)
        self._make_contestant(
            1, "stuck-mid-flight@example.com", weeks_ago, calculator_started=True, passed_start=True, passed_finish=False
        )

        client = APIClient()
        client.force_authenticate(self.superuser)
        response = client.get("/api/v1/admin/flight-stats/", {"days": 30, "bin": "day"})

        self.assertEqual(200, response.status_code, response.content)
        bucket = response.json()["series"][0]
        self.assertEqual(1, bucket["finished"])
        self.assertEqual(0, bucket["flying"])

    def test_unique_persons_series_counts_both_crew_members_once_each(self):
        now = datetime.datetime.now(datetime.timezone.utc).replace(minute=0, second=0, microsecond=0)
        shared_copilot = Person.objects.create(first_name="Shared", last_name="Copilot", email="shared-copilot@example.com")
        self._make_contestant(
            1, "pilot-a@example.com", now, calculator_started=True, passed_start=False, passed_finish=False, member2=shared_copilot
        )
        self._make_contestant(
            2, "pilot-b@example.com", now, calculator_started=True, passed_start=False, passed_finish=False, member2=shared_copilot
        )

        client = APIClient()
        client.force_authenticate(self.superuser)
        response = client.get("/api/v1/admin/flight-stats/", {"days": 1, "bin": "day"})

        self.assertEqual(200, response.status_code, response.content)
        payload = response.json()
        self.assertEqual(1, len(payload["unique_persons_series"]))
        # pilot-a, pilot-b, shared_copilot (once, not twice) = 3 unique persons.
        self.assertEqual(3, payload["unique_persons_series"][0]["count"])

    def test_unique_persons_series_follows_the_selected_bin_not_always_daily(self):
        # Two contestants on different days of the same week - with weekly binning they must
        # land in the same bucket (and their distinct pilots both counted), not one per day.
        # Anchored 10 days back (not just "today at 10:00") so monday/monday+2 stay safely
        # within the query window and in the past regardless of what day/time the suite runs -
        # a wall-clock-hour anchor broke this same way whenever the real run time fell on a
        # Monday before that hour (see the identical fix in test_admin_activity_trends_api.py).
        reference = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=10)
        monday = reference - datetime.timedelta(days=reference.weekday())
        self._make_contestant(1, "week-pilot-a@example.com", monday, calculator_started=True, passed_start=False, passed_finish=False)
        self._make_contestant(
            2, "week-pilot-b@example.com", monday + datetime.timedelta(days=2), calculator_started=True, passed_start=False, passed_finish=False
        )

        client = APIClient()
        client.force_authenticate(self.superuser)
        response = client.get("/api/v1/admin/flight-stats/", {"days": 20, "bin": "week"})

        self.assertEqual(200, response.status_code, response.content)
        payload = response.json()
        self.assertEqual(1, len(payload["unique_persons_series"]))
        self.assertEqual(2, payload["unique_persons_series"][0]["count"])

    def test_invalid_bin_is_rejected_cleanly(self):
        client = APIClient()
        client.force_authenticate(self.superuser)
        response = client.get("/api/v1/admin/flight-stats/", {"bin": "fortnight"})
        self.assertEqual(400, response.status_code)
