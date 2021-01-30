import datetime
import logging
from typing import TYPE_CHECKING, List, Callable

from display.calculators.calculator import Calculator
from display.calculators.calculator_utilities import bearing_between
from display.coordinate_utilities import get_heading_difference, calculate_distance_lat_lon
from display.models import Contestant, Scorecard, Route

if TYPE_CHECKING:
    from display.calculators.positions_and_gates import Gate, Position

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
        BACKTRACKING_TEMPORARY: "Off-track"
    }

    def __init__(self, contestant: "Contestant", scorecard: "Scorecard", gates: List["Gate"], route: "Route",
                 update_score: Callable):
        super().__init__(contestant, scorecard, gates, route, update_score)
        self.contestant = contestant
        self.scorecard = scorecard
        self.current_procedure_turn_gate = None
        self.current_procedure_turn_directions = []
        self.current_procedure_turn_slices = []
        self.current_procedure_turn_bearing_difference = 0
        self.current_procedure_turn_start_time = None
        self.backtracking_start_time = None
        self.circling_lookback_seconds = 120
        self.circling_position_list = []
        self.last_bearing = None
        self.last_gate_previous_round = None
        self.current_speed_estimate = 0
        self.previous_gate_distances = None
        self.inside_gates = None
        self.between_tracks = False
        self.calculate_track = False
        self.circling = False
        self.tracking_state = self.BEFORE_START

    def update_tracking_state(self, tracking_state: int):
        if tracking_state == self.tracking_state:
            return
        logger.info("{}: Changing state to {}".format(self.contestant, self.TRACKING_MAP[tracking_state]))
        self.tracking_state = tracking_state
        self.contestant.contestanttrack.updates_current_state(self.TRACKING_MAP[tracking_state])

    def calculate_enroute(self, track: List["Position"], last_gate: "Gate", in_range_of_gate: "Gate"):
        # Need to do the track score first since this might declare the remaining gates as missed if we are done
        # with the track. We can then calculate gate score and consider the missed gates.
        self.calculate_track_score(track, last_gate, in_range_of_gate)
        self.detect_circling(track, last_gate)

    def calculate_outside_route(self, track: List["Position"], last_gate: "Gate"):
        self.circling_position_list = []

    def update_current_leg(self, current_leg):
        if current_leg:
            self.contestant.contestanttrack.update_current_leg(current_leg.name)
        else:
            self.contestant.contestanttrack.update_current_leg("")

    TIME_FORMAT = "%H:%M:%S"

    def detect_circling(self, track: List["Position"], last_gate: "Gate"):
        last_position = track[-1]
        if self.tracking_state in (self.BACKTRACKING, self.PROCEDURE_TURN):
            self.circling_position_list = []
        self.circling_position_list.append(last_position)
        while len(self.circling_position_list) > 0:
            if (self.circling_position_list[-1].time - self.circling_position_list[
                0].time).total_seconds() > self.circling_lookback_seconds:
                self.circling_position_list.pop(0)
            else:
                break
        if len(self.circling_position_list) > 1:
            bearings = []
            for index in range(0, len(self.circling_position_list) - 2):
                bearings.append(
                    bearing_between(self.circling_position_list[index], self.circling_position_list[index + 1]))
            turn_slices = []
            for index in range(0, len(bearings) - 2):
                turn_slices.append(get_heading_difference(bearings[index], bearings[index + 1]))
            total_turn = sum(turn_slices)
            if abs(total_turn) > 180 and not self.circling:
                # We are circling
                self.circling = True
                logger.info("{} {}: Detected circling more than 180° the past {} seconds".format(self.contestant,
                                                                                                 last_position.time,
                                                                                                 (
                                                                                                         self.circling_position_list[
                                                                                                             -1].time -
                                                                                                         self.circling_position_list[
                                                                                                             0].time).total_seconds()))
                self.update_score(last_gate or self.gates[0],
                                  self.scorecard.get_backtracking_penalty(self.contestant),
                                  "circling",
                                  last_position.latitude, last_position.longitude, "anomaly",
                                  self.BACKTRACKING_SCORE_TYPE,
                                  self.scorecard.get_maximum_backtracking_penalty(self.contestant))
            elif abs(total_turn) <= 180:
                # No longer circling
                self.circling = False

    def passed_finishpoint(self):
        self.update_tracking_state(self.FINISHED)

    def calculate_track_score(self, track: List["Position"], last_gate: "Gate", in_range_of_gate: "Gate"):
        if not last_gate:
            return
        if last_gate.type == "to":
            self.update_tracking_state(self.TAKEOFF)
        if last_gate.type == "sp" and last_gate!=self.last_gate_previous_round:
            self.update_tracking_state(self.STARTED)

        last_position = track[-1]  # type: Position
        finish_index = len(track) - 1
        look_back = 1
        start_index = max(finish_index - look_back, 0)
        just_passed_gate = last_gate != self.last_gate_previous_round
        # logger.info("Current leg: {} - {}".format(current_leg, current_leg.bearing))
        self.update_current_leg(last_gate)
        first_position = track[start_index]
        bearing = bearing_between(first_position, last_position)
        bearing_difference = abs(get_heading_difference(bearing, last_gate.bearing))
        # Do not perform track evaluation between multiple subsequent tracks. This means that between iFP and iSP the
        # contestant is free to do whatever he wants.
        # if not self.between_tracks and last_gate.type in ("ifp", "ildg", "ito", "fp"):
        #     self.between_tracks = True
        #     logger.info("Past intermediate finish point, stop track evaluation")
        # if self.between_tracks and last_gate.type == "isp":
        #     self.between_tracks = False
        #     logger.info("Past intermediate starting point, resume track evaluation")
        # if self.between_tracks:
        #     return
        # self.calculate_track = True
        # logger.info(bearing_difference)
        if just_passed_gate and last_gate.is_procedure_turn and last_gate.has_extended_been_passed() and self.tracking_state not in (
                self.FAILED_PROCEDURE_TURN, self.PROCEDURE_TURN):
            # A.2.2.15
            self.update_tracking_state(self.PROCEDURE_TURN)
            self.current_procedure_turn_slices = []
            self.current_procedure_turn_directions = []
            self.current_procedure_turn_gate = last_gate
            self.current_procedure_turn_bearing_difference = get_heading_difference(
                last_gate.bearing_from_previous,
                last_gate.bearing)
            if self.current_procedure_turn_bearing_difference > 0:
                self.current_procedure_turn_bearing_difference -= 360
            else:
                self.current_procedure_turn_bearing_difference += 360

            self.current_procedure_turn_start_time = last_position.time
        if self.tracking_state == self.PROCEDURE_TURN:
            if self.last_bearing:
                self.current_procedure_turn_slices.append(get_heading_difference(self.last_bearing, bearing))
                total_turn = sum(self.current_procedure_turn_slices)
                # logger.info(
                #     "{}: Turned a total of {} degrees as part of procedure turn of {} at gate {} ".format(
                #         self.contestant, total_turn,
                #         self.current_procedure_turn_bearing_difference,
                #         self.current_procedure_turn_gate))
                if abs(total_turn - self.current_procedure_turn_bearing_difference) < 60:
                    self.update_tracking_state(self.TRACKING)
                    logger.info("{}: Procedure turn completed successfully".format(self.contestant))

                if (last_position.time - self.current_procedure_turn_start_time).total_seconds() > 180:
                    if abs(total_turn - self.current_procedure_turn_bearing_difference) >= 60:
                        self.update_tracking_state(self.FAILED_PROCEDURE_TURN)
                        score = self.scorecard.get_procedure_turn_penalty_for_gate_type(
                            self.current_procedure_turn_gate.type, self.contestant)
                        self.update_score(self.current_procedure_turn_gate, score,
                                          "incorrect procedure turn",
                                          last_position.latitude, last_position.longitude, "anomaly",
                                          self.PROCEDURE_TURN_SCORE_TYPE)
        else:
            backtracking = False
            if bearing_difference > self.scorecard.backtracking_bearing_difference:
                backtracking = True
                logger.info("{}: Backtracking according to last gate {}".format(self.contestant, last_gate))
                if in_range_of_gate is not None and in_range_of_gate != last_gate:
                    outgoing_bearing_difference = abs(get_heading_difference(bearing, in_range_of_gate.bearing))
                    if outgoing_bearing_difference <= self.scorecard.backtracking_bearing_difference:
                        # We are not backtracking according to the outgoing gate, so ignore it
                        backtracking = False
                        logger.info("{}: Not backtracking according to gate in range {}".format(self.contestant,
                                                                                                in_range_of_gate))

            if backtracking:
                if self.tracking_state == self.TRACKING:
                    # Check if we are within 0.5 NM of a gate we just passed, A.2.2.13
                    is_grace_time_after_steep_turn = last_gate.infinite_passing_time is not None and last_gate.is_steep_turn and (
                            last_position.time - last_gate.infinite_passing_time).total_seconds() < self.scorecard.get_backtracking_after_steep_gate_grace_period_seconds(
                        last_gate.type, self.contestant)
                    is_grace_distance_after_turn = calculate_distance_lat_lon(
                        (last_gate.latitude, last_gate.longitude),
                        (last_position.latitude,
                         last_position.longitude)) / 1852 < self.scorecard.get_backtracking_after_gate_grace_period_nm(
                        last_gate.type, self.contestant)
                    if not is_grace_time_after_steep_turn and not is_grace_distance_after_turn:
                        logger.info(
                            "{} {}: Started backtracking, let's see if this goes on for more than {} seconds".format(
                                self.contestant, last_position.time,
                                self.scorecard.get_backtracking_grace_time_seconds(self.contestant)))
                        self.backtracking_start_time = last_position.time
                        self.update_tracking_state(self.BACKTRACKING_TEMPORARY)
                    elif is_grace_distance_after_turn:
                        logger.info(
                            "{} {}: Backtracking within {} NM of passing a gate, ignoring".format(self.contestant,
                                                                                                  last_position.time,
                                                                                                  self.scorecard.get_backtracking_after_gate_grace_period_nm(
                                                                                                      last_gate.type,
                                                                                                      self.contestant)))
                    elif is_grace_time_after_steep_turn:
                        logger.info(
                            "{} {}: Backtracking within {} seconds of passing a gate with steep turn, ignoring".format(
                                self.contestant,
                                last_position.time,
                                self.scorecard.get_backtracking_after_steep_gate_grace_period_seconds(
                                    last_gate.type, self.contestant)))
                if self.tracking_state == self.BACKTRACKING_TEMPORARY:
                    if (
                            last_position.time - self.backtracking_start_time).total_seconds() > self.scorecard.get_backtracking_grace_time_seconds(
                        self.contestant):
                        self.update_tracking_state(self.BACKTRACKING)
                        self.update_score(last_gate,
                                          self.scorecard.get_backtracking_penalty(self.contestant),
                                          "backtracking",
                                          last_position.latitude, last_position.longitude, "anomaly",
                                          self.BACKTRACKING_SCORE_TYPE,
                                          maximum_score=self.scorecard.get_maximum_backtracking_penalty(
                                              self.contestant))
            else:
                if self.tracking_state == self.BACKTRACKING:
                    logger.info("{} {}: Done backtracking for {} seconds".format(self.contestant,
                                                                                 last_position.time, (
                                                                                         last_position.time - self.backtracking_start_time).total_seconds()))
                elif self.tracking_state == self.BACKTRACKING_TEMPORARY:
                    logger.info(
                        "{} {}: Resumed tracking within time limits ({} seconds), so no penalty".format(self.contestant,
                                                                                                        last_position.time,
                                                                                                        (
                                                                                                                last_position.time - self.backtracking_start_time).total_seconds()))

                self.update_tracking_state(self.TRACKING)
        self.last_bearing = bearing
        self.last_gate_previous_round = last_gate

