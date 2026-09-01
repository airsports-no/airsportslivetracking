"""End-to-end regression test for 2.A7 Circle scoring.

Before the CircleStrategy/effective-route fix, a properly authored circle
task (EditableRoute containing only the four circle markers, no route
backbone) compiled to an EMPTY Route.waypoints list. That made
GateCalculator.create_gates() produce zero gates, so no GatePassedEvent was
ever emitted, so CircleCalculator.on_gate_passed (its only real scoring
entry point) was unreachable in production - despite CircleCalculator's own
unit tests (test_circle_calculator.py) passing, because they call
on_gate_passed directly and never exercise gate creation.

This test builds the task the way the wizard/serialiser actually does
(EditableRoute.create_route(..., task_subtype=CIRCLE)) and drives a
synthetic track through the real Orchestrator, so it fails if that pipeline
ever breaks again.
"""

import datetime
import math
from queue import Queue
from unittest.mock import MagicMock, patch

from django.test import TestCase

from display.calculators.calculator_factory import calculator_factory
from display.calculators.gate_calculator import GateCalculator
from display.default_scorecards.create_scorecards import create_scorecards
from display.flight_order_and_maps.effective_route_rendering import get_effective_route_waypoints
from display.models import (
    INFORMATION,
    Aeroplane,
    Contest,
    Contestant,
    Crew,
    EditableRoute,
    NavigationTask,
    Person,
    Scorecard,
    Team,
)
from display.services.contestant_task_compiler import ContestantTaskCompiler
from display.utilities.cima_task_type_definitions import CIRCLE
from display.utilities.coordinate_utilities import project_position_lat_lon
from display.utilities.navigation_task_type_definitions import PRECISION
from utilities.mock_utilities import TraccarMock

CENTER_LAT = 59.895825678413914
CENTER_LON = 10.624465942382812
TRUE_RADIUS_M = 500.0


def _circle_point(bearing_deg: float, radius_m: float = TRUE_RADIUS_M):
    return project_position_lat_lon((CENTER_LAT, CENTER_LON), bearing_deg % 360, radius_m)


