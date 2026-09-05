import datetime
import itertools
import logging
from queue import Queue
from typing import List, Optional, Sequence

from display.calculators.calculator import (
    AdaptiveStartEvent,
    Calculator,
    EstimationUpdatedEvent,
    FinishLinePassedEvent,
    GateMissedEvent,
    GatePassedEvent,
    InRangeUpdatedEvent,
    LandingPassedEvent,
    NextGateExpectedEvent,
    OrchestratorEvent,
    OrchestratorState,
    StartingLineExtendedPassedWrongDirectionEvent,
    StartingLinePassedEvent,
    TakeoffPassedEvent,
)
from display.calculators.calculator_utilities import round_time_minute
from display.calculators.positions_and_gates import Gate, round_seconds
from display.calculators.update_score_message import UpdateScoreMessage
from display.flight_order_and_maps.effective_route_rendering import get_effective_route_waypoints
from display.models import ANOMALY, INFORMATION
from display.models.contestant_utility_models import ContestantReceivedPosition
from display.utilities.cima_task_type_definitions import CONTRACT_NAVIGATION_TIME_CONTROLS
from display.utilities.coordinate_utilities import (
    calculate_distance_lat_lon,
    calculate_speed_between_points,
    extend_line,
)
from display.utilities.gate_definitions import CIRCLE_CENTER, CIRCLE_ENTRY, CIRCLE_EXIT, CIRCLE_START
from display.utilities.route_building_utilities import calculate_extended_gate
from websocket_channels import WebsocketFacade

logger = logging.getLogger(__name__)

