import datetime
import logging
from multiprocessing import Queue
from typing import TYPE_CHECKING, List, Optional

from display.calculators.calculator import (
    Calculator,
    OrchestratorState,
    OrchestratorEvent,
    GatePassedEvent,
    GateMissedEvent,
    StartingLinePassedEvent,
    FinishLinePassedEvent,
)
from display.calculators.calculator_utilities import bearing_between
from display.calculators.update_score_message import UpdateScoreMessage
from display.models.contestant_utility_models import ContestantReceivedPosition
from display.utilities.coordinate_utilities import (
    get_heading_difference,
    bearing_difference,
    calculate_distance_lat_lon,
    euclidean_point_to_line_distance,
)
from display.utilities.route_building_utilities import find_closest_leg_to_point
from display.models import Contestant, Scorecard, Route, ANOMALY, INFORMATION
from display.waypoint import Waypoint

if TYPE_CHECKING:
    from display.calculators.positions_and_gates import Gate

logger = logging.getLogger(__name__)


class BacktrackingAndProcedureTurnsCalculator(Calculator):
    """
    Implements https://www.fai.org/sites/default/files/documents/gac_2020_precision_flying_rules_final.pdf
    """

    PROCEDURE_TURN_SCORE_TYPE = "procedure_turn"
    BACKTRACKING_SCORE_TYPE = "backtracking"

    BEFORE_START = 0
    STARTED = 1
    FINISHED = 2
    TAKEOFF = 4

    TRACKING = 3

    DEVIATING = 8
    BACKTRACKING = 5
    PROCEDURE_TURN = 6
    FAILED_PROCEDURE_TURN = 7
    BACKTRACKING_TEMPORARY = 9
    TRACKING_MAP = {
        BEFORE_START: "Waiting...",
        FINISHED: "Finished",
        STARTED: "Started",
        TAKEOFF: "Takeoff",
        TRACKING: "Tracking",
        BACKTRACKING: "Backtracking",
        PROCEDURE_TURN: "Procedure turn",
        FAILED_PROCEDURE_TURN: "Failed procedure turn",
        DEVIATING: "Deviating",
        BACKTRACKING_TEMPORARY: "Off-track",
    }

    def create_gates(self) -> List["Gate"]:
        """
        Helper function to create gates from the waypoints defined in a route
        """
        from display.calculators.positions_and_gates import Gate
        from display.utilities.route_building_utilities import calculate_extended_gate

        waypoints = self.contestant.navigation_task.route.waypoints
        expected_times = self.contestant.gate_times
        gates = []
        for item in waypoints:  # type: Waypoint
            # Dummy gates are not part of the actual route
            if item.type != "dummy" and not getattr(item, "on_curved_segment", False):
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

    def get_last_non_secret_gate(self, last_visible_gate: "Gate") -> Optional["Gate"]:
        from display.utilities.gate_definitions import SECRETPOINT, TURNPOINT

        # If no last_visible_gate provided, try to find the first one from our list
        gate_to_start_from = last_visible_gate
        if gate_to_start_from is None:
            if hasattr(self, "gates") and self.gates:
                gate_to_start_from = self.gates[0]
            else:
                return None

        started = False
        for gate in reversed(self.gates):
            if not started and gate == gate_to_start_from:
                started = True
            if started and gate.type != SECRETPOINT:
                return gate

        return gate_to_start_from

    def __init__(
        self,
        contestant: "Contestant",
        scorecard: "Scorecard",
        route: "Route",
        score_processing_queue: Queue,
        live_processing: bool = True,
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
        self.contestant = contestant
        self.scorecard = scorecard
        self.current_procedure_turn_gate = None
        self.current_procedure_turn_directions = []
        self.current_procedure_turn_slices = []
        self.current_procedure_turn_bearing_difference = 0
        self.current_procedure_turn_start_time = None
        self.backtracking_start_time = None
        self.backtracked_on_current_leg = False
        self.last_bearing = None
        self.last_visible_gate = None
        self.last_gate_previous_round = None
        self.last_leg_name = None
        self.was_backtracked_on_leg_leading_to_last_gate = False
        # Put into separate parameter so that we can change this when finalising in order to terminate any ongoing
        # backtracking
        self.backtracking_limit = self.scorecard.backtracking_bearing_difference
        self.tracking_state = self.BEFORE_START

    def update_tracking_state(self, tracking_state: int):
        if tracking_state == self.tracking_state:
            return
        logger.info("{}: Changing state to {}".format(self.contestant, self.TRACKING_MAP[tracking_state]))
        self.tracking_state = tracking_state
        self.contestant.contestanttrack.updates_current_state(self.TRACKING_MAP[tracking_state])

    def on_gate_passed(self, event: GatePassedEvent):
        from display.utilities.gate_definitions import SECRETPOINT, TURNPOINT

        if event.gate.type != SECRETPOINT:
            self.last_visible_gate = event.gate
        if self.tracking_state == self.FAILED_PROCEDURE_TURN:
            self.update_tracking_state(self.TRACKING)

    def on_gate_missed(self, event: GateMissedEvent):
        from display.utilities.gate_definitions import SECRETPOINT, TURNPOINT

        if event.gate.type != SECRETPOINT:
            self.last_visible_gate = event.gate
        if self.tracking_state == self.FAILED_PROCEDURE_TURN:
            self.update_tracking_state(self.TRACKING)
        self.backtracking_start_time = None
        self.was_backtracked_on_leg_leading_to_last_gate = self.backtracked_on_current_leg
        self.backtracked_on_current_leg = False

    def calculate_enroute(
        self,
        track: List[ContestantReceivedPosition],
        state: OrchestratorState,
    ) -> List[OrchestratorEvent]:
        # Need to do the track score first since this might declare the remaining gates as missed if we are done
        # with the track. We can then calculate gate score and consider the missed gates.
        # This also ensures we enter PROCEDURE_TURN state.
        self.calculate_track_score(
            track,
            state.last_visible_gate,
            state.in_range_of_gate,
            state.next_gate,
        )
        return []

    def calculate_outside_route(
        self,
        track: List[ContestantReceivedPosition],
        state: OrchestratorState,
    ) -> List[OrchestratorEvent]:
        self.calculate_track_score(
            track,
            state.last_visible_gate,
            state.in_range_of_gate,
            state.next_gate,
        )
        return []

    def update_current_leg(self, current_leg):
        leg_name = current_leg.name if current_leg else ""
        if not hasattr(self, "last_leg_name") or self.last_leg_name != leg_name:
            self.contestant.contestanttrack.update_current_leg(leg_name)
            self.last_leg_name = leg_name

    TIME_FORMAT = "%H:%M:%S"

    def passed_finishpoint(self, event: FinishLinePassedEvent):
        self.backtracking_limit = 360
        # Rerun track calculation one final time in order to terminate any ongoing backtracking
        self.calculate_track_score(event.track, event.last_gate, event.last_gate, None)
        self.update_tracking_state(self.FINISHED)

    def calculate_track_score(
        self,
        track: List[ContestantReceivedPosition],
        last_visible_gate: "Gate",
        in_range_of_gate: "Gate",
        next_gate: Optional["Gate"],
    ):
        """

        :param track:
        :param last_visible_gate:
        :param in_range_of_gate: The gate we are within the inside_distance of
        :return:
        """
        if not last_visible_gate:
            return
        if last_visible_gate.type == "to":
            self.update_tracking_state(self.TAKEOFF)
        if last_visible_gate.type == "sp" and last_visible_gate != self.last_gate_previous_round:
            self.update_tracking_state(self.STARTED)

        last_position = track[-1]  # type: ContestantReceivedPosition
        finish_index = len(track) - 1
        look_back = 1
        start_index = max(finish_index - look_back, 0)

        # Determine if we just transitioned to a new leg
        just_passed_gate = last_visible_gate != self.last_gate_previous_round

        # Reset backtracking state if we just transitioned
        if just_passed_gate:
            if self.tracking_state in (self.FAILED_PROCEDURE_TURN, self.BACKTRACKING, self.BACKTRACKING_TEMPORARY):
                self.update_tracking_state(self.TRACKING)
            self.backtracking_start_time = None
            self.was_backtracked_on_leg_leading_to_last_gate = self.backtracked_on_current_leg
            self.backtracked_on_current_leg = False
            self.last_gate_previous_round = last_visible_gate

        self.update_current_leg(last_visible_gate)
        first_position = track[start_index]
        bearing = bearing_between(first_position, last_position)
        
        # Use local reference bearing for backtracking check
        # This handles curved legs correctly by finding the closest segment of the route
        reference_bearing = self._get_local_reference_bearing(last_position, last_visible_gate, next_gate)
        bearing_difference = abs(get_heading_difference(bearing, reference_bearing))

        if (
            just_passed_gate
            and last_visible_gate.is_procedure_turn
            and not last_visible_gate.missed
            and last_visible_gate.has_extended_been_passed()
            and self.tracking_state not in (self.FAILED_PROCEDURE_TURN, self.PROCEDURE_TURN)
        ):
            # A.2.2.15
            self.update_tracking_state(self.PROCEDURE_TURN)
            self.current_procedure_turn_slices = []
            self.current_procedure_turn_gate = last_visible_gate
            self.current_procedure_turn_bearing_difference = get_heading_difference(
                last_visible_gate.bearing_from_previous, last_visible_gate.bearing
            )
            if self.current_procedure_turn_bearing_difference > 0:
                self.current_procedure_turn_bearing_difference -= 360
            else:
                self.current_procedure_turn_bearing_difference += 360

            self.current_procedure_turn_start_time = last_position.time
            logger.info("{}: Procedure turn started for gate {}".format(self.contestant, last_visible_gate.name))

        if self.tracking_state == self.PROCEDURE_TURN:
            if self.last_bearing:
                self.current_procedure_turn_slices.append(get_heading_difference(self.last_bearing, bearing))
                total_turn = sum(self.current_procedure_turn_slices)
                if abs(total_turn - self.current_procedure_turn_bearing_difference) < 5:
                    self.update_tracking_state(self.TRACKING)
                    logger.info("{}: Procedure turn completed successfully".format(self.contestant))
                if (
                    abs(total_turn - self.current_procedure_turn_bearing_difference) < 60
                    and self.current_procedure_turn_start_time is not None
                    and (last_position.time - self.current_procedure_turn_start_time).total_seconds() > 180
                ):
                    self.update_tracking_state(self.TRACKING)
                    logger.info("{}: Procedure turn completed successfully".format(self.contestant))

                if (
                    self.current_procedure_turn_start_time is not None
                    and (last_position.time - self.current_procedure_turn_start_time).total_seconds() > 180
                ):
                    if abs(total_turn - self.current_procedure_turn_bearing_difference) >= 60:
                        self.update_tracking_state(self.FAILED_PROCEDURE_TURN)
                        if self.was_backtracked_on_leg_leading_to_last_gate:
                            logger.info(
                                "{}: Suppressing procedure turn penalty for {} because circling was already penalized on previous leg".format(
                                    self.contestant, self.current_procedure_turn_gate
                                )
                            )
                        else:
                            score = self.scorecard.get_procedure_turn_penalty_for_gate_type(
                                self.current_procedure_turn_gate.type
                            )
                            self.update_score(
                                UpdateScoreMessage(
                                    last_position.time,
                                    self.current_procedure_turn_gate,
                                    score,
                                    "incorrect procedure turn",
                                    last_position.latitude,
                                    last_position.longitude,
                                    ANOMALY,
                                    self.PROCEDURE_TURN_SCORE_TYPE,
                                )
                            )
        else:
            backtracking = False
            reference_gate = in_range_of_gate or last_visible_gate

            # Suppress backtracking check entirely if we just passed a PT gate and haven't transitioned state yet
            # (In case recalculate_track_score is called before detect_circling in the same tick)
            is_new_pt_gate = just_passed_gate and last_visible_gate.is_procedure_turn and not last_visible_gate.missed

            if not is_new_pt_gate and bearing_difference > self.backtracking_limit:
                # Check if we are near the gate we just passed
                # To avoid penalties during slow turns or maneuvering near the gate
                if (
                    hasattr(last_position, "projected_x")
                    and last_position.projected_x is not None
                    and reference_gate.center_x is not None
                    and reference_gate.center_y is not None
                ):
                    distance_to_gate_sq = (last_position.projected_x - reference_gate.center_x) ** 2 + (
                        last_position.projected_y - reference_gate.center_y
                    ) ** 2
                else:
                    distance_to_gate_sq = (
                        calculate_distance_lat_lon(
                            (last_position.latitude, last_position.longitude),
                            (reference_gate.latitude, reference_gate.longitude),
                        )
                        ** 2
                    )

                # Use a small grace zone for all gates (0.5 NM)
                grace_zone = 0.5 * 1852
                # grace_zone = reference_gate.gate_radius * 1852

                if distance_to_gate_sq < grace_zone**2:
                    pass  # Ignore backtracking within grace zone of the gate
                else:
                    backtracking = True
                    if in_range_of_gate is not None and in_range_of_gate != last_visible_gate:
                        pass

            if backtracking:
                # TODO: In the precision flying scorecard get_backtracking_before_gate_grace_period_nm_for_gate_type is 0, the default value. Is this correct?
                # Use projected coordinates for grace period checks if available
                p_x = getattr(last_position, "projected_x", None)
                p_y = getattr(last_position, "projected_y", None)

                if self.tracking_state in (self.TRACKING, self.STARTED, self.TAKEOFF):
                    # Check if we are within 0.5 NM of a gate we just passed, A.2.2.13
                    is_grace_time_after_steep_turn = (
                        last_visible_gate.infinite_passing_time is not None
                        and last_visible_gate.is_steep_turn
                        and (last_position.time - last_visible_gate.infinite_passing_time).total_seconds()
                        < self.scorecard.get_backtracking_after_steep_gate_grace_period_seconds_for_gate_type(
                            last_visible_gate.type
                        )
                    )
                    is_grace_distance_before_turn = (
                        next_gate.get_distance_to_gate_line(last_position.latitude, last_position.longitude, p_x, p_y)
                        / 1852
                        < self.scorecard.get_backtracking_before_gate_grace_period_nm_for_gate_type(next_gate.type)
                        if next_gate
                        else False
                    )
                    logger.info(
                        "{} {}: Distance to next gate {} is {} NM, grace period is {} NM".format(
                            self.contestant,
                            last_position.time,
                            next_gate.name if next_gate else "N/A",
                            (
                                next_gate.get_distance_to_gate_line(
                                    last_position.latitude, last_position.longitude, p_x, p_y
                                )
                                / 1852
                                if next_gate
                                else "N/A"
                            ),
                            (
                                self.scorecard.get_backtracking_before_gate_grace_period_nm_for_gate_type(
                                    next_gate.type
                                )
                                if next_gate
                                else "N/A"
                            ),
                        )
                    )
                    is_grace_distance_after_turn = last_visible_gate.get_distance_to_gate_line(
                        last_position.latitude, last_position.longitude, p_x, p_y
                    ) / 1852 < self.scorecard.get_backtracking_after_gate_grace_period_nm_for_gate_type(
                        last_visible_gate.type
                    )
                    if (
                        not is_grace_time_after_steep_turn
                        and not is_grace_distance_after_turn
                        and not is_grace_distance_before_turn
                    ):
                        logger.info(
                            "{} {}: Started backtracking, let's see if this goes on for more than {} seconds".format(
                                self.contestant, last_position.time, self.scorecard.backtracking_grace_time_seconds
                            )
                        )
                        self.backtracking_start_time = last_position.time
                        self.update_tracking_state(self.BACKTRACKING_TEMPORARY)
                    elif is_grace_distance_before_turn:
                        logger.info(
                            "{} {}: Backtracking within {} NM of reaching next gate, ignoring".format(
                                self.contestant,
                                last_position.time,
                                self.scorecard.get_backtracking_before_gate_grace_period_nm_for_gate_type(
                                    next_gate.type
                                ),
                            )
                        )
                    elif is_grace_distance_after_turn:
                        logger.info(
                            "{} {}: Backtracking within {} NM of passing a gate, ignoring".format(
                                self.contestant,
                                last_position.time,
                                self.scorecard.get_backtracking_after_gate_grace_period_nm_for_gate_type(
                                    last_visible_gate.type
                                ),
                            )
                        )
                    elif is_grace_time_after_steep_turn:
                        logger.info(
                            "{} {}: Backtracking within {} seconds of passing a gate with steep turn, ignoring".format(
                                self.contestant,
                                last_position.time,
                                self.scorecard.get_backtracking_after_steep_gate_grace_period_seconds_for_gate_type(
                                    last_visible_gate.type
                                ),
                            )
                        )
                if self.tracking_state == self.BACKTRACKING_TEMPORARY and self.backtracking_start_time is not None:
                    if (
                        last_position.time - self.backtracking_start_time
                    ).total_seconds() >= self.scorecard.backtracking_grace_time_seconds:
                        self.update_tracking_state(self.BACKTRACKING)
                        if not self.backtracked_on_current_leg and self.tracking_state != self.PROCEDURE_TURN:
                            logger.info(
                                f"BACKTRACK_SCORE_TRIGGER: {self.contestant} {last_position.time} - Triggering penalty for {last_visible_gate.name}"
                            )
                            self.backtracked_on_current_leg = True
                            self.update_score(
                                UpdateScoreMessage(
                                    last_position.time,
                                    self.get_last_non_secret_gate(last_visible_gate),
                                    self.scorecard.backtracking_penalty,
                                    "backtracking",
                                    last_position.latitude,
                                    last_position.longitude,
                                    ANOMALY,
                                    self.BACKTRACKING_SCORE_TYPE,
                                    maximum_score=self.scorecard.backtracking_maximum_penalty,
                                )
                            )
                            # Keep state as BACKTRACKING to avoid multiple scores for the same occurrence
                            # It will transition back to TRACKING once bearing is correct
                            logger.info(
                                "{} {}: Done backtracking for {} seconds".format(
                                    self.contestant,
                                    last_position.time,
                                    (last_position.time - self.backtracking_start_time).total_seconds(),
                                )
                            )
                elif self.tracking_state == self.BACKTRACKING_TEMPORARY and self.backtracking_start_time is not None:
                    logger.info(
                        "{} {}: Resumed tracking within time limits ({} seconds), so no penalty".format(
                            self.contestant,
                            last_position.time,
                            (last_position.time - self.backtracking_start_time).total_seconds(),
                        )
                    )
            else:
                if self.tracking_state in (self.BACKTRACKING, self.BACKTRACKING_TEMPORARY):
                    # One last check for duration if we were in temporary state
                    if self.tracking_state == self.BACKTRACKING_TEMPORARY and self.backtracking_start_time is not None:
                        if (
                            last_position.time - self.backtracking_start_time
                        ).total_seconds() >= self.scorecard.backtracking_grace_time_seconds:
                            self.update_tracking_state(self.BACKTRACKING)
                            if not self.backtracked_on_current_leg and self.tracking_state != self.PROCEDURE_TURN:
                                self.backtracked_on_current_leg = True
                                self.update_score(
                                    UpdateScoreMessage(
                                        last_position.time,
                                        self.get_last_non_secret_gate(last_visible_gate),
                                        self.scorecard.backtracking_penalty,
                                        "backtracking",
                                        last_position.latitude,
                                        last_position.longitude,
                                        ANOMALY,
                                        self.BACKTRACKING_SCORE_TYPE,
                                        maximum_score=self.scorecard.backtracking_maximum_penalty,
                                    )
                                )

                    logger.info(
                        "{} {}: Done backtracking".format(
                            self.contestant,
                            last_position.time,
                        )
                    )
                    self.update_tracking_state(self.TRACKING)
        self.last_bearing = bearing
        self.last_gate_previous_round = last_visible_gate

    def on_starting_line_passed(self, event: StartingLinePassedEvent):
        self.update_tracking_state(self.STARTED)
        self.backtracking_start_time = None
        self.last_gate_previous_round = event.gate

    def finalise(self, track: List[ContestantReceivedPosition]):
        self.backtracking_limit = 360
        # Rerun track calculation one final time in order to terminate any ongoing backtracking
        self.calculate_track_score(track, self.last_visible_gate, self.last_visible_gate, None)
        self.update_tracking_state(self.FINISHED)

    def _get_local_reference_bearing(
        self, last_position: ContestantReceivedPosition, last_visible_gate: "Gate", next_gate: Optional["Gate"]
    ) -> float:
        """
        Finds the bearing of the closest segment of the route to the current position.
        This handles curved legs by considering all intermediate curve points.
        """
        relevant_waypoints = self._get_relevant_waypoints(last_visible_gate, next_gate)
        if len(relevant_waypoints) < 2:
            return last_visible_gate.bearing

        closest_leg_info = find_closest_leg_to_point(
            last_position.latitude, last_position.longitude, relevant_waypoints
        )
        if closest_leg_info:
            leg_start_wp, _ = closest_leg_info
            if leg_start_wp.bearing_next >= 0:
                return leg_start_wp.bearing_next

        # If we didn't find a closest leg or it has no bearing, use the closest end of the segment list as fallback
        if len(relevant_waypoints) >= 2:
            first_wp = relevant_waypoints[0]
            last_wp = relevant_waypoints[-1]
            dist_to_first = calculate_distance_lat_lon(
                (last_position.latitude, last_position.longitude), (first_wp.latitude, first_wp.longitude)
            )
            dist_to_last = calculate_distance_lat_lon(
                (last_position.latitude, last_position.longitude), (last_wp.latitude, last_wp.longitude)
            )
            if dist_to_first < dist_to_last:
                return first_wp.bearing_next
            else:
                return relevant_waypoints[-2].bearing_next

        return last_visible_gate.bearing

    def _get_relevant_waypoints(self, last_visible_gate: "Gate", next_gate: Optional["Gate"]) -> List[Waypoint]:
        """
        Returns the list of waypoints in the current leg, including curve points.
        """
        waypoints = []
        started = False
        for wp in self.route.waypoints:
            if wp == last_visible_gate.waypoint:
                started = True
            if started:
                waypoints.append(wp)
            if next_gate and wp == next_gate.waypoint:
                break
        return waypoints
