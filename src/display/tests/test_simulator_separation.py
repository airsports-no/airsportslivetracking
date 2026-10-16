import datetime
from unittest.mock import patch

from django.core.exceptions import ValidationError as DjangoValidationError
from django.test import TestCase
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

import position_processor_process
from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
from display.models import (
    Aeroplane,
    Contest,
    Contestant,
    ContestTeam,
    Crew,
    NavigationTask,
    Person,
    Route,
    SimulatorQuickstart,
    Team,
)
from display.models.my_user import MyUser
from display.services.self_registration import implied_flight_mode, resolve_flight_mode
from display.services.simulator_quickstart import current_quickstart
from display.utilities.simulator_policy import (
    FLIGHT_MODE_REAL,
    FLIGHT_MODE_SIMULATOR,
    SIMULATOR_ALLOWED,
    SIMULATOR_NOT_ALLOWED,
    SIMULATOR_ONLY,
    flight_mode_for_platform,
    policy_allows,
)
from display.utilities.tracking_definitions import TRACKING_PILOT
from display.waypoint import Waypoint
from utilities.mock_utilities import TraccarMock


def waypoint(name, latitude, longitude, bearing_next=-1):
    w = Waypoint(name)
    w.latitude = latitude
    w.longitude = longitude
    w.gate_line = []
    w.bearing_next = bearing_next
    return w


class FakeRequest:
    def __init__(self, platform=None, embed_client=None):
        self.META = {"HTTP_X_APP_PLATFORM": platform} if platform else {}
        self.embed_client = embed_client


class SimulatorSeparationTestCase(TestCase):
    def setUp(self):
        for target in ("display.models.contestant.get_traccar_instance", "display.signals.get_traccar_instance"):
            patcher = patch(target, return_value=TraccarMock)
            patcher.start()
            self.addCleanup(patcher.stop)
        position_processor_process.contestant_cache.clear()
        self.addCleanup(position_processor_process.contestant_cache.clear)
        self.now = datetime.datetime.now(datetime.timezone.utc)
        self.contest = Contest.objects.create(
            name="Cup", start_time=self.now, finish_time=self.now + datetime.timedelta(days=30), is_public=True
        )
        route = Route.objects.create(
            name="Route",
            waypoints=[waypoint("SP", 59.97, 11.20, bearing_next=90.0), waypoint("TP1", 59.97, 11.40)],
        )
        self.task = NavigationTask.create(
            name="Task",
            original_scorecard=get_default_scorecard(),
            start_time=self.now - datetime.timedelta(days=1),
            finish_time=self.now + datetime.timedelta(days=30),
            route=route,
            contest=self.contest,
            is_public=True,
            allow_self_management=True,
        )
        self.pilot = Person.objects.create(first_name="Pi", last_name="Lot", email="pilot@example.com")
        self.user = MyUser.objects.create(username="pilot", email="pilot@example.com")
        self.team = Team.objects.create(
            crew=Crew.objects.create(member1=self.pilot), aeroplane=Aeroplane.objects.create(registration="LN-SIM")
        )

    def set_policy(self, policy):
        NavigationTask.objects.filter(pk=self.task.pk).update(simulator_policy=policy)
        self.task.refresh_from_db()

    def make_contestant(self, flight_mode=None, number=1):
        return Contestant.objects.create(
            team=self.team,
            navigation_task=self.task,
            tracking_device=TRACKING_PILOT,
            contestant_number=number,
            tracker_start_time=self.now - datetime.timedelta(minutes=30),
            takeoff_time=self.now + datetime.timedelta(minutes=10),
            finished_by_time=self.now + datetime.timedelta(hours=2),
            flight_mode=flight_mode,
        )

    def find(self, device):
        position_processor_process.contestant_cache.clear()
        return position_processor_process.cached_find_contestant(device, self.now)


