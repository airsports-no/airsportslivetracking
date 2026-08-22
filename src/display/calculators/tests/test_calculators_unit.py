from unittest import skip
import datetime
import numpy as np
from unittest.mock import Mock, patch, MagicMock, call
from django.test import TestCase
from display.calculators.calculator import (
    OrchestratorState,
    GatePassedEvent,
    GateMissedEvent,
    TakeoffPassedEvent,
    LandingPassedEvent,
    StartingLinePassedEvent,
    PokerGatePassedEvent,
    InRangeUpdatedEvent,
    NextGateExpectedEvent,
    AdaptiveStartEvent,
)
from display.calculators.gate_calculator import GateCalculator
from display.calculators.anr_corridor_calculator import AnrCorridorCalculator
from display.calculators.backtracking_and_procedure_turns import BacktrackingAndProcedureTurnsCalculator
from display.calculators.landing_pattern_calculator import LandingPatternCalculator
from display.calculators.poker_calculator import PokerCalculator
from display.calculators.prohibited_zone_calculator import ProhibitedZoneCalculator
from display.calculators.penalty_zone_calculator import PenaltyZoneCalculator
from display.models.contestant_utility_models import ContestantReceivedPosition
from display.utilities.cima_task_type_definitions import ANR_CATALOGUE
from display.utilities.coordinate_utilities import Projector
from display.waypoint import Waypoint


class CalculatorUnitTestBase(TestCase):
    def setUp(self):
        self.contestant = MagicMock()
        self.contestant.air_speed = 70
        # An unconfigured MagicMock queryset reports exists() as truthy, which turns
        # production "while ...exists(): retry" guards into infinite loops. Default the
        # chain to empty so any code path reaching a queryset on this mock terminates.
        self.contestant.playingcard_set.all.return_value.values_list.return_value = []
        self.contestant.playingcard_set.filter.return_value.exists.return_value = False

        # Patch Gate.pre_project globally for all tests in this file
        self.pre_project_patcher = patch("display.calculators.positions_and_gates.Gate.pre_project")
        self.mock_pre_project = self.pre_project_patcher.start()

        self.route = MagicMock()
        self.contestant.navigation_task.route = self.route

        # Use MagicMock for waypoints to avoid read-only property issues with real Waypoint objects
        self.waypoint1 = MagicMock()
        self.waypoint1.latitude = 60.0
        self.waypoint1.longitude = 11.0
        self.waypoint1.name = "WP1"
        self.waypoint1.type = "sp"
        self.waypoint1.width = 100.0
        self.waypoint1.gate_line = ((60.0, 11.0), (60.0, 11.1))
        self.waypoint1.gate_line_infinite = ((60.0, 11.0), (60.0, 11.1))
        self.waypoint1.gate_line_extended = ((60.0, 11.0), (60.0, 11.1))
        self.waypoint1.bearing = 0
        self.waypoint1.center_x = 0.0
        self.waypoint1.center_y = 0.0
        self.waypoint1.inside_distance = 500
        self.waypoint1.outside_distance = 1000
        self.waypoint1.gate_check = True
        self.waypoint1.time_check = True
        self.waypoint1.is_procedure_turn = False
        self.waypoint1.is_steep_turn = False
        self.waypoint1.on_curved_segment = False
        self.waypoint1.infinite_passing_time = None
        self.waypoint1.passing_time = None
        self.waypoint1.missed = False

        self.route.waypoints = [self.waypoint1]
        self.route.corridor_polygon = [
            {"lat": 60.0, "lng": 11.0},
            {"lat": 60.1, "lng": 11.0},
            {"lat": 60.1, "lng": 11.1},
        ]
        self.route.takeoff_gates = []
        self.route.landing_gates = []

        self.scorecard = MagicMock()
        self.scorecard.get_extended_gate_width_for_gate_type.return_value = 200.0
        self.contestant.navigation_task.scorecard = self.scorecard
        self.contestant.gate_times = {"WP1": datetime.datetime(2020, 1, 1, 10, 0, tzinfo=datetime.timezone.utc)}

        self.score_processing_queue = MagicMock()
        self.projector = Projector(60, 11)

    def tearDown(self):
        self.pre_project_patcher.stop()

    def create_position(self, lat, lon, time):
        if time.tzinfo is None:
            time = time.replace(tzinfo=datetime.timezone.utc)
        pos = MagicMock(spec=ContestantReceivedPosition)
        pos.latitude = float(lat)
        pos.longitude = float(lon)
        pos.time = time
        # Calculate projected coordinates
        proj = self.projector.project_point(pos.latitude, pos.longitude)
        pos.projected_x = proj.projected_x
        pos.projected_y = proj.projected_y

        return pos


