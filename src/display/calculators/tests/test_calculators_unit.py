import datetime
import numpy as np
from unittest.mock import Mock, patch, MagicMock, call
from django.test import TestCase
from display.calculators.calculator import (
    GatekeeperState,
    GatePassedEvent,
    GateMissedEvent,
    TakeoffPassedEvent,
    LandingPassedEvent,
    StartingLinePassedEvent,
    PokerGatePassedEvent,
)
from display.calculators.gate_calculator import GateCalculator
from display.calculators.anr_corridor_calculator import AnrCorridorCalculator
from display.calculators.backtracking_and_procedure_turns import BacktrackingAndProcedureTurnsCalculator
from display.calculators.landing_pattern_calculator import LandingPatternCalculator
from display.calculators.poker_calculator import PokerCalculator
from display.calculators.prohibited_zone_calculator import ProhibitedZoneCalculator
from display.calculators.penalty_zone_calculator import PenaltyZoneCalculator
from display.models.contestant_utility_models import ContestantReceivedPosition
from shapely.geometry import Polygon

class CalculatorUnitTestBase(TestCase):
    def setUp(self):
        self.contestant = MagicMock()
        self.contestant.air_speed = 70
        
        self.route = MagicMock()
        self.contestant.navigation_task.route = self.route
        
        # Mocking waypoints as a list to be subscriptable
        self.waypoint1 = MagicMock()
        self.waypoint1.latitude = 60.0
        self.waypoint1.longitude = 11.0
        self.waypoint1.name = "WP1"
        self.waypoint1.type = "sp"
        self.waypoint1.bearing = 0
        self.waypoint1.bearing_from_previous = 0
        self.waypoint1.width = 100.0
        self.waypoint1.gate_line = ((60.0, 11.0), (60.0, 11.1))
        self.waypoint1.infinite_passing_time = None
        self.waypoint1.passing_time = None
        self.waypoint1.missed = False
        self.route.waypoints = [self.waypoint1]
        self.route.corridor_polygon = [{"lat": 60.0, "lng": 11.0}, {"lat": 60.1, "lng": 11.0}, {"lat": 60.1, "lng": 11.1}]
        self.route.takeoff_gates = []
        self.route.landing_gates = []
        
        self.scorecard = MagicMock()
        self.scorecard.get_extended_gate_width_for_gate_type.return_value = 200.0
        self.contestant.navigation_task.scorecard = self.scorecard
        
        self.gates = [self.waypoint1] # Provide a default gate to avoid IndexError
        self.score_processing_queue = MagicMock()
        self.projector = MagicMock()

    def create_position(self, lat, lon, time):
        if time.tzinfo is None:
            time = time.replace(tzinfo=datetime.timezone.utc)
        pos = MagicMock(spec=ContestantReceivedPosition)
        pos.latitude = float(lat)
        pos.longitude = float(lon)
        pos.time = time
        return pos