class TestPolicyRules(SimulatorSeparationTestCase):
    def test_policy_rule(self):
        self.assertEqual(
            (True, False), (policy_allows(SIMULATOR_NOT_ALLOWED, False), policy_allows(SIMULATOR_NOT_ALLOWED, True))
        )
        self.assertEqual((False, True), (policy_allows(SIMULATOR_ONLY, False), policy_allows(SIMULATOR_ONLY, True)))
        self.assertEqual(
            (True, True), (policy_allows(SIMULATOR_ALLOWED, False), policy_allows(SIMULATOR_ALLOWED, True))
        )

    def test_existing_tasks_default_to_not_allowed(self):
        self.assertEqual(SIMULATOR_NOT_ALLOWED, self.task.simulator_policy)

    def test_platforms_imply_the_flight_mode(self):
        self.assertEqual(FLIGHT_MODE_SIMULATOR, flight_mode_for_platform("msfs"))
        self.assertEqual(FLIGHT_MODE_REAL, flight_mode_for_platform("android"))
        self.assertEqual(FLIGHT_MODE_REAL, flight_mode_for_platform("iOS"))
        self.assertIsNone(flight_mode_for_platform(None))
        self.assertIsNone(flight_mode_for_platform("browser"))

    def test_a_new_contestant_gets_its_flight_mode_from_a_policy_that_allows_only_one_kind(self):
        self.assertEqual(FLIGHT_MODE_REAL, self.make_contestant(number=1).flight_mode)
        self.set_policy(SIMULATOR_ONLY)
        self.assertEqual(FLIGHT_MODE_SIMULATOR, self.make_contestant(number=2).flight_mode)
        self.set_policy(SIMULATOR_ALLOWED)
        self.assertIsNone(self.make_contestant(number=3).flight_mode, "somebody has to say on a task that allows both")

    def test_acceptance_combines_policy_and_declared_mode(self):
        self.set_policy(SIMULATOR_ALLOWED)
        undeclared, real, simulator = (
            self.make_contestant(None, 1),
            self.make_contestant(FLIGHT_MODE_REAL, 2),
            self.make_contestant(FLIGHT_MODE_SIMULATOR, 3),
        )
        self.assertEqual(
            [True, True], [undeclared.accepts_positions_from(False), undeclared.accepts_positions_from(True)]
        )
        self.assertEqual([True, False], [real.accepts_positions_from(False), real.accepts_positions_from(True)])
        self.assertEqual(
            [False, True], [simulator.accepts_positions_from(False), simulator.accepts_positions_from(True)]
        )
        self.set_policy(SIMULATOR_NOT_ALLOWED)
        undeclared = Contestant.objects.get(pk=undeclared.pk)
        self.assertEqual(
            [True, False], [undeclared.accepts_positions_from(False), undeclared.accepts_positions_from(True)]
        )

    def test_is_simulator_flight_follows_the_declaration_then_the_tracking(self):
        self.set_policy(SIMULATOR_ALLOWED)
        declared = self.make_contestant(FLIGHT_MODE_SIMULATOR, 1)
        self.assertTrue(declared.is_simulator_flight)
        old = self.make_contestant(None, 2)
        self.assertFalse(old.is_simulator_flight)
        old.has_been_tracked_by_simulator = True
        self.assertTrue(old.is_simulator_flight)