class TestGateCalculator(CalculatorUnitTestBase):
    def setUp(self):
        super().setUp()
        with patch("display.calculators.gate_calculator.calculate_extended_gate"):
            with patch("display.calculators.positions_and_gates.Gate.pre_project"):
                self.calculator = GateCalculator(
                    self.contestant,
                    self.scorecard,
                    self.route,
                    self.score_processing_queue,
                    live_processing=False,
                    projector=self.projector,
                )
                # Manually set up gates for unit tests
                self.calculator.gates = [self.waypoint1]

    def test_calculate_enroute_gate_passed(self):
        gate = MagicMock()
        gate.name = "TP 1"
        gate.latitude = 60.0
        gate.longitude = 11.0
        gate.center_x = 0.0
        gate.center_y = 0.0
        gate.type = "tp"
        gate.is_passed_in_correct_direction_track.return_value = True
        gate.has_been_passed.return_value = False
        gate.infinite_passing_time = None
        gate.passing_time = None
        gate.missed = False
        gate.time_check = False

        self.calculator.gates = [gate]
        self.calculator.outstanding_gates = [gate]
        state = OrchestratorState(
            last_gate=None,
            last_visible_gate=None,
            next_gate=None,
            in_range_of_gate=None,
            projector=self.projector,
            has_passed_finishpoint=False,
            recalculation_completed=True,
        )

        pos = self.create_position(60, 11, datetime.datetime(2020, 1, 1, 10, 5))
        track = [pos]

        gate.get_gate_intersection_time.return_value = pos.time

        events = self.calculator.calculate_enroute(track, state)

        self.assertTrue(any(isinstance(e, GatePassedEvent) for e in events))

    def test_calculate_enroute_starting_line_passed(self):
        gate = MagicMock()
        gate.name = "SP"
        gate.type = "sp"
        gate.center_x = 0.0
        gate.center_y = 0.0
        gate.inside_distance = 500
        gate.outside_distance = 1000
        gate.is_passed_in_correct_direction_track.return_value = True
        gate.has_infinite_been_passed.return_value = False

        self.calculator.gates = [gate]
        self.calculator.starting_line = gate
        self.calculator.outstanding_gates = [gate]
        self.contestant.adaptive_start = True

        state = OrchestratorState(
            last_gate=None,
            last_visible_gate=None,
            next_gate=gate,
            in_range_of_gate=None,
            projector=self.projector,
            has_passed_finishpoint=False,
            recalculation_completed=False,
        )

        pos = self.create_position(60, 11, datetime.datetime(2020, 1, 1, 10, 0))
        track = [pos]

        gate.get_gate_infinite_intersection_time.return_value = pos.time

        events = self.calculator.calculate_enroute(track, state)

        from display.calculators.calculator import StartingLinePassedEvent, AdaptiveStartEvent

        self.assertTrue(any(isinstance(e, StartingLinePassedEvent) for e in events))
        self.assertTrue(any(isinstance(e, AdaptiveStartEvent) for e in events))

    def test_calculate_enroute_starting_line_extended_passed_wrong_direction(self):
        gate = MagicMock()
        gate.name = "SP"
        gate.type = "sp"
        gate.center_x = 0.0
        gate.center_y = 0.0
        gate.inside_distance = 500
        gate.outside_distance = 1000
        gate.is_passed_in_correct_direction_track.return_value = False

        self.calculator.gates = [gate]
        self.calculator.starting_line = gate
        self.calculator.outstanding_gates = [gate]

        state = OrchestratorState(
            last_gate=None,
            last_visible_gate=None,
            next_gate=gate,
            in_range_of_gate=None,
            projector=self.projector,
            has_passed_finishpoint=False,
            recalculation_completed=False,
        )

        pos = self.create_position(60, 11, datetime.datetime(2020, 1, 1, 10, 0))
        track = [pos]

        # Extended line intersection
        gate.get_gate_extended_intersection_time.return_value = pos.time

        from display.calculators.calculator import StartingLineExtendedPassedWrongDirectionEvent

        events = self.calculator.calculate_enroute(track, state)

        self.assertTrue(any(isinstance(e, StartingLineExtendedPassedWrongDirectionEvent) for e in events))

    def test_calculate_enroute_gate_missed(self):
        gate1 = MagicMock()
        gate1.name = "TP 1"
        gate1.center_x = 0.0
        gate1.center_y = 0.0
        gate1.type = "tp"
        gate1.has_been_passed.return_value = False
        gate1.infinite_passing_time = None
        gate1.passing_time = None
        gate1.missed = False

        gate2 = MagicMock()
        gate2.name = "TP 2"
        gate2.center_x = 0.0
        gate2.center_y = 0.0
        gate2.type = "tp"
        gate2.is_passed_in_correct_direction_track.return_value = True
        gate2.has_been_passed.return_value = False
        gate2.infinite_passing_time = None
        gate2.passing_time = None
        gate2.missed = False

        self.calculator.gates = [gate1, gate2]
        self.calculator.outstanding_gates = [gate1, gate2]
        state = OrchestratorState(
            last_gate=None,
            last_visible_gate=None,
            next_gate=None,
            in_range_of_gate=None,
            projector=self.projector,
            has_passed_finishpoint=False,
            recalculation_completed=True,
        )

        pos = self.create_position(60, 11, datetime.datetime(2020, 1, 1, 10, 5))
        track = [pos]

        # We skip gate1 and pass gate2
        gate1.get_gate_intersection_time.return_value = None
        gate2.get_gate_intersection_time.return_value = pos.time

        events = self.calculator.calculate_enroute(track, state)

        self.assertTrue(any(isinstance(e, GateMissedEvent) and e.gate == gate1 for e in events))
        self.assertTrue(any(isinstance(e, GatePassedEvent) and e.gate == gate2 for e in events))

    @patch("display.calculators.gate_calculator.calculate_distance_lat_lon")
    def test_calculate_enroute_in_range(self, mock_dist):
        gate = MagicMock()
        gate.name = "TP 1"
        gate.type = "tp"
        gate.latitude = 60.0
        gate.longitude = 11.0
        gate.inside_distance = 1000.0  # 1km
        gate.get_gate_intersection_time.return_value = None
        gate.infinite_passing_time = None
        gate.passing_time = None
        gate.missed = False
        gate.center_x = 0.0
        gate.center_y = 0.0
        gate.gate_radius = 50.0

        self.calculator.gates = [gate]
        self.calculator.outstanding_gates = [gate]

        mock_dist.return_value = 500.0  # 500m < 1km

        state = OrchestratorState(
            last_gate=None,
            last_visible_gate=None,
            next_gate=None,
            in_range_of_gate=None,
            projector=self.projector,
            has_passed_finishpoint=False,
            recalculation_completed=True,
        )

        pos = self.create_position(60.001, 11.001, datetime.datetime(2020, 1, 1, 10, 5))
        track = [pos]

        events = self.calculator.calculate_enroute(track, state)

        self.assertTrue(any(isinstance(e, InRangeUpdatedEvent) and e.gate == gate for e in events))

    def test_on_gate_missed(self):
        gate = self.calculator.gates[0]
        gate.expected_time = datetime.datetime(2020, 1, 1, 10, 0, tzinfo=datetime.timezone.utc)
        gate.passing_time = None
        gate.missed = False
        gate.gate_check = True

        pos = self.create_position(60, 11, datetime.datetime(2020, 1, 1, 10, 5))
        event = GateMissedEvent(None, gate, pos)

        self.scorecard.get_gate_timing_score_for_gate_type.return_value = 100

        with patch.object(self.calculator, "update_score") as mock_update:
            self.calculator.on_gate_missed(event)

        self.assertTrue(gate.missed)
        mock_update.assert_called_once()
        msg = mock_update.call_args[0][0]
        self.assertEqual(msg.score, 100)
        self.assertEqual(msg.score_type, "gate_score")
        self.assertEqual(msg.planned, gate.expected_time)
        self.assertIsNone(msg.actual)

    def test_on_gate_passed(self):
        gate = self.calculator.gates[0]
        gate.expected_time = datetime.datetime(2020, 1, 1, 10, 0, tzinfo=datetime.timezone.utc)
        gate.passing_time = None
        gate.infinite_passing_position = None
        gate.missed = False
        gate.time_check = True

        pos = self.create_position(60, 11, datetime.datetime(2020, 1, 1, 10, 5))
        event = GatePassedEvent(gate, pos, pos.time, previous_gate=None)

        self.scorecard.get_gate_timing_score_for_gate_type.return_value = 50

        with patch.object(self.calculator, "transmit_actual_crossing") as mock_transmit:
            with patch.object(self.calculator, "update_score") as mock_update:
                self.calculator.on_gate_passed(event)

        mock_transmit.assert_called_once_with(gate, pos)
        mock_update.assert_called_once()
        msg = mock_update.call_args[0][0]
        self.assertEqual(msg.score, 50)
        self.assertEqual(msg.score_type, "gate_score")
        self.assertEqual(msg.planned, gate.expected_time)
        self.assertEqual(msg.actual, pos.time)

    def test_check_gate_in_range_pops_outstanding_gate_on_detected_miss(self):
        """Regression test: detecting a gate missed via the "went out of
        range without crossing" path must pop it off outstanding_gates and
        emit NextGateExpectedEvent immediately, so state.next_gate (used for
        live-tracking display) doesn't keep pointing at an already-missed
        gate until a later gate crossing retroactively cleans it up."""
        gate = MagicMock()
        gate.name = "TP 1"
        gate.center_x = 0.0
        gate.center_y = 0.0
        gate.outside_distance = 100
        gate.passing_time = None
        gate.missed = False

        self.calculator.gates = [gate]
        self.calculator.gates[0].has_infinite_been_passed = MagicMock(return_value=True)
        self.calculator.outstanding_gates = [gate]

        state = OrchestratorState(
            last_gate=None,
            last_visible_gate=None,
            next_gate=gate,
            in_range_of_gate=gate,
            projector=self.projector,
            has_passed_finishpoint=False,
            recalculation_completed=True,
        )

        # Well outside the gate's outside_distance (100m).
        pos = self.create_position(61.0, 12.0, datetime.datetime(2020, 1, 1, 10, 5))
        track = [pos]
        events = []

        self.calculator.check_gate_in_range(track, state, events)

        self.assertEqual(self.calculator.outstanding_gates, [])
        self.assertTrue(any(isinstance(e, GateMissedEvent) for e in events))
        self.assertTrue(any(isinstance(e, NextGateExpectedEvent) for e in events))

    def test_on_starting_line_extended_passed_wrong_direction(self):
        gate = MagicMock()
        gate.name = "SP"
        gate.type = "sp"
        gate.expected_time = datetime.datetime(2020, 1, 1, 10, 0, tzinfo=datetime.timezone.utc)
        gate.latitude = 60.0
        gate.longitude = 11.0
        pos = self.create_position(60, 11, datetime.datetime(2020, 1, 1, 9, 59))

        self.calculator.starting_line = gate
        self.scorecard.get_bad_crossing_extended_gate_penalty_for_gate_type.return_value = 50

        event = type("Evt", (), {"position": pos})()

        with patch.object(self.calculator, "update_score") as mock_update:
            self.calculator.on_starting_line_extended_passed_wrong_direction(event)

        mock_update.assert_called_once()
        msg = mock_update.call_args[0][0]
        self.assertEqual(msg.score, 50)
        self.assertEqual(msg.score_type, "backwards_starting_line")

    def test_on_starting_line_extended_passed_wrong_direction_scores_isp_gate(self):
        """Regression test: the penalty must fire for any starting gate type
        with a nonzero configured penalty, not just 'sp' - 'isp' (intermediary
        starting point) is a real, used gate type."""
        gate = MagicMock()
        gate.name = "ISP"
        gate.type = "isp"
        gate.expected_time = datetime.datetime(2020, 1, 1, 10, 0, tzinfo=datetime.timezone.utc)
        gate.latitude = 60.0
        gate.longitude = 11.0
        pos = self.create_position(60, 11, datetime.datetime(2020, 1, 1, 9, 59))

        self.calculator.starting_line = gate
        self.scorecard.get_bad_crossing_extended_gate_penalty_for_gate_type.return_value = 50

        event = type("Evt", (), {"position": pos})()

        with patch.object(self.calculator, "update_score") as mock_update:
            self.calculator.on_starting_line_extended_passed_wrong_direction(event)

        mock_update.assert_called_once()
        msg = mock_update.call_args[0][0]
        self.assertEqual(msg.score, 50)
        self.assertEqual(msg.score_type, "backwards_starting_line")
        self.scorecard.get_bad_crossing_extended_gate_penalty_for_gate_type.assert_called_once_with("isp")

    def test_on_starting_line_extended_passed_wrong_direction_skips_zero_score(self):
        gate = MagicMock()
        gate.name = "SP"
        gate.type = "sp"
        gate.expected_time = datetime.datetime(2020, 1, 1, 10, 0, tzinfo=datetime.timezone.utc)
        gate.latitude = 60.0
        gate.longitude = 11.0
        pos = self.create_position(60, 11, datetime.datetime(2020, 1, 1, 9, 59))

        self.calculator.starting_line = gate
        self.scorecard.get_bad_crossing_extended_gate_penalty_for_gate_type.return_value = 0

        event = type("Evt", (), {"position": pos})()

        with patch.object(self.calculator, "update_score") as mock_update:
            self.calculator.on_starting_line_extended_passed_wrong_direction(event)

        mock_update.assert_not_called()

    def test_on_adaptive_start_double_invocation_is_idempotent(self):
        """In production on_adaptive_start is invoked twice per adaptive
        crossing: once inline from check_intersections
        (gate_calculator.py:321-323) and once via the orchestrator's
        AdaptiveStartEvent fan-out (orchestrator.py:204). Regression-locks
        that this is safe: exactly one informational score message is
        emitted (the has_scored_adaptive_start guard) and the gate-time
        rewrite produces the same result both times."""
        new_start_time = datetime.datetime(2020, 1, 1, 10, 5, tzinfo=datetime.timezone.utc)
        recalculated_times = {"WP1": datetime.datetime(2020, 1, 1, 10, 6, tzinfo=datetime.timezone.utc)}
        self.contestant.calculate_missing_gate_times.return_value = recalculated_times
        pos = self.create_position(60, 11, new_start_time)
        event = AdaptiveStartEvent(new_start_time, pos)

        self.calculator.on_adaptive_start(event)
        self.assertEqual(self.waypoint1.expected_time, recalculated_times["WP1"])
        self.assertEqual(self.score_processing_queue.put_nowait.call_count, 1)

        # Second, orchestrator-driven invocation of the same event.
        self.calculator.on_adaptive_start(event)
        self.assertEqual(self.waypoint1.expected_time, recalculated_times["WP1"])
        self.assertEqual(self.score_processing_queue.put_nowait.call_count, 1)