GATE_SCORE_TYPE = "gate_score"
# Circle (2.A7) markers have no GateScore row in any scorecard - they are not
# CIMA-timed/scored gates, just geometry references CircleCalculator uses.
# get_extended_gate_width_for_gate_type would raise ValueError for them, so
# their extended-gate line is derived from the marker's own width instead of
# the scorecard, and the center marker never becomes a Gate at all (it sits
# inside the flown circle, not on its boundary, so there is nothing to cross).
CIRCLE_CROSSING_GATE_TYPES = {CIRCLE_START, CIRCLE_ENTRY, CIRCLE_EXIT}
BACKWARD_STARTING_LINE_SCORE_TYPE = "backwards_starting_line"
ADAPTIVE_TIMING_START_SCORE_TYPE = "adaptive_timing_start"
# 2.A6/2.B2 achievement score types - see contestant_processor.ACHIEVEMENT_SCORE_TYPES for why
# these two, alone among every turnpoint-hunt score_type, must be added as-is rather than
# sign-flipped under a descending scorecard.
TURNPOINT_HUNT_TARGET_VALUE_SCORE_TYPE = "turnpoint_hunt_target_value"
TURNPOINT_HUNT_SEQUENCE_BONUS_SCORE_TYPE = "turnpoint_hunt_sequence_bonus"


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
        self.starting_line: Gate = None
        self.initiate_gates()
        self.outstanding_gates = list(self.gates)
        self.websocket_facade = WebsocketFacade()
        self.last_backwards = None
        self.has_scored_adaptive_start = False
        self.scored_gates = set()
        self.scored_turnpoint_hunt_compulsory_gates = set()
        self.last_estimation_time = datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)
        self._last_speed_keeping_gate: Optional[Gate] = None
        self._last_speed_keeping_time: Optional[datetime.datetime] = None
        # 2.A6/2.B2 sequence bonus: the order actual gate PASSES happened in, compared against
        # the contestant's declared_sequence at finalise() - see
        # _score_turnpoint_hunt_sequence_bonus. Empty and unused for every other subtype.
        self.turnpoint_hunt_actual_order: List[str] = []

    def create_gates(self) -> List[Gate]:
        """
        Helper function to create gates from the waypoints defined in a route
        """
        waypoints = self._get_effective_waypoints()
        expected_times = self.contestant.gate_times
        gates = []
        for item in waypoints:  # type: Waypoint
            # Dummy gates are not part of the actual route
            # Takeoff and Landing gates are handled by TakeoffAndLandingGateCalculator
            # Circle center is a reference point, never crossed - see CIRCLE_CROSSING_GATE_TYPES
            if item.type not in ("dummy", "to", "ldg", CIRCLE_CENTER) and not getattr(item, "on_curved_segment", False):
                if item.type in CIRCLE_CROSSING_GATE_TYPES:
                    extended_gate = extend_line(item.gate_line[0], item.gate_line[1], item.width)
                else:
                    extended_gate = calculate_extended_gate(item, self.scorecard)
                gates.append(
                    Gate(
                        item,
                        expected_times[item.name],
                        extended_gate,
                    )
                )
        if gates:
            self.starting_line = gates[0]
        elif waypoints:
            self.starting_line = Gate(
                waypoints[0], expected_times[waypoints[0].name], calculate_extended_gate(waypoints[0], self.scorecard)
            )
        else:
            # Routes with no waypoints at all (e.g. 2.B3 Duration tasks, which are
            # authored as just takeoff/landing gates plus a landing area polygon)
            # have nothing for this calculator to do.
            self.starting_line = None
        return gates

    def _get_effective_waypoints(self):
        # Calculators consume a shared effective-route seam so declaration-aware
        # maps, PDFs, and scoring all reconstruct waypoint objects the same way.
        return get_effective_route_waypoints(
            self.contestant.navigation_task,
            contestant=self.contestant,
            include_contestant_declarations=True,
        )

    def initiate_gates(self):
        self.gates = self.create_gates()
        for gate in self.gates:
            gate.pre_project(self.projector)
        if self.starting_line:
            self.starting_line.pre_project(self.projector)

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

    def calculate_speed(self, track: Sequence[ContestantReceivedPosition]) -> float:
        if len(track) < 2:
            return self.contestant.air_speed  # Fallback to planned speed

        # Calculate speed over the last 10 seconds or so.
        # track[:-1] then reversed(...) would break once track became a
        # bounded deque (no slicing support) - itertools.islice(reversed(track), 1, None)
        # is the O(1)-memory equivalent for both list and deque.
        last_pos = track[-1]
        for pos in itertools.islice(reversed(track), 1, None):
            if (last_pos.time - pos.time).total_seconds() >= 10:
                speed = calculate_speed_between_points(
                    (pos.latitude, pos.longitude), (last_pos.latitude, last_pos.longitude), pos.time, last_pos.time
                )
                if speed > 10:  # Reasonable speed
                    return speed
                break
        return self.contestant.air_speed

    def estimate_crossing_time_of_next_timed_gate(
        self, track: Sequence[ContestantReceivedPosition], state: OrchestratorState
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
        track: Sequence[ContestantReceivedPosition],
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
        track: Sequence[ContestantReceivedPosition],
        state: OrchestratorState,
    ) -> List[OrchestratorEvent]:
        events = self.check_intersections(track, state)
        # Emit initial next gate if none known yet
        if state.next_gate is None and self.outstanding_gates:
            events.append(NextGateExpectedEvent(self.outstanding_gates[0], track[-1]))
        return events

    def check_intersections(
        self, track: Sequence[ContestantReceivedPosition], state: OrchestratorState
    ) -> List[OrchestratorEvent]:
        """
        Detection logic using OrchestratorState.
        """
        events = []

        # Handle crossing the starting line if we are looking for it
        if self.gates and state.next_gate and state.next_gate == self.gates[0]:
            intersection_time = self.starting_line.get_gate_extended_intersection_time(state.projector, track)
            if intersection_time and not self.starting_line.is_passed_in_correct_direction_track(track):
                if self.last_backwards is None or intersection_time > self.last_backwards + datetime.timedelta(
                    seconds=15
                ):
                    self.last_backwards = intersection_time
                    events.append(StartingLineExtendedPassedWrongDirectionEvent(self.starting_line, track[-1]))
            elif not self.starting_line.has_infinite_been_passed():
                intersection_time = self.starting_line.get_gate_infinite_intersection_time(state.projector, track)
                if intersection_time and self.starting_line.is_passed_in_correct_direction_track(track):
                    self.contestant.terminate_concurrent_contestants(intersection_time)
                    self.starting_line.pass_infinite_gate(intersection_time, track[-1])
                    # Signal starting line crossing (sets enroute, handles adaptive start)
                    events.append(StartingLinePassedEvent(self.starting_line, track[-1], intersection_time))

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
                    logger.info(
                        f"{self.contestant}: Detected missed gate {gate} due to crossing later gate {self.outstanding_gates[crossed_gate_index]}"
                    )
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
                if (
                    not gate.has_infinite_been_passed()
                    and self.starting_line.has_infinite_been_passed()
                    and (state.in_range_of_gate == gate or gate != self.gates[0])
                ):
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
                        logger.info(
                            f"{self.contestant}: Detected missed gate {gate} due to passing infinite line over 2 seconds ago without normal crossing"
                        )
                        events.append(GateMissedEvent(prev_gate, gate, gate.infinite_passing_position))
                        # Pop and emit next
                        self.outstanding_gates.pop(0)
                        events.append(NextGateExpectedEvent(self._get_next_gate(), track[-1]))

        self.check_gate_in_range(track, state, events)

        return events

    def check_gate_in_range(
        self, track: Sequence[ContestantReceivedPosition], state: OrchestratorState, events: List[OrchestratorEvent]
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
                    logger.info(
                        f"{self.contestant}: Detected missed gate {state.in_range_of_gate} due to going out of range without passing"
                    )
                    events.append(GateMissedEvent(prev_gate, state.in_range_of_gate, last_position))

                    # If this was our expected next gate, pop it so state.next_gate
                    # (used for live-tracking "next gate" display) doesn't keep
                    # pointing at an already-missed gate until a later gate crossing
                    # retroactively cleans it up.
                    if self.outstanding_gates and self.outstanding_gates[0] == state.in_range_of_gate:
                        self.outstanding_gates.pop(0)
                        events.append(NextGateExpectedEvent(self._get_next_gate(), last_position))
                return

        # Find next gate in range if none is active
        next_gate = self._get_next_gate()
        if next_gate and next_gate not in already_handled_gates:
            if next_gate.center_x is None:
                next_gate.pre_project(state.projector)

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

    def finalise(self, track: Sequence[ContestantReceivedPosition]):
        # Catch any remaining missed gates at the very end of processing
        for gate in self.gates:
            if not gate.has_been_passed() and not gate.missed and (gate.name, GATE_SCORE_TYPE) not in self.scored_gates:
                gate.missed = True
                self.on_gate_missed(GateMissedEvent(None, gate, track[-1] if track else None))
        self.outstanding_gates = []
        # After the sweep above, so a gate missed only because it's swept here (rather than
        # actually passed) correctly breaks turnpoint_hunt_actual_order's equality check.
        self._score_turnpoint_hunt_sequence_bonus(track)

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

        if self._is_invalid_post_mp_contract_crossing(event.gate, passing_time):
            event.gate.missed = True
            self.update_gate_score(
                passing_position,
                event.gate,
                0,
                GATE_SCORE_TYPE,
                "invalid post-MP point flown before MP time",
                ANOMALY,
                event.gate.expected_time,
                passing_time,
            )
            return

        if self._is_curve_navigation_repeated_crossing(event.gate):
            event.gate.missed = True
            repeated_crossing_score = self.scorecard.get_gate_timing_score_for_gate_type(
                event.gate.type, event.gate.expected_time, None
            )
            self.update_gate_score(
                passing_position,
                event.gate,
                repeated_crossing_score,
                "curve_navigation_repeated_crossing",
                "gate invalidated by repeated crossing",
                ANOMALY,
                event.gate.expected_time,
                event.gate.passing_time,
            )
            return

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
        self._track_turnpoint_hunt_actual_order(event.gate)
        self._score_turnpoint_hunt_compulsory_timing(event.gate, passing_position, passing_time)
        self._score_turnpoint_hunt_target_value(event.gate, passing_position, passing_time)
        self._score_limited_fuel_deadline(event.gate, passing_position, passing_time)
        self._score_turnpoint_hunt_maximum_duration(event.gate, passing_position, passing_time)
        self._score_speed_keeping(event.gate, passing_position, passing_time)

    def _is_curve_navigation_repeated_crossing(self, gate: Gate) -> bool:
        return (
            self.contestant.navigation_task.task_subtype == "curve_navigation_time_estimation"
            and gate.type == "secret"
            and getattr(gate, "passing_time", None) is not None
        )

    def _score_turnpoint_hunt_compulsory_timing(self, gate: Gate, position, passing_time: datetime.datetime):
        subtype = self.contestant.navigation_task.task_subtype
        if subtype not in ("turnpoint_hunt", "limited_fuel_turnpoint_hunt"):
            return
        if not hasattr(self.contestant, "contestanttaskconfiguration"):
            return
        config = self.contestant.contestanttaskconfiguration
        if not config.is_valid:
            return
        payload = config.compiled_effective_route_payload or {}
        compulsory_names = payload.get("compulsory_timing_gate_names") or []
        if gate.name not in compulsory_names:
            return
        if gate.name in self.scored_turnpoint_hunt_compulsory_gates:
            return
        self.scored_turnpoint_hunt_compulsory_gates.add(gate.name)
        tolerance_seconds = int(payload.get("compulsory_timing_tolerance_seconds", 10) or 10)
        diff_seconds = abs((passing_time - gate.expected_time).total_seconds())
        if diff_seconds <= tolerance_seconds:
            score = 0
            message = f"compulsory timing gate within {tolerance_seconds} s"
            annotation_type = INFORMATION
        else:
            score = self.scorecard.get_gate_timing_score_for_gate_type(gate.type, gate.expected_time, passing_time)
            message = f"compulsory timing gate outside {tolerance_seconds} s"
            annotation_type = ANOMALY
        self.update_gate_score(
            position,
            gate,
            score,
            "turnpoint_hunt_compulsory_timing",
            message,
            annotation_type,
            gate.expected_time,
            passing_time,
        )

    def _track_turnpoint_hunt_actual_order(self, gate: Gate):
        """
        Records the order gates were ACTUALLY passed in, for
        _score_turnpoint_hunt_sequence_bonus's comparison against declared_sequence. A gate
        already recorded (e.g. re-processed during an idempotent restart replay) is not added
        twice - order reflects the first genuine pass only.
        """
        subtype = self.contestant.navigation_task.task_subtype
        if subtype not in ("turnpoint_hunt", "limited_fuel_turnpoint_hunt"):
            return
        if gate.name in self.turnpoint_hunt_actual_order:
            return
        self.turnpoint_hunt_actual_order.append(gate.name)

    def _score_turnpoint_hunt_target_value(self, gate: Gate, position, passing_time: datetime.datetime):
        subtype = self.contestant.navigation_task.task_subtype
        if subtype not in ("turnpoint_hunt", "limited_fuel_turnpoint_hunt"):
            return
        if not hasattr(self.contestant, "contestanttaskconfiguration"):
            return
        config = self.contestant.contestanttaskconfiguration
        if not config.is_valid:
            return
        payload = config.compiled_effective_route_payload or {}
        scored_values = payload.get("scored_target_values") or {}
        if gate.name not in scored_values:
            return
        self.update_gate_score(
            position,
            gate,
            float(scored_values[gate.name]),
            TURNPOINT_HUNT_TARGET_VALUE_SCORE_TYPE,
            "catalogue target collected",
            INFORMATION,
            gate.expected_time,
            passing_time,
        )

    def _score_turnpoint_hunt_sequence_bonus(self, track: Sequence[ContestantReceivedPosition]):
        """
        2.A6/2.B2: "an additional score will be awarded if the full and correct turnpoint and
        gate sequence is achieved" (cima_task_catalog.md). Evaluated once, at finalise() (after
        any remaining missed gates have already been swept), by comparing the order gates were
        ACTUALLY passed in (turnpoint_hunt_actual_order) against the contestant's own
        declared_sequence - an exact match (same items, same order, nothing missing) is required;
        there is no partial credit, matching the catalogue's "full and correct" wording.
        """
        subtype = self.contestant.navigation_task.task_subtype
        if subtype not in ("turnpoint_hunt", "limited_fuel_turnpoint_hunt"):
            return
        bonus = self.cima_config.turnpoint_hunt_sequence_bonus
        if not bonus:
            return
        if not hasattr(self.contestant, "contestanttaskconfiguration"):
            return
        config = self.contestant.contestanttaskconfiguration
        if not config.is_valid:
            return
        payload = config.compiled_effective_route_payload or {}
        declared_sequence = [item for item in (payload.get("declared_sequence") or []) if isinstance(item, str)]
        if not declared_sequence or self.turnpoint_hunt_actual_order != declared_sequence:
            return
        last_gate = self.gates[-1] if self.gates else None
        position = track[-1] if track else None
        if last_gate is None or position is None:
            return
        self.update_gate_score(
            position,
            last_gate,
            float(bonus),
            TURNPOINT_HUNT_SEQUENCE_BONUS_SCORE_TYPE,
            "full declared sequence achieved",
            INFORMATION,
            last_gate.expected_time,
            position.time,
        )

    def _score_limited_fuel_deadline(self, gate: Gate, position, passing_time: datetime.datetime):
        if self.contestant.navigation_task.task_subtype != "limited_fuel_turnpoint_hunt":
            return
        if not hasattr(self.contestant, "contestanttaskconfiguration"):
            return
        config = self.contestant.contestanttaskconfiguration
        if not config.is_valid:
            return
        payload = config.compiled_effective_route_payload or {}
        fuel_deadline = payload.get("fuel_deadline")
        if not fuel_deadline:
            return
        deadline_dt = datetime.datetime.fromisoformat(fuel_deadline)
        if passing_time <= deadline_dt:
            return
        if any(score_type == "limited_fuel_deadline_exceeded" for _, score_type in self.scored_gates if _ == gate.name):
            return
        penalty = self.cima_config.fuel_deadline_penalty
        self.update_gate_score(
            position,
            gate,
            penalty,
            "limited_fuel_deadline_exceeded",
            "fuel endurance exceeded",
            ANOMALY,
            deadline_dt,
            passing_time,
        )

    def _score_turnpoint_hunt_maximum_duration(self, gate: Gate, position, passing_time: datetime.datetime):
        subtype = self.contestant.navigation_task.task_subtype
        if subtype not in ("turnpoint_hunt", "limited_fuel_turnpoint_hunt"):
            return
        if not hasattr(self.contestant, "contestanttaskconfiguration"):
            return
        config = self.contestant.contestanttaskconfiguration
        if not config.is_valid:
            return
        payload = config.compiled_effective_route_payload or {}
        deadline = payload.get("maximum_task_duration_deadline")
        if not deadline:
            return
        deadline_dt = datetime.datetime.fromisoformat(deadline)
        if passing_time <= deadline_dt:
            return
        if any(score_type == "turnpoint_hunt_maximum_duration_exceeded" for _, score_type in self.scored_gates if _ == gate.name):
            return
        penalty = self.cima_config.maximum_task_duration_penalty
        self.update_gate_score(
            position,
            gate,
            penalty,
            "turnpoint_hunt_maximum_duration_exceeded",
            "maximum task duration exceeded",
            ANOMALY,
            deadline_dt,
            passing_time,
        )

    def _score_speed_keeping(self, gate: Gate, position, passing_time: datetime.datetime):
        """2.A4 known circuit: penalise legs flown materially faster/slower than the
        declared uniform speed. Legs bordering a manually overridden turnpoint time are
        skipped, since the contestant is expected to deviate from the declared speed to
        hit that specific declared time (see KnownCircuitStrategy)."""
        if self.contestant.navigation_task.task_subtype != "known_circuit":
            return
        if not hasattr(self.contestant, "contestanttaskconfiguration"):
            return
        config = self.contestant.contestanttaskconfiguration
        if not config.is_valid:
            return
        payload = config.compiled_effective_route_payload or {}
        overridden_gate_names = set(payload.get("overridden_gate_names") or [])

        previous_gate = self._last_speed_keeping_gate
        previous_time = self._last_speed_keeping_time
        self._last_speed_keeping_gate = gate
        self._last_speed_keeping_time = passing_time

        if previous_gate is None:
            return
        if gate.name in overridden_gate_names or previous_gate.name in overridden_gate_names:
            return

        elapsed_seconds = (passing_time - previous_time).total_seconds()
        if elapsed_seconds <= 0:
            return

        distance_m = calculate_distance_lat_lon(
            (previous_gate.latitude, previous_gate.longitude), (gate.latitude, gate.longitude)
        )
        actual_speed_kt = distance_m / elapsed_seconds * 3600 / 1852
        declared_speed_kt = self.contestant.air_speed
        tolerance_kt = self.cima_config.speed_keeping_tolerance_kt
        penalty_per_kt = self.cima_config.speed_keeping_penalty_per_kt

        deviation = abs(actual_speed_kt - declared_speed_kt)
        if deviation <= tolerance_kt:
            score = 0
            message = f"speed kept within {tolerance_kt:.1f} kt tolerance"
            annotation_type = INFORMATION
        else:
            score = (deviation - tolerance_kt) * penalty_per_kt
            message = f"speed deviation of {deviation:.1f} kt exceeds {tolerance_kt:.1f} kt tolerance"
            annotation_type = ANOMALY

        self.update_gate_score(
            position,
            gate,
            score,
            "speed_keeping",
            message,
            annotation_type,
            gate.expected_time,
            passing_time,
        )

    def on_starting_line_extended_passed_wrong_direction(self, event: StartingLineExtendedPassedWrongDirectionEvent):
        score = self.scorecard.get_bad_crossing_extended_gate_penalty_for_gate_type(self.starting_line.type)
        if score != 0:
            self.update_gate_score(
                event.position,
                self.starting_line,
                score,
                BACKWARD_STARTING_LINE_SCORE_TYPE,
                "backwards starting line",
                ANOMALY,
                self.starting_line.expected_time,
                event.position.time,
            )

    def on_starting_line_passed(self, event: StartingLinePassedEvent):
        self.on_gate_passed(event)

    def on_adaptive_start(self, event: AdaptiveStartEvent):
        if not event.gate_times:
            new_start_time = event.intersection_time
            event.gate_times = self.contestant.calculate_missing_gate_times({}, round_time_minute(new_start_time))

        gate_times = event.gate_times
        for gate in self.gates:
            if gate.name in gate_times:
                gate.expected_time = gate_times[gate.name]

        if self.has_scored_adaptive_start:
            return
        self.has_scored_adaptive_start = True
        self.update_score(
            UpdateScoreMessage(
                event.intersection_time,
                self.starting_line,
                0,
                "adaptive start set",
                event.position.latitude,
                event.position.longitude,
                INFORMATION,
                ADAPTIVE_TIMING_START_SCORE_TYPE,
                planned=event.intersection_time,
                actual=event.intersection_time,
            )
        )

    def _is_invalid_post_mp_contract_crossing(self, gate: Gate, passing_time: datetime.datetime) -> bool:
        if self.contestant.navigation_task.task_subtype != CONTRACT_NAVIGATION_TIME_CONTROLS:
            return False
        if not hasattr(self.contestant, "contestanttaskconfiguration"):
            return False
        config = self.contestant.contestanttaskconfiguration
        if not config.is_valid:
            return False
        payload = config.compiled_effective_route_payload or {}
        declared_sequence = payload.get("declared_sequence") or []
        time_model = payload.get("time_model") or {}
        after_mp = set(time_model.get("after_mp_sequence") or [])
        if gate.name not in after_mp:
            return False
        mp_time_iso = self.contestant.gate_times.get("MP")
        if isinstance(mp_time_iso, datetime.datetime):
            mp_time = mp_time_iso
        else:
            mp_time = None
        if mp_time is None and "MP" in (self.contestant.contestanttaskconfiguration.compiled_gate_times_payload or {}):
            mp_time = datetime.datetime.fromisoformat(
                self.contestant.contestanttaskconfiguration.compiled_gate_times_payload["MP"]
            )
        if mp_time is None:
            return False
        return passing_time < mp_time
