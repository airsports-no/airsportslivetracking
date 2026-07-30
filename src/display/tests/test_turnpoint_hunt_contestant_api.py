import datetime
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from guardian.shortcuts import assign_perm

from display.default_scorecards.create_scorecards import create_scorecards
from display.models import (
    Aeroplane,
    Contest,
    ContestTeam,
    Crew,
    EditableRoute,
    NavigationTask,
    Person,
    Scorecard,
    Team,
    Contestant,
)
from display.utilities.cima_task_type_definitions import KNOWN_CIRCUIT, LIMITED_FUEL_TURNPOINT_HUNT, TURNPOINT_HUNT
from utilities.mock_utilities import TraccarMock


class BaseTurnpointHuntContestantApiTest(TestCase):
    subtype = TURNPOINT_HUNT
    expected_fuel_metadata = None

    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, *_args):
        create_scorecards()
        self.user = get_user_model().objects.create(email="turnpoint-api@example.com")
        Person.objects.create(first_name="Turnpoint", last_name="Api", email=self.user.email)
        self.scorecard = Scorecard.get_originals().get(shortcut_name="FAI Precision")
        with open("display/tests/NM.csv", "r") as file:
            editable_route, _ = EditableRoute.create_from_csv("Turnpoint API route", file.readlines()[1:])
            self.route = editable_route.create_precision_route(True, self.scorecard)

        self.contest = Contest.objects.create(
            name="Turnpoint API Contest",
            time_zone="Europe/Oslo",
            start_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 8, 1, 17, 0, tzinfo=datetime.timezone.utc),
            location="60.0,11.0",
            created_by=self.user,
        )
        assign_perm("view_contest", self.user, self.contest)
        assign_perm("change_contest", self.user, self.contest)

        self.navigation_task = NavigationTask.create(
            name="Turnpoint API Task",
            contest=self.contest,
            route=self.route,
            original_scorecard=self.scorecard,
            start_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 8, 1, 17, 0, tzinfo=datetime.timezone.utc),
            task_subtype=self.subtype,
        )
        self.editable_route = EditableRoute.objects.create(
            name="Turnpoint API primitives",
            route={
                "type": "FeatureCollection",
                "features": [
                    {"type": "Feature", "properties": {"featureType": "route_path"}, "geometry": {"type": "LineString", "coordinates": [[11.0, 60.0], [11.1, 60.1]]}},
                    {"type": "Feature", "properties": {"id": "cat-1", "name": "A", "pointType": "tp", "featureType": "catalogue_turnpoint"}, "geometry": {"type": "Point", "coordinates": [11.2, 60.2]}},
                    {"type": "Feature", "properties": {"id": "cat-2", "name": "B", "pointType": "tp", "featureType": "catalogue_turnpoint"}, "geometry": {"type": "Point", "coordinates": [11.3, 60.3]}},
                    {"type": "Feature", "properties": {"id": "kt-1", "name": "CP1", "pointType": "tp", "featureType": "known_time_gate"}, "geometry": {"type": "Point", "coordinates": [11.25, 60.25]}},
                    {"type": "Feature", "properties": {"id": "kt-2", "name": "CP2", "pointType": "tp", "featureType": "known_time_gate"}, "geometry": {"type": "Point", "coordinates": [11.35, 60.35]}},
                    {"type": "Feature", "properties": {"id": "kt-3", "name": "CP3", "pointType": "tp", "featureType": "known_time_gate"}, "geometry": {"type": "Point", "coordinates": [11.45, 60.45]}},
                    {"type": "Feature", "properties": {"id": "obs-1", "name": "A", "featureType": "observation_photo"}, "geometry": {"type": "Point", "coordinates": [11.35, 60.35]}},
                    {"type": "Feature", "properties": {"id": "obs-2", "name": "B", "featureType": "observation_photo"}, "geometry": {"type": "Point", "coordinates": [11.36, 60.36]}},
                ],
            },
        )
        self.navigation_task.editable_route = self.editable_route
        self.navigation_task.save(update_fields=["editable_route"])

        team = Team.objects.create(
            crew=Crew.objects.create(member1=Person.objects.create(first_name="Pilot", last_name="Api", email="pilot-turnpoint-api@example.com")),
            aeroplane=Aeroplane.objects.create(registration="LN-TPAPI"),
        )
        self.contest_team = ContestTeam.objects.create(contest=self.contest, team=team, air_speed=70)
        self.client.force_login(self.user)

    def build_declaration_payload(self):
        payload = {
            "compulsory_point_times": {
                "CP1": "2026-08-01T10:07:00Z",
                "CP2": "2026-08-01T10:19:00Z",
                "CP3": "2026-08-01T10:32:00Z",
            },
        }
        if self.expected_fuel_metadata is not None:
            payload["fuel_metadata"] = self.expected_fuel_metadata
        return payload

    def assert_persisted_payload(self, contestant):
        expected = {
            "compulsory_point_times": {
                "CP1": "2026-08-01T10:07:00+00:00",
                "CP2": "2026-08-01T10:19:00+00:00",
                "CP3": "2026-08-01T10:32:00+00:00",
            },
        }
        if self.expected_fuel_metadata is not None:
            expected["fuel_metadata"] = self.expected_fuel_metadata
        self.assertEqual(contestant.contestanttaskconfiguration.declaration_payload, expected)


