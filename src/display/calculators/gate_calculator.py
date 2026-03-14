import datetime
import logging
from queue import Queue
from typing import List, Optional

from display.calculators.calculator import (
    Calculator,
    OrchestratorState,
    OrchestratorEvent,
    GatePassedEvent,
    GateMissedEvent,
    TakeoffPassedEvent,
    LandingPassedEvent,
    StartingLinePassedEvent,
    StartingLineExtendedPassedWrongDirectionEvent,
    AdaptiveStartEvent,
    EstimationUpdatedEvent,
    InRangeUpdatedEvent,
    FinishLinePassedEvent,
    NextGateExpectedEvent,
)
from display.calculators.calculator_utilities import round_time_minute
from display.calculators.positions_and_gates import Gate, round_seconds
from display.calculators.update_score_message import UpdateScoreMessage
from display.models.contestant_utility_models import ContestantReceivedPosition
from display.models import ANOMALY, INFORMATION
from websocket_channels import WebsocketFacade
from display.utilities.coordinate_utilities import calculate_distance_lat_lon, calculate_speed_between_points
from display.utilities.route_building_utilities import calculate_extended_gate

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
        route,
        score_processing_queue,
        live_processing=True,
        projector=None,
    ):
        super().__init__(
            contestant,
            scorecard,
            route,
            score_processing_queue,
            live_processing=live_processing,
            projector=projector,
        )
        self.initiate_gates()
        self.outstanding_gates = list(self.gates)
        self.websocket_facade = WebsocketFacade()
        self.last_backwards = None
        self.has_scored_adaptive_start = False
        self.scored_gates = set()
        self.last_estimation_time = datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)

    def create_gates(self) -> List[Gate]:
        """
        Helper function to create gates from the waypoints defined in a route
        """
        waypoints = self.contestant.navigation_task.route.waypoints
        expected_times = self.contestant.gate_times
        gates = []
        for item in waypoints:  # type: Waypoint
            # Dummy gates are not part of the actual route
            # Takeoff and Landing gates are handled by TakeoffAndLandingGateCalculator
            if item.type not in ("dummy", "to", "ldg"):
                gates.append(
                    Gate(
                        item,
                        expected_times[item.name],
                        calculate_extended_gate(item, self.scorecard),
                    )
                )
        return gates

    def initiate_gates(self):
        self.gates = self.create_gates()
        for gate in self.gates:
            gate.pre_project(self.projector)

    def _get_next_gate(self) -> Optional[Gate]:
        return self.outstanding_gates[0] if self.outstanding_gates else None

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
                    (pos.latitude, pos.longitude), (last_pos.latitude, last_pos.longitude), pos.time, last_pos.time
                )
                if speed > 10:  # Reasonable speed
                    return speed
                break
        return self.contestant.air_speed

    def estimate_crossing_time_of_next_timed_gate(
        self, track: List[ContestantReceivedPosition], state: OrchestratorState
    ) -> Optional[EstimationUpdatedEvent]:
        # OrchestratorState.next_gate is updated by our events
        if state.next_gate is None:
            return None

        # Find next TIMED gate starting from next_gate
        next_timed_gate = None
        started = False
        for gate in self.gates:
            if not started and gate == state.next_gate:
                started = True
            if started and gate.time_check:
                next_timed_gate = gate
                break

        if next_timed_gate is None:
            return None

        speed = self.calculate_speed(track)
        if speed <= 0:
            return None

        last_pos = track[-1]

        p_x = getattr(last_pos, "projected_x", None)
        p_y = getattr(last_pos, "projected_y", None)

        if p_x is not None and next_timed_gate.center_x is not None:
            import math

            distance_m = math.sqrt((p_x - next_timed_gate.center_x) ** 2 + (p_y - next_timed_gate.center_y) ** 2)
            distance = distance_m / 1852  # nm
        else:
            distance = (
                calculate_distance_lat_lon(
                    (last_pos.latitude, last_pos.longitude), (next_timed_gate.latitude, next_timed_gate.longitude)
                )
                / 1852
            )  # nm

        seconds_to_gate = (distance / speed) * 3600
        estimated_time = last_pos.time + datetime.timedelta(seconds=seconds_to_gate)

        return EstimationUpdatedEvent(next_timed_gate, estimated_time, last_pos)

    def calculate_enroute(
        self,
        track: List[ContestantReceivedPosition],
        state: OrchestratorState,
    ) -> List[OrchestratorEvent]:
        events = self.check_intersections(track, state)

        # Performance estimation every 5 seconds
        last_pos = track[-1]
        if last_pos.time > self.last_estimation_time + datetime.timedelta(seconds=5):
            estimation_event = self.estimate_crossing_time_of_next_timed_gate(track, state)
            if estimation_event:
                events.append(estimation_event)
                self.last_estimation_time = last_pos.time

        if self.live_processing and state.estimated_next_timed_gate and state.estimated_crossing_time:
            planned_time_to_crossing = (track[-1].time - state.estimated_next_timed_gate.expected_time).total_seconds()
            score = self.scorecard.get_gate_timing_score_for_gate_type(
                state.estimated_next_timed_gate.type,
                state.estimated_next_timed_gate.expected_time,
                state.estimated_crossing_time,
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
        state: OrchestratorState,
    ) -> List[OrchestratorEvent]:
        events = self.check_intersections(track, state)
        # Emit initial next gate if none known yet
        if state.next_gate is None and self.outstanding_gates:
            events.append(NextGateExpectedEvent(self.outstanding_gates[0], track[-1]))
        return events

    def check_intersections(
        self, track: List[ContestantReceivedPosition], state: OrchestratorState
    ) -> List[OrchestratorEvent]:
        """
        Detection logic using OrchestratorState.
        """
        events = []

        # Handle crossing the starting line if we are looking for it
        if state.next_gate and state.next_gate == self.gates[0]:
            starting_line = self.gates[0]
            intersection_time = starting_line.get_gate_extended_intersection_time(state.projector, track)
            if intersection_time and not starting_line.is_passed_in_correct_direction_track(track):
                if self.last_backwards is None or intersection_time > self.last_backwards + datetime.timedelta(
                    seconds=15
                ):
                    self.last_backwards = intersection_time
                    events.append(StartingLineExtendedPassedWrongDirectionEvent(starting_line, track[-1]))
            elif not starting_line.has_infinite_been_passed():
                intersection_time = starting_line.get_gate_infinite_intersection_time(state.projector, track)
                if intersection_time and starting_line.is_passed_in_correct_direction_track(track):
                    self.contestant.terminate_concurrent_contestants(intersection_time)
                    starting_line.pass_infinite_gate(intersection_time, track[-1])
                    # Signal starting line crossing (sets enroute, handles adaptive start)
                    events.append(StartingLinePassedEvent(starting_line, track[-1], intersection_time))

                    if self.contestant.adaptive_start:
                        adaptive_event = AdaptiveStartEvent(intersection_time, track[-1])
                        events.append(adaptive_event)
                        # Ensure we recalculate immediately so the same tick logic uses new times
                        # (e.g. for scoring the same starting gate timing)
                        self.on_adaptive_start(adaptive_event)

        # Look for crossing of any future gates
        crossed_gate_index = -1
        passed_intersection_time = None
        # Use our own outstanding_gates list which is always up to date within this call
        for i, intersected_gate in enumerate(self.outstanding_gates):
            intersection_time = intersected_gate.get_gate_intersection_time(state.projector, track)
            if intersection_time and intersected_gate.is_passed_in_correct_direction_track(track):
                crossed_gate_index = i
                passed_intersection_time = intersection_time
                break

        if crossed_gate_index != -1:
            # Mark preceding as missed
            for j in range(crossed_gate_index):
                gate = self.outstanding_gates[j]
                if not gate.has_been_passed():
                    # Find previous gate for context
                    current_idx_in_all = self.gates.index(gate)
                    prev_gate = self.gates[current_idx_in_all - 1] if current_idx_in_all > 0 else None
                    events.append(GateMissedEvent(prev_gate, gate, track[-1], event_time=passed_intersection_time))

            # Mark this one as passed
            gate = self.outstanding_gates[crossed_gate_index]
            current_idx_in_all = self.gates.index(gate)
            prev_gate = self.gates[current_idx_in_all - 1] if current_idx_in_all > 0 else None
            events.append(GatePassedEvent(gate, track[-1], passed_intersection_time, previous_gate=prev_gate))

            # Pop gates from our internal list and emit next expected gate
            del self.outstanding_gates[: crossed_gate_index + 1]
            events.append(NextGateExpectedEvent(self._get_next_gate(), track[-1]))

        # Proactive missed gate detection (only for the first outstanding gate if not just passed)
        if len(self.outstanding_gates) > 0:
            gate = self.outstanding_gates[0]

            # Skip if we just added a GatePassedEvent for this specific gate
            if not (crossed_gate_index == 0):
                # 1. Check for infinite line crossing if not already detected
                if not gate.has_infinite_been_passed():
                    inf_time = gate.get_gate_infinite_intersection_time(state.projector, track)
                    if inf_time and gate.is_passed_in_correct_direction_track(track):
                        gate.pass_infinite_gate(inf_time, track[-1])

                # 2. Trigger miss if 2 seconds passed since infinite crossing and still not passed normally
                if (
                    gate.infinite_passing_time is not None
                    and not gate.has_been_passed()
                    and track[-1].time > gate.infinite_passing_time + datetime.timedelta(seconds=2)
                ):
                    # Don't mark as missed if we already have a pass or miss for this gate in current events
                    if not any(getattr(e, "gate", None) == gate for e in events):
                        # Find previous gate for context
                        current_idx_in_all = self.gates.index(gate)
                        prev_gate = self.gates[current_idx_in_all - 1] if current_idx_in_all > 0 else None
                        events.append(GateMissedEvent(prev_gate, gate, gate.infinite_passing_position))
                        # Pop and emit next
                        self.outstanding_gates.pop(0)
                        events.append(NextGateExpectedEvent(self._get_next_gate(), track[-1]))

        self.check_gate_in_range(track, state, events)

        return events

    def check_gate_in_range(
        self, track: List[ContestantReceivedPosition], state: OrchestratorState, events: List[OrchestratorEvent]
    ):
        if len(self.outstanding_gates) == 0 or len(track) == 0:
            return
        last_position = track[-1]
        now = last_position.time

        # Don't emit in-range events if we already have a pass or miss for this update
        already_handled_gates = {e.gate for e in events if hasattr(e, "gate")}

        p_x = getattr(last_position, "projected_x", None)
        p_y = getattr(last_position, "projected_y", None)
        if p_x is None or p_y is None:
            raise ValueError(f"Position at {last_position.time} is missing projected coordinates")

        if state.in_range_of_gate is not None:
            if state.in_range_of_gate in already_handled_gates:
                return

            if state.in_range_of_gate.center_x is None:
                state.in_range_of_gate.pre_project(state.projector)

            dist_sq = (p_x - state.in_range_of_gate.center_x) ** 2 + (p_y - state.in_range_of_gate.center_y) ** 2
            is_outside = dist_sq > state.in_range_of_gate.outside_distance**2

            if is_outside:
                if (
                    state.in_range_of_gate.passing_time is None
                    and not state.in_range_of_gate.missed
                    and self.gates[0].has_infinite_been_passed()
                ):
                    state.in_range_of_gate.missed = True
                    # Find previous gate for context
                    current_idx_in_all = self.gates.index(state.in_range_of_gate)
                    prev_gate = self.gates[current_idx_in_all - 1] if current_idx_in_all > 0 else None
                    events.append(GateMissedEvent(prev_gate, state.in_range_of_gate, last_position))

                    # If this was our expected next gate, pop it
                    if self.outstanding_gates and self.outstanding_gates[0] == state.in_range_of_gate:
                        self.outstanding_gates.pop(0)
                        events.append(NextGateExpectedEvent(self._get_next_gate(), last_position))

                events.append(InRangeUpdatedEvent(None, last_position))
        else:
            next_gate = self.outstanding_gates[0]
            if next_gate in already_handled_gates:
                return

            if next_gate.type not in ("secret", "sp", "fp", "tp"):
                return

            if next_gate.center_x is None:
                next_gate.pre_project(state.projector)

            # Throttle distance check if far away
            dist_sq = (p_x - next_gate.center_x) ** 2 + (p_y - next_gate.center_y) ** 2
            # If further than 5km, only check every 5 seconds
            if dist_sq > 5000**2 and now < self.last_estimation_time + datetime.timedelta(seconds=4):
                return

            if dist_sq < next_gate.inside_distance**2:
                events.append(InRangeUpdatedEvent(next_gate, last_position))

    def passed_finishpoint(self, event: FinishLinePassedEvent):
        # When finish point is passed, all outstanding regular gates should be marked as missed
        prev = None
        for gate in self.gates:
            if not gate.has_been_passed() and not gate.missed and (gate.name, GATE_SCORE_TYPE) not in self.scored_gates:
                gate.missed = True
                self.on_gate_missed(GateMissedEvent(prev, gate, event.position))
            prev = gate
        self.outstanding_gates = []

    def finalise(self, track: List[ContestantReceivedPosition]):
        # Catch any remaining missed gates at the very end of processing
        for gate in self.gates:
            if not gate.has_been_passed() and not gate.missed and (gate.name, GATE_SCORE_TYPE) not in self.scored_gates:
                gate.missed = True
                self.on_gate_missed(GateMissedEvent(None, gate, track[-1] if track else None))
        self.outstanding_gates = []

    def on_gate_missed(self, event: GateMissedEvent):
        if event.gate not in self.gates:
            return

        # Add a small offset based on gate name/order to ensure deterministic ordering if multiple gates are missed at once
        event_time = event.event_time or (event.position.time if event.position else event.gate.expected_time)
        if not event.event_time and event_time:
            # Add 1ms per gate in the route to ensure they stay in order
            gate_index = self.gates.index(event.gate)
            event_time += datetime.timedelta(milliseconds=gate_index)

        logger.info(f"{self.contestant}: Scoring missed gate {event.gate}")
        event.gate.missed = True

        if event.gate.gate_check:
            score = self.scorecard.get_gate_timing_score_for_gate_type(event.gate.type, event.gate.expected_time, None)
            message = "missing gate"

            self.update_gate_score(
                event.position,
                event.gate,
                score,
                GATE_SCORE_TYPE,
                message,
                ANOMALY,
                planned=event.gate.expected_time,
                actual=None,
                time_override=event_time,
            )

    def on_gate_passed(self, event: GatePassedEvent):
        if event.gate not in self.gates:
            return

        logger.info(f"{self.contestant}: Scoring passed gate {event.gate}")
        passing_time = (
            event.intersection_time
            or event.gate.passing_time
            or event.gate.infinite_passing_time
            or event.position.time
        )
        passing_position = event.gate.infinite_passing_position or event.position

        # Mark the gate as passed internally
        event.gate.pass_gate(passing_time, passing_position)

        time_difference = (passing_time - event.gate.expected_time).total_seconds()
        self.contestant.contestanttrack.update_last_gate(event.gate.name, time_difference)

        message = "passing gate"

        if event.gate.time_check:
            gate_score = self.scorecard.get_gate_timing_score_for_gate_type(
                event.gate.type, event.gate.expected_time, passing_time
            )
            self.transmit_actual_crossing(event.gate, passing_position)
            self.update_gate_score(
                passing_position,
                event.gate,
                gate_score,
                GATE_SCORE_TYPE,
                message,
                ANOMALY,
                event.gate.expected_time,
                passing_time,
            )
        else:
            self.update_gate_score(
                passing_position,
                event.gate,
                0,
                GATE_SCORE_TYPE,
                f"{message} (no time check)",
                INFORMATION,
                event.gate.expected_time,
                passing_time,
            )

    def on_landing_passed(self, event: LandingPassedEvent):
        pass

    def on_takeoff_passed(self, event: TakeoffPassedEvent):
        pass

    def on_starting_line_passed(self, event: StartingLinePassedEvent):
        logger.info(f"{self.contestant}: Scoring starting line {event.gate}")
        if self.contestant.adaptive_start and not self.has_scored_adaptive_start:
            self.has_scored_adaptive_start = True
            # Use a slightly earlier time to ensure it appears before the timing score in the log
            passing_time = event.gate.passing_time or event.gate.infinite_passing_time or event.position.time
            passing_position = event.gate.infinite_passing_position or event.position
            entry_time = passing_time - datetime.timedelta(seconds=1)
            self.update_gate_score(
                passing_position,
                event.gate,
                0,
                ADAPTIVE_TIMING_START_SCORE_TYPE,
                "crossing infinite starting line and starting adaptive timing",
                INFORMATION,
                actual=entry_time,
            )

    def on_adaptive_start(self, event: AdaptiveStartEvent):
        """
        Update expected times for gates based on adaptive start time.
        """
        new_start_time = event.intersection_time
        gate_times = self.contestant.calculate_missing_gate_times({}, round_time_minute(new_start_time))

        for gate in self.gates:
            if gate.name in gate_times:
                gate.expected_time = gate_times[gate.name]

    def on_starting_line_extended_passed_wrong_direction(self, event: StartingLineExtendedPassedWrongDirectionEvent):
        logger.info(f"{self.contestant}: Scoring starting line wrong direction {event.gate}")
        score = self.scorecard.get_bad_crossing_extended_gate_penalty_for_gate_type("sp")
        if score != 0:
            self.update_gate_score(
                event.position,
                event.gate,
                score,
                BACKWARD_STARTING_LINE_SCORE_TYPE,
                "crossing extended starting gate backwards",
                ANOMALY,
            )