class TestAnrCorridorCalculator(CalculatorUnitTestBase):
    def setUp(self):
        super().setUp()
        self.route.corridor_width = 0.5
        self.scorecard.corridor_grace_time = 5
        self.scorecard.corridor_outside_penalty = 10
        self.scorecard.corridor_maximum_penalty = 50
        self.scorecard.corridor_maximum_penalty_is_per_leg = False
        self.scorecard.anr_route_to_sp_penalty = 200.0
        self.scorecard.anr_route_from_fp_penalty = 200.0

        self.gate_sp = MagicMock(spec=Waypoint)
        self.gate_sp.name = "SP"
        self.gate_sp.type = "sp"
        self.gate_sp.is_visible = True
        self.gate_sp.latitude = 60.0
        self.gate_sp.longitude = 11.0

        self.gate_tp = MagicMock(spec=Waypoint)
        self.gate_tp.name = "TP1"
        self.gate_tp.type = "tp"
        self.gate_tp.is_visible = True
        self.gate_tp.latitude = 60.05
        self.gate_tp.longitude = 11.05

        self.gate_fp = MagicMock(spec=Waypoint)
        self.gate_fp.name = "FP"
        self.gate_fp.type = "fp"
        self.gate_fp.is_visible = True
        self.gate_fp.latitude = 60.1
        self.gate_fp.longitude = 11.1

        self.route.waypoints = [self.gate_sp, self.gate_tp, self.gate_fp]

        self.build_polygon_patcher = patch.object(AnrCorridorCalculator, "build_polygon", return_value=MagicMock())
        self.mock_build_polygon = self.build_polygon_patcher.start()

        self.calculator = AnrCorridorCalculator(
            self.contestant,
            self.scorecard,
            self.route,
            self.score_processing_queue,
            live_processing=False,
            projector=self.projector,
        )
        self.calculator.polygon_helper = MagicMock()
        self.calculator.polygon_helper.utm.transform_point.return_value = (0.0, 0.0)

    def tearDown(self):
        self.build_polygon_patcher.stop()
        super().tearDown()

    def test_anr_catalogue_route_to_sp_noncompliance_scores_once(self):
        self.contestant.navigation_task.task_subtype = ANR_CATALOGUE
        self.contestant.contestanttaskconfiguration = MagicMock()
        self.contestant.contestanttaskconfiguration.is_valid = True
        self.contestant.contestanttaskconfiguration.compiled_effective_route_payload = {
            "compiled_auxiliary_paths": {
                "route_to_sp_path": [[[10.9, 59.9], [11.0, 60.0]]],
                "route_from_fp_path": [],
            }
        }
        self.route.corridor_width = 0.5
        self.calculator.route_to_sp_polygon = object()
        self.calculator._is_inside_auxiliary_polygon = MagicMock(return_value=False)

        pos = self.create_position(60.5, 11.5, datetime.datetime(2020, 1, 1, 10, 0, tzinfo=datetime.timezone.utc))
        state = OrchestratorState(
            last_gate=None,
            last_visible_gate=None,
            next_gate=None,
            in_range_of_gate=None,
            projector=self.projector,
            has_passed_finishpoint=False,
            recalculation_completed=True,
            has_any_gate_passed=False,
        )

        with patch.object(self.calculator, "update_score") as mock_update:
            self.calculator.calculate_outside_route([pos], state)
            self.calculator.calculate_outside_route([pos], state)

        self.assertEqual(len(mock_update.call_args_list), 1)
        msg = mock_update.call_args_list[0][0][0]
        self.assertEqual(msg.score_type, "anr_route_to_sp")
        self.assertEqual(msg.message, "route to SP not followed")
        self.assertEqual(msg.score, 200.0)

    def test_anr_catalogue_route_to_sp_uses_scorecard_configured_penalty(self):
        self.contestant.navigation_task.task_subtype = ANR_CATALOGUE
        self.contestant.contestanttaskconfiguration = MagicMock()
        self.contestant.contestanttaskconfiguration.is_valid = True
        self.contestant.contestanttaskconfiguration.compiled_effective_route_payload = {
            "compiled_auxiliary_paths": {
                "route_to_sp_path": [[[10.9, 59.9], [11.0, 60.0]]],
                "route_from_fp_path": [],
            }
        }
        self.route.corridor_width = 0.5
        self.calculator.route_to_sp_polygon = object()
        self.calculator._is_inside_auxiliary_polygon = MagicMock(return_value=False)
        self.scorecard.anr_route_to_sp_penalty = 77.0

        pos = self.create_position(60.5, 11.5, datetime.datetime(2020, 1, 1, 10, 0, tzinfo=datetime.timezone.utc))
        state = OrchestratorState(
            last_gate=None,
            last_visible_gate=None,
            next_gate=None,
            in_range_of_gate=None,
            projector=self.projector,
            has_passed_finishpoint=False,
            recalculation_completed=True,
            has_any_gate_passed=False,
        )

        with patch.object(self.calculator, "update_score") as mock_update:
            self.calculator.calculate_outside_route([pos], state)

        msg = mock_update.call_args_list[0][0][0]
        self.assertEqual(msg.score, 77.0)

    def test_anr_catalogue_route_from_fp_noncompliance_scores_once(self):
        self.contestant.navigation_task.task_subtype = ANR_CATALOGUE
        self.contestant.contestanttaskconfiguration = MagicMock()
        self.contestant.contestanttaskconfiguration.is_valid = True
        self.contestant.contestanttaskconfiguration.compiled_effective_route_payload = {
            "compiled_auxiliary_paths": {
                "route_to_sp_path": [],
                "route_from_fp_path": [[[11.1, 60.1], [11.2, 60.0]]],
            }
        }
        self.route.corridor_width = 0.5
        self.calculator.route_from_fp_polygon = object()
        self.calculator._is_inside_auxiliary_polygon = MagicMock(return_value=False)

        pos = self.create_position(60.5, 11.5, datetime.datetime(2020, 1, 1, 10, 0, tzinfo=datetime.timezone.utc))
        state = OrchestratorState(
            last_gate=None,
            last_visible_gate=None,
            next_gate=None,
            in_range_of_gate=None,
            projector=self.projector,
            has_passed_finishpoint=True,
            recalculation_completed=True,
            has_any_gate_passed=True,
        )

        with patch.object(self.calculator, "update_score") as mock_update:
            self.calculator.calculate_outside_route([pos], state)
            self.calculator.calculate_outside_route([pos], state)

        self.assertEqual(len(mock_update.call_args_list), 1)
        msg = mock_update.call_args_list[0][0][0]
        self.assertEqual(msg.score_type, "anr_route_from_fp")
        self.assertEqual(msg.message, "route from FP not followed")
        self.assertEqual(msg.score, 200.0)

    def test_anr_catalogue_route_from_fp_uses_scorecard_configured_penalty(self):
        self.contestant.navigation_task.task_subtype = ANR_CATALOGUE
        self.contestant.contestanttaskconfiguration = MagicMock()
        self.contestant.contestanttaskconfiguration.is_valid = True
        self.contestant.contestanttaskconfiguration.compiled_effective_route_payload = {
            "compiled_auxiliary_paths": {
                "route_to_sp_path": [],
                "route_from_fp_path": [[[11.1, 60.1], [11.2, 60.0]]],
            }
        }
        self.route.corridor_width = 0.5
        self.calculator.route_from_fp_polygon = object()
        self.calculator._is_inside_auxiliary_polygon = MagicMock(return_value=False)
        self.scorecard.anr_route_from_fp_penalty = 55.0

        pos = self.create_position(60.5, 11.5, datetime.datetime(2020, 1, 1, 10, 0, tzinfo=datetime.timezone.utc))
        state = OrchestratorState(
            last_gate=None,
            last_visible_gate=None,
            next_gate=None,
            in_range_of_gate=None,
            projector=self.projector,
            has_passed_finishpoint=True,
            recalculation_completed=True,
            has_any_gate_passed=True,
        )

        with patch.object(self.calculator, "update_score") as mock_update:
            self.calculator.calculate_outside_route([pos], state)

        msg = mock_update.call_args_list[0][0][0]
        self.assertEqual(msg.score, 55.0)

    def test_calculate_enroute_inside(self):
        self.calculator._check_inside_polygon = MagicMock(return_value=True)

        pos = self.create_position(60, 11, datetime.datetime(2020, 1, 1, 10, 0))
        state = OrchestratorState(
            last_gate=MagicMock(),
            last_visible_gate=MagicMock(),
            next_gate=None,
            in_range_of_gate=None,
            projector=self.projector,
            has_passed_finishpoint=False,
            recalculation_completed=True,
        )

        events = self.calculator.calculate_enroute([pos], state)

        self.assertEqual(events, [])
        self.assertEqual(self.calculator.corridor_state, self.calculator.INSIDE_CORRIDOR)

    def test_calculate_enroute_outside(self):
        self.calculator._check_inside_polygon = MagicMock(return_value=False)

        last_gate = MagicMock()
        last_gate.name = "SP"
        last_gate.type = "sp"

        pos = self.create_position(60.5, 11.5, datetime.datetime(2020, 1, 1, 10, 0))
        state = OrchestratorState(
            last_gate=last_gate,
            last_visible_gate=last_gate,
            next_gate=None,
            in_range_of_gate=None,
            projector=self.projector,
            has_passed_finishpoint=False,
            recalculation_completed=True,
        )

        events = self.calculator.calculate_enroute([pos], state)

        self.assertEqual(self.calculator.corridor_state, self.calculator.OUTSIDE_CORRIDOR)
        self.assertEqual(self.calculator.crossed_outside_time, pos.time)

    def test_calculate_enroute_gate_pass_while_outside_single_penalty(self):
        # Initial state: already outside corridor
        self.calculator.corridor_state = self.calculator.OUTSIDE_CORRIDOR
        self.calculator.crossed_outside_time = datetime.datetime(2020, 1, 1, 10, 0, tzinfo=datetime.timezone.utc)
        self.calculator.current_leg_outside_start_time = self.calculator.crossed_outside_time
        gate1 = MagicMock(name="SP")
        gate1.name = "SP"
        gate1.type = "sp"
        self.calculator.crossed_outside_gate = gate1

        # New position still outside, but gate has advanced to TP1
        gate2 = MagicMock(name="TP1")
        gate2.name = "TP1"
        gate2.type = "tp"

        self.calculator.gates = [gate1, gate2]

        pos = self.create_position(60.5, 11.5, datetime.datetime(2020, 1, 1, 10, 1))

        with patch.object(self.calculator, "_check_inside_polygon", return_value=False):
            with patch.object(self.calculator, "update_score") as mock_update:
                # 1. Test with per-leg OFF (default)
                self.calculator.corridor_maximum_penalty_is_per_leg = False
                self.calculator.check_outside_corridor([pos], gate2)

                # Find any calls that look like "exiting corridor"
                exiting_calls = [c for c in mock_update.call_args_list if "exiting corridor" in c[0][0].message]
                self.assertEqual(
                    len(exiting_calls),
                    0,
                    "Should not emit redundant 'exiting corridor' message on leg advance while already outside",
                )

                # 2. Test with per-leg ON
                self.calculator.corridor_maximum_penalty_is_per_leg = True
                # Reset state for fresh run
                self.calculator.corridor_state = self.calculator.OUTSIDE_CORRIDOR
                self.calculator.crossed_outside_time = datetime.datetime(
                    2020, 1, 1, 10, 0, tzinfo=datetime.timezone.utc
                )
                self.calculator.current_leg_outside_start_time = self.calculator.crossed_outside_time
                self.calculator.crossed_outside_gate = gate1

                mock_update.reset_mock()
                # Simulate the event that Orchestrator would trigger when gate is passed
                self.calculator.on_gate_passed(GatePassedEvent(gate2, pos, pos.time, previous_gate=None))

                # Now we expect 1 informational message about the leg we just passed
                self.assertEqual(len(mock_update.call_args_list), 1)
                info_msg = mock_update.call_args_list[0][0][0]
                self.assertEqual(info_msg.annotation_type, "information")
                self.assertIn("passed TP1", info_msg.message)

                # But internal accumulation should have happened
                self.assertGreater(self.calculator.excursion_accumulated_score, 0)

    def test_per_leg_maximum_penalty_accumulation(self):
        # Setup per-leg scoring
        self.calculator.corridor_maximum_penalty_is_per_leg = True
        self.scorecard.corridor_maximum_penalty = 50
        self.scorecard.corridor_outside_penalty = 10
        self.scorecard.corridor_grace_time = 5

        t0 = datetime.datetime(2026, 1, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)
        gate1 = MagicMock(name="SP")
        gate1.name = "SP"
        gate1.type = "sp"

        gate2 = MagicMock(name="TP1")
        gate2.name = "TP1"
        gate2.type = "tp"

        self.calculator.gates = [gate1, gate2]

        with patch.object(self.calculator, "_check_inside_polygon") as mock_check:
            # 1. Go outside at T=0
            mock_check.return_value = False
            pos0 = self.create_position(0, 0, t0)
            self.calculator.check_outside_corridor([pos0], gate1)

            # 2. Stay outside for 10 seconds (Leg 1: SP)
            t10 = t0 + datetime.timedelta(seconds=10)
            pos10 = self.create_position(0, 0, t10)
            self.calculator.check_outside_corridor([pos10], gate1)

            # Expectation: 10s outside, 5s grace -> 5s penalty. 5 * 10 = 50 points.
            self.assertEqual(self.calculator.accumulated_score, 50.0)

            # 3. Pass gate TP1 while outside at T=15
            t15 = t0 + datetime.timedelta(seconds=15)
            pos15 = self.create_position(0, 0, t15)

            with patch.object(self.calculator, "update_score") as mock_update:
                # Simulate the event that Orchestrator would trigger when gate is passed
                self.calculator.on_gate_passed(GatePassedEvent(gate2, pos15, pos15.time, previous_gate=None))

                # Leg 1 finalized internally. 15s outside, 5s grace = 10s penalty = 100 points -> capped to 50.
                self.assertEqual(self.calculator.excursion_accumulated_score, 50.0)
                self.assertEqual(self.calculator.excursion_total_outside_seconds, 15.0)
                # accumulated_score is reset for the new leg
                self.assertEqual(self.calculator.accumulated_score, 0)

                # We expect 1 informational message about passing gate2 while outside
                self.assertEqual(len(mock_update.call_args_list), 1)
                self.assertEqual(mock_update.call_args_list[0][0][0].annotation_type, "information")

                # 4. Stay outside for another 10 seconds in Leg 2 (T=25)
                t25 = t0 + datetime.timedelta(seconds=25)
                pos25 = self.create_position(0, 0, t25)
                self.calculator.check_outside_corridor([pos25], gate2)

                # Expectation: 10s in Leg 2. NO GRACE. 10 * 10 = 100 points -> capped to 50.
                self.assertEqual(self.calculator.accumulated_score, 50.0)

                # 5. Come back inside at T=26
                t26 = t0 + datetime.timedelta(seconds=26)
                pos26 = self.create_position(60, 11, t26)
                mock_check.return_value = True
                self.calculator.check_outside_corridor([pos26], gate2)

                # Final assertion: Total excursion score should be Leg1 + Leg2 = 100
                final_msg = mock_update.call_args_list[-1][0][0]
                self.assertEqual(final_msg.score, 100.0)
                self.assertEqual(self.calculator.excursion_accumulated_score, 0)
                self.assertEqual(self.calculator.accumulated_score, 0)

    def test_get_danger_level_and_accumulated_score_lookahead(self):
        self.calculator.enroute = True
        self.calculator.corridor_state = self.calculator.INSIDE_CORRIDOR
        self.calculator.accumulated_score = 10

        pos = self.create_position(60, 11, datetime.datetime(2020, 1, 1, 10, 0))
        track = [pos]

        self.calculator.track_polygon = MagicMock()
        self.calculator.track_polygon.exterior.distance.return_value = 100.0

        with patch("display.calculators.anr_corridor_calculator.get_shortest_intersection_time", return_value=10):
            danger, score = self.calculator.get_danger_level_and_accumulated_score(track)

        self.assertGreater(danger, 0)
        self.assertEqual(score, 10)


