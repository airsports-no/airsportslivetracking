import datetime
import logging
from queue import Queue
from typing import List, Optional

from display.calculators.calculator import (
    Calculator,
    GatekeeperState,
    GatekeeperEvent,
    GatePassedEvent,
    GateMissedEvent,
    TakeoffPassedEvent,
    LandingPassedEvent,
    StartingLinePassedEvent,
    StartingLineExtendedPassedWrongDirectionEvent,
    AdaptiveStartEvent,
    EstimationUpdatedEvent,
    InRangeUpdatedEvent,
)
from display.calculators.positions_and_gates import Gate, round_seconds
from display.calculators.update_score_message import UpdateScoreMessage
from display.models.contestant_utility_models import ContestantReceivedPosition
from display.models import ANOMALY, INFORMATION
from websocket_channels import WebsocketFacade
from display.utilities.coordinate_utilities import calculate_distance_lat_lon, calculate_speed_between_points

logger = logging.getLogger(__name__)

GATE_SCORE_TYPE = "gate_score"
BACKWARD_STARTING_LINE_SCORE_TYPE = "backwards_starting_line"
ADAPTIVE_TIMING_START_SCORE_TYPE = "adaptive_timing_start"


class GateCalculator(Calculator):
    """
    Calculator responsible for scoring gate crossings and misses.
    """

    def __init__(
        self,
        contestant,
        scorecard,
        gates,
        route,
        score_processing_queue,
        live_processing=True,
    ):
        super().__init__(contestant, scorecard, gates, route, score_processing_queue, live_processing=live_processing)
        self.websocket_facade = WebsocketFacade()
        self.last_backwards = None
        self.has_scored_adaptive_start = False
        self.scored_gates = set()

    def update_gate_score(
        self,
        position: ContestantReceivedPosition,
        gate: Gate,
        score: int,
        score_type: str,
        score_string: str,
        annotation_type: str,
        planned: Optional[datetime.datetime] = None,
        actual: Optional[datetime.datetime] = None,
        time_override: Optional[datetime.datetime] = None,
    ):
        if (gate.name, score_type) in self.scored_gates:
            return
        self.scored_gates.add((gate.name, score_type))
        
        score_time = time_override or actual or (position.time if position else None)
        if not score_time:
            score_time = datetime.datetime.now(datetime.timezone.utc)

        self.update_score(
            UpdateScoreMessage(
                score_time,
                gate,
                score,
                score_string,
                position.latitude if position else gate.latitude,
                position.longitude if position else gate.longitude,
                annotation_type,
                score_type,
                planned=planned,
                actual=actual,
            )
        )

    def transmit_actual_crossing(self, gate: Gate, position: ContestantReceivedPosition):
        """
        Update the gate score arrow in the frontend with information about the actual crossing time.
        """
        estimated_crossing_time = position.time
        if gate.passing_time:
            planned_time_to_crossing = (gate.passing_time - gate.expected_time).total_seconds()
            estimated_crossing_time = gate.passing_time
        else:
            planned_time_to_crossing = (position.time - gate.expected_time).total_seconds()
        
        score = self.scorecard.get_gate_timing_score_for_gate_type(
            gate.type, gate.expected_time, estimated_crossing_time
        )

        if self.live_processing:
            self.websocket_facade.transmit_seconds_to_crossing_time_and_crossing_estimate(
                self.contestant,
                gate.name,
                planned_time_to_crossing,
                round((estimated_crossing_time - gate.expected_time).total_seconds()),
                score,
                True,
                gate.missed,
            )

    def calculate_speed(self, track: List[ContestantReceivedPosition]) -> float:
        if len(track) < 2:
            return self.contestant.air_speed  # Fallback to planned speed
        
        # Calculate speed over the last 10 seconds or so
        last_pos = track[-1]
        for pos in reversed(track[:-1]):
            if (last_pos.time - pos.time).total_seconds() >= 10:
                speed = calculate_speed_between_points(
                    (pos.latitude, pos.longitude),
                    (last_pos.latitude, last_pos.longitude),
                    pos.time,
                    last_pos.time
                )
                if speed > 10: # Reasonable speed
                    return speed
                break
        return self.contestant.air_speed

    def estimate_crossing_time_of_next_timed_gate(self, track: List[ContestantReceivedPosition], state: GatekeeperState) -> Optional[EstimationUpdatedEvent]:
        if len(state.outstanding_gates) == 0:
            return None
        
        next_timed_gate = None
        for gate in state.outstanding_gates:
            if gate.time_check:
                next_timed_gate = gate
                break
        
        if next_timed_gate is None:
            return None
            
        speed = self.calculate_speed(track)
        if speed <= 0:
            return None
            
        last_pos = track[-1]
        distance = calculate_distance_lat_lon(
            (last_pos.latitude, last_pos.longitude),
            (next_timed_gate.latitude, next_timed_gate.longitude)
        ) / 1852 # nm
        
        seconds_to_gate = (distance / speed) * 3600
        estimated_time = last_pos.time + datetime.timedelta(seconds=seconds_to_gate)
        
        return EstimationUpdatedEvent(next_timed_gate, estimated_time, last_pos)

    def calculate_enroute(
        self,
        track: List[ContestantReceivedPosition],
        state: GatekeeperState,
    ) -> List[GatekeeperEvent]:
        events = self.check_intersections(track, state)
        
        # Performance estimation
        estimation_event = self.estimate_crossing_time_of_next_timed_gate(track, state)
        if estimation_event:
            events.append(estimation_event)
            
        if self.live_processing and state.estimated_next_timed_gate and state.estimated_crossing_time:
            planned_time_to_crossing = (track[-1].time - state.estimated_next_timed_gate.expected_time).total_seconds()
            score = self.scorecard.get_gate_timing_score_for_gate_type(
                state.estimated_next_timed_gate.type, state.estimated_next_timed_gate.expected_time, state.estimated_crossing_time
            )

            self.websocket_facade.transmit_seconds_to_crossing_time_and_crossing_estimate(
                self.contestant,
                state.estimated_next_timed_gate.name,
                planned_time_to_crossing,
                round((state.estimated_crossing_time - state.estimated_next_timed_gate.expected_time).total_seconds()),
                score,
                False,
                False,
            )
        return events

    def calculate_outside_route(
        self,
        track: List[ContestantReceivedPosition],
        state: GatekeeperState,
    ) -> List[GatekeeperEvent]:
        return self.check_intersections(track, state)

    def check_intersections(self, track: List[ContestantReceivedPosition], state: GatekeeperState) -> List[GatekeeperEvent]:
        """
        Detection logic using GatekeeperState.
        """
        events = []
        # Check takeoff if exists
        if state.takeoff_gate is not None and not state.takeoff_gate.has_been_passed():
            intersection_time = state.takeoff_gate.get_gate_intersection_time(state.projector, track)
            if intersection_time:
                intersected_gate = state.takeoff_gate.intersected_gate
                self.contestant.record_actual_gate_time(intersected_gate.name, intersection_time)
                events.append(TakeoffPassedEvent(intersected_gate, track[-1], intersection_time))

        # Handle crossing the starting line
        starting_line_detected = False
        if len(state.outstanding_gates) == len(self.gates): # No gates passed yet
            starting_line = self.gates[0] 
            intersection_time = starting_line.get_gate_extended_intersection_time(state.projector, track)
            if intersection_time and not starting_line.is_passed_in_correct_direction_track(track):
                if self.last_backwards is None or intersection_time > self.last_backwards + datetime.timedelta(seconds=15):
                    self.last_backwards = intersection_time
                    events.append(StartingLineExtendedPassedWrongDirectionEvent(starting_line, track[-1]))
            elif not starting_line.has_infinite_been_passed():
                intersection_time = starting_line.get_gate_infinite_intersection_time(state.projector, track)
                if intersection_time and starting_line.is_passed_in_correct_direction_track(track):
                    self.contestant.terminate_concurrent_contestants(intersection_time)

                    # Miss takeoff if not already crossed - must happen BEFORE starting line is passed
                    if state.takeoff_gate is not None and not state.takeoff_gate.has_been_passed():
                        events.append(GateMissedEvent(None, state.takeoff_gate.gates[0], track[-1], event_time=intersection_time - datetime.timedelta(seconds=1)))

                    # Score starting line before shifting times
                    events.append(StartingLinePassedEvent(starting_line, track[-1], intersection_time))
                    
                    if self.contestant.adaptive_start:
                        events.append(AdaptiveStartEvent(round_seconds(intersection_time), track[-1]))
                    
                    starting_line_detected = True

        # Look for crossing of any future gates
        crossed_gate_index = -1
        passed_intersection_time = None
        for i, intersected_gate in enumerate(state.outstanding_gates):
            if starting_line_detected and intersected_gate == self.gates[0]:
                continue
                
            intersection_time = intersected_gate.get_gate_intersection_time(state.projector, track)
            if intersection_time and intersected_gate.is_passed_in_correct_direction_track(track):
                crossed_gate_index = i
                passed_intersection_time = intersection_time
                break
        
        if crossed_gate_index != -1:
            # Mark preceding as missed
            for j in range(crossed_gate_index):
                gate = state.outstanding_gates[j]
                if not gate.has_been_passed():
                    # Find previous gate for context
                    current_idx_in_all = self.gates.index(gate)
                    prev_gate = self.gates[current_idx_in_all - 1] if current_idx_in_all > 0 else None
                    events.append(GateMissedEvent(prev_gate, gate, track[-1]))
            
            # Mark this one as passed
            gate = state.outstanding_gates[crossed_gate_index]
            self.contestant.record_actual_gate_time(gate.name, passed_intersection_time)
            events.append(GatePassedEvent(gate, track[-1], passed_intersection_time))

        self.check_gate_in_range(track, state, events)

        # Handle landing gate
        if state.has_passed_finishpoint:
            if state.landing_gate is not None and not state.landing_gate.has_been_passed():
                intersection_time = state.landing_gate.get_gate_intersection_time(state.projector, track)
                if intersection_time:
                    intersected_gate = state.landing_gate.intersected_gate
                    self.contestant.record_actual_gate_time(intersected_gate.name, intersection_time)
                    events.append(LandingPassedEvent(intersected_gate, track[-1], intersection_time))
        
        return events

    def check_gate_in_range(self, track: List[ContestantReceivedPosition], state: GatekeeperState, events: List[GatekeeperEvent]):
        if len(state.outstanding_gates) == 0 or len(track) == 0:
            return
        last_position = track[-1]
        
        # Don't emit in-range events if we already have a pass or miss for this update
        already_handled_gates = {e.gate for e in events if hasattr(e, "gate")}
        
        if state.in_range_of_gate is not None:
            if state.in_range_of_gate in already_handled_gates:
                return
                
            distance_to_gate = calculate_distance_lat_lon(
                (last_position.latitude, last_position.longitude),
                (state.in_range_of_gate.latitude, state.in_range_of_gate.longitude),
            )
            if distance_to_gate > state.in_range_of_gate.outside_distance:
                if (state.in_range_of_gate.passing_time is None 
                    and not state.in_range_of_gate.missed
                    and self.gates[0].has_infinite_been_passed()
                ):
                    state.in_range_of_gate.missed = True
                    # Find previous gate for context
                    current_idx_in_all = self.gates.index(state.in_range_of_gate)
                    prev_gate = self.gates[current_idx_in_all - 1] if current_idx_in_all > 0 else None
                    events.append(GateMissedEvent(prev_gate, state.in_range_of_gate, last_position))
                events.append(InRangeUpdatedEvent(None, last_position))
        else:
            next_gate = state.outstanding_gates[0]
            if next_gate in already_handled_gates:
                return
                
            if next_gate.type not in ("secret", "sp", "fp", "tp"):
                return
            distance_to_gate = calculate_distance_lat_lon(
                (last_position.latitude, last_position.longitude), (next_gate.latitude, next_gate.longitude)
            )
            if distance_to_gate < next_gate.inside_distance:
                events.append(InRangeUpdatedEvent(next_gate, last_position))


    def passed_finishpoint(self, track: List[ContestantReceivedPosition], last_gate: "Gate"):
        # When finish point is passed, all outstanding regular gates should be marked as missed
        for gate in self.gates:
            if not gate.has_been_passed() and not gate.missed and (gate.name, GATE_SCORE_TYPE) not in self.scored_gates:
                gate.missed = True
                self.missed_gate(None, gate, track[-1] if track else None)

    def finalise(self, track: List[ContestantReceivedPosition]):
        # Catch any remaining missed gates at the very end of processing
        from display.utilities.route_building_utilities import calculate_extended_gate
        
        # Check main route waypoints (SP, TP, FP)
        for gate in self.gates:
            if not gate.has_been_passed() and not gate.missed and (gate.name, GATE_SCORE_TYPE) not in self.scored_gates:
                gate.missed = True
                self.missed_gate(None, gate, track[-1] if track else None)

        for tg in self.route.takeoff_gates:
            if (tg.name, GATE_SCORE_TYPE) in self.scored_gates:
                continue
            expected_time = self.contestant.gate_times.get(tg.name)
            g = Gate(tg, expected_time, calculate_extended_gate(tg, self.scorecard))
            if tg.name not in self.contestant.gate_times_actual:
                g.missed = True
                self.missed_gate(None, g, track[-1] if track else None)

        for lg in self.route.landing_gates:
            if (lg.name, GATE_SCORE_TYPE) in self.scored_gates:
                continue
            expected_time = self.contestant.gate_times.get(lg.name)
            g = Gate(lg, expected_time, calculate_extended_gate(lg, self.scorecard))
            if lg.name not in self.contestant.gate_times_actual:
                g.missed = True
                self.missed_gate(None, g, track[-1] if track else None)

    def missed_gate_with_time(self, previous_gate: Optional[Gate], gate: Gate, position: ContestantReceivedPosition, event_time: Optional[datetime.datetime]):
        logger.info(f"{self.contestant}: Scoring missed gate {gate}")
        if gate.gate_check:
            score = self.scorecard.get_gate_timing_score_for_gate_type(gate.type, gate.expected_time, None)
            message = "missing gate"
            if gate.type == "to":
                message = "missing takeoff gate"
            elif gate.type == "ldg":
                message = "missing landing gate"
            
            self.update_gate_score(
                position, gate, score, GATE_SCORE_TYPE, message, ANOMALY, planned=gate.expected_time, actual=None, time_override=event_time
            )

    def missed_gate(self, previous_gate: Optional[Gate], gate: Gate, position: ContestantReceivedPosition):
        # Add a small offset based on gate name/order to ensure deterministic ordering if multiple gates are missed at once
        event_time = gate.expected_time
        if event_time:
            # Add 1ms per gate in the route to ensure they stay in order
            gate_index = self.gates.index(gate) if gate in self.gates else 0
            event_time += datetime.timedelta(milliseconds=gate_index)
            
        self.missed_gate_with_time(previous_gate, gate, position, event_time)

    def on_gate_passed(self, gate: Gate, position: ContestantReceivedPosition):
        logger.info(f"{self.contestant}: Scoring passed gate {gate}")
        passing_time = gate.passing_time or gate.infinite_passing_time or position.time
        time_difference = (passing_time - gate.expected_time).total_seconds()
        self.contestant.contestanttrack.update_last_gate(gate.name, time_difference)
        
        message = "passing gate"
        if gate.type == "to":
            message = "passing takeoff gate"
        elif gate.type == "ldg":
            message = GATE_SCORE_TYPE

        if gate.time_check:
            gate_score = self.scorecard.get_gate_timing_score_for_gate_type(
                gate.type, gate.expected_time, passing_time
            )
            self.transmit_actual_crossing(gate, position)
            self.update_gate_score(
                position,
                gate,
                gate_score,
                GATE_SCORE_TYPE,
                message,
                ANOMALY,
                gate.expected_time,
                passing_time,
            )
        else:
            self.update_gate_score(
                position,
                gate,
                0,
                GATE_SCORE_TYPE,
                f"{message} (no time check)",
                INFORMATION,
                gate.expected_time,
                passing_time,
            )

    def on_takeoff_passed(self, gate: Gate, position: ContestantReceivedPosition):
        logger.info(f"{self.contestant}: Scoring takeoff gate {gate}")
        gate_score = self.scorecard.get_gate_timing_score_for_gate_type(
            gate.type, gate.expected_time, gate.passing_time
        )
        self.transmit_actual_crossing(gate, position)
        self.update_gate_score(
            position,
            gate,
            gate_score,
            GATE_SCORE_TYPE,
            "passing takeoff gate",
            ANOMALY,
            gate.expected_time,
            gate.passing_time,
        )

    def on_landing_passed(self, gate: Gate, position: ContestantReceivedPosition):
        logger.info(f"{self.contestant}: Scoring landing gate {gate}")
        gate_score = self.scorecard.get_gate_timing_score_for_gate_type(
            gate.type, gate.expected_time, gate.passing_time
        )
        self.transmit_actual_crossing(gate, position)
        self.update_gate_score(
            position,
            gate,
            gate_score,
            GATE_SCORE_TYPE,
            GATE_SCORE_TYPE,
            ANOMALY,
            gate.expected_time,
            gate.passing_time,
        )

    def on_starting_line_passed(self, gate: Gate, position: ContestantReceivedPosition):
        logger.info(f"{self.contestant}: Scoring starting line {gate}")
        if self.contestant.adaptive_start and not self.has_scored_adaptive_start:
            self.has_scored_adaptive_start = True
            # Use a slightly earlier time to ensure it appears before the timing score in the log
            passing_time = gate.passing_time or gate.infinite_passing_time or position.time
            entry_time = passing_time - datetime.timedelta(seconds=1)
            self.update_gate_score(
                position,
                gate,
                0,
                ADAPTIVE_TIMING_START_SCORE_TYPE,
                "crossing infinite starting line and starting adaptive timing",
                INFORMATION,
                actual=entry_time
            )

    def on_starting_line_extended_passed_wrong_direction(self, gate: Gate, position: ContestantReceivedPosition):
        logger.info(f"{self.contestant}: Scoring starting line wrong direction {gate}")
        score = self.scorecard.get_bad_crossing_extended_gate_penalty_for_gate_type("sp")
        if score != 0:
            self.update_gate_score(
                position,
                gate,
                score,
                BACKWARD_STARTING_LINE_SCORE_TYPE,
                "crossing extended starting gate backwards",
                ANOMALY,
            )