class TestTurnpointHuntContestantApi(BaseTurnpointHuntContestantApiTest):
    @patch("display.viewsets._assert_can_reserve_task_slot")
    def test_contestant_api_create_persists_turnpoint_hunt_declaration_payload(self, _mock_guard):
        url = reverse(
            "contestants-list",
            kwargs={"contest_pk": self.contest.pk, "navigationtask_pk": self.navigation_task.pk},
        )
        response = self.client.post(
            url,
            {
                "contestant_number": 1,
                "team": self.contest_team.team.pk,
                "tracking_service": str(self.contest_team.tracking_service),
                "tracking_device": self.contest_team.tracking_device or "",
                "tracker_device_id": self.contest_team.tracker_device_id or "",
                "takeoff_time": "2026-08-01T09:55:00Z",
                "adaptive_start": False,
                "tracker_start_time": "2026-08-01T09:45:00Z",
                "finished_by_time": "2026-08-01T11:30:00Z",
                "minutes_to_starting_point": 5,
                "air_speed": 70,
                "wind_direction": 0,
                "wind_speed": 0,
                "declaration_payload": self.build_declaration_payload(),
            },
            content_type="application/json",
        )
        self.assertEqual(200, response.status_code, response.content)
        contestant = self.navigation_task.contestant_set.get(team=self.contest_team.team)
        self.assert_persisted_payload(contestant)


class TestLimitedFuelTurnpointHuntContestantApi(BaseTurnpointHuntContestantApiTest):
    subtype = LIMITED_FUEL_TURNPOINT_HUNT
    expected_fuel_metadata = {"declared_endurance_minutes": 95}

    @patch("display.viewsets._assert_can_reserve_task_slot")
    def test_contestant_api_create_persists_limited_fuel_turnpoint_hunt_declaration_payload(self, _mock_guard):
        url = reverse(
            "contestants-list",
            kwargs={"contest_pk": self.contest.pk, "navigationtask_pk": self.navigation_task.pk},
        )
        response = self.client.post(
            url,
            {
                "contestant_number": 1,
                "team": self.contest_team.team.pk,
                "tracking_service": str(self.contest_team.tracking_service),
                "tracking_device": self.contest_team.tracking_device or "",
                "tracker_device_id": self.contest_team.tracker_device_id or "",
                "takeoff_time": "2026-08-01T09:55:00Z",
                "adaptive_start": False,
                "tracker_start_time": "2026-08-01T09:45:00Z",
                "finished_by_time": "2026-08-01T11:30:00Z",
                "minutes_to_starting_point": 5,
                "air_speed": 70,
                "wind_direction": 0,
                "wind_speed": 0,
                "declaration_payload": self.build_declaration_payload(),
            },
            content_type="application/json",
        )
        self.assertEqual(200, response.status_code, response.content)
        contestant = self.navigation_task.contestant_set.get(team=self.contest_team.team)
        self.assert_persisted_payload(contestant)