class TestBacktrackingAndProcedureTurnsCalculator(CalculatorUnitTestBase):
    def setUp(self):
        super().setUp()
        self.route.use_procedure_turns = False
        with patch("display.calculators.positions_and_gates.Gate.pre_project"):
            self.calculator = BacktrackingAndProcedureTurnsCalculator(
                self.contestant,
                self.scorecard,
                self.route,
                self.score_processing_queue,
                live_processing=False,
                projector=self.projector,
            )

    def test_calculate_enroute_calls_track_score(self):
        pos = self.create_position(60, 11, datetime.datetime(2020, 1, 1, 10, 0))
        last_gate = MagicMock()
        state = OrchestratorState(
            last_gate=last_gate,
            last_visible_gate=last_gate,
            next_gate=None,
            in_range_of_gate=None,
            projector=self.projector,
            has_passed_finishpoint=False,
            recalculation_completed=True,
        )

        with patch.object(self.calculator, "calculate_track_score") as mock_calc:
            events = self.calculator.calculate_enroute([pos], state)

        mock_calc.assert_called_once_with([pos], last_gate, state.in_range_of_gate, state.next_gate)
        self.assertEqual(events, [])

    def test_calculate_outside_route_calls_track_score(self):
        pos = self.create_position(60, 11, datetime.datetime(2020, 1, 1, 10, 0))
        last_gate = MagicMock()
        state = OrchestratorState(
            last_gate=last_gate,
            last_visible_gate=last_gate,
            next_gate=None,
            in_range_of_gate=None,
            projector=self.projector,
            has_passed_finishpoint=False,
            recalculation_completed=True,
        )

        with patch.object(self.calculator, "calculate_track_score") as mock_calc:
            events = self.calculator.calculate_outside_route([pos], state)

        mock_calc.assert_called_once_with([pos], last_gate, state.in_range_of_gate, state.next_gate)
        self.assertEqual(events, [])

    def test_on_gate_passed_updates_last_visible_gate(self):
        gate = MagicMock()
        gate.type = "tp"
        gate.name = "TP1"
        gate.is_visible = True
        event = GatePassedEvent(gate, None, None, previous_gate=None)

        self.calculator.on_gate_passed(event)

        self.assertEqual(self.calculator.last_visible_gate, gate)

    def test_on_gate_missed_updates_last_visible_gate(self):
        gate = MagicMock()
        gate.type = "tp"
        gate.name = "TP1"
        gate.is_visible = True
        pos = self.create_position(60, 11, datetime.datetime(2020, 1, 1, 10, 0))
        event = GateMissedEvent(None, gate, pos)

        self.calculator.on_gate_missed(event)

        self.assertEqual(self.calculator.last_visible_gate, gate)

    def test_on_gate_missed_resets_backtracking(self):
        gate = MagicMock()
        gate.type = "tp"
        gate.name = "TP1"
        gate.is_visible = True
        pos = self.create_position(60, 11, datetime.datetime(2020, 1, 1, 10, 0))
        event = GateMissedEvent(None, gate, pos)

        self.calculator.backtracking_start_time = pos.time
        self.calculator.backtracked_on_current_leg = True

        self.calculator.on_gate_missed(event)

        self.assertIsNone(self.calculator.backtracking_start_time)
        self.assertFalse(self.calculator.backtracked_on_current_leg)
        self.assertTrue(self.calculator.was_backtracked_on_leg_leading_to_last_gate)

    def test_passed_finishpoint_sets_finished_state(self):
        pos = self.create_position(60.1, 11.1, datetime.datetime(2020, 1, 1, 10, 5))
        event = type(
            "FinishEvent",
            (),
            {"track": [pos], "last_gate": self.waypoint1},
        )()

        with patch.object(self.calculator, "calculate_track_score") as mock_calc:
            self.calculator.passed_finishpoint(event)

        self.assertEqual(self.calculator.backtracking_limit, 360)
        mock_calc.assert_called_once_with(event.track, event.last_gate, event.last_gate, None)
        self.assertEqual(self.calculator.tracking_state, self.calculator.FINISHED)

    def test_update_tracking_state_ignored_when_same(self):
        initial = self.calculator.tracking_state
        with patch.object(self.contestant.contestanttrack, "updates_current_state") as mock_update:
            self.calculator.update_tracking_state(initial)
        mock_update.assert_not_called()


