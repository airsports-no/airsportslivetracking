import datetime
from unittest.mock import Mock, patch, MagicMock, call
from django.test import TestCase
from display.calculators.orchestrator import Orchestrator
from display.calculators.calculator import (
    GatePassedEvent,
    GateMissedEvent,
    TakeoffPassedEvent,
    LandingPassedEvent,
    StartingLinePassedEvent,
    AdaptiveStartEvent,
    EstimationUpdatedEvent,
    InRangeUpdatedEvent,
    OrchestratorState
)
from display.models.contestant_utility_models import ContestantReceivedPosition
from display.utilities.coordinate_utilities import Projector

class TestOrchestratorUnit(TestCase):
    def setUp(self):
        self.contestant = MagicMock()
        self.contestant.pk = 123
        self.contestant.air_speed = 70
        self.contestant.adaptive_start = False
        
        self.route = MagicMock()
        self.contestant.navigation_task.route = self.route
        self.route.waypoints = []
        self.route.takeoff_gates = []
        self.route.landing_gates = []
        
        self.scorecard = MagicMock()
        self.contestant.navigation_task.scorecard = self.scorecard
        
        self.score_processing_queue = MagicMock()
        
        # Initialize a real projector for deterministic coordinate math in tests
        self.projector = Projector(60, 11)
        
        with patch("display.calculators.orchestrator.WebsocketFacade"):
            # Mocking calculate_missing_gate_times to avoid DB issues
            self.contestant.calculate_missing_gate_times.return_value = {}
            self.orchestrator = Orchestrator(self.contestant, self.score_processing_queue, [], projector=self.projector)

    def create_position(self, lat, lon, time):
        pos = MagicMock(spec=ContestantReceivedPosition)
        pos.latitude = float(lat)
        pos.longitude = float(lon)
        pos.time = time
        
        # Calculate accurate projected coordinates
        proj = self.projector.project_point(pos.latitude, pos.longitude)
        pos.projected_x = proj.projected_x
        pos.projected_y = proj.projected_y
        
        return pos

    def test_handle_gate_passed_event(self):
        gate = MagicMock()
        gate.type = "tp"
        gate.waypoint.on_curved_segment = False
        
        pos = self.create_position(60, 11, datetime.datetime(2020, 1, 1, 10, 0))
        event = GatePassedEvent(gate, pos, pos.time, previous_gate=None)
        
        self.orchestrator.handle_event(event)
        
        self.assertEqual(self.orchestrator.last_gate, gate)
        self.assertTrue(self.orchestrator.enroute)

    def test_handle_gate_missed_event(self):
        gate = MagicMock()
        gate.type = "tp"
        gate.waypoint.on_curved_segment = False
        
        pos = self.create_position(60, 11, datetime.datetime(2020, 1, 1, 10, 0))
        event = GateMissedEvent(None, gate, pos)
        
        self.orchestrator.handle_event(event)
        
        self.assertEqual(self.orchestrator.last_gate, gate)
        self.assertTrue(self.orchestrator.enroute)

    def test_handle_takeoff_passed_event(self):
        gate = MagicMock()
        gate.waypoint.on_curved_segment = False
        
        # Mock a calculator
        calc = MagicMock()
        self.orchestrator.calculators = [calc]
        
        pos = self.create_position(60, 11, datetime.datetime(2020, 1, 1, 10, 0))
        event = TakeoffPassedEvent(gate, pos, pos.time)
        
        self.orchestrator.handle_event(event)
        
        calc.on_takeoff_passed.assert_called_with(event)
        self.assertEqual(self.orchestrator.last_gate, gate)

    def test_handle_landing_passed_event(self):
        gate = MagicMock()
        gate.waypoint.on_curved_segment = False
        
        # Mock a calculator
        calc = MagicMock()
        self.orchestrator.calculators = [calc]
        
        pos = self.create_position(60, 11, datetime.datetime(2020, 1, 1, 10, 0))
        event = LandingPassedEvent(gate, pos, pos.time)
        
        self.orchestrator.handle_event(event)
        
        calc.on_landing_passed.assert_called_with(event)
        self.assertEqual(self.orchestrator.last_gate, gate)
        self.assertTrue(self.orchestrator.has_landed)

    def test_handle_starting_line_passed_event(self):
        gate = MagicMock()
        gate.type = "sp"
        gate.waypoint.on_curved_segment = False
        
        pos = self.create_position(60, 11, datetime.datetime(2020, 1, 1, 10, 0))
        event = StartingLinePassedEvent(gate, pos, pos.time)
        
        self.orchestrator.handle_event(event)
        
        # last_gate is now updated by StartingLinePassedEvent
        self.assertEqual(self.orchestrator.last_gate, gate)
        # But enroute should be True
        self.assertTrue(self.orchestrator.enroute)

    def test_handle_adaptive_start_event(self):
        pos = self.create_position(60, 11, datetime.datetime(2020, 1, 1, 10, 0))
        event = AdaptiveStartEvent(pos.time, pos)
        
        calc = MagicMock()
        self.orchestrator.calculators = [calc]
        
        self.orchestrator.handle_event(event)
        self.assertTrue(self.orchestrator.recalculation_completed)
        calc.on_adaptive_start.assert_called_with(event)

    def test_handle_estimation_updated_event(self):
        gate = MagicMock()
        pos = self.create_position(60, 11, datetime.datetime(2020, 1, 1, 10, 0))
        event = EstimationUpdatedEvent(gate, pos.time, pos)
        
        self.orchestrator.handle_event(event)
        
        self.assertEqual(self.orchestrator.estimated_next_timed_gate, gate)
        self.assertEqual(self.orchestrator.estimated_crossing_time, pos.time)

    def test_handle_in_range_updated_event(self):
        gate = MagicMock()
        pos = self.create_position(60, 11, datetime.datetime(2020, 1, 1, 10, 0))
        event = InRangeUpdatedEvent(gate, pos)
        
        self.orchestrator.handle_event(event)
        
        self.assertEqual(self.orchestrator.in_range_of_gate, gate)

    def test_handle_finish_point_passed_triggers_passed_finishpoint(self):
        gate = MagicMock()
        gate.type = "fp"
        gate.waypoint.on_curved_segment = False
        
        pos = self.create_position(60, 11, datetime.datetime(2020, 1, 1, 10, 0))
        event = GatePassedEvent(gate, pos, pos.time, previous_gate=None)
        
        with patch.object(self.orchestrator, 'passed_finishpoint') as mock_passed:
            self.orchestrator.handle_event(event)
            mock_passed.assert_called_once()

    def test_calculate_score_ordering_between_calculators(self):
        # Order should be calc1 then calc2
        calc1 = MagicMock()
        calc2 = MagicMock()
        calc1.get_danger_level_and_accumulated_score.return_value = (0, 0)
        calc2.get_danger_level_and_accumulated_score.return_value = (0, 0)
        
        self.orchestrator.calculators = [calc1, calc2]
        pos = self.create_position(60, 11, datetime.datetime(2020, 1, 1, 10, 0))
        
        event1 = MagicMock(spec=GatePassedEvent)
        event2 = MagicMock(spec=InRangeUpdatedEvent)
        
        # Ensure they are different types or handled by correct methods
        calc1.calculate_outside_route.return_value = [event1]
        calc2.calculate_outside_route.return_value = [event2]
        
        with patch.object(self.orchestrator, 'handle_event') as mock_handle:
            self.orchestrator.calculate_score(pos)
            
            # Verify events handled in calculator order
            expected_calls = [call(event1), call(event2)]
            mock_handle.assert_has_calls(expected_calls)

    def test_state_refresh_between_calculator_calls(self):
        # State should be refreshed after calc1 emits an event
        calc1 = MagicMock()
        calc2 = MagicMock()
        calc1.get_danger_level_and_accumulated_score.return_value = (0, 0)
        calc2.get_danger_level_and_accumulated_score.return_value = (0, 0)
        
        self.orchestrator.calculators = [calc1, calc2]
        self.orchestrator.enroute = True
        pos = self.create_position(60, 11, datetime.datetime(2020, 1, 1, 10, 0))
        
        gate = MagicMock()
        gate.waypoint.on_curved_segment = False
        event1 = GatePassedEvent(gate, pos, pos.time, previous_gate=None)
        calc1.calculate_enroute.return_value = [event1]
        
        self.orchestrator.calculate_score(pos)
        
        # calc2 should have been called with the updated state (last_gate = gate)
        state_passed_to_calc2 = calc2.calculate_enroute.call_args[0][1]
        self.assertEqual(state_passed_to_calc2.last_gate, gate)

    def test_multi_event_ordering_from_single_calculator(self):
        # Events from a single calculator should be handled in the order they are returned
        calc = MagicMock()
        calc.get_danger_level_and_accumulated_score.return_value = (0, 0)
        self.orchestrator.calculators = [calc]
        
        pos = self.create_position(60, 11, datetime.datetime(2020, 1, 1, 10, 0))
        
        event1 = MagicMock(spec=GateMissedEvent)
        event2 = MagicMock(spec=GatePassedEvent)
        calc.calculate_outside_route.return_value = [event1, event2]
        
        with patch.object(self.orchestrator, 'handle_event') as mock_handle:
            self.orchestrator.calculate_score(pos)
            
            expected_calls = [call(event1), call(event2)]
            mock_handle.assert_has_calls(expected_calls)