class TestTurnpointHuntContestantTeamIdApi(BaseTurnpointHuntContestantApiTest):
    @patch("display.viewsets._assert_can_reserve_task_slot")
    def test_contestant_teamid_api_create_persists_turnpoint_hunt_declaration_payload(self, _mock_guard):
        url = reverse(
            "contestantsteamid-list",
            kwargs={"contest_pk": self.contest.pk, "navigationtask_pk": self.navigation_task.pk},
        )
        response = self.client.post(
            url,
            {
                "contestant_number": 1,
                "team": self.contest_team.team.pk,
                "tracking_service": str(self.contest_team.tracking_service),
                "tracking_device": self.contest_team.tracking_device or "",
                "tracker_device_id": self.contest_team.tracker_device_id or "",
                "takeoff_time": "2026-08-01T09:55:00Z",
                "adaptive_start": False,
                "tracker_start_time": "2026-08-01T09:45:00Z",
                "finished_by_time": "2026-08-01T11:30:00Z",
                "minutes_to_starting_point": 5,
                "air_speed": 70,
                "wind_direction": 0,
                "wind_speed": 0,
                "declaration_payload": self.build_declaration_payload(),
            },
            content_type="application/json",
        )
        self.assertEqual(201, response.status_code, response.content)
        contestant = self.navigation_task.contestant_set.get(team=self.contest_team.team)
        self.assert_persisted_payload(contestant)


class TestLimitedFuelTurnpointHuntContestantTeamIdApi(BaseTurnpointHuntContestantApiTest):
    subtype = LIMITED_FUEL_TURNPOINT_HUNT
    expected_fuel_metadata = {"declared_endurance_minutes": 95}

    @patch("display.viewsets._assert_can_reserve_task_slot")
    def test_contestant_teamid_api_create_persists_limited_fuel_turnpoint_hunt_declaration_payload(self, _mock_guard):
        url = reverse(
            "contestantsteamid-list",
            kwargs={"contest_pk": self.contest.pk, "navigationtask_pk": self.navigation_task.pk},
        )
        response = self.client.post(
            url,
            {
                "contestant_number": 1,
                "team": self.contest_team.team.pk,
                "tracking_service": str(self.contest_team.tracking_service),
                "tracking_device": self.contest_team.tracking_device or "",
                "tracker_device_id": self.contest_team.tracker_device_id or "",
                "takeoff_time": "2026-08-01T09:55:00Z",
                "adaptive_start": False,
                "tracker_start_time": "2026-08-01T09:45:00Z",
                "finished_by_time": "2026-08-01T11:30:00Z",
                "minutes_to_starting_point": 5,
                "air_speed": 70,
                "wind_direction": 0,
                "wind_speed": 0,
                "declaration_payload": self.build_declaration_payload(),
            },
            content_type="application/json",
        )
        self.assertEqual(201, response.status_code, response.content)
        contestant = self.navigation_task.contestant_set.get(team=self.contest_team.team)
        self.assert_persisted_payload(contestant)


