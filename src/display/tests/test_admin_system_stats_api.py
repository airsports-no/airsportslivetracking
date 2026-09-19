import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from display.default_scorecards.create_scorecards import create_scorecards
from display.models import Aeroplane, Contest, Contestant, Crew, NavigationTask, Person, Route, Scorecard, Team
from display.services.admin_system_stats import get_country_stats, get_retention_stats, get_task_type_popularity
from display.utilities.cima_task_type_definitions import PRECISION_NAVIGATION, TURNPOINT_HUNT


class AdminSystemStatsTestBase(TestCase):
    def setUp(self):
        create_scorecards()
        self.superuser = get_user_model().objects.create(email="admin-system-stats-super@example.com", is_superuser=True)
        self.regular_user = get_user_model().objects.create(email="admin-system-stats-regular@example.com")
        self.scorecard = Scorecard.get_originals().get(shortcut_name="FAI Precision")

    def _make_contest(self, name, start_time):
        return Contest.objects.create(
            name=name,
            time_zone="Europe/Oslo",
            start_time=start_time,
            finish_time=start_time + datetime.timedelta(hours=8),
            location="60.0,11.0",
        )

    def _make_task(self, contest, name, nominatim=None, task_subtype=None):
        task = NavigationTask.objects.create(
            name=name,
            contest=contest,
            route=Route.objects.create(name=f"{name} route", waypoints=[], takeoff_gates=[], landing_gates=[]),
            original_scorecard=self.scorecard,
            start_time=contest.start_time,
            finish_time=contest.finish_time,
            task_subtype=task_subtype,
        )
        if nominatim is not None:
            NavigationTask.objects.filter(pk=task.pk).update(_nominatim=nominatim)
        return NavigationTask.objects.get(pk=task.pk)

    def _make_contestant(self, navigation_task, number, member1_email, member2=None):
        team = Team.objects.create(
            crew=Crew.objects.create(
                member1=Person.objects.create(first_name="P", last_name=str(number), email=member1_email),
                member2=member2,
            ),
            aeroplane=Aeroplane.objects.create(registration=f"LN-SYS{number}"),
        )
        return Contestant.objects.create(
            navigation_task=navigation_task,
            team=team,
            contestant_number=number,
            takeoff_time=navigation_task.start_time,
            tracker_start_time=navigation_task.start_time,
            finished_by_time=navigation_task.finish_time,
            air_speed=70,
            minutes_to_starting_point=5,
            wind_speed=0,
            wind_direction=0,
        )


class TestAdminSystemStatsApi(AdminSystemStatsTestBase):
    def test_non_superuser_is_rejected(self):
        client = APIClient()
        client.force_authenticate(self.regular_user)
        response = client.get("/api/v1/admin/system-stats/")
        self.assertEqual(403, response.status_code)

    def test_response_shape(self):
        client = APIClient()
        client.force_authenticate(self.superuser)
        response = client.get("/api/v1/admin/system-stats/")
        self.assertEqual(200, response.status_code, response.content)
        payload = response.json()
        self.assertIn("country", payload)
        self.assertIn("task_type_popularity", payload)
        self.assertIn("retention", payload)


class TestCountryStats(AdminSystemStatsTestBase):
    def test_tasks_without_a_cached_geocode_are_grouped_as_unknown_without_triggering_a_lookup(self):
        contest = self._make_contest("No geocode contest", datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.timezone.utc))
        self._make_task(contest, "No geocode task")

        rows = get_country_stats()
        unknown_rows = [row for row in rows if row["country_name"] == "Unknown"]
        self.assertEqual(1, len(unknown_rows))
        self.assertEqual(1, unknown_rows[0]["tasks"])
        self.assertEqual("", unknown_rows[0]["country_code"])

    def test_tasks_and_contestants_are_aggregated_per_country_code(self):
        contest = self._make_contest("Norway contest", datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.timezone.utc))
        task = self._make_task(
            contest,
            "Norway task",
            nominatim={"address": {"country": "Norway", "country_code": "no"}},
        )
        self._make_contestant(task, 1, "country-stats-1@example.com")
        self._make_contestant(task, 2, "country-stats-2@example.com")

        rows = get_country_stats()
        norway_rows = [row for row in rows if row["country_code"] == "NO"]
        self.assertEqual(1, len(norway_rows))
        self.assertEqual("Norway", norway_rows[0]["country_name"])
        self.assertEqual(1, norway_rows[0]["contests"])
        self.assertEqual(1, norway_rows[0]["tasks"])
        self.assertEqual(2, norway_rows[0]["contestants"])

    def test_multiple_tasks_in_the_same_contest_count_the_contest_once(self):
        contest = self._make_contest("Multi-task contest", datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.timezone.utc))
        self._make_task(contest, "Task A", nominatim={"address": {"country": "Norway", "country_code": "no"}})
        self._make_task(contest, "Task B", nominatim={"address": {"country": "Norway", "country_code": "no"}})

        rows = get_country_stats()
        norway_rows = [row for row in rows if row["country_code"] == "NO"]
        self.assertEqual(1, norway_rows[0]["contests"])
        self.assertEqual(2, norway_rows[0]["tasks"])


class TestTaskTypePopularity(AdminSystemStatsTestBase):
    def test_counts_group_by_task_subtype(self):
        contest = self._make_contest("Popularity contest", datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.timezone.utc))
        self._make_task(contest, "T1", task_subtype=TURNPOINT_HUNT)
        self._make_task(contest, "T2", task_subtype=TURNPOINT_HUNT)
        self._make_task(contest, "T3", task_subtype=PRECISION_NAVIGATION)

        rows = get_task_type_popularity()
        by_subtype = {row["task_subtype"]: row["count"] for row in rows}
        self.assertEqual(2, by_subtype[TURNPOINT_HUNT])
        self.assertEqual(1, by_subtype[PRECISION_NAVIGATION])


class TestRetentionStats(AdminSystemStatsTestBase):
    def test_a_team_flying_in_two_contests_counts_as_returning(self):
        contest_a = self._make_contest("Contest A", datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.timezone.utc))
        contest_b = self._make_contest("Contest B", datetime.datetime(2026, 9, 1, 9, 0, tzinfo=datetime.timezone.utc))
        task_a = self._make_task(contest_a, "Task A")
        task_b = self._make_task(contest_b, "Task B")

        pilot = Person.objects.create(first_name="Returning", last_name="Pilot", email="returning-pilot@example.com")
        team = Team.objects.create(crew=Crew.objects.create(member1=pilot), aeroplane=Aeroplane.objects.create(registration="LN-RET"))
        for i, task in enumerate((task_a, task_b), start=1):
            Contestant.objects.create(
                navigation_task=task,
                team=team,
                contestant_number=i,
                takeoff_time=task.start_time,
                tracker_start_time=task.start_time,
                finished_by_time=task.finish_time,
                air_speed=70,
                minutes_to_starting_point=5,
                wind_speed=0,
                wind_direction=0,
            )

        # A one-and-done team for contrast.
        one_time_task = self._make_task(contest_a, "One-time task")
        self._make_contestant(one_time_task, 99, "one-time-pilot@example.com")

        stats = get_retention_stats()
        self.assertEqual(2, stats["teams"]["total"])
        self.assertEqual(1, stats["teams"]["returning"])
        self.assertEqual(50.0, stats["teams"]["returning_pct"])
        self.assertEqual(1, stats["persons"]["returning"])

    def test_no_participation_returns_zero_without_dividing_by_zero(self):
        stats = get_retention_stats()
        self.assertEqual({"total": 0, "returning": 0, "returning_pct": 0.0, "distribution": []}, stats["teams"])