class TestLandingPatternCalculator(CalculatorUnitTestBase):
    def setUp(self):
        super().setUp()
        self.calculator = LandingPatternCalculator(
            self.contestant,
            self.scorecard,
            self.route,
            self.score_processing_queue,
            live_processing=False,
            projector=self.projector,
        )

    def test_calculate_enroute_returns_empty(self):
        pos = self.create_position(60, 11, datetime.datetime(2020, 1, 1, 10, 0))
        state = OrchestratorState(
            last_gate=None,
            last_visible_gate=None,
            next_gate=None,
            in_range_of_gate=None,
            projector=self.projector,
            has_passed_finishpoint=False,
            recalculation_completed=True,
        )
        self.assertEqual(self.calculator.calculate_enroute([pos], state), [])

    def test_calculate_outside_route_returns_empty(self):
        pos = self.create_position(60, 11, datetime.datetime(2020, 1, 1, 10, 0))
        state = OrchestratorState(
            last_gate=None,
            last_visible_gate=None,
            next_gate=None,
            in_range_of_gate=None,
            projector=self.projector,
            has_passed_finishpoint=False,
            recalculation_completed=True,
        )
        self.assertEqual(self.calculator.calculate_outside_route([pos], state), [])


class TestPokerCalculator(CalculatorUnitTestBase):
    def setUp(self):
        super().setUp()
        self.contestant.team = MagicMock()
        self.calculator = PokerCalculator(
            self.contestant,
            self.scorecard,
            self.route,
            self.score_processing_queue,
            live_processing=False,
            projector=self.projector,
        )

    def test_calculate_enroute_returns_empty(self):
        pos = self.create_position(60, 11, datetime.datetime(2020, 1, 1, 10, 0))
        state = OrchestratorState(
            last_gate=None,
            last_visible_gate=None,
            next_gate=None,
            in_range_of_gate=None,
            projector=self.projector,
            has_passed_finishpoint=False,
            recalculation_completed=True,
        )
        self.calculator.gates = []
        self.assertEqual(self.calculator.calculate_enroute([pos], state), [])

    def test_calculate_outside_route_returns_empty(self):
        pos = self.create_position(60, 11, datetime.datetime(2020, 1, 1, 10, 0))
        state = OrchestratorState(
            last_gate=None,
            last_visible_gate=None,
            next_gate=None,
            in_range_of_gate=None,
            projector=self.projector,
            has_passed_finishpoint=False,
            recalculation_completed=True,
        )
        self.calculator.gates = []
        self.assertEqual(self.calculator.calculate_outside_route([pos], state), [])

    def test_on_poker_gate_passed_assigns_card(self):
        gate = MagicMock(spec=Waypoint)
        gate.name = "TP1"
        gate.latitude = 60.0
        gate.longitude = 11.0
        gate.card_drawn = False
        gate.passing_time = None

        pos = self.create_position(60, 11, datetime.datetime(2020, 1, 1, 10, 0))
        event = PokerGatePassedEvent(gate, pos)

        # get_random_unique_card must be patched: it would otherwise run for real against
        # self.contestant, which is a bare MagicMock (see CalculatorUnitTestBase.setUp), so
        # its unconfigured playingcard_set.filter(...).exists() is always truthy and the
        # "while ...exists(): pick another card" retry loop would never terminate.
        with (
            patch("display.calculators.poker_calculator.PlayingCard.get_random_unique_card", return_value="2s"),
            patch("display.calculators.poker_calculator.PlayingCard.add_contestant_card") as mock_add_card,
        ):
            self.calculator.on_poker_gate_passed(event)

        mock_add_card.assert_called_once()

    def test_check_distance_only_emits_one_event_per_gate(self):
        """A gate already in passed_gates must not be dealt a second card."""
        gate = self.calculator.gates[0]
        gate.center_x = 0.0
        gate.center_y = 0.0
        gate.gate_radius = 1000
        self.calculator.gates = [gate]

        state = OrchestratorState(
            last_gate=None,
            last_visible_gate=None,
            next_gate=None,
            in_range_of_gate=None,
            projector=self.projector,
            has_passed_finishpoint=False,
            recalculation_completed=True,
        )
        # Both positions sit inside the gate radius, so proximity alone would match twice.
        first = self.calculator.check_distance(self.create_position(60, 11, datetime.datetime(2020, 1, 1, 10, 0)), state)
        second = self.calculator.check_distance(
            self.create_position(60, 11, datetime.datetime(2020, 1, 1, 10, 1)), state
        )

        self.assertEqual(len(first), 1)
        self.assertIsInstance(first[0], PokerGatePassedEvent)
        self.assertEqual(second, [])


