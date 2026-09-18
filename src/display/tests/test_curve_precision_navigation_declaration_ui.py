"""
Curve/precision navigation had a real dead-end: ContestantList.tsx's declaration_status highlight
correctly flagged these contestants as missing a required declaration, but there was no editor UI
to actually clear it (ContestantDeclarationPage.tsx only handled turnpoint_hunt/limited_fuel_
turnpoint_hunt/contract_navigation_time_controls/known_circuit, and supportsDeclarationEditing
didn't even show the "Edit declaration" link for these two subtypes). These tests cover the REST
side of closing that gap - the frontend form was added to ContestantDeclarationPage.tsx, this
confirms the REST contract it depends on (compiled_effective_route_payload.waypoint_names/
expected_prediction_names, and saving known_time_gate_predictions via PATCH) already worked
correctly without any backend change.
"""

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
from display.utilities.cima_task_type_definitions import CURVE_NAVIGATION_TIME_ESTIMATION, PRECISION_NAVIGATION
from utilities.mock_utilities import TraccarMock


class CurvePrecisionNavigationDeclarationTestBase(TestCase):
    task_subtype = None

    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, *args):
        create_scorecards()
        self.user = get_user_model().objects.create(email=f"{self.task_subtype}-organizer@example.com")
        Person.objects.create(first_name="Organizer", last_name="User", email=self.user.email)
        self.scorecard = Scorecard.get_originals().get(shortcut_name="FAI Precision")
        with open("display/tests/NM.csv", "r") as file:
            self.editable_route, _ = EditableRoute.create_from_csv(f"{self.task_subtype} declaration UI", file.readlines()[1:])
            self.route = self.editable_route.create_precision_route(True, self.scorecard)

        self.contest = Contest.objects.create(
            name=f"{self.task_subtype} Declaration Contest",
            time_zone="Europe/Oslo",
            start_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 8, 1, 17, 0, tzinfo=datetime.timezone.utc),
            location="60.0,11.0",
            created_by=self.user,
        )
        assign_perm("view_contest", self.user, self.contest)
        assign_perm("change_contest", self.user, self.contest)

        self.navigation_task = NavigationTask.create(
            name=f"{self.task_subtype} Declaration Task",
            contest=self.contest,
            route=self.route,
            original_scorecard=self.scorecard,
            start_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 8, 1, 17, 0, tzinfo=datetime.timezone.utc),
            task_subtype=self.task_subtype,
        )
        self.navigation_task.editable_route = self.editable_route
        self.navigation_task.save(update_fields=["editable_route"])
        team = Team.objects.create(
            crew=Crew.objects.create(member1=Person.objects.create(first_name="Pilot", last_name="One", email=f"pilot-{self.task_subtype}@example.com")),
            aeroplane=Aeroplane.objects.create(registration="LN-DECL"),
        )
        self.contest_team = ContestTeam.objects.create(contest=self.contest, team=team, air_speed=70)
        self.create_url = reverse(
            "contestants-list", kwargs={"contest_pk": self.contest.pk, "navigationtask_pk": self.navigation_task.pk}
        )

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
        if response.status_code != 200:
            self.fail(str(response.json()))
        return self.navigation_task.contestant_set.get(team=self.contest_team.team)

    def _contestant_detail_url(self, contestant):
        return reverse(
            "contestants-detail",
            kwargs={"contest_pk": self.contest.pk, "navigationtask_pk": self.navigation_task.pk, "pk": contestant.pk},
        )


