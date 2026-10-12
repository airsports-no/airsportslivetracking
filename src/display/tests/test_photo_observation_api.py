import datetime
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
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
    ScoreLogEntry,
    Team,
)
from display.calculators.cima_score_normalization import get_cima_gate_qmax
from display.services.photo_observations import (
    finalize_photo_observations,
    judging_is_hidden,
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
        # The observation photos are the route's observation_photo features; the Photo table also holds photos of the
        # route's waypoints (for the flight order), which are not observations
        self.navigation_task.editable_route = EditableRoute.objects.create(
            name="Observation features",
            route={
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"id": "obs-a", "name": "A", "featureType": "observation_photo"},
                        "geometry": {"type": "Point", "coordinates": [self.photo_lon, self.photo_lat]},
                    }
                ],
            },
        )
        self.navigation_task.save(update_fields=["editable_route"])
        self.waypoint_photo = Photo.objects.create(
            name="TP 1", route=self.route, latitude=self.leg_end.latitude, longitude=self.leg_end.longitude
        )
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
        response = self.post(self.manager)
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
        self.set_now(START + datetime.timedelta(hours=3, minutes=6))  # after the finished-by time and the five minutes of grace
        self.assertEqual(self.post(self.pilot).status_code, 409)
        self.assertEqual(PhotoObservation.objects.count(), 0)

    def test_queued_observations_are_accepted_during_the_grace_period_after_the_flight(self):
        self.set_scale(SCALE_200)
        self.set_now(START + datetime.timedelta(hours=3, minutes=4))  # finished by 12:00, five minutes of grace
        self.contestant.contestanttrack.set_calculator_finished()
        self.assertEqual(self.post(self.pilot).status_code, 201)
        self.set_now(START + datetime.timedelta(hours=3, minutes=6))
        self.assertEqual(self.post(self.pilot, time="2026-08-01T10:01:00Z").status_code, 409)

    @override_settings(OBSERVATION_REGISTRATION_GRACE_MINUTES=720)
    def test_the_grace_period_can_never_be_longer_than_five_minutes(self):
        self.set_now(START + datetime.timedelta(hours=3, minutes=6))
        self.assertEqual(self.post(self.pilot).status_code, 409)

    @override_settings(OBSERVATION_REGISTRATION_GRACE_MINUTES=0)
    def test_grace_period_can_be_made_shorter(self):
        self.set_now(START + datetime.timedelta(hours=3, minutes=1))
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

    def photos_url(self):
        return reverse("all-contestants-observation-photos", kwargs={"pk": self.contestant.pk})

    def make_private(self):
        Contest.objects.filter(pk=self.contest.pk).update(is_public=False)
        NavigationTask.objects.filter(pk=self.navigation_task.pk).update(is_public=False)

    def test_crew_lists_the_observation_photos_without_their_coordinates(self):
        self.client.force_login(self.pilot)
        response = self.client.get(self.photos_url())
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertTrue(data["enabled"])
        self.assertTrue(data["may_register"])
        self.assertEqual([p["name"] for p in data["photos"]], ["A"])
        self.assertEqual(data["photos"][0]["id"], self.photo.pk)
        self.assertEqual(set(data["photos"][0]), {"id", "name", "file"}, "the coordinates are the answer")
        self.assertEqual(data["observations"], [])

    def test_a_private_task_still_works_for_its_crew(self):
        """The task photos endpoint needs permissions on a private contest; the crew endpoint and registration must not."""
        self.make_private()
        self.set_scale(SCALE_200)
        self.client.force_login(self.pilot)
        task_photos = self.client.get(
            f"/api/v1/contests/{self.contest.pk}/navigationtasks/{self.navigation_task.pk}/photos/?contestant={self.contestant.pk}"
        )
        self.assertIn(task_photos.status_code, (401, 403, 404), "documents why the app needs its own endpoint")
        self.assertEqual(self.client.get(self.photos_url()).status_code, 200)
        self.assertEqual(self.post(self.pilot).status_code, 201)
        listed = self.client.get(self.photos_url()).json()
        self.assertEqual([o["photo"] for o in listed["observations"]], [self.photo.pk])
        self.assertEqual(
            set(listed["observations"][0]), {"id", "photo", "photo_name", "time"}, "no score or error for the crew"
        )

    def test_others_cannot_list_the_photos_of_a_flight(self):
        self.client.force_login(self.stranger)
        self.assertEqual(self.client.get(self.photos_url()).status_code, 403)
        self.client.logout()
        self.assertIn(self.client.get(self.photos_url()).status_code, (401, 403))

    def test_photos_are_hidden_and_registration_not_possible_when_the_task_does_not_use_the_app(self):
        NavigationTask.objects.filter(pk=self.navigation_task.pk).update(allow_observation_registration=False)
        self.client.force_login(self.pilot)
        data = self.client.get(self.photos_url()).json()
        self.assertEqual((data["enabled"], data["may_register"], data["photos"]), (False, False, []))

    def test_may_register_follows_the_tracking_window_and_grace_period(self):
        self.client.force_login(self.pilot)
        self.set_now(START + datetime.timedelta(minutes=30))
        self.assertFalse(self.client.get(self.photos_url()).json()["may_register"])
        self.set_now(START + datetime.timedelta(hours=3, minutes=4))  # after landing, inside the grace period
        data = self.client.get(self.photos_url()).json()
        self.assertTrue(data["may_register"])
        self.assertEqual(data["registration_grace_minutes"], 5)
        self.assertEqual(data["registration_closes_at"], "2026-08-01T12:05:00Z")  # finished by 12:00 plus five minutes
        self.set_now(START + datetime.timedelta(hours=3, minutes=6))
        self.assertFalse(self.client.get(self.photos_url()).json()["may_register"])

    def delete_url(self, observation_id):
        return reverse(
            "all-contestants-delete-photo-observation",
            kwargs={"pk": self.contestant.pk, "observation_id": observation_id},
        )

    def add_reports(self):
        """One position report per 10 s along the first leg, from 10:00:00."""
        from display.models import ContestantReceivedPosition

        for i in range(0, 7):
            fraction = i / 6
            ContestantReceivedPosition.objects.create(
                contestant=self.contestant,
                time=datetime.datetime(2026, 8, 1, 10, 0, 0, tzinfo=datetime.timezone.utc)
                + datetime.timedelta(seconds=i * 10),
                latitude=self.leg_start.latitude + (self.leg_end.latitude - self.leg_start.latitude) * fraction,
                longitude=self.leg_start.longitude + (self.leg_end.longitude - self.leg_start.longitude) * fraction,
            )

    def test_marks_can_be_changed_and_cancelled_until_five_minutes_after_the_tracking_window(self):
        self.set_scale(SCALE_200)
        self.set_now(START + datetime.timedelta(hours=2))
        self.assertEqual(self.post(self.pilot, time="2026-08-01T10:20:00Z").status_code, 201)
        observation = PhotoObservation.objects.get()
        self.set_now(START + datetime.timedelta(hours=3, minutes=1))  # the tracking window is over, the grace period is not
        self.client.force_login(self.pilot)
        replaced = self.client.post(
            self.url,
            {
                "photo": self.photo.pk, "time": "2026-08-01T10:30:00Z", "replace": True,
                "latitude": self.photo_lat, "longitude": self.photo_lon,
            },
            content_type="application/json",
        )
        self.assertEqual(replaced.status_code, 201)
        self.assertEqual(PhotoObservation.objects.get().time.minute, 30)
        self.assertEqual(self.client.delete(self.delete_url(observation.pk)).status_code, 204)
        self.assertEqual(self.post(self.pilot, time="2026-08-01T10:26:00Z").status_code, 201)
        # Five minutes after the window nothing can be changed any more.
        self.set_now(START + datetime.timedelta(hours=3, minutes=6))
        self.assertEqual(self.post(self.pilot, time="2026-08-01T10:27:00Z").status_code, 409)
        self.assertEqual(self.client.delete(self.delete_url(PhotoObservation.objects.get().pk)).status_code, 409)
        self.assertEqual(PhotoObservation.objects.get().time.minute, 26)

    def test_an_unmarked_photo_can_still_be_marked_after_tracking_stops(self):
        self.set_scale(SCALE_200)
        self.set_now(START + datetime.timedelta(hours=2))
        self.contestant.contestanttrack.set_calculator_finished()  # the queue is sent once there is wifi
        self.assertEqual(self.post(self.pilot, time="2026-08-01T10:20:00Z").status_code, 201)

    def test_marks_can_still_be_changed_after_tracking_stops_until_the_deadline(self):
        self.set_scale(SCALE_200)
        self.post(self.pilot, time="2026-08-01T10:00:00Z")
        self.contestant.contestanttrack.set_calculator_finished()
        self.assertEqual(self.post(self.pilot, time="2026-08-01T10:05:00Z").status_code, 201)

    def test_managers_can_change_marks_after_the_flight(self):
        self.set_scale(SCALE_200)
        self.post(self.pilot, time="2026-08-01T10:00:00Z")
        self.contestant.contestanttrack.set_calculator_finished()
        self.assertEqual(self.post(self.manager, time="2026-08-01T10:05:00Z").status_code, 201)

    def test_crew_sees_the_judging_once_the_registration_has_closed(self):
        self.assertTrue(judging_is_hidden(self.contestant))
        self.contestant.contestanttrack.set_calculator_finished()
        self.assertTrue(judging_is_hidden(self.contestant), "still within the five minutes: a mark can still be corrected")
        self.set_now(START + datetime.timedelta(hours=3, minutes=6))
        self.assertFalse(judging_is_hidden(self.contestant))

    def test_crew_cancels_an_observation_and_marks_again(self):
        self.set_scale(SCALE_200)
        self.assertEqual(self.post(self.pilot).status_code, 201)
        observation = PhotoObservation.objects.get()
        self.client.force_login(self.pilot)
        self.assertEqual(self.client.delete(self.delete_url(observation.pk)).status_code, 204)
        self.assertEqual(PhotoObservation.objects.count(), 0)
        self.assertEqual(self.post(self.pilot).status_code, 201)

    def test_crew_cannot_cancel_when_not_tracking_or_for_others(self):
        self.assertEqual(self.post(self.manager).status_code, 201)
        observation = PhotoObservation.objects.get()
        self.client.force_login(self.stranger)
        self.assertEqual(self.client.delete(self.delete_url(observation.pk)).status_code, 403)
        self.client.force_login(self.pilot)
        self.set_now(START + datetime.timedelta(hours=3, minutes=6))  # past the grace period
        self.assertEqual(self.client.delete(self.delete_url(observation.pk)).status_code, 409)
        self.assertEqual(PhotoObservation.objects.count(), 1)

    def test_the_crew_can_cancel_a_mark_just_after_the_flight_and_the_photo_then_counts_as_missed(self):
        self.set_scale(SCALE_200)
        self.assertEqual(self.post(self.pilot).status_code, 201)
        observation = PhotoObservation.objects.get()
        self.set_now(START + datetime.timedelta(hours=3, minutes=3))  # after the window, inside the grace period
        self.client.force_login(self.pilot)
        self.assertEqual(self.client.delete(self.delete_url(observation.pk)).status_code, 204)

    def test_registering_with_a_time_only_takes_the_position_from_the_reports(self):
        self.set_scale(SCALE_200)
        self.add_reports()
        self.client.force_login(self.pilot)
        # 10:00:30 is exactly the report halfway along the leg: the photo target
        response = self.client.post(
            self.url, {"photo": self.photo.pk, "time": "2026-08-01T10:00:30Z"}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 201, response.content)
        observation = PhotoObservation.objects.get()
        self.assertAlmostEqual(observation.latitude, self.photo_lat, places=5)
        self.assertEqual(observation.score_fraction, 1.0)

    def test_crew_gets_no_judging_while_registration_is_open(self):
        self.set_scale(SCALE_200)
        crew_response = self.post(self.pilot).json()
        self.assertEqual(set(crew_response), {"id", "contestant", "photo", "photo_name", "time"})
        # Managers always see the judging
        self.client.force_login(self.manager)
        self.assertIn("score_fraction", self.client.get(self.url).json()[0])

    def test_the_position_is_interpolated_between_two_reports(self):
        self.add_reports()
        self.client.force_login(self.pilot)
        self.client.post(
            self.url, {"photo": self.photo.pk, "time": "2026-08-01T10:00:35Z"}, content_type="application/json"
        )
        observation = PhotoObservation.objects.get()
        expected = self.leg_start.latitude + (self.leg_end.latitude - self.leg_start.latitude) * (35 / 60)
        self.assertAlmostEqual(observation.latitude, expected, places=6)

    def test_a_time_without_a_position_report_is_refused_with_a_reason(self):
        self.add_reports()
        self.client.force_login(self.pilot)
        response = self.client.post(
            self.url, {"photo": self.photo.pk, "time": "2026-08-01T10:05:00Z"}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 422)
        self.assertIn("position report", response.json()["detail"])
        self.assertEqual(PhotoObservation.objects.count(), 0)

    def test_a_correction_can_move_the_observation_earlier_only_when_asked_to_replace(self):
        self.set_scale(SCALE_200)
        self.add_reports()
        self.client.force_login(self.pilot)
        late = self.client.post(
            self.url, {"photo": self.photo.pk, "time": "2026-08-01T10:00:50Z"}, content_type="application/json"
        )
        self.assertEqual(late.status_code, 201)
        ignored = self.client.post(
            self.url, {"photo": self.photo.pk, "time": "2026-08-01T10:00:30Z"}, content_type="application/json"
        )
        self.assertEqual(ignored.status_code, 200)
        self.assertEqual(PhotoObservation.objects.get().time.second, 50)
        replaced = self.client.post(
            self.url,
            {"photo": self.photo.pk, "time": "2026-08-01T10:00:30Z", "replace": True},
            content_type="application/json",
        )
        self.assertEqual(replaced.status_code, 201)
        self.assertEqual(PhotoObservation.objects.get().time.second, 30)

    def test_the_time_cannot_be_in_the_future(self):
        self.add_reports()
        self.client.force_login(self.pilot)
        self.set_now(datetime.datetime(2026, 8, 1, 10, 0, 10, tzinfo=datetime.timezone.utc))
        response = self.client.post(
            self.url, {"photo": self.photo.pk, "time": "2026-08-01T10:05:00Z"}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)

    def test_latitude_without_longitude_is_invalid(self):
        self.client.force_login(self.pilot)
        response = self.client.post(
            self.url,
            {"photo": self.photo.pk, "time": OBSERVATION_TIME, "latitude": 60.0},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_unknown_photo_is_rejected(self):
        self.assertEqual(self.post(self.pilot, photo=999999).status_code, 400)

    def test_tolerance_follows_the_map_scale(self):
        # Move the observation about 400 m along the first leg
        bearing_scale = 400 / self._leg_length_m()
        lat = self.photo_lat + (self.leg_end.latitude - self.leg_start.latitude) * bearing_scale
        lon = self.photo_lon + (self.leg_end.longitude - self.leg_start.longitude) * bearing_scale
        self.set_scale(SCALE_200)  # 1 mm = 200 m -> 2 mm off
        self.assertEqual(self.post(self.manager, lat, lon).json()["score_fraction"], 0.0)
        PhotoObservation.objects.all().delete()
        self.set_scale(500)  # 1 mm = 500 m -> 0.8 mm off
        response = self.post(self.manager, lat, lon)
        self.assertEqual(response.json()["score_fraction"], 1.0)
        self.assertAlmostEqual(response.json()["error_mm"], 0.8, delta=0.05)

    def test_fit_page_and_missing_configuration_default_to_1_250_000(self):
        self.set_scale(SCALE_TO_FIT)
        self.assertEqual(self.post(self.manager).json()["metres_per_mm"], 250.0)
        PhotoObservation.objects.all().delete()
        FlightOrderConfiguration.objects.all().delete()
        self.assertEqual(self.post(self.manager).json()["metres_per_mm"], 250.0)

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
        self.post(self.manager)
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
        response = self.post(self.manager, *self.along_leg(400))  # 2 mm off, beyond the 1 mm tolerance
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
        full = self.post(self.manager, *self.along_leg(300))  # 1.5 mm
        self.assertEqual((full.json()["score_fraction"], full.json()["points"]), (1.0, 0.0))
        half = self.post(self.manager, *self.along_leg(600), time="2026-08-01T10:01:00Z")  # 3 mm
        self.assertEqual(half.json()["score_fraction"], 0.5)
        self.assertAlmostEqual(half.json()["points"], -1000 * 50 / qmax)
        zero = self.post(self.manager, *self.along_leg(1200), time="2026-08-01T10:02:00Z")  # 6 mm
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
        zero = self.post(self.manager, *self.along_leg(1200))
        self.assertAlmostEqual(zero.json()["points"], -1000 * 200 / qmax)

    def test_tolerances_are_configurable_on_the_scorecard(self):
        self.set_scale(SCALE_200)
        scorecard = self.navigation_task.scorecard
        scorecard.observation_photo_full_tolerance_mm = 3
        scorecard.save()
        self.navigation_task.refresh_from_db()
        self.contestant.refresh_from_db()
        # 2 mm off: a miss with the legacy default of 1 mm, a hit with 3 mm
        response = self.post(self.manager, *self.along_leg(400))
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
        self.assertEqual(self.post(self.manager, *self.along_leg(300)).json()["score_fraction"], 0.5)  # 1.5 mm
        self.assertEqual(
            self.post(self.manager, *self.along_leg(600), time="2026-08-01T10:01:00Z").json()["score_fraction"], 0.0
        )  # 3 mm, would have been half by default


class ObservationPhotoSelectionTest(PhotoObservationApiTest):
    def test_the_photos_of_waypoints_are_not_observation_photos(self):
        from display.services.photo_observations import get_contestant_observation_photos

        self.assertEqual([p.name for p in get_contestant_observation_photos(self.contestant)], ["A"])

    def test_unmarked_waypoint_photos_are_not_misses(self):
        self.assertEqual(finalize_photo_observations(self.contestant), 1)  # only the observation photo "A"
        self.assertEqual(ScoreLogEntry.objects.filter(contestant=self.contestant).count(), 1)

    def test_a_waypoint_photo_cannot_be_registered(self):
        self.assertEqual(self.post(self.pilot, photo=self.waypoint_photo.pk).status_code, 400)

    def test_the_crew_is_only_offered_the_observation_photos(self):
        self.client.force_login(self.pilot)
        url = reverse("all-contestants-observation-photos", kwargs={"pk": self.contestant.pk})
        self.assertEqual([p["name"] for p in self.client.get(url).json()["photos"]], ["A"])

    def test_photo_targets_include_observation_photos_on_every_task_type(self):
        from display.services.photo_management import get_navigation_task_photo_targets

        targets = {t["name"]: t["target_kind"] for t in get_navigation_task_photo_targets(self.navigation_task)}
        self.assertEqual(targets["A"], "observation")
        self.assertEqual(targets["TP 1"] if "TP 1" in targets else "route_waypoint", "route_waypoint")

    def test_the_photos_endpoint_can_be_limited_to_observation_photos(self):
        self.client.force_login(self.manager)
        url = reverse(
            "navigationtasks-photos",
            kwargs={"contest_pk": self.contest.pk, "pk": self.navigation_task.pk},
        )
        names = {p["name"] for p in self.client.get(url).json()}
        self.assertIn("A", names)
        self.assertGreater(len(names), 1)  # the waypoint photos are there too without the filter
        self.assertEqual({p["name"] for p in self.client.get(url, {"kind": "observation"}).json()}, {"A"})

    def test_flight_order_photo_pages_do_not_mix_in_the_waypoint_photos(self):
        from display.flight_order_and_maps.generate_flight_orders import _route_photos

        Photo.objects.create(name="DECOY", route=self.route, latitude=60, longitude=11, is_decoy=True)
        self.assertEqual(sorted(p.name for p in _route_photos(self.contestant)), ["A", "DECOY"])
        # A route without editable-route features cannot tell them apart and keeps everything
        NavigationTask.objects.filter(pk=self.navigation_task.pk).update(editable_route=None)
        self.contestant.navigation_task.refresh_from_db()
        self.assertEqual(sorted(p.name for p in _route_photos(self.contestant)), ["A", "DECOY", "TP 1"])