class TestGateCalculator(CalculatorUnitTestBase):
    def setUp(self):
        super().setUp()
        self.calculator = GateCalculator(
            self.contestant,
            self.scorecard,
            self.gates,
            self.route,
            self.score_processing_queue,
            live_processing=False
        )

    def test_calculate_enroute_takeoff(self):
        # Mock takeoff gate
        takeoff_gate = MagicMock()
        takeoff_gate.has_been_passed.return_value = False
        takeoff_gate.intersected_gate = MagicMock()
        takeoff_gate.intersected_gate.name = "Takeoff 1"
        
        state = GatekeeperState(
            last_gate=None,
            outstanding_gates=[],
            in_range_of_gate=None,
            projector=self.projector,
            takeoff_gate=takeoff_gate,
            landing_gate=None,
            has_passed_finishpoint=False,
            recalculation_completed=True
        )
        
        pos = self.create_position(60, 11, datetime.datetime(2020, 1, 1, 10, 0))
        track = [pos, pos] # Need at least 2 for some calculations
        
        # Intersection time found
        takeoff_gate.get_gate_intersection_time.return_value = pos.time
        
        events = self.calculator.calculate_enroute(track, state)
        
        self.assertTrue(any(isinstance(e, TakeoffPassedEvent) for e in events))

    def test_calculate_enroute_gate_passed(self):
        gate = MagicMock()
        gate.name = "TP 1"
        gate.latitude = 60.0
        gate.longitude = 11.0
        gate.is_passed_in_correct_direction_track.return_value = True
        gate.has_been_passed.return_value = False
        gate.infinite_passing_time = None
        gate.passing_time = None
        gate.missed = False
        gate.time_check = False
        
        self.calculator.gates = [gate]
        
        state = GatekeeperState(
            last_gate=None,
            outstanding_gates=[gate],
            in_range_of_gate=None,
            projector=self.projector,
            takeoff_gate=None,
            landing_gate=None,
            has_passed_finishpoint=False,
            recalculation_completed=True
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
        gate.is_passed_in_correct_direction_track.return_value = True
        gate.has_infinite_been_passed.return_value = False
        
        self.calculator.gates = [gate]
        self.contestant.adaptive_start = True
        
        state = GatekeeperState(
            last_gate=None,
            outstanding_gates=[gate],
            in_range_of_gate=None,
            projector=self.projector,
            takeoff_gate=None,
            landing_gate=None,
            has_passed_finishpoint=False,
            recalculation_completed=False
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
        gate.is_passed_in_correct_direction_track.return_value = False
        
        self.calculator.gates = [gate]
        
        state = GatekeeperState(
            last_gate=None,
            outstanding_gates=[gate],
            in_range_of_gate=None,
            projector=self.projector,
            takeoff_gate=None,
            landing_gate=None,
            has_passed_finishpoint=False,
            recalculation_completed=False
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
        gate1.has_been_passed.return_value = False
        gate1.infinite_passing_time = None
        gate1.passing_time = None
        gate1.missed = False
        
        gate2 = MagicMock()
        gate2.name = "TP 2"
        gate2.is_passed_in_correct_direction_track.return_value = True
        gate2.has_been_passed.return_value = False
        gate2.infinite_passing_time = None
        gate2.passing_time = None
        gate2.missed = False
        
        self.calculator.gates = [gate1, gate2]
        
        state = GatekeeperState(
            last_gate=None,
            outstanding_gates=[gate1, gate2],
            in_range_of_gate=None,
            projector=self.projector,
            takeoff_gate=None,
            landing_gate=None,
            has_passed_finishpoint=False,
            recalculation_completed=True
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
        gate.inside_distance = 1000.0 # 1km
        gate.get_gate_intersection_time.return_value = None
        gate.infinite_passing_time = None
        gate.passing_time = None
        gate.missed = False
        
        mock_dist.return_value = 500.0 # 500m < 1km
        
        state = GatekeeperState(
            last_gate=None,
            outstanding_gates=[gate],
            in_range_of_gate=None,
            projector=self.projector,
            takeoff_gate=None,
            landing_gate=None,
            has_passed_finishpoint=False,
            recalculation_completed=True
        )
        
        # Position within 1km (roughly 111m North and 55m East)
        pos = self.create_position(60.001, 11.001, datetime.datetime(2020, 1, 1, 10, 0))
        
        from display.calculators.calculator import InRangeUpdatedEvent
        events = self.calculator.calculate_enroute([pos], state)
        self.assertTrue(any(isinstance(e, InRangeUpdatedEvent) and e.gate == gate for e in events))

class TestAnrCorridorCalculator(CalculatorUnitTestBase):
    @patch("display.calculators.anr_corridor_calculator.PolygonHelper")
    @patch("display.calculators.anr_corridor_calculator.plt")
    @patch.object(AnrCorridorCalculator, 'plot_polygon')
    def setUp(self, mock_plot, mock_plt, mock_polygon_helper):
        super().setUp()
        self.scorecard.corridor_grace_time = 5
        self.scorecard.corridor_outside_penalty = 10
        self.scorecard.corridor_maximum_penalty = 100
        self.scorecard.corridor_maximum_penalty_is_per_leg = False
        
        # Mock PolygonHelper to return a mock boundary
        mock_ph_instance = mock_polygon_helper.return_value
        mock_ph_instance.utm.transform_points.return_value = np.array([[0,0], [1,0], [1,1], [0,0]])
        # Mock transform_point to return a tuple to avoid unpacking error
        mock_ph_instance.utm.transform_point.return_value = (0.0, 0.0)
        
        self.calculator = AnrCorridorCalculator(
            self.contestant,
            self.scorecard,
            self.gates,
            self.route,
            self.score_processing_queue,
            live_processing=False
        )
        self.calculator.polygon_helper = MagicMock()
        # Ensure transform_point is mocked on the assigned instance too
        self.calculator.polygon_helper.utm.transform_point.return_value = (0.0, 0.0)

    def test_calculate_enroute_inside(self):
        self.calculator._check_inside_polygon = MagicMock(return_value=True)
        
        pos = self.create_position(60, 11, datetime.datetime(2020, 1, 1, 10, 0))
        state = GatekeeperState(last_gate=MagicMock(), outstanding_gates=[], in_range_of_gate=None, projector=self.projector, takeoff_gate=None, landing_gate=None, has_passed_finishpoint=False, recalculation_completed=True)
        
        events = self.calculator.calculate_enroute([pos], state)
        
        self.assertEqual(events, [])
        self.assertEqual(self.calculator.corridor_state, self.calculator.INSIDE_CORRIDOR)

    def test_calculate_enroute_outside(self):
        self.calculator._check_inside_polygon = MagicMock(return_value=False)
        
        last_gate = MagicMock()
        last_gate.name = "SP"
        last_gate.type = "sp"
        
        pos = self.create_position(60.5, 11.5, datetime.datetime(2020, 1, 1, 10, 0))
        state = GatekeeperState(last_gate=last_gate, outstanding_gates=[], in_range_of_gate=None, projector=self.projector, takeoff_gate=None, landing_gate=None, has_passed_finishpoint=False, recalculation_completed=True)
        
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
        
        with patch.object(self.calculator, '_check_inside_polygon', return_value=False):
            with patch.object(self.calculator, 'update_score') as mock_update:
                # 1. Test with per-leg OFF (default)
                self.calculator.corridor_maximum_penalty_is_per_leg = False
                self.calculator.check_outside_corridor([pos], gate2)
                
                # Find any calls that look like "exiting corridor"
                exiting_calls = [c for c in mock_update.call_args_list if "exiting corridor" in c[0][0].message]
                self.assertEqual(len(exiting_calls), 0, "Should not emit redundant 'exiting corridor' message on leg advance while already outside")
                
                # 2. Test with per-leg ON
                self.calculator.corridor_maximum_penalty_is_per_leg = True
                # Reset state for fresh run
                self.calculator.corridor_state = self.calculator.OUTSIDE_CORRIDOR
                self.calculator.crossed_outside_time = datetime.datetime(2020, 1, 1, 10, 0, tzinfo=datetime.timezone.utc)
                self.calculator.current_leg_outside_start_time = self.calculator.crossed_outside_time
                self.calculator.crossed_outside_gate = gate1
                self.calculator.is_first_leg_of_excursion = True
                
                mock_update.reset_mock()
                self.calculator.check_outside_corridor([pos], gate2)
                
                exiting_calls_per_leg = [c for c in mock_update.call_args_list if "exiting corridor" in c[0][0].message]
                # When per-leg is ON, it SHOULD emit exactly ONE "exiting corridor" for the NEW leg TP1
                self.assertEqual(len(exiting_calls_per_leg), 1)
                self.assertEqual(exiting_calls_per_leg[0][0][0].gate.name, "TP1")
                
                # Verify the SP was finalized (should be the first call)
                sp_final_msg = mock_update.call_args_list[0][0][0]
                self.assertEqual(sp_final_msg.gate.name, "SP")
                self.assertIn("outside corridor", sp_final_msg.message)

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
        
        with patch.object(self.calculator, '_check_inside_polygon') as mock_check:
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
            
            with patch.object(self.calculator, 'update_score') as mock_update:
                self.calculator.check_outside_corridor([pos15], gate2)
                
                # SP finalized, TP1 started.
                # TP1 check_and_apply_outside_penalty called at T=15.
                # Since current_time=T=15 and current_leg_start=T=15, outside_time=0.
                self.assertEqual(self.calculator.accumulated_score, 0)
                self.assertFalse(self.calculator.is_first_leg_of_excursion)
                
                # 4. Stay outside for another 10 seconds in Leg 2 (T=25)
                t25 = t0 + datetime.timedelta(seconds=25)
                pos25 = self.create_position(0, 0, t25)
                self.calculator.check_outside_corridor([pos25], gate2)
                
                # Expectation: 10s in Leg 2. NO GRACE. 10 * 10 = 100 points.
                self.assertEqual(self.calculator.accumulated_score, 100.0)
                
                # Check message score_type contains gate name
                self.assertEqual(mock_update.call_args_list[1][0][0].score_type, "outside_corridor_TP1")

class TestBacktrackingAndProcedureTurnsCalculator(CalculatorUnitTestBase):
    def setUp(self):
        super().setUp()
        self.scorecard.backtracking_bearing_difference = 90
        self.scorecard.backtracking_penalty = 200
        self.scorecard.backtracking_maximum_penalty = 1000
        self.scorecard.backtracking_grace_time_seconds = 10
        self.scorecard.get_backtracking_after_steep_gate_grace_period_seconds_for_gate_type.return_value = 0
        self.scorecard.get_backtracking_after_gate_grace_period_nm_for_gate_type.return_value = 0
        self.scorecard.get_backtracking_before_gate_grace_period_nm_for_gate_type.return_value = 0
        
        self.calculator = BacktrackingAndProcedureTurnsCalculator(
            self.contestant,
            self.scorecard,
            self.gates,
            self.route,
            self.score_processing_queue,
            live_processing=False
        )

    def test_calculate_enroute_tracking(self):
        last_gate = MagicMock()
        last_gate.bearing = 0 # North
        last_gate.bearing_from_previous = 0
        last_gate.type = "not_sp"
        last_gate.get_distance_to_gate_line.return_value = 2000 # far away
        last_gate.is_procedure_turn = False
        
        pos1 = self.create_position(60, 11, datetime.datetime(2020, 1, 1, 10, 0))
        pos2 = self.create_position(60.1, 11, datetime.datetime(2020, 1, 1, 10, 1)) # Heading North (0)
        
        state = GatekeeperState(last_gate=last_gate, outstanding_gates=[], in_range_of_gate=None, projector=self.projector, takeoff_gate=None, landing_gate=None, has_passed_finishpoint=False, recalculation_completed=True)
        
        self.calculator.tracking_state = self.calculator.TRACKING
        self.calculator.calculate_enroute([pos1, pos2], state)
        
        self.assertEqual(self.calculator.tracking_state, self.calculator.TRACKING)

    def test_calculate_enroute_backtracking(self):
        last_gate = MagicMock()
        last_gate.bearing = 0 # North
        last_gate.bearing_from_previous = 0
        last_gate.type = "not_sp"
        last_gate.is_steep_turn = False
        last_gate.get_distance_to_gate_line.return_value = 2000 # far away
        last_gate.is_procedure_turn = False
        
        pos1 = self.create_position(60.1, 11, datetime.datetime(2020, 1, 1, 10, 0))
        pos2 = self.create_position(60.0, 11, datetime.datetime(2020, 1, 1, 10, 1)) # Heading South (180) - backtracking
        
        # Force state to TRACKING to allow backtracking detection
        self.calculator.tracking_state = self.calculator.TRACKING
        
        state = GatekeeperState(last_gate=last_gate, outstanding_gates=[], in_range_of_gate=None, projector=self.projector, takeoff_gate=None, landing_gate=None, has_passed_finishpoint=False, recalculation_completed=True)
        
        # One call to start backtracking (temporary)
        self.calculator.calculate_enroute([pos1, pos2], state)
        self.assertEqual(self.calculator.tracking_state, self.calculator.BACKTRACKING_TEMPORARY)
        
        # Fast forward time to exceed grace period
        pos3 = self.create_position(59.9, 11, datetime.datetime(2020, 1, 1, 10, 15))
        self.calculator.calculate_enroute([pos1, pos2, pos3], state)
        self.assertEqual(self.calculator.tracking_state, self.calculator.BACKTRACKING)

class TestLandingPatternCalculator(CalculatorUnitTestBase):
    @patch("display.calculators.landing_pattern_calculator.Projector")
    def setUp(self, mock_projector):
        super().setUp()
        self.route.landing_gates = [MagicMock()]
        self.route.landing_gates[0].latitude = 60.0
        self.route.landing_gates[0].longitude = 11.0
        
        self.calculator = LandingPatternCalculator(
            self.contestant,
            self.scorecard,
            self.gates,
            self.route,
            self.score_processing_queue,
            live_processing=False
        )

    def test_calculate_outside_route_landing(self):
        landing_gate = MagicMock()
        landing_gate.gates = [MagicMock()]
        landing_gate.intersected_gate = MagicMock()
        
        state = GatekeeperState(last_gate=None, outstanding_gates=[], in_range_of_gate=None, projector=self.projector, takeoff_gate=None, landing_gate=landing_gate, has_passed_finishpoint=False, recalculation_completed=True)
        
        pos = self.create_position(60, 11, datetime.datetime(2020, 1, 1, 10, 0))
        landing_gate.get_gate_intersection_time.return_value = pos.time
        
        events = self.calculator.calculate_outside_route([pos], state)
        
        self.assertTrue(any(isinstance(e, LandingPassedEvent) for e in events))

class TestPokerCalculator(CalculatorUnitTestBase):
    @patch("display.calculators.poker_calculator.PolygonHelper")
    def setUp(self, mock_polygon_helper):
        super().setUp()
        gate = MagicMock()
        gate.name = "Poker 1"
        gate.waypoint.latitude = 60.0
        gate.waypoint.longitude = 11.0
        self.gates = [gate]
        # Make the mock prohibited_set.filter return something subscriptable
        self.route.prohibited_set.filter.return_value = [MagicMock(name="Poker 1", path=[])]
        # Explicitly set return value for filter since we accessed it by name before
        self.route.prohibited_set.filter.return_value[0].name = "Poker 1"
        
        self.calculator = PokerCalculator(
            self.contestant,
            self.scorecard,
            self.gates,
            self.route,
            self.score_processing_queue,
            live_processing=False
        )
        # PolygonHelper is already mocked in setUp, but we need to re-mock the instance attributes
        self.calculator.polygon_helper = MagicMock()

    def test_check_polygons_passed(self):
        # We need to re-initialize sorted_polygons because it was built during __init__ with mocked filter
        # Or better, just make sure __init__ worked.
        self.calculator.sorted_polygons = [("Poker 1", MagicMock(), 0)]
        self.calculator.polygon_helper.check_inside_polygons.return_value = ["Poker 1"]
        
        pos = self.create_position(60, 11, datetime.datetime(2020, 1, 1, 10, 0))
        state = GatekeeperState(last_gate=None, outstanding_gates=[], in_range_of_gate=None, projector=self.projector, takeoff_gate=None, landing_gate=None, has_passed_finishpoint=False, recalculation_completed=True)
        
        events = self.calculator.check_polygons(pos, state)
        
        self.assertTrue(any(isinstance(e, PokerGatePassedEvent) for e in events))

class TestProhibitedZoneCalculator(CalculatorUnitTestBase):
    @patch("display.calculators.prohibited_zone_calculator.PolygonHelper")
    def setUp(self, mock_polygon_helper):
        super().setUp()
        self.scorecard.prohibited_zone_grace_time = 5
        self.scorecard.prohibited_zone_penalty = 200
        self.scorecard.prohibited_zone_maximum = 1000
        zone = MagicMock(pk=1, name="Zone 1", path=[(60, 11), (60, 12), (61, 12), (61, 11)])
        self.route.prohibited_set.filter.return_value = [zone]
        
        self.calculator = ProhibitedZoneCalculator(
            self.contestant,
            self.scorecard,
            self.gates,
            self.route,
            self.score_processing_queue,
            live_processing=False
        )
        # In refactored version, we use self.polygon_helper directly
        self.mock_helper = self.calculator.polygon_helper

    def test_check_inside_prohibited_zone_penalty(self):
        self.mock_helper.check_inside_polygons.return_value = [1]
        
        pos1 = self.create_position(60, 11, datetime.datetime(2020, 1, 1, 10, 0))
        self.calculator.check_inside_prohibited_zone([pos1], None)
        self.assertFalse(self.score_processing_queue.put_nowait.called)
        
        pos2 = self.create_position(60, 11, datetime.datetime(2020, 1, 1, 10, 10))
        self.calculator.check_inside_prohibited_zone([pos1, pos2], None)
        self.assertTrue(self.score_processing_queue.put_nowait.called)

class TestPenaltyZoneCalculator(CalculatorUnitTestBase):
    @patch("display.calculators.penalty_zone_calculator.PolygonHelper")
    def setUp(self, mock_polygon_helper):
        super().setUp()
        self.scorecard.calculate_penalty_zone_score.return_value = 50
        zone = MagicMock(pk=1, name="Penalty 1", path=[(60, 11), (60, 12), (61, 12), (61, 11)])
        self.route.prohibited_set.filter.return_value = [zone]
        
        self.calculator = PenaltyZoneCalculator(
            self.contestant,
            self.scorecard,
            self.gates,
            self.route,
            self.score_processing_queue,
            live_processing=False
        )
        # In refactored version, we use self.polygon_helper directly
        self.mock_helper = self.calculator.polygon_helper

    def test_check_inside_penalty_zone(self):
        # Entering
        self.mock_helper.check_inside_polygons.return_value = [1]
        pos1 = self.create_position(60, 11, datetime.datetime(2020, 1, 1, 10, 0))
        self.calculator.check_inside_prohibited_zone([pos1], None)
        
        self.assertEqual(self.calculator.entered_polygon_times[1], pos1.time)
        self.assertTrue(self.score_processing_queue.put_nowait.called)
        
        # Inside
        pos2 = self.create_position(60, 11, datetime.datetime(2020, 1, 1, 10, 1))
        self.calculator.check_inside_prohibited_zone([pos1, pos2], None)
        self.assertEqual(self.calculator.running_penalty[1], 50)
        
        # Exiting
        self.mock_helper.check_inside_polygons.return_value = []
        pos3 = self.create_position(60.1, 11.1, datetime.datetime(2020, 1, 1, 10, 2))
        self.calculator.check_inside_prohibited_zone([pos1, pos2, pos3], None)
        
        self.assertNotIn(1, self.calculator.entered_polygon_times)

from display.calculators.gatekeeper import Gatekeeper