class TestPositionIngest(SimulatorSeparationTestCase):
    def test_simulator_positions_are_dropped_on_a_task_that_does_not_allow_simulators(self):
        contestant = self.make_contestant()
        self.assertEqual([], self.find(self.pilot.simulator_tracking_id))
        contestant.refresh_from_db()
        self.assertIsNotNone(contestant.blocked_positions_at, "the first ignored position is noted")
        self.assertFalse(contestant.has_been_tracked_by_simulator)
        self.assertEqual([contestant.pk], [c.pk for c, _ in self.find(self.pilot.app_tracking_id)])

    def test_real_positions_are_dropped_on_a_simulator_only_task(self):
        self.set_policy(SIMULATOR_ONLY)
        contestant = self.make_contestant()
        self.assertEqual([], self.find(self.pilot.app_tracking_id))
        contestant.refresh_from_db()
        self.assertIsNotNone(contestant.blocked_positions_at)
        found = self.find(self.pilot.simulator_tracking_id)
        self.assertEqual([(contestant.pk, True)], [(c.pk, sim) for c, sim in found])
        contestant.refresh_from_db()
        self.assertTrue(contestant.has_been_tracked_by_simulator)

    def test_both_kinds_are_used_where_simulators_are_allowed_and_nothing_is_declared(self):
        self.set_policy(SIMULATOR_ALLOWED)
        contestant = self.make_contestant(None)
        self.assertEqual(1, len(self.find(self.pilot.app_tracking_id)))
        self.assertEqual(1, len(self.find(self.pilot.simulator_tracking_id)))
        contestant.refresh_from_db()
        self.assertIsNone(contestant.blocked_positions_at)

    def test_the_declared_mode_decides_where_simulators_are_allowed(self):
        self.set_policy(SIMULATOR_ALLOWED)
        contestant = self.make_contestant(FLIGHT_MODE_REAL)
        self.assertEqual([], self.find(self.pilot.simulator_tracking_id))
        self.assertEqual(1, len(self.find(self.pilot.app_tracking_id)))
        contestant.refresh_from_db()
        self.assertIsNotNone(contestant.blocked_positions_at)

    def test_a_policy_change_takes_effect_when_the_cache_expires(self):
        contestant = self.make_contestant()
        self.assertEqual([], self.find(self.pilot.simulator_tracking_id))
        self.set_policy(SIMULATOR_ALLOWED)
        # The contestant was created for "not allowed" and so declared real: an organizer clears that to let simulators in
        Contestant.objects.filter(pk=contestant.pk).update(flight_mode=None)
        self.assertEqual(1, len(self.find(self.pilot.simulator_tracking_id)))

    def test_the_current_task_endpoints_tell_the_pilot_why_positions_are_ignored(self):
        self.make_contestant()
        client = APIClient()
        client.force_authenticate(self.user)

        def current(endpoint):
            response = client.get(f"/api/v1/userprofile/{endpoint}/")
            self.assertEqual(200, response.status_code, response.content)
            return response.json()[0]["active_contestants"][0]

        app = current("get_current_app_navigation_task")
        self.assertEqual((True, None), (app["positions_accepted"], app["positions_ignored_reason"]))
        simulator = current("get_current_sim_navigation_task")
        self.assertFalse(simulator["positions_accepted"])
        self.assertIn("does not accept flights flown in a simulator", simulator["positions_ignored_reason"])

    def test_the_reason_names_the_cause(self):
        self.set_policy(SIMULATOR_ALLOWED)
        real = self.make_contestant(FLIGHT_MODE_REAL, 1)
        self.assertIn("booked as a real aircraft flight", real.positions_ignored_reason(True))
        self.assertIsNone(real.positions_ignored_reason(False))
        simulator = self.make_contestant(FLIGHT_MODE_SIMULATOR, 2)
        self.assertIn("booked as a simulator flight", simulator.positions_ignored_reason(False))
        self.set_policy(SIMULATOR_ONLY)
        self.assertIn("for flight simulators only", Contestant.objects.get(pk=real.pk).positions_ignored_reason(False))


