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
from django.test import SimpleTestCase, TestCase
from types import SimpleNamespace
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
from display.services.contestant_task_compiler import ContestantTaskCompiler, _join_names
from display.utilities.task_types import CURVE_NAVIGATION_TIME_ESTIMATION, PRECISION_NAVIGATION
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
        if self.task_subtype == CURVE_NAVIGATION_TIME_ESTIMATION:
            # 2.A1 needs a curved leg. Only the stored editable route gets it: the precision route above is what the
            # declaration is compiled against.
            last_waypoint = self.editable_route.get_ordered_track_waypoints()[-1]
            previous_waypoint = self.editable_route.get_ordered_track_waypoints()[-2]
            last_waypoint["properties"].update(
                segmentType="curved",
                controlLat=previous_waypoint["geometry"]["coordinates"][1],
                controlLng=last_waypoint["geometry"]["coordinates"][0],
            )
            self.editable_route.save()

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
        # 2.A2: the visible turn points and the finish point, not the start point (or hidden gates)
        expected = [wp.name for wp in self.route.waypoints if wp.type in ("tp", "fp")]
        self.assertEqual(payload["expected_prediction_names"], expected)
        self.assertNotIn(self.route.waypoints[0].name, payload["expected_prediction_names"])
        self.assertEqual(payload["expected_prediction_names"][-1], self.route.waypoints[-1].name)
        self.assertEqual(payload["known_time_gate_predictions"], {})

    def test_declaration_status_flags_missing_declaration_as_required(self):
        contestant = self._create_contestant()
        detail_response = self.client.get(
            reverse("navigationtasks-detail", kwargs={"contest_pk": self.contest.pk, "pk": self.navigation_task.pk})
        )
        contestant_payload = next(c for c in detail_response.json()["contestant_set"] if c["id"] == contestant.pk)
        status = contestant_payload["declaration_status"]
        self.assertEqual((True, False), (status["required"], status["complete"]))
        expected_names = [wp.name for wp in self.route.waypoints if wp.type in ("tp", "fp")]
        self.assertEqual([f"Give a time for {_join_names(expected_names)}."], status["errors"])

    def test_declaring_the_turn_points_and_the_finish_point_only_makes_declaration_valid(self):
        contestant = self._create_contestant()
        names = [wp.name for wp in self.route.waypoints if wp.type in ("tp", "fp")]
        self.assertGreaterEqual(len(names), 2)

        response = self.client.patch(
            self._contestant_detail_url(contestant),
            {"declaration_payload": {"known_time_gate_predictions": {name: "2026-08-01T10:00:00Z" for name in names}}},
            content_type="application/json",
        )
        self.assertEqual(200, response.status_code, response.content)
        contestant.refresh_from_db()
        self.assertTrue(contestant.contestanttaskconfiguration.is_valid)
        self.assertEqual(contestant.contestanttaskconfiguration.validation_errors, [])

    def test_times_of_the_start_point_and_hidden_gates_are_ignored(self):
        contestant = self._create_contestant()
        route_names = [wp.name for wp in self.route.waypoints]
        expected_names = [wp.name for wp in self.route.waypoints if wp.type in ("tp", "fp")]
        extras = [name for name in route_names if name not in expected_names]
        self.assertIn(route_names[0], extras)
        sentinel = "2026-08-01T11:11:11+00:00"
        declared = {name: sentinel for name in extras}
        declared.update({name: f"2026-08-01T10:{20 + index}:00+00:00" for index, name in enumerate(expected_names)})

        response = self.client.patch(
            self._contestant_detail_url(contestant),
            {"declaration_payload": {"known_time_gate_predictions": declared}},
            content_type="application/json",
        )
        self.assertEqual(200, response.status_code, response.content)
        configuration = self.navigation_task.contestant_set.get(pk=contestant.pk).contestanttaskconfiguration
        self.assertTrue(configuration.is_valid, configuration.validation_errors)
        payload = configuration.compiled_effective_route_payload
        self.assertEqual(sorted(payload["known_time_gate_predictions"]), sorted(expected_names))
        gate_times = configuration.compiled_gate_times_payload
        for name in extras:
            self.assertNotEqual(gate_times[name], sentinel, f"{name} took a declared time")
        for name in expected_names:
            self.assertEqual(gate_times[name], declared[name])

    def test_an_older_declaration_with_start_point_and_hidden_gate_times_still_compiles(self):
        # Declarations made before 2.A2 asked for the turn points and the finish only carry a time for every waypoint;
        # stored as they are, they must not break.
        contestant = self._create_contestant()
        route_names = [wp.name for wp in self.route.waypoints]
        scheduled = ContestantTaskCompiler(contestant).compile(force=True).compiled_gate_times_payload
        declared = {name: "2026-08-01T10:00:00+00:00" for name in route_names}

        configuration = ContestantTaskCompiler(contestant).compile(
            declaration_payload={"known_time_gate_predictions": declared}, force=True
        )

        self.assertTrue(configuration.is_valid, configuration.validation_errors)
        self.assertEqual(configuration.compiled_gate_times_payload[route_names[0]], scheduled[route_names[0]])
        self.assertEqual(configuration.compiled_gate_times_payload[route_names[-1]], declared[route_names[-1]])

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
        status = contestant_payload["declaration_status"]
        self.assertEqual((True, True, []), (status["required"], status["complete"], status["errors"]))

    def test_declaring_predictions_for_only_some_waypoints_stays_invalid(self):
        contestant = self._create_contestant()
        expected_names = [wp.name for wp in self.route.waypoints if wp.type in ("tp", "fp")]

        response = self.client.patch(
            self._contestant_detail_url(contestant),
            {"declaration_payload": {"known_time_gate_predictions": {expected_names[0]: "2026-08-01T10:00:00Z"}}},
            content_type="application/json",
        )
        self.assertEqual(200, response.status_code, response.content)
        contestant.refresh_from_db()
        self.assertFalse(contestant.contestanttaskconfiguration.is_valid)
        self.assertIn(
            "Give a time for",
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
        status = contestant_payload["declaration_status"]
        self.assertEqual((True, True, []), (status["required"], status["complete"], status["errors"]))

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

    def _update_details_url(self):
        return reverse(
            "navigationtasks-update-details", kwargs={"contest_pk": self.contest.pk, "pk": self.navigation_task.pk}
        )

    def test_tmax_saved_through_the_update_details_action_reaches_the_declaration_check(self):
        contestant = self._create_contestant()
        response = self.client.post(
            self._update_details_url(), {"curve_navigation_tmax_seconds": 60}, content_type="application/json"
        )
        self.assertEqual(200, response.status_code, response.content)
        self.navigation_task.refresh_from_db()
        self.assertEqual({"curve_navigation_tmax_seconds": 60}, self.navigation_task.task_config)

        response = self.client.patch(
            self._contestant_detail_url(contestant),
            # SP at 10:00, FP declared 30 minutes later
            {"declaration_payload": {"known_time_gate_predictions": {"FP": "2026-08-01T10:30:00Z"}}},
            content_type="application/json",
        )
        self.assertEqual(200, response.status_code, response.content)
        contestant.refresh_from_db()
        self.assertFalse(contestant.contestanttaskconfiguration.is_valid)
        self.assertIn("Tmax", " ".join(contestant.contestanttaskconfiguration.validation_errors))

    def test_an_empty_tmax_removes_the_limit_and_keeps_the_other_settings(self):
        self.navigation_task.task_config = {"curve_navigation_tmax_seconds": 60, "other": 1}
        self.navigation_task.save(update_fields=["task_config"])
        self.client.force_login(self.user)
        response = self.client.post(
            self._update_details_url(), {"curve_navigation_tmax_seconds": None}, content_type="application/json"
        )
        self.assertEqual(200, response.status_code, response.content)
        self.navigation_task.refresh_from_db()
        self.assertEqual({"other": 1}, self.navigation_task.task_config)

    def test_tmax_is_left_alone_when_the_update_does_not_mention_it(self):
        self.navigation_task.task_config = {"curve_navigation_tmax_seconds": 600}
        self.navigation_task.save(update_fields=["task_config"])
        self.client.force_login(self.user)
        response = self.client.post(self._update_details_url(), {"name": "Renamed"}, content_type="application/json")
        self.assertEqual(200, response.status_code, response.content)
        self.navigation_task.refresh_from_db()
        self.assertEqual({"curve_navigation_tmax_seconds": 600}, self.navigation_task.task_config)

    def test_a_task_of_another_type_does_not_take_a_tmax(self):
        self.navigation_task.task_subtype = PRECISION_NAVIGATION
        self.navigation_task.save(update_fields=["task_subtype"])
        self.client.force_login(self.user)
        response = self.client.post(
            self._update_details_url(), {"curve_navigation_tmax_seconds": 60}, content_type="application/json"
        )
        self.assertEqual(400, response.status_code)
        self.navigation_task.refresh_from_db()
        self.assertFalse((self.navigation_task.task_config or {}).get("curve_navigation_tmax_seconds"))


class PrecisionNavigationGateTimeInterpolationTest(SimpleTestCase):
    """2.A2: the organisation estimates the hidden gate times between the declared times."""

    START = datetime.datetime(2026, 8, 1, 10, 0, tzinfo=datetime.timezone.utc)

    def compiler(self, names):
        waypoints = [SimpleNamespace(name=name) for name in names]
        route = SimpleNamespace(waypoints=waypoints)
        contestant = SimpleNamespace(navigation_task=SimpleNamespace(route=route))
        return ContestantTaskCompiler(contestant)

    def scheduled(self, minutes_by_name):
        return {name: (self.START + datetime.timedelta(minutes=minutes)).isoformat() for name, minutes in minutes_by_name.items()}

    def at(self, minutes):
        return self.START + datetime.timedelta(minutes=minutes)

    def test_the_declared_times_are_kept_and_hidden_gates_follow_their_share_of_the_leg(self):
        # SP at 0, hidden gate a quarter of the way to TP1 (scheduled at 1 of 4 minutes), TP1 at 4, HG2 at 6 of 4..10
        scheduled = self.scheduled({"SP": 0, "HG1": 1, "TP1": 4, "HG2": 6, "FP": 10})
        declared = {"TP1": self.at(6), "FP": self.at(14)}

        times = self.compiler(["SP", "HG1", "TP1", "HG2", "FP"])._interpolate_gate_times(scheduled, declared)

        self.assertEqual(times["SP"], self.at(0))
        self.assertEqual(times["HG1"], self.at(1.5))
        self.assertEqual(times["TP1"], self.at(6))
        self.assertEqual(times["HG2"], self.at(6 + 8 * 2 / 6))
        self.assertEqual(times["FP"], self.at(14))

    def test_declaring_the_scheduled_times_gives_the_scheduled_times(self):
        scheduled = self.scheduled({"SP": 0, "HG1": 1, "TP1": 4, "HG2": 6, "FP": 10})
        declared = {"TP1": self.at(4), "FP": self.at(10)}

        times = self.compiler(["SP", "HG1", "TP1", "HG2", "FP"])._interpolate_gate_times(scheduled, declared)

        self.assertEqual({name: times[name] for name in scheduled}, {name: self.at(m) for name, m in {"SP": 0, "HG1": 1, "TP1": 4, "HG2": 6, "FP": 10}.items()})

    def test_gates_after_the_last_declared_point_are_left_to_the_schedule(self):
        scheduled = self.scheduled({"SP": 0, "TP1": 4, "HG1": 6, "FP": 10})

        times = self.compiler(["SP", "TP1", "HG1", "FP"])._interpolate_gate_times(scheduled, {"TP1": self.at(5)})

        self.assertNotIn("HG1", times)

    def test_interpolated_times_are_whole_seconds(self):
        scheduled = self.scheduled({"SP": 0, "HG1": 1, "FP": 3})

        times = self.compiler(["SP", "HG1", "FP"])._interpolate_gate_times(scheduled, {"FP": self.at(3.01)})

        self.assertEqual(times["HG1"].microsecond, 0)
