import datetime
import itertools
import logging
import math
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
from display.calculators.calculator_utilities import round_time_minute, travel_bearing_from_track
from display.calculators.positions_and_gates import Gate, round_seconds
from display.calculators.update_score_message import ACHIEVEMENT, PENALTY, UpdateScoreMessage
from display.flight_order_and_maps.effective_route_rendering import get_effective_route_waypoints
from display.models import ANOMALY, INFORMATION
from display.models.contestant_utility_models import ContestantReceivedPosition
from display.services.catalogue_gate_quality import CatalogueGateQuality
from display.services.task_scoring import relative_term_values
from display.utilities.task_types import CONTRACT_POINTS_SCORE_TYPE, SPEED_TERM_SCORE_TYPE, stored_task_type
from display.utilities.coordinate_utilities import (
    bearing_difference,
    calculate_distance_lat_lon,
    calculate_speed_between_points,
    extend_line,
)
from display.utilities.gate_definitions import (
    CIRCLE_CENTER,
    CIRCLE_ENTRY,
    CIRCLE_EXIT,
    CIRCLE_START,
    SECRETPOINT,
    UNKNOWN_LEG,
)
from display.utilities.route_building_utilities import calculate_extended_gate
from websocket_channels import WebsocketFacade

# How long before the planned starting line crossing (set start times) the gate score arrow gets a prediction of it.
START_ESTIMATE_LEAD = datetime.timedelta(minutes=1)

# How often the crossing of the next timed gate is estimated again: every few seconds, every second in the last half
# minute before the estimated crossing.
ESTIMATE_INTERVAL = datetime.timedelta(seconds=5)
CLOSE_ESTIMATE_INTERVAL = datetime.timedelta(seconds=1)
CLOSE_CROSSING_WITHIN = datetime.timedelta(seconds=30)

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
# 2.A6/2.B2 achievement score types: the two score types of the turnpoint hunt that add to the score (they are sent
# as ACHIEVEMENT messages); every other score type is a penalty.
TURNPOINT_HUNT_TARGET_VALUE_SCORE_TYPE = "turnpoint_hunt_target_value"
TURNPOINT_HUNT_SEQUENCE_BONUS_SCORE_TYPE = "turnpoint_hunt_sequence_bonus"
# 200 per time gate crossed (an achievement) and what its timing error costs beyond the tolerance (a penalty); the
# catalogue charges the error once, so the generic gate timing score is not charged on a compulsory gate (Annex 4, 2.A6).
TURNPOINT_HUNT_TIME_GATE_VALUE_SCORE_TYPE = "turnpoint_hunt_time_gate_value"
TURNPOINT_HUNT_COMPULSORY_TIMING_SCORE_TYPE = "turnpoint_hunt_compulsory_timing"
TURNPOINT_HUNT_MAXIMUM_DURATION_SCORE_TYPE = "turnpoint_hunt_maximum_duration_exceeded"
# A hidden gate that was crossed again or crossed against the route is invalidated (Annex 4: "crossing the same gate
# more than once in any direction invalidates the gate"). The score type is stable (it was introduced for 2.A1) and
# is also what the one log entry of the invalidation carries for 2.A2, 2.A4 and 2.A5.
HIDDEN_GATE_INVALIDATED_SCORE_TYPE = "curve_navigation_repeated_crossing"
# A timed hidden gate (2.A2) charged as not crossed, crossed afterwards (out of order, or against the route after the
# pilot had left its range): its time is taken from that crossing and the error it was charged as not crossed is
# given back, less the error of the crossing.
HIDDEN_GATE_TIMED_FROM_CROSSING_SCORE_TYPE = "hidden_gate_timed_from_crossing"
# A crossing of a hidden gate within this many seconds of the previous crossing of it is the same crossing: crossings
# are found from the chord of the last three positions, so a single crossing is seen on two consecutive positions.
SAME_CROSSING_SECONDS = 3


