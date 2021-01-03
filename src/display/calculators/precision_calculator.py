import datetime
import logging
from typing import TYPE_CHECKING

from display.calculators.calculator import Calculator
from display.calculators.calculator_utilities import distance_between_gates, bearing_between
from display.coordinate_utilities import get_heading_difference, calculate_distance_lat_lon
from display.models import Contestant

if TYPE_CHECKING:
    from influx_facade import InfluxFacade
    from display.calculators.positions_and_gates import Gate, Position

logger = logging.getLogger(__name__)


class PrecisionCalculator(Calculator):
    """
    Implements https://www.fai.org/sites/default/files/documents/gac_2020_precision_flying_rules_final.pdf
    """
    DEVIATING = 8
    BACKTRACKING = 5
    PROCEDURE_TURN = 6
    FAILED_PROCEDURE_TURN = 7
    BACKTRACKING_TEMPORARY = 9
    TRACKING_MAP = dict(Calculator.TRACKING_MAP)
    TRACKING_MAP.update({
        BACKTRACKING: "Backtracking",
        PROCEDURE_TURN: "Procedure turn",
        FAILED_PROCEDURE_TURN: "Failed procedure turn",
        DEVIATING: "Deviating",
        BACKTRACKING_TEMPORARY: "Off-track"
    })

    def __init__(self, contestant: "Contestant", influx: "InfluxFacade", live_processing: bool = True):
        super().__init__(contestant, influx, live_processing=live_processing)
        self.current_procedure_turn_gate = None
        self.current_procedure_turn_directions = []
        self.current_procedure_turn_slices = []
        self.current_procedure_turn_bearing_difference = 0
        self.current_procedure_turn_start_time = None
        self.backtracking_start_time = None

        self.last_gate_index = 0
        self.last_bearing = None
        self.last_gate_previous_round = None
        self.current_speed_estimate = 0
        self.previous_gate_distances = None
        self.inside_gates = None
        self.between_tracks = False

    def check_intersections(self):
        # Check starting line
        if not self.starting_line.has_infinite_been_passed():
            # First check extended and see if we are in the correct direction
            # Implements https://www.fai.org/sites/default/files/documents/gac_2020_precision_flying_rules_final.pdf
            # A 2.2.14
            intersection_time = self.starting_line.get_gate_extended_intersection_time(self.projector, self.track)
            if intersection_time:
                if not self.starting_line.is_passed_in_correct_direction_track_to_next(self.track):
                    # Add penalty for crossing in the wrong direction
                    score = self.scorecard.get_bad_crossing_extended_gate_penalty_for_gate_type("sp",
                                                                                                self.basic_score_override)
                    self.update_score(self.starting_line, score,
                                      "crossing extended starting gate backwards",
                                      self.track[-1].latitude, self.track[-1].longitude, "anomaly")
        super(PrecisionCalculator, self).check_intersections()

    def calculate_score(self):
        self.check_intersections()
        # Need to do the track score first since this might declare the remaining gates as missed if we are done
        # with the track. We can then calculate gate score and consider the missed gates.
        self.calculate_track_score()
        self.calculate_gate_score()

    def update_current_leg(self, current_leg):
        if current_leg:
            self.contestant.contestanttrack.update_current_leg(current_leg.name)
        else:
            self.contestant.contestanttrack.update_current_leg("")

    TIME_FORMAT = "%H:%M:%S"

    def calculate_gate_score(self):
        index = 0
        finished = False
        current_position = self.track[-1]
        for gate in self.gates[self.last_gate_index:]:  # type: Gate
            if finished:
                break
            if gate.missed:
                index += 1
                if gate.gate_check:
                    score = self.scorecard.get_gate_timing_score_for_gate_type(gate.type, gate.expected_time, None,
                                                                               self.basic_score_override)
                    self.update_score(gate, score, "missing gate", current_position.latitude,
                                      current_position.longitude, "anomaly", planned=gate.expected_time)
                    # Commented out because of A.2.2.16
                    # if gate.is_procedure_turn and not gate.extended_passing_time:
                    # Penalty if not crossing extended procedure turn turning point, then the procedure turn was per definition not performed
                    # score = self.scorecard.get_procedure_turn_penalty_for_gate_type(gate.type,
                    #                                                                 self.basic_score_override)
                    # self.update_score(gate, score,
                    #                   "missing procedure turn",
                    #                   current_position.latitude, current_position.longitude, "anomaly")
            elif gate.passing_time is not None:
                index += 1
                if gate.time_check:
                    time_difference = (gate.passing_time - gate.expected_time).total_seconds()
                    # logger.info("Time difference at gate {}: {}".format(gate.name, time_difference))
                    self.contestant.contestanttrack.update_last_gate(gate.name, time_difference)
                    gate_score = self.scorecard.get_gate_timing_score_for_gate_type(gate.type, gate.expected_time,
                                                                                    gate.passing_time,
                                                                                    self.basic_score_override)
                    self.update_score(gate, gate_score,
                                      "passing gate",
                                      current_position.latitude, current_position.longitude, "information",
                                      planned=gate.expected_time, actual=gate.passing_time)
                else:
                    self.update_score(gate, 0,
                                      "passing gate (no time check)",
                                      current_position.latitude, current_position.longitude, "information",
                                      planned=gate.expected_time, actual=gate.passing_time)

            else:
                finished = True
        self.last_gate_index += index

    def any_gate_passed(self):
        return any([gate.has_been_passed() for gate in self.gates])

    def all_gates_passed(self):
        return all([gate.has_been_passed() for gate in self.gates])

    def miss_outstanding_gates(self):
        for item in self.outstanding_gates:
            item.missed = True
        self.outstanding_gates = []

    def calculate_track_score(self):
        if self.tracking_state == self.FINISHED:
            return
        if self.track_terminated:
            self.miss_outstanding_gates()
            logger.info("{}: This is the end of the track, terminating".format(self.contestant))
            self.update_tracking_state(self.FINISHED)
            return
        now = datetime.datetime.now(datetime.timezone.utc)
        if self.live_processing and now > self.contestant.finished_by_time:
            self.miss_outstanding_gates()
            logger.info("{}: Current time {} is beyond contestant finish time {}, terminating".format(
                now, self.contestant.finished_by_time, self.contestant))
            self.update_tracking_state(self.FINISHED)
            return
        last_position = self.track[-1]  # type: Position
        finish_index = len(self.track) - 1
        speed = self.get_speed()
        if (speed == 0 or last_position.time > self.contestant.finished_by_time) and not self.all_gates_passed():
            self.miss_outstanding_gates()
            logger.info("{}: Speed is 0, terminating".format(self.contestant))
            self.update_tracking_state(self.FINISHED)
            return
        if not self.any_gate_passed():
            return
        look_back = 1
        start_index = max(finish_index - look_back, 0)
        just_passed_gate = self.last_gate != self.last_gate_previous_round
        # logger.info("Current leg: {} - {}".format(current_leg, current_leg.bearing))
        self.update_current_leg(self.last_gate)
        first_position = self.track[start_index]
        if len(self.outstanding_gates) == 0:
            logger.info("{}: No more turning points, terminating".format(self.contestant))
            self.update_tracking_state(self.FINISHED)
            self.contestant.contestanttrack.set_calculator_finished()
            return
        bearing = bearing_between(first_position, last_position)
        bearing_difference = abs(get_heading_difference(bearing, self.last_gate.bearing))
        # Do not perform track evaluation between multiple subsequent tracks. This means that between iFP and iSP the
        # contestant is free to do whatever he wants.
        if not self.between_tracks and self.last_gate.type in ("ifp", "ildg", "ito", "fp"):
            self.between_tracks = True
            logger.info("Past intermediate finish point, stop track evaluation")
        if self.between_tracks and self.last_gate.type == "isp":
            self.between_tracks = False
            logger.info("Past intermediate starting point, resume track evaluation")
        if self.between_tracks:
            return
        # logger.info(bearing_difference)
        if just_passed_gate and self.last_gate.is_procedure_turn and self.tracking_state not in (
                self.FAILED_PROCEDURE_TURN, self.PROCEDURE_TURN):
            # A.2.2.15
            self.update_tracking_state(self.PROCEDURE_TURN)
            self.current_procedure_turn_slices = []
            self.current_procedure_turn_directions = []
            self.current_procedure_turn_gate = self.last_gate
            self.current_procedure_turn_bearing_difference = get_heading_difference(
                self.last_gate.bearing_from_previous,
                self.last_gate.bearing)
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
                            self.current_procedure_turn_gate.type, self.basic_score_override)
                        self.update_score(self.current_procedure_turn_gate, score,
                                          "incorrect procedure turn",
                                          last_position.latitude, last_position.longitude, "anomaly")
        else:
            if bearing_difference > self.scorecard.backtracking_bearing_difference:
                if self.tracking_state == self.TRACKING:
                    # Check if we are within 0.5 NM of a gate we just passed, A.2.2.13
                    is_grace_time_after_steep_turn = self.last_gate.infinite_passing_time is not None and self.last_gate.is_steep_turn and (
                            last_position.time - self.last_gate.infinite_passing_time).total_seconds() < self.scorecard.get_backtracking_after_steep_gate_grace_period_seconds(
                        self.last_gate.type, self.basic_score_override)
                    is_grace_distance_after_turn = calculate_distance_lat_lon(
                        (self.last_gate.latitude, self.last_gate.longitude),
                        (last_position.latitude,
                         last_position.longitude)) / 1852 < self.scorecard.get_backtracking_after_gate_grace_period_nm(
                        self.last_gate.type, self.basic_score_override)
                    if not is_grace_time_after_steep_turn and not is_grace_distance_after_turn:
                        logger.info(
                            "{} {}: Started backtracking, let's see if this goes on for more than {} seconds".format(
                                self.contestant, last_position.time,
                                self.scorecard.get_backtracking_grace_time_seconds(self.basic_score_override)))
                        self.backtracking_start_time = last_position.time
                        self.update_tracking_state(self.BACKTRACKING_TEMPORARY)
                    elif is_grace_distance_after_turn:
                        logger.info(
                            "{} {}: Backtracking within {} NM of passing a gate, ignoring".format(self.contestant,
                                                                                                  last_position.time,
                                                                                                  self.scorecard.get_backtracking_after_gate_grace_period_nm(
                                                                                                      self.last_gate.type,
                                                                                                      self.basic_score_override)))
                    elif is_grace_time_after_steep_turn:
                        logger.info(
                            "{} {}: Backtracking within {} seconds of passing a gate with steep turn, ignoring".format(
                                self.contestant,
                                last_position.time,
                                self.scorecard.get_backtracking_after_steep_gate_grace_period_seconds(
                                    self.last_gate.type)))
                if self.tracking_state == self.BACKTRACKING_TEMPORARY:
                    if (
                            last_position.time - self.backtracking_start_time).total_seconds() > self.scorecard.get_backtracking_grace_time_seconds(
                        self.basic_score_override):
                        self.update_tracking_state(self.BACKTRACKING)
                        self.update_score(self.last_gate,
                                          self.scorecard.get_backtracking_penalty(self.basic_score_override),
                                          "backtracking",
                                          last_position.latitude, last_position.longitude, "anomaly")
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
        self.last_gate_previous_round = self.last_gate

    def get_speed(self):
        previous_index = min(5, len(self.track))
        distance = distance_between_gates(self.track[-previous_index], self.track[-1]) / 1852
        time_difference = (self.track[-1].time - self.track[-previous_index].time).total_seconds() / 3600
        if time_difference == 0:
            time_difference = 0.01
        return distance / time_difference
