import datetime
from unittest.mock import MagicMock, patch
from django.test import TestCase

from display.calculators.calculator import OrchestratorState, GateMissedEvent, GatePassedEvent
from display.calculators.backtracking_and_procedure_turns import BacktrackingAndProcedureTurnsCalculator
from display.models.contestant_utility_models import ContestantReceivedPosition
from display.utilities.coordinate_utilities import Projector

class DummyWaypoint:
    def __init__(self, name, type, bearing, is_procedure_turn=False, lat=60.0, lon=11.0):
        self.name = name
        self.type = type
        self.latitude = lat
        self.longitude = lon
        self.bearing = float(bearing)
        self.bearing_from_previous = 0.0
        self.width = 100.0
        self.gate_line = ((lat, lon), (lat, lon + 0.01))
        self.gate_line_infinite = ((lat, lon - 1.0), (lat, lon + 1.0))
        self.gate_heading = 0.0
        self.inside_distance = 100.0
        self.outside_distance = 200.0
        self.gate_check = True
        self.time_check = True
        self.gate_passed = False
        self.gate_missed = False
        self.distance_next = 1000.0
        self.bearing_next = 0.0
        self.is_procedure_turn = is_procedure_turn
        self.is_steep_turn = False
        self.is_dummy = False
        self.has_extended_been_passed = MagicMock(return_value=True)