class TestProhibitedZoneCalculator(CalculatorUnitTestBase):
    def setUp(self):
        super().setUp()
        self.scorecard.prohibited_zone_grace_time = 5
        self.scorecard.prohibited_zone_penalty = 100
        self.scorecard.prohibited_zone_maximum = 300
        self.route.prohibited_set = MagicMock()
        self.route.prohibited_set.filter.return_value = []

        self.calculator = ProhibitedZoneCalculator(
            self.contestant,
            self.scorecard,
            self.route,
            self.score_processing_queue,
            live_processing=False,
            projector=self.projector,
        )

    def test_calculate_enroute_no_zones(self):
        pos = self.create_position(60, 11, datetime.datetime(2020, 1, 1, 10, 0))
        state = OrchestratorState(
            last_gate=None,
            last_visible_gate=None,
            next_gate=None,
            in_range_of_gate=None,
            projector=self.projector,
            has_passed_finishpoint=False,
            recalculation_completed=True,
        )
        self.assertEqual(self.calculator.calculate_enroute([pos], state), [])

    def test_calculate_outside_route_no_zones(self):
        pos = self.create_position(60, 11, datetime.datetime(2020, 1, 1, 10, 0))
        state = OrchestratorState(
            last_gate=None,
            last_visible_gate=None,
            next_gate=None,
            in_range_of_gate=None,
            projector=self.projector,
            has_passed_finishpoint=False,
            recalculation_completed=True,
        )
        self.assertEqual(self.calculator.calculate_outside_route([pos], state), [])

    def test_enter_and_leave_zone_scores_after_grace(self):
        zone = MagicMock()
        zone.pk = 1
        zone.name = "PZ1"
        zone.path = [(11.0, 60.0), (11.1, 60.0), (11.1, 60.1)]
        zone.altitude = 0
        zone.ceiling = 10000
        self.calculator.zone_map = {1: zone}
        self.calculator.polygons = [(1, MagicMock())]
        self.calculator.polygon_helper = MagicMock()
        self.calculator.polygon_helper.check_inside_polygons.side_effect = [[1], [1], []]

        pos1 = self.create_position(60.05, 11.05, datetime.datetime(2020, 1, 1, 10, 0))
        pos2 = self.create_position(60.05, 11.05, datetime.datetime(2020, 1, 1, 10, 0, 10))
        pos3 = self.create_position(60.2, 11.2, datetime.datetime(2020, 1, 1, 10, 0, 11))

        with patch.object(self.calculator, "update_score") as mock_update:
            self.calculator.calculate_enroute([pos1], Mock(projector=self.projector))
            self.calculator.calculate_enroute([pos2], Mock(projector=self.projector))
            self.calculator.calculate_enroute([pos3], Mock(projector=self.projector))

        self.assertEqual(len(mock_update.call_args_list), 1)
        score_msg = mock_update.call_args_list[0][0][0]
        self.assertEqual(score_msg.score_type, "inside_prohibited_zone_PZ1")
        self.assertGreaterEqual(score_msg.score, 100)