class TestRegistrationIntent(SimulatorSeparationTestCase):
    def test_the_website_has_to_choose(self):
        with self.assertRaises(ValidationError):
            resolve_flight_mode(FakeRequest(), None, self.task)
        self.set_policy(SIMULATOR_ALLOWED)
        self.assertEqual(FLIGHT_MODE_SIMULATOR, resolve_flight_mode(FakeRequest(), FLIGHT_MODE_SIMULATOR, self.task))
        self.assertEqual(FLIGHT_MODE_REAL, resolve_flight_mode(FakeRequest(), FLIGHT_MODE_REAL, self.task))

    def test_the_clients_are_recognised_by_the_server(self):
        self.set_policy(SIMULATOR_ALLOWED)
        self.assertEqual(FLIGHT_MODE_SIMULATOR, resolve_flight_mode(FakeRequest("msfs"), None, self.task))
        self.assertEqual(FLIGHT_MODE_REAL, resolve_flight_mode(FakeRequest("ios"), None, self.task))
        self.assertEqual(FLIGHT_MODE_SIMULATOR, resolve_flight_mode(FakeRequest(embed_client="msfs"), None, self.task))
        self.assertEqual(
            FLIGHT_MODE_REAL, resolve_flight_mode(FakeRequest("android"), FLIGHT_MODE_SIMULATOR, self.task)
        )
        self.assertIsNone(implied_flight_mode(FakeRequest()))

    def test_a_flight_the_task_does_not_accept_is_refused(self):
        with self.assertRaisesMessage(ValidationError, "does not accept flights flown in a simulator"):
            resolve_flight_mode(FakeRequest(), FLIGHT_MODE_SIMULATOR, self.task)
        with self.assertRaises(ValidationError):
            resolve_flight_mode(FakeRequest("msfs"), None, self.task)
        self.set_policy(SIMULATOR_ONLY)
        with self.assertRaisesMessage(ValidationError, "for flight simulators only"):
            resolve_flight_mode(FakeRequest(), FLIGHT_MODE_REAL, self.task)

    def test_the_registration_endpoint_stores_the_mode(self):
        self.set_policy(SIMULATOR_ALLOWED)
        contest_team = ContestTeam.objects.create(contest=self.contest, team=self.team, air_speed=70)
        client = APIClient()
        client.force_authenticate(self.user)
        url = f"/api/v1/contests/{self.contest.pk}/navigationtasks/{self.task.pk}/contestant_self_registration/"
        start = (self.now + datetime.timedelta(hours=3)).isoformat()
        payload = {
            "starting_point_time": start,
            "contest_team": contest_team.pk,
            "adaptive_start": False,
            "wind_speed": 0,
            "wind_direction": 0,
        }
        with patch("display.tasks.generate_and_maybe_notify_flight_order.apply_async"):
            self.assertEqual(400, client.post(url, payload, format="json").status_code, "the website must say")
            response = client.post(url, {**payload, "flight_mode": "simulator"}, format="json")
            self.assertEqual(201, response.status_code, response.content)
            self.assertEqual("simulator", response.json()["flight_mode"])
            self.assertTrue(response.json()["is_simulator_flight"])
            self.set_policy(SIMULATOR_NOT_ALLOWED)
            refused = client.post(url, {**payload, "flight_mode": "simulator"}, format="json")
            self.assertEqual(400, refused.status_code)

    def test_open_today_lists_only_tasks_that_accept_the_clients_flights(self):
        client = APIClient()
        listed = lambda **headers: [  # noqa: E731
            item["navigation_task_id"]
            for item in client.get("/api/v1/contests/open_registration_today/", **headers).json()
        ]
        self.assertEqual([self.task.pk], listed(), "the website shows it, with the policy")
        self.assertEqual([self.task.pk], listed(HTTP_X_APP_PLATFORM="android"))
        self.assertEqual([], listed(HTTP_X_APP_PLATFORM="msfs"))
        self.set_policy(SIMULATOR_ONLY)
        self.assertEqual([self.task.pk], listed(HTTP_X_APP_PLATFORM="msfs"))
        self.assertEqual([], listed(HTTP_X_APP_PLATFORM="ios"))

    def test_the_quickstart_needs_a_task_that_accepts_simulators(self):
        quickstart = SimulatorQuickstart(navigation_task=self.task, start_location="Kjeller")
        with self.assertRaises(DjangoValidationError):
            quickstart.full_clean()
        self.set_policy(SIMULATOR_ONLY)
        quickstart.full_clean()
        quickstart.save()
        self.assertEqual(quickstart, current_quickstart())
        self.set_policy(SIMULATOR_NOT_ALLOWED)
        self.assertIsNone(current_quickstart(), "its flights would be dropped")


class TestEmbedClientMarker(TestCase):
    def test_the_client_marker_is_remembered_with_the_embed_flag(self):
        client = APIClient()
        client.get("/?embed=app&client=msfs")
        self.assertEqual("msfs", client.cookies.get("embed_client").value)
        client.get("/?embed=off")
        self.assertEqual("", client.cookies.get("embed_client").value)

    def test_unknown_clients_are_ignored(self):
        client = APIClient()
        client.get("/?embed=app&client=somethingelse")
        self.assertNotIn("embed_client", client.cookies)


class TestReviewFixes(SimulatorSeparationTestCase):
    def test_a_real_flight_is_not_the_practice_flight(self):
        from display.services.simulator_quickstart import registered_flight

        self.set_policy(SIMULATOR_ALLOWED)
        quickstart = SimulatorQuickstart.objects.create(navigation_task=self.task, start_location="Kjeller")
        self.make_contestant(FLIGHT_MODE_REAL, 1)
        self.assertIsNone(registered_flight(quickstart, self.pilot))
        simulator = self.make_contestant(FLIGHT_MODE_SIMULATOR, 2)
        self.assertEqual(simulator, registered_flight(quickstart, self.pilot))

    def test_the_serializer_refuses_a_flight_mode_the_new_contestants_task_does_not_accept(self):
        from display.serialisers import ContestantSerialiser

        serialiser = ContestantSerialiser(context={"navigation_task": self.task})
        with self.assertRaises(ValidationError):
            serialiser.validate({"flight_mode": FLIGHT_MODE_SIMULATOR})
        serialiser.validate({"flight_mode": FLIGHT_MODE_REAL})

    def test_ignored_flymaster_positions_are_noted_once(self):
        self.set_policy(SIMULATOR_ONLY)
        contestant = self.make_contestant()
        first = self.now - datetime.timedelta(minutes=1)
        self.assertTrue(contestant.note_blocked_positions(first))
        self.assertFalse(contestant.note_blocked_positions(self.now))
        contestant.refresh_from_db()
        self.assertEqual(first, contestant.blocked_positions_at)