class TestPTDoublePenalty(TestCase):
    def setUp(self):
        self.contestant = MagicMock()
        self.contestant.air_speed = 70
        self.contestant.pk = 1

        self.route = MagicMock()
        self.contestant.navigation_task.route = self.route

        self.scorecard = MagicMock()
        self.scorecard.backtracking_bearing_difference = 90
        self.scorecard.backtracking_penalty = 200
        self.scorecard.backtracking_maximum_penalty = 1000
        self.scorecard.backtracking_grace_time_seconds = 10
        self.scorecard.get_backtracking_after_steep_gate_grace_period_seconds_for_gate_type.return_value = 0
        self.scorecard.get_backtracking_after_gate_grace_period_nm_for_gate_type.return_value = 0
        self.scorecard.get_backtracking_before_gate_grace_period_nm_for_gate_type.return_value = 0
        self.scorecard.get_procedure_turn_penalty_for_gate_type.return_value = 200
        self.scorecard.get_extended_gate_width_for_gate_type.return_value = 200.0

        self.contestant.navigation_task.scorecard = self.scorecard
        
        # Waypoints
        self.wp_sp = DummyWaypoint("SP", "sp", 0.0, lat=60.0, lon=11.0)
        self.wp_pt = DummyWaypoint("PT_GATE", "tp", 90.0, is_procedure_turn=True, lat=60.1, lon=11.0)
        
        self.route.waypoints = [self.wp_sp, self.wp_pt]
        self.contestant.gate_times = {
            "SP": datetime.datetime(2020, 1, 1, 10, 0, tzinfo=datetime.timezone.utc),
            "PT_GATE": datetime.datetime(2020, 1, 1, 10, 10, tzinfo=datetime.timezone.utc)
        }

        self.score_processing_queue = MagicMock()
        self.projector = Projector(60, 11)

        self.calculator = BacktrackingAndProcedureTurnsCalculator(
            self.contestant,
            self.scorecard,
            self.route,
            self.score_processing_queue,
            live_processing=False,
            projector=self.projector,
        )
        
        self.calculator.update_score = MagicMock()

    def create_position(self, lat, lon, time):
        if time.tzinfo is None:
            time = time.replace(tzinfo=datetime.timezone.utc)
        pos = ContestantReceivedPosition()
        pos.latitude = float(lat)
        pos.longitude = float(lon)
        pos.time = time
        proj = self.projector.project_point(pos.latitude, pos.longitude)
        pos.projected_x = proj.projected_x
        pos.projected_y = proj.projected_y
        return pos

    def test_double_penalty(self):
        # 1. Start at SP
        gate_sp = self.calculator.gates[0]
        start_time = datetime.datetime(2020, 1, 1, 10, 0, 0, tzinfo=datetime.timezone.utc)
        pos_sp = self.create_position(60.0, 11.0, start_time)
        self.calculator.on_gate_passed(GatePassedEvent(gate_sp, pos_sp, start_time))
        self.calculator.tracking_state = self.calculator.TRACKING
        self.calculator.last_gate_previous_round = gate_sp
        
        # Warmup call
        pos_warmup = self.create_position(59.9, 11.0, start_time + datetime.timedelta(seconds=1))
        self.calculator.calculate_track_score([pos_sp, pos_warmup], gate_sp, gate_sp, self.calculator.gates[1])

        # 2. Move towards PT_GATE, but circle BEFORE reaching it
        # We need to trigger backtracked_on_current_leg = True
        pos1 = self.create_position(60.0, 11.0, start_time + datetime.timedelta(seconds=1))
        # 180 degree turn detected by detect_circling
        track = [pos_warmup, pos1]
        for i in range(2, 10):
            angle = (i-1) * 45 
            import math
            radius = 0.01
            lat = 60.0 + radius * math.cos(math.radians(angle))
            lon = 11.0 + radius * math.sin(math.radians(angle))
            pos = self.create_position(lat, lon, start_time + datetime.timedelta(seconds=i))
            track.append(pos)
            self.calculator.detect_circling(track, gate_sp, gate_sp)
        
        # Fast forward time to exceed circling duration (5s)
        pos_last = track[-1]
        pos_final = self.create_position(pos_last.latitude, pos_last.longitude, pos_last.time + datetime.timedelta(seconds=10))
        track.append(pos_final)
        self.calculator.detect_circling(track, gate_sp, gate_sp)
        
        self.assertTrue(self.calculator.backtracked_on_current_leg)
        
        # 3. Now miss the gate
        gate_pt = self.calculator.gates[1]
        gate_pt.missed = True
        self.calculator.on_gate_missed(GateMissedEvent(gate_sp, gate_pt, pos_final))
        
        # 4. Continue flying (after missing the gate)
        pos3 = self.create_position(60.1, 11.1, pos_final.time + datetime.timedelta(seconds=5))
        self.calculator.calculate_track_score(track + [pos3], gate_pt, None, None)

        # Now it should stay in TRACKING (or STARTED) because it was missed
        # Wait, if it missed the gate, it advanced last_visible_gate to gate_pt
        # but because missed is True, it should not have entered PROCEDURE_TURN state.
        self.assertNotEqual(self.calculator.tracking_state, self.calculator.PROCEDURE_TURN)
        self.assertTrue(self.calculator.was_backtracked_on_leg_leading_to_last_gate)

        # 5. Wait for time (PT timeout would have been 180s)
        pos4 = self.create_position(60.1, 11.2, pos3.time + datetime.timedelta(seconds=200))
        self.calculator.calculate_track_score(track + [pos3, pos4], gate_pt, None, None)

        # Verify second penalty (procedure_turn) suppressed
        pt_calls = [c for c in self.calculator.update_score.call_args_list if c[0][0].score_type == "procedure_turn"]
        self.assertEqual(len(pt_calls), 0, "Should NOT have issued a procedure turn penalty for missed gate")

    def test_double_penalty_gate_passed(self):
        # 1. Start at SP
        gate_sp = self.calculator.gates[0]
        start_time = datetime.datetime(2020, 1, 1, 10, 0, 0, tzinfo=datetime.timezone.utc)
        pos_sp = self.create_position(60.0, 11.0, start_time)
        self.calculator.on_gate_passed(GatePassedEvent(gate_sp, pos_sp, start_time))
        self.calculator.tracking_state = self.calculator.TRACKING
        self.calculator.last_gate_previous_round = gate_sp
        
        pos_warmup = self.create_position(59.9, 11.0, start_time + datetime.timedelta(seconds=1))
        self.calculator.calculate_track_score([pos_sp, pos_warmup], gate_sp, gate_sp, self.calculator.gates[1])

        # 2. Circle BEFORE reaching it
        track = [pos_sp, pos_warmup]
        for i in range(2, 10):
            angle = (i-1) * 45 
            import math
            radius = 0.01
            lat = 60.0 + radius * math.cos(math.radians(angle))
            lon = 11.0 + radius * math.sin(math.radians(angle))
            pos = self.create_position(lat, lon, start_time + datetime.timedelta(seconds=i))
            track.append(pos)
            self.calculator.detect_circling(track, gate_sp, gate_sp)
        
        # Fast forward time to exceed circling duration (5s)
        pos_last = track[-1]
        pos_final = self.create_position(pos_last.latitude, pos_last.longitude, pos_last.time + datetime.timedelta(seconds=10))
        track.append(pos_final)
        self.calculator.detect_circling(track, gate_sp, gate_sp)
        
        self.assertTrue(self.calculator.backtracked_on_current_leg)
        
        # 3. Now PASS the gate
        gate_pt = self.calculator.gates[1]
        self.calculator.on_gate_passed(GatePassedEvent(gate_pt, pos_final, pos_final.time))
        
        # 4. Continue flying
        pos3 = self.create_position(60.1, 11.1, pos_final.time + datetime.timedelta(seconds=5))
        self.calculator.calculate_track_score(track + [pos3], gate_pt, None, None)
        
        self.assertEqual(self.calculator.tracking_state, self.calculator.PROCEDURE_TURN)
        self.assertTrue(self.calculator.was_backtracked_on_leg_leading_to_last_gate)
        
        # 5. Wait for PT timeout (180s)
        pos4 = self.create_position(60.1, 11.2, pos3.time + datetime.timedelta(seconds=200))
        self.calculator.calculate_track_score(track + [pos3, pos4], gate_pt, None, None)
        
        self.assertEqual(self.calculator.tracking_state, self.calculator.FAILED_PROCEDURE_TURN)
        
        # Verify second penalty (procedure_turn) suppressed
        pt_calls = [c for c in self.calculator.update_score.call_args_list if c[0][0].score_type == "procedure_turn"]
        self.assertEqual(len(pt_calls), 0, "Should NOT have issued a procedure turn penalty because circling was already penalized")