class TestKnownCircuitContestantApi(TestCase):
    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    @patch("display.viewsets._assert_can_reserve_task_slot")
    def test_contestant_api_response_includes_compiled_observation_evidence_payload(self, _mock_guard, *_args):
        create_scorecards()
        user = get_user_model().objects.create(email="known-circuit-api@example.com")
        Person.objects.create(first_name="Known", last_name="Circuit", email=user.email)
        scorecard = Scorecard.get_originals().get(shortcut_name="FAI Precision")
        with open("display/tests/NM.csv", "r") as file:
            editable_route, _ = EditableRoute.create_from_csv("Known circuit API route", file.readlines()[1:])
            route = editable_route.create_precision_route(True, scorecard)

        contest = Contest.objects.create(
            name="Known Circuit API Contest",
            time_zone="Europe/Oslo",
            start_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 8, 1, 17, 0, tzinfo=datetime.timezone.utc),
            location="60.0,11.0",
            created_by=user,
        )
        assign_perm("view_contest", user, contest)
        assign_perm("change_contest", user, contest)

        navigation_task = NavigationTask.create(
            name="Known Circuit API Task",
            contest=contest,
            route=route,
            original_scorecard=scorecard,
            start_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 8, 1, 17, 0, tzinfo=datetime.timezone.utc),
            task_subtype=KNOWN_CIRCUIT,
        )
        known_circuit_route = EditableRoute.objects.create(
            name="Known Circuit API primitives",
            route={
                "type": "FeatureCollection",
                "features": [
                    {"type": "Feature", "properties": {"featureType": "route_path"}, "geometry": {"type": "LineString", "coordinates": [[11.0, 60.0], [11.1, 60.1]]}},
                    {"type": "Feature", "properties": {"id": "hg-1", "name": "HG1", "pointType": "tp", "featureType": "hidden_gate"}, "geometry": {"type": "Point", "coordinates": [11.2, 60.2]}},
                    {"type": "Feature", "properties": {"id": "obs-1", "name": "Photo 1", "featureType": "observation_photo"}, "geometry": {"type": "Point", "coordinates": [11.35, 60.35]}},
                ],
            },
        )
        navigation_task.editable_route = known_circuit_route
        navigation_task.save(update_fields=["editable_route"])

        team = Team.objects.create(
            crew=Crew.objects.create(member1=Person.objects.create(first_name="Pilot", last_name="Known", email="pilot-known@example.com")),
            aeroplane=Aeroplane.objects.create(registration="LN-KNOWNAPI"),
        )
        contest_team = ContestTeam.objects.create(contest=contest, team=team, air_speed=70)

        client = self.client
        client.force_login(user)
        create_url = reverse("contestants-list", kwargs={"contest_pk": contest.pk, "navigationtask_pk": navigation_task.pk})
        create_response = client.post(
            create_url,
            {
                "contestant_number": 1,
                "team": contest_team.team.pk,
                "tracking_service": str(contest_team.tracking_service),
                "tracking_device": contest_team.tracking_device or "",
                "tracker_device_id": contest_team.tracker_device_id or "",
                "takeoff_time": "2026-08-01T09:55:00Z",
                "adaptive_start": False,
                "tracker_start_time": "2026-08-01T09:45:00Z",
                "finished_by_time": "2026-08-01T11:30:00Z",
                "minutes_to_starting_point": 5,
                "air_speed": 70,
                "wind_direction": 0,
                "wind_speed": 0,
            },
            content_type="application/json",
        )
        self.assertEqual(200, create_response.status_code, create_response.content)

        contestant = navigation_task.contestant_set.get(team=contest_team.team)
        detail_url = reverse("contestants-detail", kwargs={"contest_pk": contest.pk, "navigationtask_pk": navigation_task.pk, "pk": contestant.pk})
        detail_response = client.get(detail_url)
        self.assertEqual(200, detail_response.status_code, detail_response.content)
        payload = detail_response.json().get("compiled_effective_route_payload", {})
        self.assertEqual(payload.get("hidden_gate_names"), ["HG1"])
        self.assertEqual(payload.get("observation_judging_mode"), "external_manual")
        self.assertEqual(payload.get("manual_adjudication_categories"), ["observation", "map"])
        self.assertEqual(payload.get("observation_photos", [])[0]["name"], "Photo 1")
        self.assertEqual(payload.get("observation_photos", [])[0]["evidence_category"], "observation")

        photos_url = reverse("navigationtasks-photos", kwargs={"contest_pk": contest.pk, "pk": navigation_task.pk})
        photos_response = client.get(f"{photos_url}?contestant={contestant.pk}")
        self.assertEqual(200, photos_response.status_code, photos_response.content)
        photo_payload = photos_response.json()
        self.assertEqual(photo_payload[0]["name"], "Photo 1")
        self.assertEqual(photo_payload[0]["compiled_coordinates"], [11.35, 60.35])
        self.assertEqual(photo_payload[0]["evidence_category"], "observation")

        score_url = reverse("contestants-score", kwargs={"contest_pk": contest.pk, "navigationtask_pk": navigation_task.pk, "pk": contestant.pk})
        score_response = client.get(score_url)
        self.assertEqual(200, score_response.status_code, score_response.content)
        score_payload = score_response.json().get("compiled_effective_route_payload", {})
        self.assertEqual(score_payload.get("hidden_gate_names"), ["HG1"])
        self.assertEqual(score_payload.get("observation_judging_mode"), "external_manual")
        self.assertEqual(score_payload.get("manual_adjudication_categories"), ["observation", "map"])
        self.assertEqual(score_payload.get("observation_photos", [])[0]["name"], "Photo 1")
        self.assertEqual(score_payload.get("observation_photos", [])[0]["evidence_category"], "observation")

        evidence_url = reverse("contestants-compiled-evidence", kwargs={"contest_pk": contest.pk, "navigationtask_pk": navigation_task.pk, "pk": contestant.pk})
        evidence_response = client.get(evidence_url)
        self.assertEqual(200, evidence_response.status_code, evidence_response.content)
        evidence_payload = evidence_response.json()
        self.assertEqual(evidence_payload.get("hidden_gate_names"), ["HG1"])
        self.assertEqual(evidence_payload.get("observation_judging_mode"), "external_manual")
        self.assertEqual(evidence_payload.get("manual_adjudication_categories"), ["observation", "map"])
        self.assertEqual(evidence_payload.get("observation_photos", [])[0]["coordinates"], [11.35, 60.35])
        self.assertEqual(evidence_payload.get("observation_photos", [])[0]["evidence_category"], "observation")