class TestPrecisionNavigationDeclaration(CurvePrecisionNavigationDeclarationTestBase):
    task_subtype = PRECISION_NAVIGATION

    def test_compiled_payload_exposes_expected_prediction_names_before_any_declaration(self):
        contestant = self._create_contestant()
        response = self.client.get(self._contestant_detail_url(contestant))
        self.assertEqual(200, response.status_code)
        payload = response.json()["compiled_effective_route_payload"]
        self.assertTrue(payload["waypoint_names"])
        self.assertEqual(payload["expected_prediction_names"], payload["waypoint_names"])
        self.assertEqual(payload["known_time_gate_predictions"], {})

    def test_declaration_status_flags_missing_declaration_as_required(self):
        contestant = self._create_contestant()
        detail_response = self.client.get(
            reverse("navigationtasks-detail", kwargs={"contest_pk": self.contest.pk, "pk": self.navigation_task.pk})
        )
        contestant_payload = next(c for c in detail_response.json()["contestant_set"] if c["id"] == contestant.pk)
        self.assertEqual(contestant_payload["declaration_status"], {"required": True, "complete": False})

    def test_declaring_predictions_for_every_waypoint_makes_declaration_valid(self):
        contestant = self._create_contestant()
        waypoint_names = self.route.waypoints
        waypoint_names = [wp.name for wp in waypoint_names]

        response = self.client.patch(
            self._contestant_detail_url(contestant),
            {"declaration_payload": {"known_time_gate_predictions": {name: "2026-08-01T10:00:00Z" for name in waypoint_names}}},
            content_type="application/json",
        )
        self.assertEqual(200, response.status_code, response.content)
        contestant.refresh_from_db()
        self.assertTrue(contestant.contestanttaskconfiguration.is_valid)

        detail_response = self.client.get(
            reverse("navigationtasks-detail", kwargs={"contest_pk": self.contest.pk, "pk": self.navigation_task.pk})
        )
        contestant_payload = next(c for c in detail_response.json()["contestant_set"] if c["id"] == contestant.pk)
        self.assertEqual(contestant_payload["declaration_status"], {"required": True, "complete": True})

    def test_declaring_predictions_for_only_some_waypoints_stays_invalid(self):
        contestant = self._create_contestant()
        waypoint_names = [wp.name for wp in self.route.waypoints]

        response = self.client.patch(
            self._contestant_detail_url(contestant),
            {"declaration_payload": {"known_time_gate_predictions": {waypoint_names[0]: "2026-08-01T10:00:00Z"}}},
            content_type="application/json",
        )
        self.assertEqual(200, response.status_code, response.content)
        contestant.refresh_from_db()
        self.assertFalse(contestant.contestanttaskconfiguration.is_valid)
        self.assertIn(
            "Missing precision navigation predictions",
            " ".join(contestant.contestanttaskconfiguration.validation_errors),
        )


class TestCurveNavigationDeclaration(CurvePrecisionNavigationDeclarationTestBase):
    task_subtype = CURVE_NAVIGATION_TIME_ESTIMATION

    def test_declaring_a_single_prediction_is_sufficient(self):
        contestant = self._create_contestant()
        waypoint_names = [wp.name for wp in self.route.waypoints]

        response = self.client.patch(
            self._contestant_detail_url(contestant),
            {"declaration_payload": {"known_time_gate_predictions": {waypoint_names[-1]: "2026-08-01T10:00:00Z"}}},
            content_type="application/json",
        )
        self.assertEqual(200, response.status_code, response.content)
        contestant.refresh_from_db()
        self.assertTrue(contestant.contestanttaskconfiguration.is_valid)

    def test_declaration_status_becomes_complete_once_any_prediction_is_declared(self):
        contestant = self._create_contestant()
        waypoint_names = [wp.name for wp in self.route.waypoints]

        self.client.patch(
            self._contestant_detail_url(contestant),
            {"declaration_payload": {"known_time_gate_predictions": {waypoint_names[-1]: "2026-08-01T10:00:00Z"}}},
            content_type="application/json",
        )

        detail_response = self.client.get(
            reverse("navigationtasks-detail", kwargs={"contest_pk": self.contest.pk, "pk": self.navigation_task.pk})
        )
        contestant_payload = next(c for c in detail_response.json()["contestant_set"] if c["id"] == contestant.pk)
        self.assertEqual(contestant_payload["declaration_status"], {"required": True, "complete": True})

    def test_declaration_rejected_beyond_tmax(self):
        self.navigation_task.task_config = {"curve_navigation_tmax_seconds": 60}
        self.navigation_task.save(update_fields=["task_config"])
        contestant = self._create_contestant()

        response = self.client.patch(
            self._contestant_detail_url(contestant),
            # takeoff_time 09:55 + minutes_to_starting_point 5 = SP at 10:00; FP declared here is
            # 30 minutes later, well beyond the 60-second Tmax configured above.
            {"declaration_payload": {"known_time_gate_predictions": {"FP": "2026-08-01T10:30:00Z"}}},
            content_type="application/json",
        )
        self.assertEqual(200, response.status_code, response.content)
        contestant.refresh_from_db()
        self.assertFalse(contestant.contestanttaskconfiguration.is_valid)
        self.assertIn("Tmax", " ".join(contestant.contestanttaskconfiguration.validation_errors))
