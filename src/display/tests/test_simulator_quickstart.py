import datetime
from unittest.mock import PropertyMock, patch

from django.test import TestCase
from guardian.shortcuts import assign_perm
from rest_framework.test import APIClient

from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
from display.models import (
    Aeroplane,
    Contest,
    Contestant,
    ContestTeam,
    Crew,
    EmailMapLink,
    NavigationTask,
    Person,
    Route,
    SimulatorQuickstart,
    Team,
)
from display.models.my_user import MyUser
from display.services.simulator_quickstart import (
    AIR_START_DISTANCE_M,
    air_start,
    current_quickstart,
    ground_start,
    register,
    registered_flight,
)
from display.utilities.coordinate_utilities import calculate_bearing, calculate_distance_lat_lon
from display.utilities.tracking_definitions import TRACKING_PILOT
from display.waypoint import Waypoint
from utilities.mock_utilities import TraccarMock


def waypoint(name, latitude, longitude, gate_line=None, bearing_next=-1):
    w = Waypoint(name)
    w.latitude = latitude
    w.longitude = longitude
    w.gate_line = gate_line or []
    w.bearing_next = bearing_next
    return w


class TestSimulatorQuickstart(TestCase):
    def setUp(self):
        for target in ("display.models.contestant.get_traccar_instance", "display.signals.get_traccar_instance"):
            patcher = patch(target, return_value=TraccarMock)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.now = datetime.datetime.now(datetime.timezone.utc)
        self.contest = Contest.objects.create(
            name="MSFS practice",
            start_time=self.now,
            finish_time=self.now + datetime.timedelta(days=30),
            is_public=True,
        )
        # A runway running east-west at the take-off gate (the gate line runs north-south across it); the route goes east.
        route = Route.objects.create(
            name="Practice route",
            takeoff_gates=[waypoint("TO", 59.97, 11.03, gate_line=[[59.971, 11.03], [59.969, 11.03]])],
            waypoints=[waypoint("SP", 59.97, 11.20, bearing_next=90.0), waypoint("TP1", 59.97, 11.40)],
        )
        self.task = NavigationTask.create(
            name="Practice",
            original_scorecard=get_default_scorecard(),
            start_time=self.now - datetime.timedelta(days=1),
            finish_time=self.now + datetime.timedelta(days=30),
            route=route,
            contest=self.contest,
            is_public=True,
            allow_self_management=True,
        )
        self.quickstart = SimulatorQuickstart.objects.create(
            navigation_task=self.task, start_location="Kjeller (ENKJ), runway 30", air_start_altitude_ft=2000
        )
        self.pilot = Person.objects.create(first_name="Pi", last_name="Lot", email="pilot@example.com")
        self.user = MyUser.objects.create(username="pilot", email="pilot@example.com")
        self.client = APIClient()

    def test_the_newest_active_quickstart_of_a_self_managed_open_task_is_offered(self):
        self.assertEqual(self.quickstart, current_quickstart())
        newer = SimulatorQuickstart.objects.create(navigation_task=self.task, start_location="Elsewhere", active=False)
        self.assertEqual(self.quickstart, current_quickstart(), "an inactive one is not offered")
        newer.active = True
        newer.save()
        self.assertEqual(newer, current_quickstart())
        self.task.allow_self_management = False
        self.task.save()
        self.assertIsNone(current_quickstart(), "pilots could not register for it themselves")

    def test_a_finished_task_is_not_offered(self):
        self.assertIsNone(current_quickstart(self.now + datetime.timedelta(days=31)))

    def test_the_ground_start_faces_along_the_runway_towards_the_route(self):
        start = ground_start(self.quickstart)
        self.assertEqual((59.97, 11.03), (start["latitude"], start["longitude"]))
        self.assertAlmostEqual(90.0, start["heading"], delta=1.0)

    def test_the_air_start_is_two_miles_before_the_starting_point_on_course(self):
        start = air_start(self.quickstart)
        self.assertEqual(2000, start["altitude_ft"])
        self.assertAlmostEqual(90.0, start["heading"], delta=0.1)
        distance = calculate_distance_lat_lon((start["latitude"], start["longitude"]), (59.97, 11.20))
        self.assertAlmostEqual(AIR_START_DISTANCE_M, distance, delta=50)
        self.assertAlmostEqual(
            90.0, calculate_bearing((start["latitude"], start["longitude"]), (59.97, 11.20)), delta=1.0
        )

    def test_the_client_gets_the_flight_where_to_start_and_how_to_register(self):
        self.client.force_authenticate(self.user)
        response = self.client.get("/api/v1/userprofile/msfs_quickstart/")
        self.assertEqual(200, response.status_code)
        data = response.json()
        self.assertEqual("Practice", data["title"])
        self.assertEqual("MSFS practice", data["contest_name"])
        self.assertEqual("Kjeller (ENKJ), runway 30", data["start_location"])
        self.assertEqual(
            f"/schedule-flight?contestId={self.contest.pk}&navigationTaskId={self.task.pk}", data["registration_path"]
        )
        self.assertIsNone(data["registered_flight"])
        self.assertIsNotNone(data["ground_start"])
        self.assertIsNotNone(data["air_start"])

    def test_the_pilots_own_registration_is_reported(self):
        team = Team.objects.create(
            crew=Crew.objects.create(member1=self.pilot), aeroplane=Aeroplane.objects.create(registration="LN-SIM")
        )
        flight = Contestant.objects.create(
            team=team,
            navigation_task=self.task,
            tracking_device=TRACKING_PILOT,
            contestant_number=1,
            tracker_start_time=self.now,
            takeoff_time=self.now + datetime.timedelta(minutes=10),
            finished_by_time=self.now + datetime.timedelta(hours=2),
        )
        self.client.force_authenticate(self.user)
        data = self.client.get("/api/v1/userprofile/msfs_quickstart/").json()
        self.assertEqual(flight.pk, data["registered_flight"]["id"])

    def test_nothing_offered_is_a_404_and_signing_in_is_required(self):
        self.assertIn(self.client.get("/api/v1/userprofile/msfs_quickstart/").status_code, (401, 403))
        self.quickstart.active = False
        self.quickstart.save()
        self.client.force_authenticate(self.user)
        self.assertEqual(404, self.client.get("/api/v1/userprofile/msfs_quickstart/").status_code)

    def register(self):
        self.client.force_authenticate(self.user)
        with patch("display.tasks.generate_and_maybe_notify_flight_order.apply_async") as flight_order:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post("/api/v1/userprofile/msfs_quickstart_register/")
        return response, flight_order

    def test_one_press_registration_signs_up_with_the_practice_defaults(self):
        response, flight_order = self.register()
        self.assertEqual(201, response.status_code, response.content)
        data = response.json()
        flight = Contestant.objects.get(pk=data["registered_flight"]["id"])
        self.assertTrue(flight.adaptive_start)
        self.assertEqual(70, flight.air_speed)
        self.assertEqual((0, 0), (flight.wind_speed, flight.wind_direction))
        self.assertEqual("MSFS", flight.team.aeroplane.registration)
        self.assertEqual("MSFS pilots", flight.team.club.name)
        self.assertEqual(self.pilot, flight.team.crew.member1)
        self.assertTrue(ContestTeam.objects.filter(contest=self.contest, team=flight.team, air_speed=70).exists())
        # Adaptive: tracking is open now, and the starting line may be crossed for two hours.
        self.assertLessEqual(flight.tracker_start_time, datetime.datetime.now(datetime.timezone.utc), "open at once")
        self.assertGreater(flight.finished_by_time, self.now + datetime.timedelta(hours=2))
        self.assertIsNone(data["registered_flight"]["flight_order_path"], "the flight order is made in the background")
        flight_order.assert_called_once()
        self.assertEqual(flight.pk, flight_order.call_args[0][0][0])

    def test_registering_again_returns_the_same_flight(self):
        first, _ = self.register()
        second, flight_order = self.register()
        self.assertEqual(first.json()["registered_flight"]["id"], second.json()["registered_flight"]["id"])
        self.assertEqual(1, Contestant.objects.filter(navigation_task=self.task).count())
        flight_order.assert_not_called()

    def test_a_pilot_already_signed_up_keeps_their_own_team_and_speed(self):
        team = Team.objects.create(
            crew=Crew.objects.create(member1=self.pilot), aeroplane=Aeroplane.objects.create(registration="LN-OWN")
        )
        ContestTeam.objects.create(contest=self.contest, team=team, air_speed=95)
        response, _ = self.register()
        self.assertEqual(201, response.status_code, response.content)
        flight = Contestant.objects.get(pk=response.json()["registered_flight"]["id"])
        self.assertEqual(team, flight.team)
        self.assertEqual(95, flight.air_speed)

    def test_the_flight_order_path_appears_once_it_is_made(self):
        response, _ = self.register()
        flight = Contestant.objects.get(pk=response.json()["registered_flight"]["id"])
        link = EmailMapLink.objects.create(contestant=flight, orders=b"pdf")
        data = self.client.get("/api/v1/userprofile/msfs_quickstart/").json()
        self.assertEqual(f"/display/maplink/{link.pk}/", data["registered_flight"]["flight_order_path"])
        self.assertEqual(70, data["air_speed"])
        self.assertEqual("MSFS", data["aircraft_registration"])

    def test_registering_without_an_offer_is_refused(self):
        self.quickstart.active = False
        self.quickstart.save()
        response, flight_order = self.register()
        self.assertEqual(400, response.status_code)
        flight_order.assert_not_called()

    def make_private(self):
        Contest.objects.filter(pk=self.contest.pk).update(is_public=False)
        NavigationTask.objects.filter(pk=self.task.pk).update(is_public=False)

    def test_a_private_practice_flight_is_only_offered_to_those_who_may_view_the_contest(self):
        self.make_private()
        self.client.force_authenticate(self.user)
        self.assertEqual(404, self.client.get("/api/v1/userprofile/msfs_quickstart/").status_code)
        response, flight_order = self.register()
        self.assertEqual(400, response.status_code)
        flight_order.assert_not_called()
        self.assertFalse(ContestTeam.objects.filter(contest=self.contest).exists(), "no registration was made")

        assign_perm("view_contest", self.user, Contest.objects.get(pk=self.contest.pk))
        self.client.force_authenticate(MyUser.objects.get(pk=self.user.pk))  # no cached permissions
        self.assertEqual(200, self.client.get("/api/v1/userprofile/msfs_quickstart/").status_code)
        response, _ = self.register()
        self.assertEqual(201, response.status_code)

    def test_the_newest_one_the_user_may_register_in_is_offered(self):
        private_contest = Contest.objects.create(
            name="Private", start_time=self.now, finish_time=self.now + datetime.timedelta(days=30), is_public=False
        )
        private_task = NavigationTask.create(
            name="Private practice",
            original_scorecard=get_default_scorecard(),
            start_time=self.now - datetime.timedelta(days=1),
            finish_time=self.now + datetime.timedelta(days=30),
            route=Route.objects.create(
                name="Private route", waypoints=[waypoint("SP", 59.97, 11.20), waypoint("TP1", 59.97, 11.40)]
            ),
            contest=private_contest,
            is_public=False,
            allow_self_management=True,
        )
        newer = SimulatorQuickstart.objects.create(navigation_task=private_task, start_location="Elsewhere")
        self.assertEqual(self.quickstart, current_quickstart(user=self.user), "the newest one this user may use")
        assign_perm("view_contest", self.user, private_contest)
        self.assertEqual(newer, current_quickstart(user=MyUser.objects.get(pk=self.user.pk)))

    def test_a_new_pilot_without_a_profile_can_register_straight_away(self):
        Person.objects.all().delete()
        self.assertFalse(Person.objects.filter(email="pilot@example.com").exists())
        response, _ = self.register()
        self.assertEqual(201, response.status_code, response.content)
        self.assertEqual(1, Contestant.objects.filter(navigation_task=self.task).count())

    def test_a_double_press_makes_one_flight(self):
        calls = []

        def stale_first_check(quickstart, person, now=None):
            # The first request looked before the other had finished: it saw nothing
            calls.append(1)
            return None if len(calls) == 1 else registered_flight(quickstart, person, now)

        first = register(self.user, self.pilot)
        with patch("display.services.simulator_quickstart.registered_flight", side_effect=stale_first_check):
            second = register(self.user, self.pilot)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(1, Contestant.objects.filter(navigation_task=self.task).count())

    def test_a_route_without_a_flight_duration_still_registers(self):
        with patch.object(Contestant, "flight_duration", new_callable=PropertyMock, return_value=None):
            response, _ = self.register()
        self.assertEqual(201, response.status_code, response.content)