class TestUnknownLegsContestantApi(TestCase):
    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    @patch("display.viewsets._assert_can_reserve_task_slot")
    def test_unknown_legs_api_response_includes_unknown_leg_evidence_payload(self, _mock_guard, *_args):
        create_scorecards()
        user = get_user_model().objects.create(email="unknown-legs-api@example.com")
        Person.objects.create(first_name="Unknown", last_name="Legs", email=user.email)
        scorecard = Scorecard.get_originals().get(shortcut_name="FAI Precision")
        with open("display/tests/NM.csv", "r") as file:
            editable_route, _ = EditableRoute.create_from_csv("Unknown legs API route", file.readlines()[1:])
            route = editable_route.create_precision_route(True, scorecard)

        contest = Contest.objects.create(
            name="Unknown Legs API Contest",
            time_zone="Europe/Oslo",
            start_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 8, 1, 17, 0, tzinfo=datetime.timezone.utc),
            location="60.0,11.0",
            created_by=user,
        )
        assign_perm("view_contest", user, contest)
        assign_perm("change_contest", user, contest)

        navigation_task = NavigationTask.create(
            name="Unknown Legs API Task",
            contest=contest,
            route=route,
            original_scorecard=scorecard,
            start_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 8, 1, 17, 0, tzinfo=datetime.timezone.utc),
            task_subtype="unknown_legs",
        )
        unknown_legs_route = EditableRoute.objects.create(
            name="Unknown Legs API primitives",
            route={
                "type": "FeatureCollection",
                "features": [
                    {"type": "Feature", "properties": {"featureType": "route_path"}, "geometry": {"type": "LineString", "coordinates": [[11.0, 60.0], [11.1, 60.1]]}},
                    {"type": "Feature", "properties": {"id": "ul-1", "name": "UL1", "pointType": "ul", "featureType": "route_waypoint", "width": 1852, "isTiming": True, "isPassing": True, "sequence": 0, "segmentType": "straight"}, "geometry": {"type": "Point", "coordinates": [11.2, 60.2]}},
                    {"type": "Feature", "properties": {"id": "obs-1", "name": "Photo 1", "featureType": "observation_photo"}, "geometry": {"type": "Point", "coordinates": [11.35, 60.35]}},
                ],
            },
        )
        navigation_task.editable_route = unknown_legs_route
        navigation_task.save(update_fields=["editable_route"])

        team = Team.objects.create(
            crew=Crew.objects.create(member1=Person.objects.create(first_name="Pilot", last_name="Unknown", email="pilot-unknown@example.com")),
            aeroplane=Aeroplane.objects.create(registration="LN-UNKNOWNAPI"),
        )
        contest_team = ContestTeam.objects.create(contest=contest, team=team, air_speed=70)

        client = self.client
        client.force_login(user)
        create_url = reverse("contestants-list", kwargs={"contest_pk": contest.pk, "navigationtask_pk": navigation_task.pk})
        create_response = client.post(
            create_url,
            {
                "contestant_number": 1,
                "team": contest_team.team.pk,
                "tracking_service": str(contest_team.tracking_service),
                "tracking_device": contest_team.tracking_device or "",
                "tracker_device_id": contest_team.tracker_device_id or "",
                "takeoff_time": "2026-08-01T09:55:00Z",
                "adaptive_start": False,
                "tracker_start_time": "2026-08-01T09:45:00Z",
                "finished_by_time": "2026-08-01T11:30:00Z",
                "minutes_to_starting_point": 5,
                "air_speed": 70,
                "wind_direction": 0,
                "wind_speed": 0,
            },
            content_type="application/json",
        )
        self.assertEqual(200, create_response.status_code, create_response.content)

        contestant = navigation_task.contestant_set.get(team=contest_team.team)
        detail_url = reverse("contestants-detail", kwargs={"contest_pk": contest.pk, "navigationtask_pk": navigation_task.pk, "pk": contestant.pk})
        detail_response = client.get(detail_url)
        self.assertEqual(200, detail_response.status_code, detail_response.content)
        payload = detail_response.json().get("compiled_effective_route_payload", {})
        self.assertEqual(payload.get("unknown_leg_names"), ["UL1"])
        self.assertEqual(payload.get("observation_judging_mode"), "external_manual")
        self.assertEqual(payload.get("manual_adjudication_categories"), ["observation", "map"])
        self.assertEqual(payload.get("observation_photos", [])[0]["name"], "Photo 1")
        self.assertEqual(payload.get("observation_photos", [])[0]["evidence_category"], "observation")

        photos_url = reverse("navigationtasks-photos", kwargs={"contest_pk": contest.pk, "pk": navigation_task.pk})
        photos_response = client.get(f"{photos_url}?contestant={contestant.pk}")
        self.assertEqual(200, photos_response.status_code, photos_response.content)
        photo_payload = photos_response.json()
        self.assertEqual(photo_payload[0]["name"], "Photo 1")
        self.assertEqual(photo_payload[0]["compiled_coordinates"], [11.35, 60.35])
        self.assertEqual(photo_payload[0]["evidence_category"], "observation")

        score_url = reverse("contestants-score", kwargs={"contest_pk": contest.pk, "navigationtask_pk": navigation_task.pk, "pk": contestant.pk})
        score_response = client.get(score_url)
        self.assertEqual(200, score_response.status_code, score_response.content)
        score_payload = score_response.json().get("compiled_effective_route_payload", {})
        self.assertEqual(score_payload.get("unknown_leg_names"), ["UL1"])
        self.assertEqual(score_payload.get("observation_judging_mode"), "external_manual")
        self.assertEqual(score_payload.get("manual_adjudication_categories"), ["observation", "map"])
        self.assertEqual(score_payload.get("observation_photos", [])[0]["name"], "Photo 1")
        self.assertEqual(score_payload.get("observation_photos", [])[0]["evidence_category"], "observation")

        evidence_url = reverse("contestants-compiled-evidence", kwargs={"contest_pk": contest.pk, "navigationtask_pk": navigation_task.pk, "pk": contestant.pk})
        evidence_response = client.get(evidence_url)
        self.assertEqual(200, evidence_response.status_code, evidence_response.content)
        evidence_payload = evidence_response.json()
        self.assertEqual(evidence_payload.get("unknown_leg_names"), ["UL1"])
        self.assertEqual(evidence_payload.get("observation_judging_mode"), "external_manual")
        self.assertEqual(evidence_payload.get("manual_adjudication_categories"), ["observation", "map"])
        self.assertEqual(evidence_payload.get("observation_photos", [])[0]["coordinates"], [11.35, 60.35])
        self.assertEqual(evidence_payload.get("observation_photos", [])[0]["evidence_category"], "observation")


