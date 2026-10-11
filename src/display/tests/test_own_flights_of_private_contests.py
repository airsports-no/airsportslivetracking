import datetime
from unittest.mock import patch

from django.test import TestCase
from guardian.shortcuts import assign_perm
from rest_framework.test import APIClient

from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
from display.models import Aeroplane, Contest, Contestant, Crew, MyUser, NavigationTask, Person, Route, Team
from display.utilities.tracking_definitions import TRACKING_PILOT
from utilities.mock_utilities import TraccarMock


class OwnFlightsOfPrivateContestsTest(TestCase):
    """A pilot who is crew in a private contest, without view permission on it, must still see their own flights."""

    def setUp(self):
        for target in ("display.models.contestant.get_traccar_instance", "display.signals.get_traccar_instance"):
            patcher = patch(target, return_value=TraccarMock)
            patcher.start()
            self.addCleanup(patcher.stop)
        now = datetime.datetime.now(datetime.timezone.utc)
        self.contest = Contest.objects.create(name="Secret Cup", start_time=now, finish_time=now, is_public=False)
        self.task = NavigationTask.create(
            name="Hidden Day 1",
            original_scorecard=get_default_scorecard(),
            start_time=now,
            finish_time=now + datetime.timedelta(days=2),
            route=Route.objects.create(name="Route"),
            contest=self.contest,
            is_public=False,
        )
        self.user = MyUser.objects.create(username="p", email="p@example.com")
        pilot = Person.objects.create(first_name="Pi", last_name="Lot", email="p@example.com")
        team = Team.objects.create(crew=Crew.objects.create(member1=pilot), aeroplane=Aeroplane.objects.create(registration="LN-Y"))
        self.future = Contestant.objects.create(
            team=team, navigation_task=self.task, tracking_device=TRACKING_PILOT, contestant_number=1,
            tracker_start_time=now + datetime.timedelta(hours=1),
            takeoff_time=now + datetime.timedelta(hours=2),
            finished_by_time=now + datetime.timedelta(hours=4),
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_a_future_flight_in_a_private_contest_is_listed_with_names_and_no_map_access(self):
        response = self.client.get("/api/v1/userprofile/my_future_flights/")
        self.assertEqual(response.status_code, 200)
        flights = response.json()
        self.assertEqual([f["id"] for f in flights], [self.future.pk])
        self.assertEqual(flights[0]["contest_name"], "Secret Cup")
        self.assertEqual(flights[0]["navigation_task_name"], "Hidden Day 1")
        self.assertIs(flights[0]["map_viewable"], False)

    def test_the_flight_carries_metadata_but_nothing_about_the_route(self):
        flight = self.client.get("/api/v1/userprofile/my_future_flights/").json()[0]
        self.assertEqual(
            set(flight),
            {
                "id", "contest_id", "navigation_task", "contest_name", "navigation_task_name", "task_type", "contest_logo",
                "contest_header_image", "contest_location", "contest_country", "contest_website", "map_viewable",
                "contestant_number", "takeoff_time", "tracker_start_time", "finished_by_time", "air_speed", "wind_speed",
                "wind_direction", "adaptive_start", "can_cancel",
            },
        )
        for secret in ("gate_times", "declaration_payload", "compiled_effective_route_payload", "scorecard_rules", "team", "default_map_url"):
            self.assertNotIn(secret, flight)
        previous = self._previous()
        for secret in ("gate_times", "declaration_payload", "compiled_effective_route_payload", "contestanttrack", "team"):
            self.assertNotIn(secret, previous)

    def _previous(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        Contestant.objects.filter(pk=self.future.pk).update(
            tracker_start_time=now - datetime.timedelta(hours=5), takeoff_time=now - datetime.timedelta(hours=4),
            finished_by_time=now - datetime.timedelta(hours=2),
        )
        return self.client.get("/api/v1/userprofile/my_previous_flights/").json()[0]

    def test_the_old_full_payload_is_still_there_with_detail_full_but_only_for_contests_the_user_may_view(self):
        self.assertEqual(self.client.get("/api/v1/userprofile/my_future_flights/?detail=full").json(), [])
        assign_perm("view_contest", self.user, self.contest)
        full = self.client.get("/api/v1/userprofile/my_future_flights/?detail=full").json()
        self.assertEqual([f["id"] for f in full], [self.future.pk])
        self.assertIn("team", full[0])

    def test_view_permission_opens_the_map(self):
        assign_perm("view_contest", self.user, self.contest)
        flights = self.client.get("/api/v1/userprofile/my_future_flights/").json()
        self.assertIs(flights[0]["map_viewable"], True)

    def test_a_public_task_has_a_map_for_everybody(self):
        Contest.objects.filter(pk=self.contest.pk).update(is_public=True)
        NavigationTask.objects.filter(pk=self.task.pk).update(is_public=True)
        self.assertIs(self.client.get("/api/v1/userprofile/my_future_flights/").json()[0]["map_viewable"], True)

    def test_a_previous_flight_in_a_private_contest_is_listed_too(self):
        flight = self._previous()
        self.assertEqual(flight["id"], self.future.pk)
        self.assertEqual(flight["contest_name"], "Secret Cup")
        self.assertIs(flight["map_viewable"], False)

    def test_other_peoples_flights_are_not_listed(self):
        other = MyUser.objects.create(username="o", email="o@example.com")
        Person.objects.create(first_name="Ot", last_name="Her", email="o@example.com")
        client = APIClient()
        client.force_authenticate(other)
        self.assertEqual(client.get("/api/v1/userprofile/my_future_flights/").json(), [])

    def test_the_now_endpoint_names_the_contest_for_a_pilot_who_may_not_view_it(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        Contestant.objects.filter(pk=self.future.pk).update(
            tracker_start_time=now - datetime.timedelta(minutes=5), takeoff_time=now + datetime.timedelta(minutes=5)
        )
        response = self.client.get("/api/v1/userprofile/get_current_app_navigation_task/")
        self.assertEqual(response.status_code, 200)
        active = response.json()[0]["active_contestants"][0]
        self.assertEqual(active["contest_name"], "Secret Cup")
        self.assertIn("task_type", active)
        self.assertIn("contest_header_image", active)
