import datetime
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from guardian.shortcuts import assign_perm

from display.default_scorecards.create_scorecards import create_scorecards
from display.flight_order_and_maps.map_constants import SCALE_200, SCALE_TO_FIT
from display.models import (
    Aeroplane,
    Contest,
    Contestant,
    ContestTeam,
    Crew,
    EditableRoute,
    FlightOrderConfiguration,
    NavigationTask,
    Person,
    Photo,
    PhotoObservation,
    Scorecard,
    Team,
)
from display.utilities.gate_definitions import LANDING_GATE, TAKEOFF_GATE
from utilities.mock_utilities import TraccarMock

START = datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.timezone.utc)
OBSERVATION_TIME = "2026-08-01T10:00:00Z"


class PhotoObservationApiTest(TestCase):
    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, *_args):
        create_scorecards()
        self.manager = get_user_model().objects.create(email="manager@example.com")
        self.pilot = get_user_model().objects.create(email="pilot@example.com")
        self.stranger = get_user_model().objects.create(email="stranger@example.com")
        Person.objects.create(first_name="Man", last_name="Ager", email=self.manager.email)
        pilot_person = Person.objects.create(first_name="Pi", last_name="Lot", email=self.pilot.email)
        scorecard = Scorecard.get_originals().get(shortcut_name="FAI Precision")
        with open("display/tests/NM.csv", "r") as file:
            editable_route, _ = EditableRoute.create_from_csv("Photo route", file.readlines()[1:])
            self.route = editable_route.create_precision_route(True, scorecard)
        self.contest = Contest.objects.create(
            name="Photo Contest",
            time_zone="Europe/Oslo",
            start_time=START,
            finish_time=START + datetime.timedelta(hours=8),
            location="60.0,11.0",
            created_by=self.manager,
        )
        assign_perm("view_contest", self.manager, self.contest)
        assign_perm("change_contest", self.manager, self.contest)
        self.navigation_task = NavigationTask.create(
            name="Photo Task",
            contest=self.contest,
            route=self.route,
            original_scorecard=scorecard,
            start_time=START,
            finish_time=START + datetime.timedelta(hours=8),
        )
        team = Team.objects.create(
            crew=Crew.objects.create(member1=pilot_person),
            aeroplane=Aeroplane.objects.create(registration="LN-PHOTO"),
        )
        contest_team = ContestTeam.objects.create(contest=self.contest, team=team, air_speed=70)
        self.contestant = Contestant.objects.create(
            team=team,
            navigation_task=self.navigation_task,
            contestant_number=1,
            takeoff_time=START + datetime.timedelta(hours=1),
            tracker_start_time=START + datetime.timedelta(minutes=50),
            finished_by_time=START + datetime.timedelta(hours=3),
            minutes_to_starting_point=5,
            air_speed=70,
            wind_speed=0,
            wind_direction=0,
            tracking_service=contest_team.tracking_service,
            tracking_device=contest_team.tracking_device or "",
            tracker_device_id=contest_team.tracker_device_id or "",
        )
        waypoints = [wp for wp in self.route.waypoints if wp.type not in (TAKEOFF_GATE, LANDING_GATE)]
        self.leg_start, self.leg_end = waypoints[0], waypoints[1]
        # The photo target sits halfway along the first leg
        self.photo_lat = (self.leg_start.latitude + self.leg_end.latitude) / 2
        self.photo_lon = (self.leg_start.longitude + self.leg_end.longitude) / 2
        self.photo = Photo.objects.create(name="A", route=self.route, latitude=self.photo_lat, longitude=self.photo_lon)
        self.url = reverse("all-contestants-photo-observations", kwargs={"pk": self.contestant.pk})

    def set_scale(self, scale):
        FlightOrderConfiguration.objects.update_or_create(
            navigation_task=self.navigation_task, defaults={"map_scale": scale}
        )

    def post(self, user, lat=None, lon=None, time=OBSERVATION_TIME, name="A"):
        self.client.force_login(user)
        return self.client.post(
            self.url,
            {
                "photo_name": name,
                "time": time,
                "latitude": self.photo_lat if lat is None else lat,
                "longitude": self.photo_lon if lon is None else lon,
            },
            content_type="application/json",
        )

    def test_crew_member_registers_a_scored_observation(self):
        self.set_scale(SCALE_200)
        response = self.post(self.pilot)
        self.assertEqual(response.status_code, 201, response.content)
        self.assertTrue(response.json()["scored"])
        self.assertEqual(response.json()["score_fraction"], 1.0)
        self.assertEqual(response.json()["metres_per_mm"], 200.0)
        self.assertEqual(PhotoObservation.objects.count(), 1)

    def test_contest_manager_can_register(self):
        self.set_scale(SCALE_200)
        self.assertEqual(self.post(self.manager).status_code, 201)

    def test_stranger_cannot_register(self):
        self.assertEqual(self.post(self.stranger).status_code, 403)
        self.assertEqual(PhotoObservation.objects.count(), 0)

    def test_unknown_photo_is_rejected(self):
        self.assertEqual(self.post(self.pilot, name="NOPE").status_code, 400)

    def test_tolerance_follows_the_map_scale(self):
        # Move the observation about 400 m along the first leg
        bearing_scale = 400 / self._leg_length_m()
        lat = self.photo_lat + (self.leg_end.latitude - self.leg_start.latitude) * bearing_scale
        lon = self.photo_lon + (self.leg_end.longitude - self.leg_start.longitude) * bearing_scale
        self.set_scale(SCALE_200)  # 1 mm = 200 m -> 2 mm off
        self.assertEqual(self.post(self.pilot, lat, lon).json()["score_fraction"], 0.0)
        PhotoObservation.objects.all().delete()
        self.set_scale(500)  # 1 mm = 500 m -> 0.8 mm off
        response = self.post(self.pilot, lat, lon)
        self.assertEqual(response.json()["score_fraction"], 1.0)
        self.assertAlmostEqual(response.json()["error_mm"], 0.8, delta=0.05)

    def test_fit_page_scale_is_estimated_from_the_route(self):
        self.set_scale(SCALE_TO_FIT)
        response = self.post(self.pilot)
        self.assertTrue(response.json()["scored"])
        self.assertGreater(response.json()["metres_per_mm"], 0)

    def test_later_registration_replaces_and_earlier_is_ignored(self):
        self.set_scale(SCALE_200)
        self.post(self.pilot, time="2026-08-01T10:00:00Z")
        later = self.post(self.pilot, time="2026-08-01T10:05:00Z")
        self.assertEqual(later.status_code, 201)
        replay = self.post(self.pilot, time="2026-08-01T09:59:00Z")
        self.assertEqual(replay.status_code, 200)
        observation = PhotoObservation.objects.get()
        self.assertEqual(observation.time, datetime.datetime(2026, 8, 1, 10, 5, tzinfo=datetime.timezone.utc))

    def test_manager_lists_and_deletes(self):
        self.set_scale(SCALE_200)
        self.post(self.pilot)
        self.client.force_login(self.manager)
        listing = self.client.get(self.url)
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(len(listing.json()), 1)
        delete_url = reverse(
            "all-contestants-delete-photo-observation",
            kwargs={"pk": self.contestant.pk, "observation_id": listing.json()[0]["id"]},
        )
        self.assertEqual(self.client.delete(delete_url).status_code, 204)
        self.assertEqual(PhotoObservation.objects.count(), 0)

    def _leg_length_m(self):
        import math

        d_lat = (self.leg_end.latitude - self.leg_start.latitude) * 111195
        d_lon = (self.leg_end.longitude - self.leg_start.longitude) * 111195 * math.cos(math.radians(self.photo_lat))
        return math.hypot(d_lat, d_lon)