class TestKnownCircuitContestantEvidenceVisibility(TestCase):
    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    @patch("display.viewsets._assert_can_reserve_task_slot")
    def test_view_only_user_can_read_compiled_known_circuit_evidence(self, _mock_guard, *_args):
        create_scorecards()
        organizer = get_user_model().objects.create(email="known-circuit-organizer@example.com")
        viewer = get_user_model().objects.create(email="known-circuit-viewer@example.com")
        Person.objects.create(first_name="Known", last_name="Organizer", email=organizer.email)
        Person.objects.create(first_name="Known", last_name="Viewer", email=viewer.email)
        scorecard = Scorecard.get_originals().get(shortcut_name="FAI Precision")
        with open("display/tests/NM.csv", "r") as file:
            editable_route, _ = EditableRoute.create_from_csv("Known circuit visibility route", file.readlines()[1:])
            route = editable_route.create_precision_route(True, scorecard)

        contest = Contest.objects.create(
            name="Known Circuit Visibility Contest",
            time_zone="Europe/Oslo",
            start_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 8, 1, 17, 0, tzinfo=datetime.timezone.utc),
            location="60.0,11.0",
            created_by=organizer,
        )
        assign_perm("view_contest", organizer, contest)
        assign_perm("change_contest", organizer, contest)
        assign_perm("view_contest", viewer, contest)

        navigation_task = NavigationTask.create(
            name="Known Circuit Visibility Task",
            contest=contest,
            route=route,
            original_scorecard=scorecard,
            start_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 8, 1, 17, 0, tzinfo=datetime.timezone.utc),
            task_subtype=KNOWN_CIRCUIT,
        )
        known_circuit_route = EditableRoute.objects.create(
            name="Known Circuit Visibility primitives",
            route={
                "type": "FeatureCollection",
                "features": [
                    {"type": "Feature", "properties": {"featureType": "route_path"}, "geometry": {"type": "LineString", "coordinates": [[11.0, 60.0], [11.1, 60.1]]}},
                    {"type": "Feature", "properties": {"id": "hg-1", "name": "HG1", "pointType": "tp", "featureType": "hidden_gate"}, "geometry": {"type": "Point", "coordinates": [11.2, 60.2]}},
                    {"type": "Feature", "properties": {"id": "obs-1", "name": "Photo 1", "featureType": "observation_photo"}, "geometry": {"type": "Point", "coordinates": [11.35, 60.35]}},
                ],
            },
        )
        navigation_task.editable_route = known_circuit_route
        navigation_task.save(update_fields=["editable_route"])

        team = Team.objects.create(
            crew=Crew.objects.create(member1=Person.objects.create(first_name="Pilot", last_name="Visible", email="pilot-visible@example.com")),
            aeroplane=Aeroplane.objects.create(registration="LN-KCVIS"),
        )
        contest_team = ContestTeam.objects.create(contest=contest, team=team, air_speed=70)

        organizer_client = self.client_class()
        organizer_client.force_login(organizer)
        create_url = reverse("contestants-list", kwargs={"contest_pk": contest.pk, "navigationtask_pk": navigation_task.pk})
        create_response = organizer_client.post(
            create_url,
            {
                "contestant_number": 1,
                "team": contest_team.team.pk,
                "tracking_service": str(contest_team.tracking_service),
                "tracking_device": contest_team.tracking_device or "",
                "tracker_device_id": contest_team.tracker_device_id or "",
                "takeoff_time": "2026-08-01T09:55:00Z",
                "adaptive_start": False,
                "tracker_start_time": "2026-08-01T09:45:00Z",
                "finished_by_time": "2026-08-01T11:30:00Z",
                "minutes_to_starting_point": 5,
                "air_speed": 70,
                "wind_direction": 0,
                "wind_speed": 0,
            },
            content_type="application/json",
        )
        self.assertEqual(200, create_response.status_code, create_response.content)

        contestant = navigation_task.contestant_set.get(team=contest_team.team)

        with patch("display.viewsets.get_objects_for_user", return_value=Contest.objects.filter(pk=contest.pk)):
            viewer_client = self.client_class()
            viewer_client.force_login(viewer)

            score_url = reverse("contestants-score", kwargs={"contest_pk": contest.pk, "navigationtask_pk": navigation_task.pk, "pk": contestant.pk})
            score_response = viewer_client.get(score_url)
            self.assertEqual(200, score_response.status_code, score_response.content)
            score_payload = score_response.json().get("compiled_effective_route_payload", {})
            self.assertEqual(score_payload.get("observation_judging_mode"), "external_manual")
            self.assertEqual(score_payload.get("manual_adjudication_categories"), ["observation", "map"])
            self.assertEqual(score_payload.get("hidden_gate_names"), ["HG1"])

            evidence_url = reverse("contestants-compiled-evidence", kwargs={"contest_pk": contest.pk, "navigationtask_pk": navigation_task.pk, "pk": contestant.pk})
            evidence_response = viewer_client.get(evidence_url)
            self.assertEqual(200, evidence_response.status_code, evidence_response.content)
            evidence_payload = evidence_response.json()
            self.assertEqual(evidence_payload.get("observation_judging_mode"), "external_manual")
            self.assertEqual(evidence_payload.get("manual_adjudication_categories"), ["observation", "map"])
            self.assertEqual(evidence_payload.get("hidden_gate_names"), ["HG1"])