class TestPenaltyZoneCalculator(CalculatorUnitTestBase):
    def setUp(self):
        super().setUp()
        self.scorecard.penalty_zone_grace_time = 3
        self.scorecard.penalty_zone_penalty_per_second = 10
        self.scorecard.penalty_zone_maximum = 50
        self.route.prohibited_set = MagicMock()
        self.route.prohibited_set.filter.return_value = []

        self.calculator = PenaltyZoneCalculator(
            self.contestant,
            self.scorecard,
            self.route,
            self.score_processing_queue,
            live_processing=False,
            projector=self.projector,
        )

    def test_calculate_enroute_no_zones(self):
        pos = self.create_position(60, 11, datetime.datetime(2020, 1, 1, 10, 0))
        state = OrchestratorState(
            last_gate=None,
            last_visible_gate=None,
            next_gate=None,
            in_range_of_gate=None,
            projector=self.projector,
            has_passed_finishpoint=False,
            recalculation_completed=True,
        )
        self.assertEqual(self.calculator.calculate_enroute([pos], state), [])

    def test_calculate_outside_route_no_zones(self):
        pos = self.create_position(60, 11, datetime.datetime(2020, 1, 1, 10, 0))
        state = OrchestratorState(
            last_gate=None,
            last_visible_gate=None,
            next_gate=None,
            in_range_of_gate=None,
            projector=self.projector,
            has_passed_finishpoint=False,
            recalculation_completed=True,
        )
        self.assertEqual(self.calculator.calculate_outside_route([pos], state), [])

    def test_enter_and_leave_zone_scores_capped(self):
        zone = MagicMock()
        zone.pk = 1
        zone.name = "EZ1"
        zone.path = [(11.0, 60.0), (11.1, 60.0), (11.1, 60.1)]
        zone.altitude = 0
        zone.ceiling = 10000
        self.calculator.zone_map = {1: zone}
        self.calculator.polygons = [(1, MagicMock())]
        self.calculator.polygon_helper = MagicMock()
        self.calculator.polygon_helper.check_inside_polygons.side_effect = [[1], [1], []]
        self.calculator.scorecard.calculate_penalty_zone_score.return_value = 50

        pos1 = self.create_position(60.05, 11.05, datetime.datetime(2020, 1, 1, 10, 0))
        pos2 = self.create_position(60.05, 11.05, datetime.datetime(2020, 1, 1, 10, 0, 10))
        pos3 = self.create_position(60.2, 11.2, datetime.datetime(2020, 1, 1, 10, 0, 11))

        with patch.object(self.calculator, "update_score") as mock_update:
            self.calculator.calculate_enroute([pos1], Mock(projector=self.projector))
            self.calculator.calculate_enroute([pos2], Mock(projector=self.projector))
            self.calculator.calculate_enroute([pos3], Mock(projector=self.projector))

        self.assertEqual(len(mock_update.call_args_list), 2)
        leave_msg = mock_update.call_args_list[1][0][0]
        self.assertEqual(leave_msg.score_type, "inside_penalty_zone")
        self.assertEqual(leave_msg.score, 50)
