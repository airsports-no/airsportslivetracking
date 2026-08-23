import datetime
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from guardian.shortcuts import assign_perm

from display.default_scorecards.create_scorecards import create_scorecards
from display.forms import ContestantForm
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
from display.utilities.cima_task_type_definitions import CONTRACT_NAVIGATION_TIME_CONTROLS, CURVE_NAVIGATION_TIME_ESTIMATION, PRECISION_NAVIGATION
from utilities.mock_utilities import TraccarMock


class TestContractNavigationDeclarationUI(TestCase):
    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, *args):
        create_scorecards()
        self.user = get_user_model().objects.create(email="organizer@example.com")
        self.person = Person.objects.create(first_name="Org", last_name="User", email=self.user.email)
        self.scorecard = Scorecard.get_originals().get(shortcut_name="FAI Precision")
        with open("display/tests/NM.csv", "r") as file:
            editable_route, _ = EditableRoute.create_from_csv("Declaration UI", file.readlines()[1:])
            self.route = editable_route.create_precision_route(True, self.scorecard)

        self.contest = Contest.objects.create(
            name="Declaration Contest",
            time_zone="Europe/Oslo",
            start_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 8, 1, 17, 0, tzinfo=datetime.timezone.utc),
            location="60.0,11.0",
            created_by=self.user,
        )
        assign_perm("view_contest", self.user, self.contest)
        assign_perm("change_contest", self.user, self.contest)

        self.navigation_task = NavigationTask.create(
            name="Declaration Task",
            contest=self.contest,
            route=self.route,
            original_scorecard=self.scorecard,
            start_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 8, 1, 17, 0, tzinfo=datetime.timezone.utc),
            task_subtype=CONTRACT_NAVIGATION_TIME_CONTROLS,
            task_config={"contract_time_seconds": 600},
        )
        self.editable_route = EditableRoute.objects.create(
            name="Declaration primitives",
            route={
                "type": "FeatureCollection",
                "features": [
                    {"type": "Feature", "properties": {"featureType": "route_path"}, "geometry": {"type": "LineString", "coordinates": [[11.0, 60.0], [11.1, 60.1]]}},
                    {"type": "Feature", "properties": {"id": "wp-sp", "name": "SP", "pointType": "sp", "featureType": "route_waypoint", "width": 1852, "isTiming": True, "isPassing": True, "sequence": 0}, "geometry": {"type": "Point", "coordinates": [11.0, 60.0]}},
                    {"type": "Feature", "properties": {"id": "wp-mp", "name": "MP", "pointType": "tp", "featureType": "route_waypoint", "width": 1852, "isTiming": True, "isPassing": True, "sequence": 1}, "geometry": {"type": "Point", "coordinates": [11.1, 60.1]}},
                    {"type": "Feature", "properties": {"id": "wp-fp", "name": "FP", "pointType": "fp", "featureType": "route_waypoint", "width": 1852, "isTiming": True, "isPassing": True, "sequence": 2}, "geometry": {"type": "Point", "coordinates": [11.2, 60.2]}},
                    {"type": "Feature", "properties": {"id": "cat-1", "name": "A", "pointType": "tp", "featureType": "catalogue_turnpoint"}, "geometry": {"type": "Point", "coordinates": [11.2, 60.21]}},
                    {"type": "Feature", "properties": {"id": "cat-1b", "name": "B", "pointType": "tp", "featureType": "catalogue_turnpoint"}, "geometry": {"type": "Point", "coordinates": [11.22, 60.22]}},
                    {"type": "Feature", "properties": {"id": "cat-3", "name": "C", "pointType": "tp", "featureType": "catalogue_turnpoint"}, "geometry": {"type": "Point", "coordinates": [11.35, 60.35]}},
                    {"type": "Feature", "properties": {"id": "cat-4", "name": "D", "pointType": "tp", "featureType": "catalogue_turnpoint"}, "geometry": {"type": "Point", "coordinates": [11.45, 60.45]}},
                ],
            },
        )
        self.navigation_task.editable_route = self.editable_route
        self.navigation_task.save(update_fields=["editable_route"])

        team = Team.objects.create(
            crew=Crew.objects.create(member1=Person.objects.create(first_name="Pilot", last_name="One", email="pilot@example.com")),
            aeroplane=Aeroplane.objects.create(registration="LN-DECL"),
        )
        self.contest_team = ContestTeam.objects.create(contest=self.contest, team=team, air_speed=70)
        self.create_url = reverse("contestant_create", kwargs={"navigationtask_pk": self.navigation_task.pk})
        self.update_url = None

    def test_contract_navigation_form_does_not_expose_declared_sequence_fields(self):
        form = ContestantForm(navigation_task=self.navigation_task)
        self.assertNotIn("declared_before_mp_1", form.fields)
        self.assertNotIn("declared_before_mp_2", form.fields)
        self.assertNotIn("declared_after_mp_1", form.fields)
        self.assertNotIn("declared_after_mp_2", form.fields)

    def test_curve_navigation_form_does_not_expose_prediction_fields(self):
        curve_route = EditableRoute.objects.create(
            name="Curve declaration primitives",
            route={
                "type": "FeatureCollection",
                "features": [
                    {"type": "Feature", "properties": {"featureType": "route_path"}, "geometry": {"type": "LineString", "coordinates": [[11.0, 60.0], [11.1, 60.1]]}},
                    {"type": "Feature", "properties": {"id": "kt-1", "name": "KT1", "pointType": "tp", "featureType": "known_time_gate"}, "geometry": {"type": "Point", "coordinates": [11.2, 60.2]}},
                    {"type": "Feature", "properties": {"id": "hg-1", "name": "HG1", "pointType": "tp", "featureType": "hidden_gate"}, "geometry": {"type": "Point", "coordinates": [11.3, 60.3]}},
                ],
            },
        )
        self.navigation_task.task_subtype = CURVE_NAVIGATION_TIME_ESTIMATION
        self.navigation_task.editable_route = curve_route
        self.navigation_task.save(update_fields=["task_subtype", "editable_route"])
        form = ContestantForm(navigation_task=self.navigation_task)
        self.assertNotIn("known_time_gate_prediction_KT1", form.fields)

    def test_precision_navigation_form_does_not_expose_per_waypoint_prediction_fields(self):
        self.navigation_task.task_subtype = PRECISION_NAVIGATION
        self.navigation_task.save(update_fields=["task_subtype"])
        form = ContestantForm(navigation_task=self.navigation_task)
        self.assertNotIn("known_time_gate_prediction_SP", form.fields)
        self.assertNotIn("known_time_gate_prediction_TP1", form.fields)
        self.assertNotIn("known_time_gate_prediction_FP", form.fields)

    def test_create_view_persists_empty_contract_navigation_declaration_until_editor_is_used(self):
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
        if response.status_code != 302:
            self.fail(str(response.context["form"].errors))
        self.assertEqual(302, response.status_code)
        contestant = self.navigation_task.contestant_set.get(team=self.contest_team.team)
        self.assertEqual(contestant.contestanttaskconfiguration.declaration_payload, {})

    def test_create_view_does_not_render_progressive_slot_controls(self):
        self.client.force_login(self.user)
        response = self.client.get(self.create_url)
        self.assertEqual(200, response.status_code)
        self.assertNotContains(response, 'id="add-before-mp-slot"')
        self.assertNotContains(response, 'id="remove-before-mp-slot"')
        self.assertNotContains(response, 'id="add-after-mp-slot"')
        self.assertNotContains(response, 'id="remove-after-mp-slot"')
        self.assertNotContains(response, 'id="id_declared_before_mp_1"')
        self.assertNotContains(response, 'id="id_declared_after_mp_1"')

    def test_update_view_does_not_render_existing_slot_values(self):
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
        contestant = self.navigation_task.contestant_set.get(team=self.contest_team.team)
        update_url = reverse("contestant_update", kwargs={"pk": contestant.pk})
        response = self.client.get(update_url)
        self.assertNotContains(response, 'name="declared_before_mp_2"')
        self.assertNotContains(response, 'name="declared_after_mp_2"')

    def test_create_view_persists_empty_curve_navigation_predictions_until_editor_is_used(self):
        curve_route = EditableRoute.objects.create(
            name="Curve declaration save primitives",
            route={
                "type": "FeatureCollection",
                "features": [
                    {"type": "Feature", "properties": {"featureType": "route_path"}, "geometry": {"type": "LineString", "coordinates": [[11.0, 60.0], [11.1, 60.1]]}},
                    {"type": "Feature", "properties": {"id": "kt-1", "name": "KT1", "pointType": "tp", "featureType": "known_time_gate"}, "geometry": {"type": "Point", "coordinates": [11.2, 60.2]}},
                    {"type": "Feature", "properties": {"id": "hg-1", "name": "HG1", "pointType": "tp", "featureType": "hidden_gate"}, "geometry": {"type": "Point", "coordinates": [11.3, 60.3]}},
                ],
            },
        )
        self.navigation_task.task_subtype = CURVE_NAVIGATION_TIME_ESTIMATION
        self.navigation_task.editable_route = curve_route
        self.navigation_task.save(update_fields=["task_subtype", "editable_route"])

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
        contestant = self.navigation_task.contestant_set.get(team=self.contest_team.team)
        self.assertEqual(contestant.contestanttaskconfiguration.declaration_payload, {})

    def test_navigation_task_detail_shows_edit_declaration_link_for_contract_navigation(self):
        self.client.force_login(self.user)
        create_response = self.client.post(
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
        self.assertEqual(302, create_response.status_code)
        contestant = self.navigation_task.contestant_set.get(team=self.contest_team.team)

        detail_response = self.client.get(reverse("navigationtask_detail", kwargs={"pk": self.navigation_task.pk}))
        self.assertEqual(200, detail_response.status_code)
        self.assertContains(detail_response, "Edit declaration")
        self.assertContains(
            detail_response,
            f"/contestant-declaration/{self.contest.pk}/{self.navigation_task.pk}/{contestant.pk}",
        )

    def test_contract_navigation_compiler_requires_declared_t_seconds(self):
        from display.models import Contestant
        from display.services.contestant_task_compiler import ContestantTaskCompiler

        contestant = Contestant.objects.create(
            navigation_task=self.navigation_task,
            team=self.contest_team.team,
            takeoff_time=datetime.datetime(2026, 8, 1, 9, 55, tzinfo=datetime.timezone.utc),
            tracker_start_time=datetime.datetime(2026, 8, 1, 9, 45, tzinfo=datetime.timezone.utc),
            finished_by_time=datetime.datetime(2026, 8, 1, 11, 30, tzinfo=datetime.timezone.utc),
            contestant_number=1,
            minutes_to_starting_point=5,
            air_speed=70,
            wind_direction=0,
            wind_speed=0,
        )

        compiled = ContestantTaskCompiler(contestant).compile(
            declaration_payload={"declared_sequence": ["A", "MP", "C", "FP"]},
            force=True,
        )

        self.assertFalse(compiled.is_valid)
        self.assertIn("Contract navigation requires declared_t_seconds.", compiled.validation_errors)
