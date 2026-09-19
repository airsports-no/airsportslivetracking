"""
Turnpoint hunt (and precision/curve navigation) declarations record predicted gate times as
absolute timestamps, not offsets from takeoff. Once such a declaration compiles successfully,
Contestant.schedule_locked is set (ContestantTaskCompiler._lock_if_needed) so the automated
scheduler leaves the contestant alone - but nothing previously stopped a manual takeoff/finish
time edit from moving the schedule out from under an already-declared, now-stale predicted time.
These tests cover the fix: Contestant.clean() rejects such an edit unless the declared times still
fall inside the new window, ContestantTaskCompiler rejects declaring a time outside the current
window in the first place, and the new clear_declaration action is the only way to unlock a
schedule-locked contestant again.
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
    Route,
    Scorecard,
    Team,
)
from display.tests.test_curve_precision_navigation_declaration_ui import (
    CurvePrecisionNavigationDeclarationTestBase,
)
from display.utilities.cima_task_type_definitions import (
    KNOWN_CIRCUIT,
    LIMITED_FUEL_TURNPOINT_HUNT,
    PRECISION_NAVIGATION,
    TURNPOINT_HUNT,
)
from utilities.mock_utilities import TraccarMock


@patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
@patch("display.signals.get_traccar_instance", return_value=TraccarMock)
class TestTurnpointHuntScheduleLock(TestCase):
    task_subtype = TURNPOINT_HUNT

    def setUp(self):
        create_scorecards()
        self.user = get_user_model().objects.create(email="turnpoint-lock@example.com")
        Person.objects.create(first_name="Turnpoint", last_name="Lock", email=self.user.email)
        self.scorecard = Scorecard.get_originals().get(shortcut_name="FAI Precision")

        self.contest = Contest.objects.create(
            name="Turnpoint Hunt Lock Contest",
            time_zone="Europe/Oslo",
            start_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 8, 1, 17, 0, tzinfo=datetime.timezone.utc),
            location="60.0,11.0",
            created_by=self.user,
        )
        assign_perm("view_contest", self.user, self.contest)
        assign_perm("change_contest", self.user, self.contest)

        # No route backbone (no route_path feature) - matches the real shape of a 2.A6 route
        # (see turnpoint_hunt_structural_errors, route_compatibility.py), unlike
        # BaseTurnpointHuntContestantApiTest's fixture (NM.csv-derived, route_path present) which
        # is fine for that file's own tests since none of them assert is_valid.
        self.editable_route = EditableRoute.objects.create(
            name="Turnpoint lock primitives",
            route={
                "type": "FeatureCollection",
                "features": [
                    {"type": "Feature", "properties": {"id": "cat-1", "name": "A", "pointType": "tp", "featureType": "catalogue_turnpoint"}, "geometry": {"type": "Point", "coordinates": [11.2, 60.2]}},
                    {"type": "Feature", "properties": {"id": "kt-1", "name": "CP1", "pointType": "tp", "featureType": "known_time_gate"}, "geometry": {"type": "Point", "coordinates": [11.25, 60.25]}},
                    {"type": "Feature", "properties": {"id": "kt-2", "name": "CP2", "pointType": "tp", "featureType": "known_time_gate"}, "geometry": {"type": "Point", "coordinates": [11.35, 60.35]}},
                    {"type": "Feature", "properties": {"id": "kt-3", "name": "CP3", "pointType": "tp", "featureType": "known_time_gate"}, "geometry": {"type": "Point", "coordinates": [11.45, 60.45]}},
                ],
            },
        )
        self.navigation_task = NavigationTask.objects.create(
            name="Turnpoint Hunt Lock Task",
            contest=self.contest,
            route=Route.objects.create(name="Backbone-less Route", waypoints=[], takeoff_gates=[], landing_gates=[]),
            original_scorecard=self.scorecard,
            start_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 8, 1, 17, 0, tzinfo=datetime.timezone.utc),
            task_subtype=self.task_subtype,
        )
        self.navigation_task.editable_route = self.editable_route
        self.navigation_task.save(update_fields=["editable_route"])

        team = Team.objects.create(
            crew=Crew.objects.create(member1=Person.objects.create(first_name="Pilot", last_name="Lock", email="pilot-turnpoint-lock@example.com")),
            aeroplane=Aeroplane.objects.create(registration="LN-LOCK"),
        )
        self.contest_team = ContestTeam.objects.create(contest=self.contest, team=team, air_speed=70)
        self.client.force_login(self.user)

    def _detail_url(self, contestant):
        return reverse(
            "contestants-detail",
            kwargs={"contest_pk": self.contest.pk, "navigationtask_pk": self.navigation_task.pk, "pk": contestant.pk},
        )

    def _clear_declaration_url(self, contestant):
        return reverse(
            "contestants-clear-declaration",
            kwargs={"contest_pk": self.contest.pk, "navigationtask_pk": self.navigation_task.pk, "pk": contestant.pk},
        )

    def _create_contestant(self, declaration_payload=None):
        url = reverse(
            "contestants-list",
            kwargs={"contest_pk": self.contest.pk, "navigationtask_pk": self.navigation_task.pk},
        )
        payload = {
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
        }
        if declaration_payload is not None:
            payload["declaration_payload"] = declaration_payload
        with patch("display.viewsets._assert_can_reserve_task_slot"):
            response = self.client.post(url, payload, content_type="application/json")
        self.assertEqual(200, response.status_code, response.content)
        return self.navigation_task.contestant_set.get(team=self.contest_team.team)

    def _declaration_payload(self):
        return {
            "compulsory_point_times": {
                "CP1": "2026-08-01T10:07:00Z",
                "CP2": "2026-08-01T10:19:00Z",
                "CP3": "2026-08-01T10:32:00Z",
            },
            "declared_sequence": ["A", "CP1", "CP2", "CP3"],
        }

    def test_valid_declaration_locks_the_schedule(self, *_mocks):
        contestant = self._create_contestant(self._declaration_payload())
        config = contestant.contestanttaskconfiguration
        self.assertTrue(config.is_valid, config.validation_errors)
        self.assertTrue(contestant.schedule_locked)

    def test_takeoff_time_change_rejected_when_it_would_strand_a_declared_time(self, *_mocks):
        contestant = self._create_contestant(self._declaration_payload())
        # CP1/CP2/CP3 are declared at 10:07/10:19/10:32Z; pushing finished_by_time to 10:10Z
        # strands CP2/CP3 outside the new window.
        response = self.client.patch(
            self._detail_url(contestant),
            {"finished_by_time": "2026-08-01T10:10:00Z"},
            content_type="application/json",
        )
        self.assertEqual(400, response.status_code, response.content)
        self.assertIn("Clear the declaration", str(response.content))
        contestant.refresh_from_db()
        self.assertEqual(contestant.finished_by_time, datetime.datetime(2026, 8, 1, 11, 30, tzinfo=datetime.timezone.utc))

    def test_takeoff_time_change_allowed_when_declared_times_stay_within_window(self, *_mocks):
        contestant = self._create_contestant(self._declaration_payload())
        # Widening the window (later finish) keeps every declared time inside it.
        response = self.client.patch(
            self._detail_url(contestant),
            {"finished_by_time": "2026-08-01T12:00:00Z"},
            content_type="application/json",
        )
        self.assertEqual(200, response.status_code, response.content)
        contestant.refresh_from_db()
        self.assertEqual(contestant.finished_by_time, datetime.datetime(2026, 8, 1, 12, 0, tzinfo=datetime.timezone.utc))

    def test_clear_declaration_unlocks_the_schedule(self, *_mocks):
        contestant = self._create_contestant(self._declaration_payload())
        self.assertTrue(contestant.schedule_locked)

        response = self.client.post(self._clear_declaration_url(contestant))
        self.assertEqual(200, response.status_code, response.content)

        contestant.refresh_from_db()
        self.assertFalse(contestant.schedule_locked)
        self.assertEqual(contestant.contestanttaskconfiguration.declaration_payload, {})
        self.assertFalse(contestant.contestanttaskconfiguration.is_valid)

        # Now the previously-rejected edit succeeds.
        response = self.client.patch(
            self._detail_url(contestant),
            {"finished_by_time": "2026-08-01T10:10:00Z"},
            content_type="application/json",
        )
        self.assertEqual(200, response.status_code, response.content)

    def test_declaring_a_compulsory_point_time_outside_the_flight_window_is_rejected(self, *_mocks):
        # No declaration yet, so nothing is locked - the window check runs on the PATCH below
        # against the create-time window instead.
        contestant = self._create_contestant()

        response = self.client.patch(
            self._detail_url(contestant),
            # 12:00Z is after finished_by_time (11:30Z).
            {"declaration_payload": {"compulsory_point_times": {"CP1": "2026-08-01T12:00:00Z"}}},
            content_type="application/json",
        )
        self.assertEqual(400, response.status_code, response.content)
        contestant.refresh_from_db()
        self.assertEqual(contestant.contestanttaskconfiguration.declaration_payload, {})


class TestLimitedFuelTurnpointHuntDeclarationOptional(TestTurnpointHuntScheduleLock):
    """
    Unlike plain turnpoint hunt, a limited fuel contestant may not have enough fuel for any of
    the three compulsory points - TurnpointHuntStrategy.validate_declaration never errors on an
    empty declaration for this subtype (minimum_required=0), so it must never be locked or
    flagged as missing a required declaration for having declared nothing.
    """

    task_subtype = LIMITED_FUEL_TURNPOINT_HUNT

    def test_empty_declaration_is_valid_unlocked_and_not_flagged_as_required(self, *_mocks):
        contestant = self._create_contestant()
        config = contestant.contestanttaskconfiguration
        self.assertTrue(config.is_valid, config.validation_errors)
        self.assertFalse(contestant.schedule_locked)

        response = self.client.get(self._detail_url(contestant))
        self.assertEqual(200, response.status_code)
        self.assertEqual(
            response.json()["declaration_status"],
            {"required": False, "complete": True, "errors": []},
        )

        # Nothing was ever declared, so the takeoff/finish window is free to move.
        response = self.client.patch(
            self._detail_url(contestant),
            {"finished_by_time": "2026-08-01T10:00:00Z"},
            content_type="application/json",
        )
        self.assertEqual(200, response.status_code, response.content)


class TestPrecisionNavigationScheduleLock(CurvePrecisionNavigationDeclarationTestBase):
    task_subtype = PRECISION_NAVIGATION

    def _clear_declaration_url(self, contestant):
        return reverse(
            "contestants-clear-declaration",
            kwargs={"contest_pk": self.contest.pk, "navigationtask_pk": self.navigation_task.pk, "pk": contestant.pk},
        )

    def test_valid_declaration_locks_the_schedule_and_blocks_a_stranding_edit(self):
        contestant = self._create_contestant()
        waypoint_names = [wp.name for wp in self.route.waypoints]

        response = self.client.patch(
            self._contestant_detail_url(contestant),
            {"declaration_payload": {"known_time_gate_predictions": {name: "2026-08-01T10:00:00Z" for name in waypoint_names}}},
            content_type="application/json",
        )
        self.assertEqual(200, response.status_code, response.content)
        contestant.refresh_from_db()
        self.assertTrue(contestant.schedule_locked)

        # finished_by_time was 11:30Z; moving it to 09:58Z strands the 10:00Z predictions.
        response = self.client.patch(
            self._contestant_detail_url(contestant),
            {"finished_by_time": "2026-08-01T09:58:00Z"},
            content_type="application/json",
        )
        self.assertEqual(400, response.status_code, response.content)

        response = self.client.post(self._clear_declaration_url(contestant))
        self.assertEqual(200, response.status_code, response.content)
        contestant.refresh_from_db()
        self.assertFalse(contestant.schedule_locked)

        response = self.client.patch(
            self._contestant_detail_url(contestant),
            {"finished_by_time": "2026-08-01T09:58:00Z"},
            content_type="application/json",
        )
        self.assertEqual(200, response.status_code, response.content)

    def test_declaring_a_prediction_outside_the_flight_window_is_rejected(self):
        contestant = self._create_contestant()
        waypoint_names = [wp.name for wp in self.route.waypoints]

        response = self.client.patch(
            self._contestant_detail_url(contestant),
            # finished_by_time is 11:30Z.
            {"declaration_payload": {"known_time_gate_predictions": {waypoint_names[0]: "2026-08-01T12:00:00Z"}}},
            content_type="application/json",
        )
        self.assertEqual(400, response.status_code, response.content)
        contestant.refresh_from_db()
        self.assertEqual(contestant.contestanttaskconfiguration.declaration_payload, {})


class TestKnownCircuitScheduleLock(CurvePrecisionNavigationDeclarationTestBase):
    """
    Known circuit's turnpoint_time_overrides is optional (most points are speed-derived and move
    with the schedule automatically) - so unlike turnpoint hunt/precision/curve nav, a known
    circuit contestant should only be locked out of a schedule edit once they've actually
    overridden a point with an absolute time, not merely for having a valid (possibly
    override-free) declaration.
    """

    task_subtype = KNOWN_CIRCUIT

    def _clear_declaration_url(self, contestant):
        return reverse(
            "contestants-clear-declaration",
            kwargs={"contest_pk": self.contest.pk, "navigationtask_pk": self.navigation_task.pk, "pk": contestant.pk},
        )

    def test_declaration_without_overrides_does_not_lock_the_schedule(self):
        contestant = self._create_contestant()
        response = self.client.patch(
            self._contestant_detail_url(contestant),
            {"declaration_payload": {}},
            content_type="application/json",
        )
        self.assertEqual(200, response.status_code, response.content)
        contestant.refresh_from_db()

        # No override was ever declared, so the takeoff/finish window is free to move.
        response = self.client.patch(
            self._contestant_detail_url(contestant),
            {"finished_by_time": "2026-08-01T09:58:00Z"},
            content_type="application/json",
        )
        self.assertEqual(200, response.status_code, response.content)

    def test_overriding_a_point_locks_the_schedule_and_blocks_a_stranding_edit(self):
        contestant = self._create_contestant()
        waypoint_name = self.route.waypoints[0].name

        response = self.client.patch(
            self._contestant_detail_url(contestant),
            {"declaration_payload": {"turnpoint_time_overrides": {waypoint_name: "2026-08-01T10:00:00Z"}}},
            content_type="application/json",
        )
        self.assertEqual(200, response.status_code, response.content)

        # finished_by_time was 11:30Z; moving it to 09:58Z strands the 10:00Z override.
        response = self.client.patch(
            self._contestant_detail_url(contestant),
            {"finished_by_time": "2026-08-01T09:58:00Z"},
            content_type="application/json",
        )
        self.assertEqual(400, response.status_code, response.content)

        response = self.client.post(self._clear_declaration_url(contestant))
        self.assertEqual(200, response.status_code, response.content)

        response = self.client.patch(
            self._contestant_detail_url(contestant),
            {"finished_by_time": "2026-08-01T09:58:00Z"},
            content_type="application/json",
        )
        self.assertEqual(200, response.status_code, response.content)

    def test_overriding_a_point_outside_the_flight_window_is_rejected(self):
        contestant = self._create_contestant()
        waypoint_name = self.route.waypoints[0].name

        response = self.client.patch(
            self._contestant_detail_url(contestant),
            # finished_by_time is 11:30Z.
            {"declaration_payload": {"turnpoint_time_overrides": {waypoint_name: "2026-08-01T12:00:00Z"}}},
            content_type="application/json",
        )
        self.assertEqual(400, response.status_code, response.content)
        contestant.refresh_from_db()
        self.assertEqual(contestant.contestanttaskconfiguration.declaration_payload, {})