class TestCircleEndToEnd(TestCase):
    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, *args):
        create_scorecards()
        self.scorecard = Scorecard.get_originals().get(shortcut_name="FAI Precision")
        self.scorecard.circle_radius_min_m = 200
        self.scorecard.circle_radius_max_m = 750
        self.scorecard.save(update_fields=["config"])

        sp_lat, sp_lon = _circle_point(90)  # due east of center, on the circle boundary
        x_lat, x_lon = _circle_point(0)  # due north - straight-line SP->X passes near the center
        wp_lat, wp_lon = _circle_point(180)

        self.editable_route = EditableRoute.objects.create(
            name="Circle end to end",
            route={
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {
                            "id": "cs-1",
                            "name": "SP",
                            "pointType": "circle_start",
                            "featureType": "circle_start_marker",
                        },
                        "geometry": {"type": "Point", "coordinates": [sp_lon, sp_lat]},
                    },
                    {
                        "type": "Feature",
                        "properties": {
                            "id": "ce-1",
                            "name": "X",
                            "pointType": "circle_entry",
                            "featureType": "circle_entry_marker",
                        },
                        "geometry": {"type": "Point", "coordinates": [x_lon, x_lat]},
                    },
                    {
                        "type": "Feature",
                        "properties": {
                            "id": "cm-1",
                            "name": "CM",
                            "pointType": "circle_center",
                            "featureType": "circle_center_marker",
                        },
                        "geometry": {"type": "Point", "coordinates": [CENTER_LON, CENTER_LAT]},
                    },
                    {
                        "type": "Feature",
                        "properties": {
                            "id": "cx-1",
                            "name": "WP",
                            "pointType": "circle_exit",
                            "featureType": "circle_exit_marker",
                        },
                        "geometry": {"type": "Point", "coordinates": [wp_lon, wp_lat]},
                    },
                ],
            },
        )
        self.route = self.editable_route.create_route(PRECISION, self.scorecard, None, None, task_subtype=CIRCLE)

        self.contest = Contest.objects.create(
            name="Circle e2e contest",
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc),
            time_zone="Europe/Oslo",
        )
        self.navigation_task = NavigationTask.create(
            name="Circle e2e task",
            contest=self.contest,
            route=self.route,
            original_scorecard=self.scorecard,
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc),
            task_subtype=CIRCLE,
        )
        self.navigation_task.editable_route = self.editable_route
        self.navigation_task.save(update_fields=["editable_route"])

        crew = Crew.objects.create(member1=Person.objects.create(first_name="Circle", last_name="E2E"))
        team = Team.objects.create(crew=crew, aeroplane=Aeroplane.objects.create(registration="LN-E2E"))
        start_time = datetime.datetime(2020, 8, 1, 8, 5, tzinfo=datetime.timezone.utc)
        self.contestant = Contestant.objects.create(
            navigation_task=self.navigation_task,
            team=team,
            takeoff_time=start_time,
            tracker_start_time=start_time - datetime.timedelta(minutes=30),
            finished_by_time=start_time + datetime.timedelta(hours=2),
            tracker_device_id="circle-e2e",
            contestant_number=1,
            minutes_to_starting_point=6,
            air_speed=75,
            wind_direction=165,
            wind_speed=8,
        )
        ContestantTaskCompiler(self.contestant).compile(force=True)
        self.contestant.refresh_from_db()

    def test_route_has_no_backbone_waypoints_but_effective_route_does(self):
        # This is the empty-Route-by-design contract for backbone-less
        # subtypes (editable_route.py's create_route) - the fix is at the
        # effective-route layer above it, not here.
        self.assertEqual(self.route.waypoints, [])
        effective = get_effective_route_waypoints(self.navigation_task, contestant=self.contestant)
        self.assertEqual([w.name for w in effective], ["SP", "X", "CM", "WP"])
        self.assertEqual([w.type for w in effective], ["circle_start", "circle_entry", "circle_center", "circle_exit"])

    def test_gate_calculator_creates_gates_for_boundary_markers_but_not_center(self):
        gate_calculator = GateCalculator(
            self.contestant,
            self.scorecard,
            self.route,
            MagicMock(),
            live_processing=False,
            projector=self.navigation_task.get_projector(),
        )
        self.assertEqual([gate.name for gate in gate_calculator.gates], ["SP", "X", "WP"])

    def test_gate_calculator_finalise_does_not_crash_and_scores_no_circle_gates(self):
        # Regression guard for the ValueError previously raised by
        # Scorecard.get_gate_scorecard for unknown gate types (circle_start
        # etc. have no GateScore row in any scorecard) once these gates
        # started being created at all.
        queue = MagicMock()
        gate_calculator = GateCalculator(
            self.contestant,
            self.scorecard,
            self.route,
            queue,
            live_processing=False,
            projector=self.navigation_task.get_projector(),
        )
        gate_calculator.finalise([])
        gate_score_calls = [call for call in queue.put_nowait.call_args_list if call.args[0].score_type == "gate_score"]
        self.assertEqual(gate_score_calls, [])

    def test_projector_is_centered_on_the_circle_not_the_origin(self):
        projector = self.navigation_task.get_projector()
        origin = projector.project_point(0.0001, 0.0001)
        # If the projector fell back to Projector(0, 0), its own origin would
        # project to (~0, ~0); if centered on the circle, the origin is far away.
        self.assertGreater(math.hypot(origin.projected_x, origin.projected_y), 1_000_000)

        center_projected = projector.project_point(CENTER_LAT, CENTER_LON)
        self.assertLess(math.hypot(center_projected.projected_x, center_projected.projected_y), 1.0)

        # Pin the regression numerically: a true 500 m circle must measure
        # close to 500 m. Before the projector fix this measured 506-603 m
        # depending on bearing (Projector(0, 0) badly distorts distances this
        # far from the equator/prime meridian).
        boundary_lat, boundary_lon = _circle_point(45)
        boundary_projected = projector.project_point(boundary_lat, boundary_lon)
        measured_radius = math.hypot(boundary_projected.projected_x, boundary_projected.projected_y)
        self.assertAlmostEqual(measured_radius, TRUE_RADIUS_M, delta=5)

    def test_full_synthetic_circle_track_scores_through_the_orchestrator(self):
        projector = self.navigation_task.get_projector()
        queue = Queue()
        orchestrator = calculator_factory(self.contestant, queue, live_processing=False, projector=projector)

        def make_position(lat, lon, offset_seconds, altitude=1000.0):
            position = MagicMock()
            position.time = datetime.datetime(2020, 8, 1, 8, 5, tzinfo=datetime.timezone.utc) + datetime.timedelta(
                seconds=offset_seconds
            )
            position.latitude = lat
            position.longitude = lon
            position.altitude = altitude
            position.speed = 40.0
            position.course = 0.0
            position.projected_x = None
            position.projected_y = None
            return position

        # SP due east of center, X diametrically opposite (due west) so the
        # straight SP->X entry line passes through CM, satisfying
        # CircleCalculator._is_valid_straight_entry's bearing/distance checks.
        sp_bearing = 90.0
        x_bearing = 270.0
        # > 540 required progress; _is_clockwise_turn only compares entry vs
        # exit position (not the whole path), so the NET short-way angle from
        # entry (270) to the landing bearing must read as CCW - 810 lands
        # exactly on WP's marker bearing (180, i.e. two full loops plus 90).
        sweep_degrees = 810.0
        wp_bearing = (x_bearing - sweep_degrees) % 360.0

        track = []
        offset = 0.0

        # Lead-in: approach SP from further out along the same SP->X bearing
        # (due west), then continue straight through SP and CM to X, so the
        # crossing-detection algorithm sees genuine before/after track
        # segments straddling each gate line rather than starting exactly on
        # a marker's coordinates.
        for distance_m in (-300.0, -150.0, 0.0, 500.0, 750.0, 1000.0):
            lat, lon = project_position_lat_lon(_circle_point(sp_bearing), 270.0, distance_m)
            track.append(make_position(lat, lon, offset))
            offset += 10.0

        # Bearing DEcreasing over time = counter-clockwise physical motion =
        # the math angle atan2(dlat, dlon) CircleCalculator uses increases,
        # which is what _is_clockwise_turn requires to not flag an anomaly.
        #
        # A total sweep >540 (required for a completed scored arc) with the
        # sweep landing exactly on WP's bearing necessarily passes back
        # through that same bearing at least twice before the final lap (the
        # geometry only closes cleanly at 810 degrees here). Flying those
        # earlier passes a little inside the true radius keeps the track
        # firmly on one side of WP's tangential gate line every time except
        # the last, so only the final, deliberate radially-outward lead-out
        # below actually crosses it.
        n = 162
        sweep_radius_m = TRUE_RADIUS_M - 30.0
        for i in range(1, n + 1):
            bearing = x_bearing - (sweep_degrees * i / n)
            lat, lon = _circle_point(bearing, sweep_radius_m)
            track.append(make_position(lat, lon, offset))
            offset += 5.0

        # WP's gate line is tangent to the circle (perpendicular to the CM->WP
        # radius), since _apply_effective_gate_lines builds it from the CM->WP
        # bearing. Continuing tangentially along the arc only ever touches
        # that line at the single point WP itself, never crosses it. A real
        # exit breaks off the circular pattern and flies outward past the
        # gate line, so the lead-out here does the same: continue straight
        # out from CM through WP's bearing, beyond the circle's radius.
        for radius_m in (600.0, 900.0, 1300.0):
            lat, lon = project_position_lat_lon((CENTER_LAT, CENTER_LON), wp_bearing, radius_m)
            track.append(make_position(lat, lon, offset))
            offset += 5.0

        for position in track:
            orchestrator.calculate_score(position)

        messages = []
        while not queue.empty():
            messages.append(queue.get_nowait())

        score_types = [message.score_type for message in messages]
        self.assertIn("circle_start", score_types)
        self.assertIn("circle_entry", score_types)
        self.assertIn("circle_exit", score_types)
        self.assertIn("circle_score", score_types)
        # No anomaly-triggering branch (clockwise/radius/ratio/center/arc)
        # should have fired for a clean, correctly-shaped circle.
        self.assertNotIn("circle_invalid_direction", score_types)
        self.assertNotIn("circle_invalid_radius", score_types)
        self.assertNotIn("circle_invalid_score_ratio", score_types)
        self.assertNotIn("circle_invalid_center", score_types)
        self.assertNotIn("circle_incomplete_scored_arc", score_types)

        # GateCalculator still emits an informational "(no time check)"
        # gate_score message when a gate_check=False, time_check=False gate is
        # passed (see on_gate_passed's else branch) - that's expected
        # bookkeeping, not a scored penalty. What must never happen is a real
        # scored/anomaly gate_score, which would mean get_gate_scorecard was
        # asked for a "circle_start"/"circle_entry"/"circle_exit" GateScore
        # row that does not exist in any scorecard.
        gate_score_messages = [message for message in messages if message.score_type == "gate_score"]
        for message in gate_score_messages:
            self.assertEqual(message.score, 0)
            self.assertEqual(message.annotation_type, INFORMATION)

        score_message = next(message for message in messages if message.score_type == "circle_score")
        self.assertGreater(score_message.score, 0)
