import datetime
import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from guardian.shortcuts import assign_perm
from unittest.mock import patch

from display.default_scorecards.create_scorecards import create_scorecards
from display.forms import ContestantForm, ContestantQuickAddForm
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
)
from display.services.contestant_task_compiler import ContestantTaskCompiler
from display.utilities.cima_task_type_definitions import LIMITED_FUEL_TURNPOINT_HUNT, TURNPOINT_HUNT
from utilities.mock_utilities import TraccarMock


class TestTurnpointHuntDeclarationUI(TestCase):
    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, *args):
        create_scorecards()
        self.user = get_user_model().objects.create(email="turnpoint-organizer@example.com")
        Person.objects.create(first_name="Turnpoint", last_name="Organizer", email=self.user.email)
        self.scorecard = Scorecard.get_originals().get(shortcut_name="FAI Precision")
        with open("display/tests/NM.csv", "r") as file:
            editable_route, _ = EditableRoute.create_from_csv("Turnpoint declaration UI", file.readlines()[1:])
            self.route = editable_route.create_precision_route(True, self.scorecard)

        self.contest = Contest.objects.create(
            name="Turnpoint Declaration Contest",
            time_zone="Europe/Oslo",
            start_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 8, 1, 17, 0, tzinfo=datetime.timezone.utc),
            location="60.0,11.0",
            created_by=self.user,
        )
        assign_perm("view_contest", self.user, self.contest)
        assign_perm("change_contest", self.user, self.contest)

        self.navigation_task = NavigationTask.create(
            name="Turnpoint Declaration Task",
            contest=self.contest,
            route=self.route,
            original_scorecard=self.scorecard,
            start_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 8, 1, 17, 0, tzinfo=datetime.timezone.utc),
            task_subtype=TURNPOINT_HUNT,
        )
        self.editable_route = EditableRoute.objects.create(
            name="Turnpoint declaration primitives",
            route={
                "type": "FeatureCollection",
                "features": [
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
            crew=Crew.objects.create(member1=Person.objects.create(first_name="Pilot", last_name="Turnpoint", email="pilot-turnpoint@example.com")),
            aeroplane=Aeroplane.objects.create(registration="LN-TPHUNT"),
        )
        self.contest_team = ContestTeam.objects.create(contest=self.contest, team=team, air_speed=70)
        self.create_url = reverse("contestant_create", kwargs={"navigationtask_pk": self.navigation_task.pk})
        self.quick_add_url = reverse("contestant_quick_create", kwargs={"navigationtask_pk": self.navigation_task.pk})

    def _create_contestant(self):
        self.client.force_login(self.user)
        response = self.client.post(
            self.create_url,
            {
                "contestant_number": 1,
                "team": self.contest_team.team.pk,
                "tracking_service": str(self.contest_team.tracking_service),
                "tracking_device": self.contest_team.tracking_device or "",
                "tracker_device_id": self.contest_team.tracker_device_id or "",
                "takeoff_time": "2026-08-01T09:55",
                "adaptive_start": False,
                "tracker_start_time": "2026-08-01T09:45",
                "finished_by_time": "2026-08-01T11:30",
                "minutes_to_starting_point": 5,
                "air_speed": 70,
                "wind_direction": 0,
                "wind_speed": 0,
            },
        )
        self.assertEqual(302, response.status_code)
        return self.navigation_task.contestant_set.get(team=self.contest_team.team)

    def test_turnpoint_hunt_form_does_not_expose_declaration_fields(self):
        form = ContestantForm(navigation_task=self.navigation_task)
        self.assertNotIn("predicted_sequence_1", form.fields)
        self.assertNotIn("predicted_gate_time_CP1", form.fields)

    def test_turnpoint_hunt_form_does_not_require_declaration_fields(self):
        form = ContestantForm(
            navigation_task=self.navigation_task,
            data={
                "contestant_number": 1,
                "team": self.contest_team.team.pk,
                "tracking_service": str(self.contest_team.tracking_service),
                "tracking_device": self.contest_team.tracking_device or "",
                "tracker_device_id": self.contest_team.tracker_device_id or "",
                "takeoff_time": "2026-08-01T09:55",
                "adaptive_start": False,
                "tracker_start_time": "2026-08-01T09:45",
                "finished_by_time": "2026-08-01T11:30",
                "minutes_to_starting_point": 5,
                "air_speed": 70,
                "wind_direction": 0,
                "wind_speed": 0,
            },
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_turnpoint_hunt_create_view_persists_empty_declaration_until_editor_is_used(self):
        contestant = self._create_contestant()
        self.assertEqual(contestant.contestanttaskconfiguration.declaration_payload, {})

    def test_turnpoint_hunt_quick_add_form_does_not_expose_declaration_fields(self):
        form = ContestantQuickAddForm(navigation_task=self.navigation_task)
        self.assertNotIn("predicted_sequence_1", form.fields)
        self.assertNotIn("predicted_gate_time_CP1", form.fields)

    def test_turnpoint_hunt_quick_add_persists_empty_declaration_until_editor_is_used(self):
        self.client.force_login(self.user)
        response = self.client.post(
            self.quick_add_url,
            {
                "contest_team": self.contest_team.pk,
                "starting_point_time": "2026-08-01T10:00",
                "adaptive_start": False,
            },
        )
        self.assertEqual(302, response.status_code)
        contestant = self.navigation_task.contestant_set.get(team=self.contest_team.team)
        self.assertEqual(contestant.contestanttaskconfiguration.declaration_payload, {})

    def test_limited_fuel_turnpoint_hunt_form_does_not_expose_fuel_metadata_field(self):
        self.navigation_task.task_subtype = LIMITED_FUEL_TURNPOINT_HUNT
        self.navigation_task.save(update_fields=["task_subtype"])
        form = ContestantForm(navigation_task=self.navigation_task)
        self.assertNotIn("fuel_declared_endurance_minutes", form.fields)

    def test_turnpoint_hunt_create_view_does_not_render_task_specific_declaration_section(self):
        self.client.force_login(self.user)
        response = self.client.get(self.create_url)
        self.assertEqual(200, response.status_code)
        self.assertNotContains(response, "Task-specific declaration")

    def test_turnpoint_hunt_contestant_detail_exposes_compiled_payload_even_before_declaration_is_valid(self):
        contestant = self._create_contestant()
        url = reverse(
            "contestants-detail",
            kwargs={"contest_pk": self.contest.pk, "navigationtask_pk": self.navigation_task.pk, "pk": contestant.pk},
        )
        self.client.force_login(self.user)
        response = self.client.get(url)
        self.assertEqual(200, response.status_code, response.content)
        payload = json.loads(response.content).get("compiled_effective_route_payload", {})
        self.assertEqual(payload.get("compulsory_point_names"), ["CP1", "CP2", "CP3"])
        self.assertEqual(payload.get("declared_sequence"), [])
        self.assertEqual(payload.get("free_target_names"), ["A", "B"])
        self.assertEqual(payload.get("free_target_evidence"), {"A": ["A"], "B": ["B"]})

    def test_turnpoint_hunt_live_shape_with_three_backbone_waypoints_surfaces_backbone_names(self):
        editable_route = EditableRoute.objects.create(
            name="Turnpoint hunt route-backed backbone",
            route={
                "type": "FeatureCollection",
                "features": [
                    {"type": "Feature", "properties": {"featureType": "route_path"}, "geometry": {"type": "LineString", "coordinates": [[11.0, 60.0], [11.1, 60.1], [11.2, 60.2]]}},
                    {"type": "Feature", "properties": {"id": "wp-sp", "name": "SP", "pointType": "sp", "featureType": "route_waypoint", "width": 1852, "isTiming": True, "isPassing": True, "sequence": 0}, "geometry": {"type": "Point", "coordinates": [11.0, 60.0]}},
                    {"type": "Feature", "properties": {"id": "wp-mp", "name": "MP", "pointType": "tp", "featureType": "route_waypoint", "width": 1852, "isTiming": True, "isPassing": True, "sequence": 1}, "geometry": {"type": "Point", "coordinates": [11.1, 60.1]}},
                    {"type": "Feature", "properties": {"id": "wp-fp", "name": "FP", "pointType": "fp", "featureType": "route_waypoint", "width": 1852, "isTiming": True, "isPassing": True, "sequence": 2}, "geometry": {"type": "Point", "coordinates": [11.2, 60.2]}},
                    {"type": "Feature", "properties": {"id": "cat-1", "name": "A", "pointType": "tp", "featureType": "catalogue_turnpoint"}, "geometry": {"type": "Point", "coordinates": [11.25, 60.25]}},
                ],
            },
        )
        self.navigation_task.editable_route = editable_route
        self.navigation_task.task_subtype = "turnpoint_hunt"
        self.navigation_task.save(update_fields=["editable_route", "task_subtype"])
        compiled = ContestantTaskCompiler(self._create_contestant()).compile(force=True)
        payload = compiled.compiled_effective_route_payload
        if not isinstance(payload, dict):
            payload = {}
        self.assertEqual(payload.get("compulsory_point_names"), ["SP", "MP", "FP"])
        self.assertEqual(payload.get("declared_sequence"), [])