class GateCalculator(Calculator):
    """
    Calculator responsible for scoring gate crossings and misses.
    """

    # Class default so a calculator built without __init__ (as some unit tests do) can still be finalised.
    _speed_term_scored = False

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
        # 2.B2: the gates are matched as they are crossed, in any order (see TaskTypeDefinition.free_order_gate_matching).
        self._free_order = stored_task_type(contestant.navigation_task).free_order_gate_matching
        self.initiate_gates()
        # What a gate is worth and costs where the task follows the catalogue's formulas literally (2.A1, 2.A2), the
        # same weights that make the contestant's starting quality; None for the scorecard's flat scores.
        self.catalogue_quality: Optional[CatalogueGateQuality] = CatalogueGateQuality.for_task_type(
            stored_task_type(contestant.navigation_task), self.scorecard, self.gates
        )
        self.outstanding_gates = list(self.gates)
        self.websocket_facade = WebsocketFacade()
        self.last_backwards = None
        self.has_scored_adaptive_start = False
        self.scored_gates = set()
        # Annex 4 hidden gates (task types with repeated_hidden_gate_crossing_invalidates): the hidden gates already
        # passed, which are watched for a second crossing until the finish point is passed, the time of the last
        # crossing seen of each (to tell a second crossing from the same crossing seen again), what the first
        # crossing's timing already cost, and the hidden gates first crossed against the route.
        self._watched_hidden_gates: List[Gate] = []
        self._last_hidden_crossing: dict = {}
        self._hidden_timing_charged: dict = {}
        self._wrong_direction_hidden_gates: set = set()
        # Timed hidden gates charged as not crossed, with the time they were charged at, watched for a crossing after it.
        self._missed_timed_hidden_gates: List[tuple] = []
        self.scored_turnpoint_hunt_compulsory_gates = set()
        # 2.A6/2.B2: the seconds over the maximum task duration already charged, so that every later gate crossed only
        # costs the seconds since the previous one and the total is the seconds the last gate was crossed after the end.
        self._hunt_seconds_over_charged = 0.0
        self.last_estimation_time = datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)
        self._last_speed_keeping_gate: Optional[Gate] = None
        self._last_speed_keeping_time: Optional[datetime.datetime] = None
        # 2.A4 speed term: when the timed gates were crossed, the speed section runs between the first and the last.
        self._timed_gate_crossings: dict = {}
        self._speed_term_scored = False
        # 2.A6/2.B2 sequence bonus: the order actual gate PASSES happened in, compared against
        # the contestant's declared_sequence at finalise() - see
        # _score_turnpoint_hunt_sequence_bonus. Empty and unused for every other subtype.
        self.turnpoint_hunt_actual_order: List[str] = []
        # What publish_next_timed_gate last stored, so the database is only written when it changes.
        self._published_next_timed_gate = None

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
        kind: str = PENALTY,
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
                kind=kind,
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

        score = self._timing_score(gate, gate.expected_time, estimated_crossing_time)

        if self.live_processing:
            self.websocket_facade.transmit_seconds_to_crossing_time_and_crossing_estimate(
                self.contestant,
                gate.name,
                planned_time_to_crossing,
                round((estimated_crossing_time - gate.expected_time).total_seconds()),
                score,
                True,
                gate.missed,
                gate.expected_time,
                position.time,
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

        # Find next TIMED gate starting from next_gate, and accumulate the route-following
        # (leg-by-leg) distance from next_gate up to (but not including) that timed gate. A
        # straight-line distance from the current position directly to a distant timed gate
        # (e.g. FP) badly underestimates the actual remaining distance whenever there are
        # untimed turnpoints - and therefore turns - in between, such as an ANR corridor: a
        # contestant only halfway around a winding route can be much closer to FP as the crow
        # flies than the distance they still have to actually fly. gate.distance (distance_next)
        # is exactly the leg length from each gate to the next one in route order, in metres.
        # A task that keeps its secret gates and unknown legs hidden gets no countdown to them either: the arrow counts
        # to the next gate the pilot is told about, the secret gate's distance still being part of the way there.
        hides_secrets = not self.contestant.navigation_task.display_secrets
        next_timed_gate = None
        remaining_leg_distance_m = 0.0
        started = False
        for gate in self.gates:
            if not started and gate == state.next_gate:
                started = True
            if started:
                if gate.time_check and not (hides_secrets and gate.type in (SECRETPOINT, UNKNOWN_LEG)):
                    next_timed_gate = gate
                    break
                remaining_leg_distance_m += gate.distance or 0

        if next_timed_gate is None:
            return None

        speed = self.calculate_speed(track)
        if speed <= 0:
            return None

        last_pos = track[-1]

        p_x = getattr(last_pos, "projected_x", None)
        p_y = getattr(last_pos, "projected_y", None)

        if p_x is not None and state.next_gate.center_x is not None:

            distance_to_next_gate_m = math.sqrt(
                (p_x - state.next_gate.center_x) ** 2 + (p_y - state.next_gate.center_y) ** 2
            )
        else:
            distance_to_next_gate_m = calculate_distance_lat_lon(
                (last_pos.latitude, last_pos.longitude), (state.next_gate.latitude, state.next_gate.longitude)
            )

        if remaining_leg_distance_m == 0:
            distance_to_next_gate_m = self._distance_along_heading_to_gate_line(
                state.next_gate, last_pos, track, distance_to_next_gate_m
            )

        distance = (distance_to_next_gate_m + remaining_leg_distance_m) / 1852  # nm

        seconds_to_gate = (distance / speed) * 3600
        estimated_time = last_pos.time + datetime.timedelta(seconds=seconds_to_gate)

        return EstimationUpdatedEvent(next_timed_gate, estimated_time, last_pos)

    @staticmethod
    def _distance_along_heading_to_gate_line(
        gate: Gate, last_pos, track: Sequence[ContestantReceivedPosition], distance_to_centre_m: float
    ) -> float:
        """
        The distance the aircraft still has to fly to reach the gate's line, not its centre. An aircraft that approaches
        off-centre never gets closer to the centre than its sideways offset, so the estimate to the centre stops
        falling a few seconds before the line and then jumps back when the crossing is detected. Falls back to the
        distance to the centre whenever the line, the heading or the geometry does not give a better answer.
        """
        line = gate.projected_gate_line_infinite or gate.projected_gate_line
        p_x = getattr(last_pos, "projected_x", None)
        p_y = getattr(last_pos, "projected_y", None)
        bearing = travel_bearing_from_track(track)
        if not line or p_x is None or p_y is None or bearing is None or gate.gate_heading is None:
            return distance_to_centre_m
        dx = line[1].projected_x - line[0].projected_x
        dy = line[1].projected_y - line[0].projected_y
        length = math.hypot(dx, dy)
        if length == 0:
            return distance_to_centre_m
        perpendicular = abs(dx * (p_y - line[0].projected_y) - dy * (p_x - line[0].projected_x)) / length
        # How square to the line the aircraft is flying; a shallow angle would make the distance blow up.
        cosine = max(math.cos(math.radians(bearing_difference(bearing, gate.gate_heading))), 0.5)
        return min(distance_to_centre_m, perpendicular / cosine)

    def calculate_enroute(
        self,
        track: Sequence[ContestantReceivedPosition],
        state: OrchestratorState,
    ) -> List[OrchestratorEvent]:
        events = self.check_intersections(track, state)

        # Performance estimation every 5 seconds, every second once the crossing is near (or overdue): the last half
        # minute is where the live map's prediction is watched, and a stale one is then up to five seconds old.
        last_pos = track[-1]
        crossing_is_near = (
            state.estimated_crossing_time is not None
            and state.estimated_crossing_time - last_pos.time < CLOSE_CROSSING_WITHIN
        )
        interval = CLOSE_ESTIMATE_INTERVAL if crossing_is_near else ESTIMATE_INTERVAL
        if last_pos.time >= self.last_estimation_time + interval:
            estimation_event = self.estimate_crossing_time_of_next_timed_gate(track, state)
            if estimation_event:
                events.append(estimation_event)
                self.last_estimation_time = last_pos.time

        if self.live_processing and state.estimated_next_timed_gate and state.estimated_crossing_time:
            self._transmit_estimate(state.estimated_next_timed_gate, state.estimated_crossing_time, track[-1].time)
        return events

    def _transmit_estimate(self, gate: Gate, estimated_crossing_time: datetime.datetime, position_time: datetime.datetime):
        """
        Update the gate score arrow in the frontend with the predicted crossing of a gate, made from the position at
        position_time.
        """
        planned_time_to_crossing = (position_time - gate.expected_time).total_seconds()
        score = self._timing_score(gate, gate.expected_time, estimated_crossing_time)
        self.websocket_facade.transmit_seconds_to_crossing_time_and_crossing_estimate(
            self.contestant,
            gate.name,
            planned_time_to_crossing,
            round((estimated_crossing_time - gate.expected_time).total_seconds()),
            score,
            False,
            False,
            gate.expected_time,
            position_time,
        )

    def _transmit_start_estimate(self, track: Sequence[ContestantReceivedPosition], state: OrchestratorState):
        """
        The prediction of the starting line crossing, for a start at a set time, in the last START_ESTIMATE_LEAD before
        the planned time (and on until the line is crossed). Earlier the contestant may be parked, taxiing or climbing:
        the estimate would be made from a speed that says nothing about when they get there. An adaptive start has no
        planned time to predict against.
        """
        line = self.starting_line
        if (
            not self.live_processing
            or not track
            or self.contestant.adaptive_start
            or line is None
            or state.next_gate is not line
            or not line.time_check
            or track[-1].time < line.expected_time - START_ESTIMATE_LEAD
        ):
            return
        estimation = self.estimate_crossing_time_of_next_timed_gate(track, state)
        if estimation and estimation.gate is line:
            self._transmit_estimate(line, estimation.estimated_time, track[-1].time)

    def calculate_outside_route(
        self,
        track: Sequence[ContestantReceivedPosition],
        state: OrchestratorState,
    ) -> List[OrchestratorEvent]:
        events = self.check_intersections(track, state)
        # Emit initial next gate if none known yet
        if state.next_gate is None and self.outstanding_gates:
            events.append(NextGateExpectedEvent(self.outstanding_gates[0], track[-1]))
        self._transmit_start_estimate(track, state)
        return events

    def check_intersections(
        self, track: Sequence[ContestantReceivedPosition], state: OrchestratorState
    ) -> List[OrchestratorEvent]:
        """
        Detection logic using OrchestratorState.
        """
        events = []

        if self._free_order:
            events.extend(self._check_free_order_intersections(state, track))
            self.publish_next_timed_gate()
            return events

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
        invalidates_hidden_gates = self._task_type.repeated_hidden_gate_crossing_invalidates
        hidden_gates_crossed_backwards = []
        # Use our own outstanding_gates list which is always up to date within this call
        for i, intersected_gate in enumerate(self.outstanding_gates):
            intersection_time = intersected_gate.get_gate_intersection_time(state.projector, track)
            if intersection_time and intersected_gate.is_passed_in_correct_direction_track(track):
                crossed_gate_index = i
                passed_intersection_time = intersection_time
                break
            if (
                intersection_time
                and invalidates_hidden_gates
                and intersected_gate.type == SECRETPOINT
                and travel_bearing_from_track(track) is not None
            ):
                hidden_gates_crossed_backwards.append((intersected_gate, intersection_time))

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

        events.extend(self._hidden_gates_crossed_backwards(hidden_gates_crossed_backwards, track))
        if invalidates_hidden_gates:
            self._invalidate_repeated_hidden_gate_crossings(state, track)
            self._time_missed_hidden_gates_from_crossing(state, track)

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
        self.publish_next_timed_gate()

        return events

    def _check_free_order_intersections(
        self, state: OrchestratorState, track: Sequence[ContestantReceivedPosition]
    ) -> List[OrchestratorEvent]:
        """
        2.B2 ("all gate crossings provide points"): a gate counts when it is crossed, whichever it is, in either
        direction, and flying one gate before another never marks the other as missed. Every outstanding gate is tested
        against the latest positions, which costs the distance to its centre per position (the crossing test returns at
        once for a gate more than its radius plus 500 m away) and a line intersection only for the gate the aircraft is
        at; gates already crossed leave the list, so the cost falls as the flight proceeds. Gates not crossed are charged
        nothing, so there is no missed-gate detection either.
        """
        crossed = []
        for gate in self.outstanding_gates:
            intersection_time = gate.get_gate_intersection_time(state.projector, track)
            if intersection_time:
                crossed.append((intersection_time, gate))
        events: List[OrchestratorEvent] = []
        for intersection_time, gate in sorted(crossed, key=lambda item: item[0]):
            index = self.gates.index(gate)
            previous_gate = self.gates[index - 1] if index > 0 else None
            events.append(GatePassedEvent(gate, track[-1], intersection_time, previous_gate=previous_gate))
            self.outstanding_gates.remove(gate)
        if crossed:
            events.append(NextGateExpectedEvent(self._get_next_gate(), track[-1]))
        return events

    def _hidden_gates_crossed_backwards(self, crossings, track) -> List[OrchestratorEvent]:
        """
        A hidden gate whose first crossing is against the route does not count (Annex 4: gates must be crossed in the
        proper direction), and as it is crossed it can no longer be crossed correctly once: it is invalidated at once and
        leaves the outstanding gates as a missed gate, scored under the invalidation score type. Gates the correct
        crossing of a later gate has just marked as missed or passed are no longer outstanding and are left alone.
        """
        events: List[OrchestratorEvent] = []
        for gate, crossing_time in crossings:
            if gate not in self.outstanding_gates:
                continue
            self._wrong_direction_hidden_gates.add(gate.name)
            was_next = self.outstanding_gates[0] is gate
            self.outstanding_gates.remove(gate)
            index = self.gates.index(gate)
            previous_gate = self.gates[index - 1] if index > 0 else None
            logger.info(f"{self.contestant}: Hidden gate {gate} crossed against the route, invalidated")
            events.append(GateMissedEvent(previous_gate, gate, track[-1], event_time=crossing_time))
            if was_next:
                events.append(NextGateExpectedEvent(self._get_next_gate(), track[-1]))
        return events

    def _invalidate_repeated_hidden_gate_crossings(self, state: OrchestratorState, track):
        """
        A hidden gate already passed is invalidated by any later crossing of it, in either direction (Annex 4: "crossing
        the same gate more than once in any direction invalidates the gate"). Only the passed hidden gates are watched,
        and only until the finish point is passed. Each costs one distance to the gate's centre per position (the
        crossing test itself returns at once for a gate more than its radius plus 500 m away), so the cost follows the
        number of hidden gates passed and nothing is checked for the other gates or once the flight is finished.
        """
        if not self._watched_hidden_gates:
            return
        if state.has_passed_finishpoint:
            self._watched_hidden_gates = []
            return
        for gate in list(self._watched_hidden_gates):
            crossing_time = gate.get_gate_intersection_time(state.projector, track)
            if crossing_time is None:
                continue
            if abs((crossing_time - self._last_hidden_crossing[gate.name]).total_seconds()) <= SAME_CROSSING_SECONDS:
                # The crossing that passed the gate (or the previous crossing) seen on the next position.
                self._last_hidden_crossing[gate.name] = crossing_time
                continue
            self._watched_hidden_gates.remove(gate)
            logger.info(f"{self.contestant}: Hidden gate {gate} crossed again, invalidated")
            if not gate.gate_check:
                continue
            if self.catalogue_quality:
                # It loses its value; the time of the first crossing is already charged (Annex 4: time is extracted
                # from the first crossing).
                invalidation_score = self.catalogue_quality.invalidated_loss(gate)
            else:
                # The gate is worth what a gate not correctly crossed is worth: its missed score less the timing score
                # its first crossing already cost (which is where its time keeps coming from).
                missed_score = self.scorecard.get_gate_timing_score_for_gate_type(gate.type, gate.expected_time, None)
                invalidation_score = max(0, missed_score - self._hidden_timing_charged.get(gate.name, 0))
            self.update_gate_score(
                track[-1],
                gate,
                invalidation_score,
                HIDDEN_GATE_INVALIDATED_SCORE_TYPE,
                "gate invalidated by repeated crossing",
                ANOMALY,
                gate.expected_time,
                gate.passing_time,
                time_override=crossing_time,
            )

    def _time_missed_hidden_gates_from_crossing(self, state: OrchestratorState, track):
        """
        A timed hidden gate (2.A2) is timed from its first crossing, in whichever direction and order (Annex 4: "if a
        gate is crossed twice, time will be extracted from the first crossing"). One charged as not crossed (its Emax of
        time error) that is crossed afterwards has that error replaced by the error of the crossing; the gate stays
        invalidated and keeps losing its value. Only these few gates are watched, until the finish point is passed.
        """
        if not self._missed_timed_hidden_gates:
            return
        if state.has_passed_finishpoint:
            self._missed_timed_hidden_gates = []
            return
        for gate, missed_time in list(self._missed_timed_hidden_gates):
            crossing_time = gate.get_gate_intersection_time(state.projector, track)
            if crossing_time is None or crossing_time <= missed_time:
                continue
            self._missed_timed_hidden_gates.remove((gate, missed_time))
            quality = self.catalogue_quality
            credit = quality.timing_loss(gate, gate.expected_time, None) - quality.timing_loss(
                gate, gate.expected_time, crossing_time
            )
            logger.info(f"{self.contestant}: Hidden gate {gate} crossed after it was missed, timed from the crossing")
            self.update_gate_score(
                track[-1],
                gate,
                credit,
                HIDDEN_GATE_TIMED_FROM_CROSSING_SCORE_TYPE,
                "hidden gate timed from its crossing",
                ANOMALY,
                gate.expected_time,
                crossing_time,
                time_override=crossing_time,
                kind=ACHIEVEMENT,
            )

    def _next_timed_gate(self) -> Optional[Gate]:
        """
        The next gate the pilot may count down to in the app's training mode: the first outstanding gate that has a time
        check and is shown to the pilot. Secret gates, unknown legs and curve points are skipped, so a countdown never
        gives away a gate the pilot is not told about. With an adaptive start the gate times are only known once the
        starting point is crossed (on_adaptive_start moves them), and the starting point itself has no time to count down
        to: its time is set by the crossing.
        """
        # The crossing itself, not has_infinite_been_passed(), which is also true for a missed starting point: the gate
        # times only move when the line is actually crossed.
        if self.contestant.adaptive_start and not (self.starting_line and self.starting_line.infinite_passing_time is not None):
            return None
        for gate in self.outstanding_gates:
            if self.contestant.adaptive_start and gate is self.starting_line:
                continue
            if gate.time_check and gate.is_visible and gate.expected_time and not gate.has_been_passed():
                return gate
        return None

    def publish_next_timed_gate(self):
        """Stores the next timed gate for the app's training countdown (see _next_timed_gate) whenever it or its time changes."""
        if not self.live_processing:
            return
        gate = self._next_timed_gate()
        published = (gate.name, gate.expected_time) if gate else ("", None)
        if published == self._published_next_timed_gate:
            return
        self._published_next_timed_gate = published
        self.contestant.contestanttrack.update_next_timed_gate(*published)

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
        self._watched_hidden_gates = []
        self._missed_timed_hidden_gates = []
        self._score_speed_term(event.position)

    def finalise(self, track: Sequence[ContestantReceivedPosition]):
        # Catch any remaining missed gates at the very end of processing
        for gate in self.gates:
            if not gate.has_been_passed() and not gate.missed and (gate.name, GATE_SCORE_TYPE) not in self.scored_gates:
                gate.missed = True
                self.on_gate_missed(GateMissedEvent(None, gate, track[-1] if track else None))
        self.outstanding_gates = []
        self._watched_hidden_gates = []
        self._score_speed_term(track[-1] if track else None)
        # The flight is over: no next gate for the app's countdown any more.
        self.publish_next_timed_gate()
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

        if self._task_type.scores_turnpoint_hunt_targets:
            # 2.A6, 2.B2: a gate or target not flown earns nothing and costs nothing (Annex 4).
            return

        if event.gate.gate_check:
            wrong_direction = event.gate.name in self._wrong_direction_hidden_gates
            if self.catalogue_quality:
                self._score_declared_point_not_flown(
                    event.gate, event.position, event_time, "declared point not flown or not in order (V -1)"
                )
                if wrong_direction:
                    # Timed from its only crossing, the one against the route.
                    score = self.catalogue_quality.invalidated_loss(
                        event.gate, event.gate.expected_time, event.event_time
                    )
                else:
                    score = self.catalogue_quality.missed_loss(event.gate)
                if not score:
                    return  # SP, or a gate the task does not score: nothing was lost
            else:
                score = self.scorecard.get_gate_timing_score_for_gate_type(
                    event.gate.type, event.gate.expected_time, None
                )
            message = "missing gate"
            score_type = GATE_SCORE_TYPE
            if wrong_direction:
                message = "hidden gate crossed against the route"
                score_type = HIDDEN_GATE_INVALIDATED_SCORE_TYPE

            self.update_gate_score(
                event.position,
                event.gate,
                score,
                score_type,
                message,
                ANOMALY,
                planned=event.gate.expected_time,
                actual=None,
                time_override=event_time,
            )
            if (
                self.catalogue_quality
                and not wrong_direction
                and event.gate.type == SECRETPOINT
                and self.catalogue_quality.is_timed(event.gate)
                and event_time
            ):
                self._missed_timed_hidden_gates.append((event.gate, event_time))

    def on_gate_passed(self, event: GatePassedEvent):
        if event.gate not in self.gates:
            return

        logger.info(f"{self.contestant}: Scoring passed gate {event.gate}")
        if event.gate.time_check:
            # The countdown goes on to the next timed gate from the next position, not up to five seconds later.
            self.last_estimation_time = datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)
        passing_time = (
            event.intersection_time
            or event.gate.passing_time
            or event.gate.infinite_passing_time
            or event.position.time
        )
        passing_position = event.gate.infinite_passing_position or event.position

        if self._is_invalid_post_mp_contract_crossing(event.gate, passing_time):
            event.gate.missed = True
            # A point declared after MP and flown before the time of MP is invalid: a declared point not flown (Ep).
            self._score_declared_point_not_flown(
                event.gate,
                passing_position,
                passing_time,
                "invalid post-MP point flown before MP time (declared point not flown, V -1)",
            )
            return

        # Mark the gate as passed internally
        event.gate.pass_gate(passing_time, passing_position)

        time_difference = (passing_time - event.gate.expected_time).total_seconds()
        self.contestant.contestanttrack.update_last_gate(event.gate.name, time_difference)
        if event.gate.time_check:
            self.contestant.contestanttrack.update_last_timed_gate(event.gate.name, time_difference)

        message = "passing gate"
        self._watch_passed_hidden_gate(event.gate, passing_time)

        if self._is_turnpoint_hunt_compulsory_gate(event.gate):
            # Its timing is scored once, below, as the time gate it is (value less the error beyond the tolerance).
            self.transmit_actual_crossing(event.gate, passing_position)
        elif self.catalogue_quality.is_timed(event.gate) if self.catalogue_quality else event.gate.time_check:
            gate_score = self.scorecard.get_gate_timing_score_for_gate_type(
                event.gate.type, event.gate.expected_time, passing_time
            )
            self._hidden_timing_charged[event.gate.name] = gate_score
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
        self._score_declared_point_flown(event.gate, passing_position, passing_time)
        self._track_turnpoint_hunt_actual_order(event.gate)
        self._score_turnpoint_hunt_compulsory_timing(event.gate, passing_position, passing_time)
        self._score_turnpoint_hunt_target_value(event.gate, passing_position, passing_time)
        self._score_limited_fuel_deadline(event.gate, passing_position, passing_time)
        self._score_turnpoint_hunt_maximum_duration(event.gate, passing_position, passing_time)
        self._score_speed_keeping(event.gate, passing_position, passing_time)
        if event.gate.time_check:
            self._timed_gate_crossings[event.gate] = passing_time

    def _score_declared_point_flown(self, gate: Gate, position, passing_time: datetime.datetime):
        """2.A3: a declared turn point flown in order counts in N, so it adds one to V (Qp = 1000 x V / Vmax)."""
        if self.catalogue_quality and self.catalogue_quality.v_gain(gate):
            self.update_gate_score(
                position,
                gate,
                self.catalogue_quality.v_gain(gate),
                CONTRACT_POINTS_SCORE_TYPE,
                "declared point flown in order (V +1)",
                INFORMATION,
                time_override=passing_time,
                kind=ACHIEVEMENT,
            )

    def _score_declared_point_not_flown(
        self, gate: Gate, position, time: Optional[datetime.datetime], message: str
    ):
        """2.A3: a declared point not flown, or not in order, counts in Ep: it takes one off V (SP, MP and FP too)."""
        if self.catalogue_quality and self.catalogue_quality.v_loss(gate):
            self.update_gate_score(
                position,
                gate,
                self.catalogue_quality.v_loss(gate),
                CONTRACT_POINTS_SCORE_TYPE,
                message,
                ANOMALY,
                time_override=time,
            )

    def _watch_passed_hidden_gate(self, gate: Gate, passing_time: datetime.datetime):
        """A hidden gate just passed is watched for a second crossing, see _invalidate_repeated_hidden_gate_crossings."""
        if gate.type != SECRETPOINT or not self._task_type.repeated_hidden_gate_crossing_invalidates:
            return
        if gate in self._watched_hidden_gates:
            return
        self._watched_hidden_gates.append(gate)
        self._last_hidden_crossing[gate.name] = passing_time

    @property
    def _task_type(self):
        return stored_task_type(self.contestant.navigation_task)

    def _turnpoint_hunt_payload(self) -> dict:
        """The compiled effective route of a valid declaration of a turnpoint hunt, else nothing."""
        if not self._task_type.scores_turnpoint_hunt_targets:
            return {}
        if not hasattr(self.contestant, "contestanttaskconfiguration"):
            return {}
        config = self.contestant.contestanttaskconfiguration
        if not config.is_valid:
            return {}
        return config.compiled_effective_route_payload or {}

    def _is_turnpoint_hunt_compulsory_gate(self, gate: Gate) -> bool:
        return gate.name in (self._turnpoint_hunt_payload().get("compulsory_timing_gate_names") or [])

    def _turnpoint_hunt_timing_penalty(self, seconds_off: float) -> float:
        """Annex 4 2.A6: nothing within the tolerance, beyond it every second costs the scorecard's points per second."""
        beyond = abs(seconds_off) - self.cima_config.compulsory_timing_tolerance_seconds
        return max(0.0, beyond) * self.cima_config.compulsory_timing_penalty_per_second

    def _timing_score(self, gate: Gate, expected_time, actual_time) -> float:
        """What a crossing of the gate at `actual_time` costs, for the gate score the live map shows."""
        if self._is_turnpoint_hunt_compulsory_gate(gate):
            if actual_time is None:
                return 0
            return self._turnpoint_hunt_timing_penalty((actual_time - expected_time).total_seconds())
        return self.scorecard.get_gate_timing_score_for_gate_type(gate.type, expected_time, actual_time)

    def _score_turnpoint_hunt_compulsory_timing(self, gate: Gate, position, passing_time: datetime.datetime):
        """
        2.A6/2.B2: a compulsory time gate crossed is worth `turnpoint_hunt_time_gate_value` (200) and loses 10 points per
        second its crossing is off the declared time beyond the tolerance of 10 s, once (the generic gate timing score
        is not charged on these gates). A gate not crossed earns and costs nothing.
        """
        if not self._is_turnpoint_hunt_compulsory_gate(gate):
            return
        if gate.name in self.scored_turnpoint_hunt_compulsory_gates:
            return
        self.scored_turnpoint_hunt_compulsory_gates.add(gate.name)
        tolerance_seconds = self.cima_config.compulsory_timing_tolerance_seconds
        seconds_off = (passing_time - gate.expected_time).total_seconds()
        # A gate without a declared time has nothing to be timed against (its expected time is a placeholder).
        declared = gate.name in (self._turnpoint_hunt_payload().get("compulsory_point_times") or {})
        penalty = self._turnpoint_hunt_timing_penalty(seconds_off) if declared else 0
        direction = "late" if seconds_off > 0 else "early"
        if penalty:
            timing = f"{abs(seconds_off):.0f} s {direction}, {abs(seconds_off) - tolerance_seconds:.0f} s beyond the tolerance"
        else:
            timing = f"{abs(seconds_off):.0f} s {direction}, within the {tolerance_seconds} s tolerance"
        value = float(self.cima_config.turnpoint_hunt_time_gate_value)
        if value:
            self.update_gate_score(
                position,
                gate,
                value,
                TURNPOINT_HUNT_TIME_GATE_VALUE_SCORE_TYPE,
                f"time gate crossed {timing}",
                INFORMATION,
                gate.expected_time,
                passing_time,
                kind=ACHIEVEMENT,
            )
        if penalty:
            self.update_gate_score(
                position,
                gate,
                penalty,
                TURNPOINT_HUNT_COMPULSORY_TIMING_SCORE_TYPE,
                f"compulsory timing gate {timing}",
                ANOMALY,
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
        if not self._task_type.scores_turnpoint_hunt_targets:
            return
        if gate.name in self.turnpoint_hunt_actual_order:
            return
        self.turnpoint_hunt_actual_order.append(gate.name)

    def _score_turnpoint_hunt_target_value(self, gate: Gate, position, passing_time: datetime.datetime):
        if not self._task_type.scores_turnpoint_hunt_targets:
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
            kind=ACHIEVEMENT,
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
        if not self._task_type.scores_turnpoint_hunt_targets:
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
            kind=ACHIEVEMENT,
        )

    def _score_limited_fuel_deadline(self, gate: Gate, position, passing_time: datetime.datetime):
        if not self._task_type.has_fuel_deadline:
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
        """
        2.A6/2.B2: every second the flight lasts beyond the maximum task duration costs the scorecard's points per second.
        The application has no event for the end of the task, so the end is the last gate crossed: each gate crossed after
        the deadline charges the seconds since the previous charge, and the charges add up to the seconds the last gate was
        crossed after the deadline.
        """
        deadline = self._turnpoint_hunt_payload().get("maximum_task_duration_deadline")
        if not deadline:
            return
        deadline_dt = datetime.datetime.fromisoformat(deadline)
        seconds_over = (passing_time - deadline_dt).total_seconds()
        additional = seconds_over - self._hunt_seconds_over_charged
        if additional <= 0:
            return
        self._hunt_seconds_over_charged = seconds_over
        self.update_gate_score(
            position,
            gate,
            additional * self.cima_config.maximum_task_duration_penalty,
            TURNPOINT_HUNT_MAXIMUM_DURATION_SCORE_TYPE,
            f"maximum task duration exceeded: {additional:.0f} s more (crossed {seconds_over:.0f} s after the end)",
            ANOMALY,
            deadline_dt,
            passing_time,
        )

    def _score_speed_term(self, position):
        """
        2.A4 speed term Qv = Vs x S / Smax. S is the ground speed in the speed section, which runs along the route
        between the first and the last time gate the pilot crossed (the catalogue leaves the section to the briefing).
        The calculator logs S once the flight is over; task_scoring divides it by the best S of the task and multiplies
        by Vs, which the scorecard briefs (0: no speed term).
        """
        if self._speed_term_scored or not self._task_type.scores_speed_keeping:
            return
        if not relative_term_values(self.scorecard, self._task_type).get(SPEED_TERM_SCORE_TYPE):
            return
        crossed = sorted(self._timed_gate_crossings.items(), key=lambda item: self.gates.index(item[0]))
        if len(crossed) < 2:
            return
        (first, first_time), (last, last_time) = crossed[0], crossed[-1]
        seconds = (last_time - first_time).total_seconds()
        if seconds <= 0:
            return
        section = self.gates[self.gates.index(first) : self.gates.index(last) + 1]
        metres = sum(
            calculate_distance_lat_lon((a.latitude, a.longitude), (b.latitude, b.longitude))
            for a, b in zip(section, section[1:])
        )
        speed_kt = round(metres / seconds * 3600 / 1852, 2)
        self._speed_term_scored = True
        self.update_gate_score(
            position,
            last,
            speed_kt,
            SPEED_TERM_SCORE_TYPE,
            f"ground speed {speed_kt:g} kt from {first.name} to {last.name} (S, scored against the best of the task)",
            INFORMATION,
            time_override=last_time,
            kind=ACHIEVEMENT,
        )

    def _score_speed_keeping(self, gate: Gate, position, passing_time: datetime.datetime):
        """2.A4 known circuit: penalise legs flown materially faster/slower than the
        declared uniform speed, when the scorecard turns the rule on (it is not part of
        the catalogue). Legs bordering a manually overridden turnpoint time are
        skipped, since the contestant is expected to deviate from the declared speed to
        hit that specific declared time (see KnownCircuitStrategy)."""
        if not self._task_type.scores_speed_keeping or not self.cima_config.speed_keeping_enabled:
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
            event.gate_times = self.contestant.adaptive_start_gate_times(round_time_minute(new_start_time))

        gate_times = event.gate_times
        for gate in self.gates:
            if gate.name in gate_times:
                gate.expected_time = gate_times[gate.name]
        # The app's training countdown must count to the moved times at once.
        self.publish_next_timed_gate()

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
        if not self._task_type.has_post_mp_rule:
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
