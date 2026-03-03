import datetime
import numpy as np
from unittest.mock import Mock, patch, MagicMock
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
            self.score_processing_queue
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

class TestAnrCorridorCalculator(CalculatorUnitTestBase):
    @patch("display.calculators.anr_corridor_calculator.PolygonHelper")
    @patch("display.calculators.anr_corridor_calculator.plt")
    @patch.object(AnrCorridorCalculator, 'plot_polygon')
    def setUp(self, mock_plot, mock_plt, mock_polygon_helper):
        super().setUp()
        self.scorecard.corridor_grace_time = 5
        self.scorecard.corridor_outside_penalty = 10
        self.scorecard.corridor_maximum_penalty = 100
        
        # Mock PolygonHelper to return a mock boundary
        mock_ph_instance = mock_polygon_helper.return_value
        mock_ph_instance.utm.transform_points.return_value = np.array([[0,0], [1,0], [1,1], [0,0]])
        
        self.calculator = AnrCorridorCalculator(
            self.contestant,
            self.scorecard,
            self.gates,
            self.route,
            self.score_processing_queue
        )
        self.calculator.polygon_helper = MagicMock()

    def test_calculate_enroute_inside(self):
        self.calculator.polygon_helper.check_inside_polygons.return_value = ["test"]
        
        pos = self.create_position(60, 11, datetime.datetime(2020, 1, 1, 10, 0))
        state = GatekeeperState(last_gate=MagicMock(), outstanding_gates=[], in_range_of_gate=None, projector=self.projector, takeoff_gate=None, landing_gate=None, has_passed_finishpoint=False, recalculation_completed=True)
        
        events = self.calculator.calculate_enroute([pos], state)
        
        self.assertEqual(events, [])
        self.assertEqual(self.calculator.corridor_state, self.calculator.INSIDE_CORRIDOR)

    def test_calculate_enroute_outside(self):
        self.calculator.polygon_helper.check_inside_polygons.return_value = [] # Outside
        
        last_gate = MagicMock()
        last_gate.name = "SP"
        last_gate.type = "sp"
        
        pos = self.create_position(60.5, 11.5, datetime.datetime(2020, 1, 1, 10, 0))
        state = GatekeeperState(last_gate=last_gate, outstanding_gates=[], in_range_of_gate=None, projector=self.projector, takeoff_gate=None, landing_gate=None, has_passed_finishpoint=False, recalculation_completed=True)
        
        events = self.calculator.calculate_enroute([pos], state)
        
        self.assertEqual(self.calculator.corridor_state, self.calculator.OUTSIDE_CORRIDOR)
        self.assertEqual(self.calculator.crossed_outside_time, pos.time)

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
            self.score_processing_queue
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
            self.score_processing_queue
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
            self.score_processing_queue
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
            self.score_processing_queue
        )
        # Mock the per-zone helper
        self.mock_helper = self.calculator.zone_helpers[0][1]

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
            self.score_processing_queue
        )
        # Mock the per-zone helper
        self.mock_helper = self.calculator.zone_helpers[0][1]

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

class TestGatekeeperEventHandling(CalculatorUnitTestBase):
    @patch("display.calculators.gatekeeper.WebsocketFacade")
    def setUp(self, mock_ws):
        super().setUp()
        # Mocking calculate_missing_gate_times to avoid DB issues
        self.contestant.calculate_missing_gate_times.return_value = {}
        self.gatekeeper = Gatekeeper(self.contestant, self.score_processing_queue, [])

    def test_handle_gate_passed_event(self):
        gate = MagicMock()
        gate.type = "tp"
        self.gatekeeper.outstanding_gates = [gate]
        
        pos = self.create_position(60, 11, datetime.datetime(2020, 1, 1, 10, 0))
        event = GatePassedEvent(gate, pos, pos.time)
        
        self.gatekeeper.handle_event(event)
        
        self.assertEqual(self.gatekeeper.last_gate, gate)
        self.assertNotIn(gate, self.gatekeeper.outstanding_gates)
        self.assertTrue(gate.pass_gate.called)

    def test_handle_gate_missed_event(self):
        gate = MagicMock()
        self.gatekeeper.outstanding_gates = [gate]
        
        pos = self.create_position(60, 11, datetime.datetime(2020, 1, 1, 10, 0))
        event = GateMissedEvent(None, gate, pos)
        
        self.gatekeeper.handle_event(event)
        
        self.assertNotIn(gate, self.gatekeeper.outstanding_gates)
        self.assertTrue(gate.missed)

    def test_handle_takeoff_passed_event(self):
        gate = MagicMock()
        takeoff_gate = MagicMock()
        self.gatekeeper.takeoff_gate = takeoff_gate
        
        pos = self.create_position(60, 11, datetime.datetime(2020, 1, 1, 10, 0))
        event = TakeoffPassedEvent(gate, pos, pos.time)
        
        self.gatekeeper.handle_event(event)
        
        self.assertTrue(gate.pass_gate.called)
        self.assertTrue(takeoff_gate.pass_gate.called)
