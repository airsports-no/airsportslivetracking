import datetime
from unittest.mock import MagicMock, patch
from django.test import TestCase
from display.calculators.takeoff_and_landing_gate_calculator import TakeoffAndLandingGateCalculator
from display.calculators.calculator import OrchestratorState, TakeoffPassedEvent, LandingPassedEvent, GateMissedEvent, GatePassedEvent
from display.calculators.positions_and_gates import Gate, MultiGate
from display.models.contestant_utility_models import ContestantReceivedPosition
from display.utilities.coordinate_utilities import Projector
from display.utilities.cima_task_type_definitions import ANR_CATALOGUE

class TestTakeoffAndLandingGateCalculator(TestCase):
    def setUp(self):
        self.contestant = MagicMock()
        self.contestant.air_speed = 70
        self.contestant.navigation_task.task_subtype = None
        
        # Real-ish times for testing
        to_time = datetime.datetime(2026, 1, 1, 10, 0, tzinfo=datetime.timezone.utc)
        ldg_time = datetime.datetime(2026, 1, 1, 11, 0, tzinfo=datetime.timezone.utc)
        self.contestant.gate_times = {"TO 1": to_time, "LDG 1": ldg_time}
        
        self.scorecard = MagicMock()
        self.scorecard.get_gate_timing_score_for_gate_type.return_value = 0
        self.scorecard.get_extended_gate_width_for_gate_type.return_value = 200.0
        self.scorecard.task_type = ["precision"]
        
        self.route = MagicMock()
        tg = MagicMock()
        tg.name = "TO 1"
        tg.type = "to"
        tg.width = 50.0
        tg.gate_line = ((60.0, 11.0), (60.0, 11.1))
        
        lg = MagicMock()
        lg.name = "LDG 1"
        lg.type = "ldg"
        lg.width = 50.0
        lg.gate_line = ((60.0, 11.0), (60.0, 11.1))
        
        self.route.takeoff_gates = [tg]
        self.route.landing_gates = [lg]
        
        self.score_processing_queue = MagicMock()
        self.projector = Projector(60, 11)
        
        # Setup mock gates
        self.mock_to_gate = MagicMock(spec=Gate)
        self.mock_to_gate.name = "TO 1"
        self.mock_to_gate.type = "to"
        self.mock_to_gate.expected_time = to_time
        self.mock_to_gate.passing_time = None
        self.mock_to_gate.has_been_passed.return_value = False
        
        self.mock_ldg_gate = MagicMock(spec=Gate)
        self.mock_ldg_gate.name = "LDG 1"
        self.mock_ldg_gate.type = "ldg"
        self.mock_ldg_gate.expected_time = ldg_time
        self.mock_ldg_gate.passing_time = None
        self.mock_ldg_gate.has_been_passed.return_value = False
        
        # Setup MultiGates
        self.takeoff_multigate = MagicMock(spec=MultiGate)
        self.takeoff_multigate.gates = [self.mock_to_gate]
        # Use lambda or separate function to avoid issues with closure in has_been_passed
        self.takeoff_multigate.has_been_passed.side_effect = lambda: self.calculator.scored_takeoff
        
        self.landing_multigate = MagicMock(spec=MultiGate)
        self.landing_multigate.gates = [self.mock_ldg_gate]
        self.landing_multigate.has_been_passed.side_effect = lambda: self.calculator.scored_landing
        
        # We need to block the internal initiation to use our mocks
        with patch.object(TakeoffAndLandingGateCalculator, 'initiate_takeoff_and_landing_gates'):
            self.calculator = TakeoffAndLandingGateCalculator(
                self.contestant,
                self.scorecard,
                self.route,
                self.score_processing_queue,
                live_processing=False,
                projector=self.projector,
            )
            # Manually inject mocks after init
            self.calculator.takeoff_gate = self.takeoff_multigate
            self.calculator.landing_gate = self.landing_multigate


    def create_position(self, lat, lon, time):
        pos = MagicMock(spec=ContestantReceivedPosition)
        pos.latitude = float(lat)
        pos.longitude = float(lon)
        pos.time = time
        proj = self.projector.project_point(pos.latitude, pos.longitude)
        pos.projected_x = proj.projected_x
        pos.projected_y = proj.projected_y
        return pos

    def test_takeoff_gate_passed_only_once(self):
        # 1. Pass takeoff gate
        self.takeoff_multigate.get_gate_intersection_time.return_value = self.mock_to_gate.expected_time
        self.takeoff_multigate.intersected_gate = self.mock_to_gate
        self.mock_to_gate.passing_time = self.takeoff_multigate.get_gate_intersection_time.return_value
        
        pos = self.create_position(60, 11, self.mock_to_gate.expected_time)
        state = OrchestratorState(
            last_gate=None, last_visible_gate=None, next_gate=None,
            
            in_range_of_gate=None,
            projector=self.projector,
            has_passed_finishpoint=False,
            recalculation_completed=True,
            enroute=False
        )

        # Reset mock from init
        self.score_processing_queue.put_nowait.reset_mock()

        events = self.calculator.calculate_outside_route([pos], state)
        self.assertEqual(len(events), 1)
        self.assertIsInstance(events[0], TakeoffPassedEvent)
        
        # Scoring
        self.calculator.on_takeoff_passed(events[0])
        self.assertTrue(self.calculator.scored_takeoff)
        self.assertEqual(self.score_processing_queue.put_nowait.call_count, 1)
        
        # 2. Try to pass again
        self.takeoff_multigate.has_been_passed.side_effect = None
        self.takeoff_multigate.has_been_passed.return_value = True
        self.score_processing_queue.put_nowait.reset_mock()
        
        events2 = self.calculator.calculate_outside_route([pos], state)
        self.assertEqual(len(events2), 0)
        
        # Manual event trigger should also be blocked
        event2 = TakeoffPassedEvent(self.mock_to_gate, pos, pos.time)
        self.calculator.on_takeoff_passed(event2)
        self.score_processing_queue.put_nowait.assert_not_called()

    def test_takeoff_gate_missed_only_once(self):
        # Setup route with takeoff gates
        self.scorecard.get_gate_timing_score_for_gate_type.return_value = 200
        
        # Mock landing as already passed to prevent it interfering with takeoff finalize check
        self.calculator.scored_landing = True

        pos = self.create_position(60, 11, self.mock_to_gate.expected_time + datetime.timedelta(minutes=5))
        
        # Reset queue mock from init
        self.score_processing_queue.put_nowait.reset_mock()

        # Finalize without any pass
        self.calculator.finalise([pos])
        
        self.assertTrue(self.calculator.scored_takeoff)
        # We expect exactly 1 official score update
        self.assertEqual(self.score_processing_queue.put_nowait.call_count, 1)
        msg = self.score_processing_queue.put_nowait.call_args[0][0]
        self.assertEqual(msg.message, "missing takeoff gate")
        self.assertEqual(msg.score, 200)
        
        # Calling finalise again should not double score
        self.score_processing_queue.put_nowait.reset_mock()
        self.calculator.finalise([pos])
        self.score_processing_queue.put_nowait.assert_not_called()

    def test_landing_gate_passed_only_once(self):
        # Pass landing gate
        self.landing_multigate.get_gate_intersection_time.return_value = self.mock_ldg_gate.expected_time
        self.landing_multigate.intersected_gate = self.mock_ldg_gate
        self.mock_ldg_gate.passing_time = self.landing_multigate.get_gate_intersection_time.return_value
        
        # ALSO mock takeoff as already passed to prevent it interfering
        self.calculator.scored_takeoff = True
        self.takeoff_multigate.intersected_gate = self.mock_to_gate

        pos = self.create_position(60, 11, self.mock_ldg_gate.expected_time)
        state = OrchestratorState(
            last_gate=None, last_visible_gate=None, next_gate=None,
            
            in_range_of_gate=None,
            projector=self.projector,
            has_passed_finishpoint=True, 
            recalculation_completed=True,
            enroute=True
        )

        # Reset mock from init
        self.score_processing_queue.put_nowait.reset_mock()

        events = self.calculator.calculate_enroute([pos], state)
        self.assertEqual(len(events), 1)
        self.assertIsInstance(events[0], LandingPassedEvent)
        
        self.calculator.on_landing_passed(events[0])
        self.assertTrue(self.calculator.scored_landing)
        self.assertEqual(self.score_processing_queue.put_nowait.call_count, 1)
        
        # Pass again
        self.landing_multigate.has_been_passed.side_effect = None
        self.landing_multigate.has_been_passed.return_value = True
        events2 = self.calculator.calculate_enroute([pos], state)
        self.assertEqual(len(events2), 0)

    def test_landing_gate_missed_only_once(self):
        self.scorecard.get_gate_timing_score_for_gate_type.return_value = 200
        
        # Mock takeoff as already passed
        self.calculator.scored_takeoff = True

        pos = self.create_position(60, 11, self.mock_ldg_gate.expected_time + datetime.timedelta(minutes=5))
        
        # Reset queue mock
        self.score_processing_queue.put_nowait.reset_mock()

        self.calculator.finalise([pos])
        
        self.assertTrue(self.calculator.scored_landing)
        self.assertEqual(self.score_processing_queue.put_nowait.call_count, 1)
        msg = self.score_processing_queue.put_nowait.call_args[0][0]
        self.assertEqual(msg.message, "missing landing gate")
        
        self.score_processing_queue.put_nowait.reset_mock()
        self.calculator.finalise([pos])
        self.score_processing_queue.put_nowait.assert_not_called()

    def test_gate_passed_outside_route(self):
        self.takeoff_multigate.get_gate_intersection_time.return_value = self.mock_to_gate.expected_time
        self.takeoff_multigate.intersected_gate = self.mock_to_gate
        
        pos = self.create_position(60, 11, self.mock_to_gate.expected_time)
        state = OrchestratorState(
            last_gate=None, last_visible_gate=None, next_gate=None,
            
            in_range_of_gate=None,
            projector=self.projector,
            has_passed_finishpoint=False,
            recalculation_completed=True,
            enroute=False
        )

        events = self.calculator.calculate_outside_route([pos], state)
        self.assertEqual(len(events), 1)
        self.assertIsInstance(events[0], TakeoffPassedEvent)

    def test_proactive_takeoff_miss_on_route_gate_pass(self):
        # If SP is passed, takeoff must be missed if not already scored
        sp_gate = MagicMock(spec=Gate)
        sp_gate.name = "SP"
        sp_gate.type = "sp"
        
        pos = self.create_position(60, 11, self.mock_to_gate.expected_time + datetime.timedelta(minutes=1))
        event = GatePassedEvent(sp_gate, pos, pos.time)
        
        # Scorecard for miss
        self.scorecard.get_gate_timing_score_for_gate_type.return_value = 200
        self.score_processing_queue.put_nowait.reset_mock()

        self.calculator.on_gate_passed(event)
        
        self.assertTrue(self.calculator.scored_takeoff)
        self.assertEqual(self.score_processing_queue.put_nowait.call_count, 1)
        msg = self.score_processing_queue.put_nowait.call_args[0][0]
        self.assertEqual(msg.message, "missing takeoff gate")

    def test_anr_catalogue_takeoff_pass_uses_dedicated_score_type(self):
        self.contestant.navigation_task.task_subtype = ANR_CATALOGUE
        pos = self.create_position(60, 11, self.mock_to_gate.expected_time)
        event = TakeoffPassedEvent(self.mock_to_gate, pos, pos.time)

        self.score_processing_queue.put_nowait.reset_mock()
        self.calculator.on_takeoff_passed(event)

        msg = self.score_processing_queue.put_nowait.call_args[0][0]
        self.assertEqual(msg.score_type, "anr_takeoff_timing")
        self.assertEqual(msg.message, "ANR takeoff timing")

    def test_anr_catalogue_takeoff_miss_uses_dedicated_score_type(self):
        self.contestant.navigation_task.task_subtype = ANR_CATALOGUE
        self.scorecard.get_gate_timing_score_for_gate_type.return_value = 200
        self.calculator.scored_landing = True
        pos = self.create_position(60, 11, self.mock_to_gate.expected_time + datetime.timedelta(minutes=5))

        self.score_processing_queue.put_nowait.reset_mock()
        self.calculator.finalise([pos])

        msg = self.score_processing_queue.put_nowait.call_args[0][0]
        self.assertEqual(msg.score_type, "anr_takeoff_timing")
        self.assertEqual(msg.message, "ANR takeoff timing missed")
