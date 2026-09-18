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
)
from display.utilities.cima_task_type_definitions import CONTRACT_NAVIGATION_TIME_CONTROLS, CURVE_NAVIGATION_TIME_ESTIMATION
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
        # ContestantCreateView/contestant_create (classic) was retired in favour of the REST
        # contestants-list create action (ContestantFormModal, React) - see the
        # navigation_task_detail_spa_migration project memory.
        self.create_url = reverse(
            "contestants-list", kwargs={"contest_pk": self.contest.pk, "navigationtask_pk": self.navigation_task.pk}
        )

    def test_create_rest_action_leaves_contract_navigation_declaration_incomplete_until_editor_is_used(self):
        # Unlike the retired classic ContestantCreateView (which called
        # ContestantTaskCompiler.compile() directly with no declaration_payload, leaving it {}),
        # the REST create action always runs build_declaration_payload_from_input first (see
        # contestant_persistence.py's _compile_contestant_configuration) - for contract
        # navigation that unconditionally synthesizes a minimal declared_sequence of ["MP", "FP"]
        # even with no input, but still without declared_t_seconds, so the configuration remains
        # invalid/incomplete until the dedicated declaration editor supplies a real one.
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
        if response.status_code != 200:
            self.fail(str(response.json()))
        contestant = self.navigation_task.contestant_set.get(team=self.contest_team.team)
        self.assertEqual(contestant.contestanttaskconfiguration.declaration_payload, {"declared_sequence": ["MP", "FP"]})
        self.assertFalse(contestant.contestanttaskconfiguration.is_valid)

    def test_contestant_rest_payload_flags_missing_declaration_for_contract_navigation(self):
        # ContestantList.tsx highlights a contestant's team name when declaration_status.required
        # is true but declaration_status.complete is false - a regular ANR task never sets
        # required, but contract navigation (like every other CIMA task type whose
        # ContestantTaskCompilerStrategy actually validates a declaration) does.
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
        self.assertEqual(200, create_response.status_code, create_response.content)

        detail_response = self.client.get(
            reverse("navigationtasks-detail", kwargs={"contest_pk": self.contest.pk, "pk": self.navigation_task.pk})
        )
        contestant_payload = detail_response.json()["contestant_set"][0]
        self.assertEqual(
            contestant_payload["declaration_status"],
            {"required": True, "complete": False, "errors": ["Contract navigation requires declared_t_seconds."]},
        )

    def test_create_view_persists_empty_curve_navigation_predictions_until_editor_is_used(self):
        curve_route = EditableRoute.objects.create(
            name="Curve declaration save primitives",
            route={
                "type": "FeatureCollection",
                "features": [
                    {"type": "Feature", "properties": {"featureType": "route_path"}, "geometry": {"type": "LineString", "coordinates": [[11.0, 60.0], [11.1, 60.1]]}},
                    {"type": "Feature", "properties": {"id": "kt-1", "name": "KT1", "pointType": "tp", "featureType": "known_time_gate"}, "geometry": {"type": "Point", "coordinates": [11.2, 60.2]}},
                    {"type": "Feature", "properties": {"id": "hg-1", "name": "HG1", "pointType": "secret", "featureType": "route_waypoint", "width": 1852, "isTiming": False, "isPassing": True}, "geometry": {"type": "Point", "coordinates": [11.3, 60.3]}},
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
        self.assertEqual(200, response.status_code, response.content)
        contestant = self.navigation_task.contestant_set.get(team=self.contest_team.team)
        self.assertEqual(contestant.contestanttaskconfiguration.declaration_payload, {})

    def test_navigation_task_rest_payload_carries_task_subtype_for_contract_navigation(self):
        # NavigationTaskDetailPage (React) shows an "Edit declaration" link/CONTESTANT_DECLARATION
        # route for a contestant whenever task_subtype is one of the declaration-editable
        # subtypes (see ContestantActionsMenu.tsx's supportsDeclarationEditing) - that decision is
        # made client-side, so this test can only confirm the REST payload it depends on
        # (task_subtype) is actually present and correct; the classic navigationtask_detail.html
        # page this test used to check (via its rendered "Edit declaration" link) was removed in
        # Slice 4 of the navigation-task-detail-spa-migration.
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
        self.assertEqual(200, create_response.status_code, create_response.content)
        contestant = self.navigation_task.contestant_set.get(team=self.contest_team.team)

        detail_response = self.client.get(
            reverse("navigationtasks-detail", kwargs={"contest_pk": self.contest.pk, "pk": self.navigation_task.pk})
        )
        self.assertEqual(200, detail_response.status_code)
        self.assertEqual(detail_response.json()["task_subtype"], CONTRACT_NAVIGATION_TIME_CONTROLS)
        self.assertTrue(
            any(c["id"] == contestant.pk for c in detail_response.json()["contestant_set"]),
            "the created contestant should appear in the navigation task's contestant_set",
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
