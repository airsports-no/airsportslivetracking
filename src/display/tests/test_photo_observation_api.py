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
from display.calculators.cima_score_normalization import get_cima_gate_qmax
from display.services.photo_observations import (
    finalize_photo_observations,
    get_currently_tracked_contestants,
    get_scoring_mode,
)
from display.utilities.cima_task_type_definitions import KNOWN_CIRCUIT
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
        # Observation registration is switched on for the task, and the flight is under way (10:10)
        NavigationTask.objects.filter(pk=self.navigation_task.pk).update(allow_observation_registration=True)
        self.navigation_task.refresh_from_db()
        self.contestant.refresh_from_db()
        self.set_now(START + datetime.timedelta(minutes=70))

    def set_now(self, now):
        patcher = patch("display.services.photo_observations._now", return_value=now)
        patcher.start()
        self.addCleanup(patcher.stop)

    def set_scale(self, scale):
        FlightOrderConfiguration.objects.update_or_create(
            navigation_task=self.navigation_task, defaults={"map_scale": scale}
        )

    def post(self, user, lat=None, lon=None, time=OBSERVATION_TIME, photo=None):
        self.client.force_login(user)
        return self.client.post(
            self.url,
            {
                "photo": self.photo.pk if photo is None else photo,
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

    def test_registration_must_be_enabled_for_the_task(self):
        NavigationTask.objects.filter(pk=self.navigation_task.pk).update(allow_observation_registration=False)
        response = self.post(self.pilot)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(PhotoObservation.objects.count(), 0)

    def test_manager_can_register_when_the_app_registration_is_off_but_it_is_not_scored(self):
        NavigationTask.objects.filter(pk=self.navigation_task.pk).update(allow_observation_registration=False)
        self.set_scale(SCALE_200)
        response = self.post(self.manager)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["points"], 0.0)

    def test_crew_can_only_register_for_a_flight_they_are_currently_tracking(self):
        self.set_now(START + datetime.timedelta(minutes=30))  # before the tracker start time
        self.assertEqual(self.post(self.pilot).status_code, 409)
        self.set_now(START + datetime.timedelta(hours=4))  # after the finished-by time
        self.assertEqual(self.post(self.pilot).status_code, 409)
        self.assertEqual(PhotoObservation.objects.count(), 0)

    def test_finished_calculator_is_no_longer_tracked(self):
        self.contestant.contestanttrack.set_calculator_finished()
        self.assertEqual(self.post(self.pilot).status_code, 409)

    def test_currently_tracked_contestants_are_the_users_active_flights(self):
        self.assertEqual([c.pk for c in get_currently_tracked_contestants(self.pilot)], [self.contestant.pk])
        self.assertEqual(get_currently_tracked_contestants(self.stranger), [])
        self.assertEqual(get_currently_tracked_contestants(self.manager), [])

    def test_observation_time_must_be_within_the_flight(self):
        self.assertEqual(self.post(self.pilot, time="2026-08-01T08:00:00Z").status_code, 400)
        self.assertEqual(self.post(self.pilot, time="2026-08-01T13:00:00Z").status_code, 400)
        self.assertEqual(PhotoObservation.objects.count(), 0)

    def test_stranger_cannot_register(self):
        self.assertEqual(self.post(self.stranger).status_code, 403)
        self.assertEqual(PhotoObservation.objects.count(), 0)

    def test_unknown_photo_is_rejected(self):
        self.assertEqual(self.post(self.pilot, photo=999999).status_code, 400)

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

    def test_fit_page_and_missing_configuration_default_to_1_250_000(self):
        self.set_scale(SCALE_TO_FIT)
        self.assertEqual(self.post(self.pilot).json()["metres_per_mm"], 250.0)
        PhotoObservation.objects.all().delete()
        FlightOrderConfiguration.objects.all().delete()
        self.assertEqual(self.post(self.pilot).json()["metres_per_mm"], 250.0)

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


class PhotoObservationScoringTest(PhotoObservationApiTest):
    def along_leg(self, metres):
        fraction = metres / self._leg_length_m()
        return (
            self.photo_lat + (self.leg_end.latitude - self.leg_start.latitude) * fraction,
            self.photo_lon + (self.leg_end.longitude - self.leg_start.longitude) * fraction,
        )

    def score(self):
        self.contestant.contestanttrack.refresh_from_db()
        return self.contestant.contestanttrack.score

    def test_legacy_task_penalises_a_missed_observation(self):
        self.set_scale(SCALE_200)
        self.assertEqual(get_scoring_mode(self.contestant), "legacy")
        response = self.post(self.pilot, *self.along_leg(400))  # 2 mm off, beyond the 1 mm tolerance
        self.assertEqual(response.json()["points"], 100.0)
        self.assertEqual(self.score(), 100.0)

    def test_legacy_task_does_not_penalise_a_hit(self):
        self.set_scale(SCALE_200)
        self.post(self.pilot, *self.along_leg(100))
        self.assertEqual(self.score(), 0.0)

    def test_penalty_follows_the_scorecard(self):
        self.set_scale(SCALE_200)
        scorecard = self.navigation_task.scorecard
        scorecard.observation_photo_penalty = 40
        scorecard.save()
        self.post(self.pilot, *self.along_leg(400))
        self.assertEqual(self.score(), 40.0)

    def test_correcting_a_miss_removes_the_penalty(self):
        self.set_scale(SCALE_200)
        self.post(self.pilot, *self.along_leg(400), time="2026-08-01T10:00:00Z")
        self.post(self.pilot, *self.along_leg(0), time="2026-08-01T10:01:00Z")
        self.assertEqual(self.score(), 0.0)
        self.assertEqual(PhotoObservation.objects.get().points, 0.0)

    def test_unmarked_photos_are_not_misses_when_the_task_does_not_use_app_registration(self):
        NavigationTask.objects.filter(pk=self.navigation_task.pk).update(allow_observation_registration=False)
        self.contestant.refresh_from_db()
        self.assertEqual(finalize_photo_observations(self.contestant), 0)
        self.assertEqual(self.score(), 0.0)

    def test_unmarked_photo_is_a_miss_when_the_flight_ends(self):
        self.assertEqual(finalize_photo_observations(self.contestant), 1)
        self.assertEqual(self.score(), 100.0)
        self.assertEqual(finalize_photo_observations(self.contestant), 0)
        self.assertEqual(self.score(), 100.0)

    def test_deleting_a_registration_removes_its_score(self):
        self.set_scale(SCALE_200)
        self.post(self.pilot, *self.along_leg(400))
        self.client.force_login(self.manager)
        observation = PhotoObservation.objects.get()
        delete_url = reverse(
            "all-contestants-delete-photo-observation",
            kwargs={"pk": self.contestant.pk, "observation_id": observation.pk},
        )
        self.client.delete(delete_url)
        self.assertEqual(self.score(), 0.0)

    def make_cima(self):
        self.navigation_task.task_subtype = KNOWN_CIRCUIT
        self.navigation_task.save()
        scorecard = self.navigation_task.scorecard
        scorecard.score_sorting_direction = "desc"
        scorecard.initial_score = 1000
        scorecard.save()
        self.navigation_task.refresh_from_db()
        self.contestant.refresh_from_db()
        self.set_scale(SCALE_200)

    def test_cima_scores_by_the_millimetre_bands(self):
        self.make_cima()
        qmax = get_cima_gate_qmax(self.contestant)
        self.assertGreaterEqual(qmax, 100)  # includes Vh for the photo
        baseline = self.score()
        full = self.post(self.pilot, *self.along_leg(300))  # 1.5 mm
        self.assertEqual((full.json()["score_fraction"], full.json()["points"]), (1.0, 0.0))
        half = self.post(self.pilot, *self.along_leg(600), time="2026-08-01T10:01:00Z")  # 3 mm
        self.assertEqual(half.json()["score_fraction"], 0.5)
        self.assertAlmostEqual(half.json()["points"], -1000 * 50 / qmax)
        zero = self.post(self.pilot, *self.along_leg(1200), time="2026-08-01T10:02:00Z")  # 6 mm
        self.assertEqual(zero.json()["score_fraction"], 0.0)
        self.assertAlmostEqual(zero.json()["points"], -1000 * 100 / qmax)
        self.assertAlmostEqual(self.score() - baseline, -1000 * 100 / qmax)

    def test_cima_value_per_observation_follows_the_scorecard(self):
        self.make_cima()
        scorecard = self.navigation_task.scorecard
        scorecard.observation_photo_value = 200
        scorecard.save()
        self.navigation_task.refresh_from_db()
        self.contestant.refresh_from_db()
        qmax = get_cima_gate_qmax(self.contestant)
        zero = self.post(self.pilot, *self.along_leg(1200))
        self.assertAlmostEqual(zero.json()["points"], -1000 * 200 / qmax)

    def test_tolerances_are_configurable_on_the_scorecard(self):
        self.set_scale(SCALE_200)
        scorecard = self.navigation_task.scorecard
        scorecard.observation_photo_full_tolerance_mm = 3
        scorecard.save()
        self.navigation_task.refresh_from_db()
        self.contestant.refresh_from_db()
        # 2 mm off: a miss with the legacy default of 1 mm, a hit with 3 mm
        response = self.post(self.pilot, *self.along_leg(400))
        self.assertEqual(response.json()["score_fraction"], 1.0)
        self.assertEqual(self.score(), 0.0)

    def test_cima_half_band_is_configurable(self):
        self.make_cima()
        scorecard = self.navigation_task.scorecard
        scorecard.observation_photo_full_tolerance_mm = 1
        scorecard.observation_photo_half_tolerance_mm = 2
        scorecard.save()
        self.navigation_task.refresh_from_db()
        self.contestant.refresh_from_db()
        self.assertEqual(self.post(self.pilot, *self.along_leg(300)).json()["score_fraction"], 0.5)  # 1.5 mm
        self.assertEqual(
            self.post(self.pilot, *self.along_leg(600), time="2026-08-01T10:01:00Z").json()["score_fraction"], 0.0
        )  # 3 mm, would have been half by default
