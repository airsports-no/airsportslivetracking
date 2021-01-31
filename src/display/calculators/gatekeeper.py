import datetime
import logging
import threading
from typing import List, TYPE_CHECKING, Optional, Callable

import pytz

from display.calculators.calculator import Calculator
from display.calculators.calculator_utilities import round_time, distance_between_gates
from display.calculators.positions_and_gates import Gate, Position
from display.convert_flightcontest_gpx import calculate_extended_gate
from display.coordinate_utilities import line_intersect, fraction_of_leg, Projector, calculate_distance_lat_lon, \
    calculate_fractional_distance_point_lat_lon
from display.models import ContestantTrack, Contestant
from display.waypoint import Waypoint

if TYPE_CHECKING:
    from influx_facade import InfluxFacade

logger = logging.getLogger(__name__)


class ScoreAccumulator:
    def __init__(self):
        self.related_score = {}

    def set_and_update_score(self, score: float, score_type: str, maximum_score: Optional[float]) -> float:
        """
        Returns the calculated score given the maximum limits. If there is no maximum limit, score is returned
        """
        current_score_for_type = self.related_score.setdefault(score_type, 0)
        if maximum_score is not None and maximum_score > -1:
            if current_score_for_type + score >= maximum_score:
                score = maximum_score - current_score_for_type
        self.related_score[score_type] += score
        return score


LOOP_TIME = 60


class Gatekeeper(threading.Thread):
    GATE_SCORE_TYPE = "gate_score"
    BACKWARD_STARTING_LINE_SCORE_TYPE = "backwards_starting_line"

    def __init__(self, contestant: "Contestant", influx: "InfluxFacade", calculators: List[Callable],
                 live_processing: bool = True):
        super().__init__()
        self.live_processing = live_processing
        self.track_terminated = False
        self.contestant = contestant
        self.influx = influx
        self.track = []  # type: List[Position]
        self.pending_points = []
        self.score = 0
        self.score_by_gate = {}
        self.score_log = []
        self.last_gate_index = 0
        self.enroute = False
        self.process_event = threading.Event()
        _, _ = ContestantTrack.objects.get_or_create(contestant=self.contestant)
        self.scorecard = self.contestant.navigation_task.scorecard
        self.gates = self.create_gates()
        self.position_update_lock = threading.Lock()
        self.last_gate = None  # type: Optional[Gate]
        self.previous_last_gate = None  # type: Optional[Gate]
        self.accumulated_scores = ScoreAccumulator()
        self.starting_line = Gate(self.gates[0].waypoint, self.gates[0].expected_time,
                                  calculate_extended_gate(self.gates[0].waypoint, self.scorecard,
                                                          self.contestant))
        self.projector = Projector(self.starting_line.latitude, self.starting_line.longitude)
        self.takeoff_gate = Gate(self.contestant.navigation_task.route.takeoff_gate,
                                 self.contestant.gate_times[self.contestant.navigation_task.route.takeoff_gate.name],
                                 calculate_extended_gate(self.contestant.navigation_task.route.takeoff_gate,
                                                         self.scorecard,
                                                         self.contestant)) if self.contestant.navigation_task.route.takeoff_gate else None
        self.landing_gate = Gate(self.contestant.navigation_task.route.landing_gate,
                                 self.contestant.gate_times[self.contestant.navigation_task.route.landing_gate.name],
                                 calculate_extended_gate(self.contestant.navigation_task.route.landing_gate,
                                                         self.scorecard,
                                                         self.contestant)) if self.contestant.navigation_task.route.landing_gate else None
        if self.landing_gate is not None:
            # If there is a landing gate we need to include this so that it can be scored and we do not terminate the
            # tracker until this has been passed.
            self.gates.append(self.landing_gate)
        self.outstanding_gates = list(self.gates)
        # Take of gate is handled separately, so should not be part of outstanding gates
        if self.takeoff_gate is not None:
            self.gates.insert(0, self.takeoff_gate)
        self.in_range_of_gate = None
        self.calculators = []
        for calculator in calculators:
            self.calculators.append(
                calculator(self.contestant, self.scorecard, self.gates, self.contestant.navigation_task.route,
                           self.update_score))

    def recalculate_gates_times_from_start_time(self, start_time: datetime.datetime):
        gate_times = self.contestant.calculate_and_get_gate_times(start_time)
        for item in self.outstanding_gates:  # type: Gate
            item.expected_time = gate_times[item.name]
        if self.landing_gate is not None:
            self.landing_gate.expected_time = gate_times[self.landing_gate.name]

    def interpolate_track(self, position: Position) -> List[Position]:
        if len(self.track) == 0:
            return [position]
        initial_time = self.track[-1].time
        distance = calculate_distance_lat_lon((self.track[-1].latitude, self.track[-1].longitude), (position.latitude, position.longitude))
        if distance<0.001:
            return [position]
        time_difference = int((position.time - initial_time).total_seconds())
        positions = []
        if time_difference > 2:
            fraction = 1/time_difference
            for step in range(1, time_difference):
                new_position = calculate_fractional_distance_point_lat_lon(
                    (self.track[-1].latitude, self.track[-1].longitude), (position.latitude, position.longitude),
                    step * fraction)
                positions.append(Position((initial_time + datetime.timedelta(seconds=step)).isoformat(), new_position[0], new_position[1],
                                          position.altitude, position.speed, position.course, position.battery_level))
        positions.append(position)
        return positions

    def run(self):
        logger.info("Started calculator for contestant {}".format(self.contestant))
        while not self.track_terminated:
            self.process_event.wait(LOOP_TIME)
            self.process_event.clear()
            while len(self.pending_points) > 0:
                with self.position_update_lock:
                    data = self.pending_points.pop(0)
                    if data is None:
                        # Signal the track processor that this is the end, and perform the track calculation
                        self.track_terminated = True
                        continue
                for position in self.interpolate_track(data):
                    self.track.append(position)
                    if len(self.track) > 1:
                        self.calculate_score()
        logger.info("Terminating calculator for {}".format(self.contestant))

    def update_score(self, gate: "Gate", score: float, message: str, latitude: float, longitude: float,
                     annotation_type: str, score_type: str, maximum_score: Optional[float] = None,
                     planned: Optional[datetime.datetime] = None,
                     actual: Optional[datetime.datetime] = None):
        """

        :param gate: The last gate which indicates the current leg
        :param score: The penalty awarded
        :param message: A brief description of why the penalty is awarded
        :param latitude: The position of the contestant
        :param longitude: The position of the contestant
        :param annotation_type: information or anomaly
        :param score_type: Keyword that is linked to maximum score. Schools are accumulated for each keyword and compared to maximum if supplied
        :param maximum_score: Maximum score for the score type
        :param planned: The planned passing time if gate
        :param actual: The actual passing time if gate
        :return:
        """
        score = self.accumulated_scores.set_and_update_score(score, score_type, maximum_score)
        if planned is not None and actual is not None:
            offset = (actual - planned).total_seconds()
            offset_string = "{} s".format("+{}".format(int(offset)) if offset > 0 else int(offset))
        else:
            offset_string = None
        internal_message = {
            "gate": gate.name,
            "message": message,
            "points": score,
            "planned": planned.astimezone(self.contestant.navigation_task.contest.time_zone).strftime(
                "%H:%M:%S %z") if planned else None,
            "actual": actual.astimezone(self.contestant.navigation_task.contest.time_zone).strftime(
                "%H:%M:%S %z") if actual else None,
            "offset_string": offset_string
        }
        string = "{}: {} points {}".format(gate.name, score, message)
        if offset_string:
            string += " ({})".format(offset_string)
        if planned and actual:
            string += "\n(planned: {}, actual: {})".format(internal_message["planned"], internal_message["actual"])
        elif planned:
            string += "\n(planned: {}, actual: --)".format(internal_message["planned"])
        internal_message["string"] = string
        logger.info("UPDATE_SCORE {}: {}".format(self.contestant, string))
        self.score += score
        try:
            self.score_by_gate[gate.name] += score
        except KeyError:
            self.score_by_gate[gate.name] = self.score
        self.influx.add_annotation(self.contestant, latitude, longitude, string, annotation_type,
                                   self.track[-1].time)  # TODO: Annotations with the same time
        self.score_log.append(internal_message)
        self.contestant.contestanttrack.update_score(self.score_by_gate, self.score, self.score_log)

    def create_gates(self) -> List[Gate]:
        waypoints = self.contestant.navigation_task.route.waypoints
        expected_times = self.contestant.gate_times
        gates = []
        for item in waypoints:  # type: Waypoint
            gates.append(Gate(item, expected_times[item.name],
                              calculate_extended_gate(item, self.scorecard, self.contestant)))
        return gates

    def add_positions(self, positions):
        with self.position_update_lock:
            self.pending_points.extend(
                [Position(**position) if position is not None else None for position in positions])
        self.process_event.set()

    def pop_gate(self, index, update_last: bool = True):
        gate = self.outstanding_gates.pop(index)
        if update_last:
            self.previous_last_gate = self.last_gate
            self.last_gate = gate
        self.update_enroute()

    def any_gate_passed(self):
        return any([gate.has_been_passed() for gate in self.gates])

    def all_gates_passed(self):
        return all([gate.has_been_passed() for gate in self.gates])

    def update_enroute(self):
        logger.info(f"last_gate: {self.last_gate} {self.last_gate.type}")
        if self.last_gate is not None and self.last_gate.type in ["ldg", "ifp", "fp"]:
            self.enroute = False
            logger.info("Switching to not enroute")
            return
        if self.last_gate is not None and self.last_gate.type in ["sp", "isp", "tp", "secret"]:
            self.enroute = True
            logger.info("Switching to enroute")

    def check_gate_in_range(self):
        if len(self.outstanding_gates) == 0 or len(self.track) == 0:
            return
        last_position = self.track[-1]
        if self.in_range_of_gate is not None:
            distance_to_gate = calculate_distance_lat_lon((last_position.latitude, last_position.longitude),
                                                          (self.in_range_of_gate.latitude,
                                                           self.in_range_of_gate.longitude))
            if distance_to_gate > self.in_range_of_gate.outside_distance:
                logger.info("{}: Moved out of range of gate {} at {}".format(self.contestant, self.in_range_of_gate,
                                                                             last_position.time))
                if self.in_range_of_gate.passing_time is None and not self.in_range_of_gate.missed:
                    # Moving out of range of the gate, let's assume we have missed it
                    logger.info("{}: Missing gate {} since it has not been passed or detected missed before.".format(
                        self.contestant, self.in_range_of_gate))
                    self.in_range_of_gate.missed = True
                    self.pop_gate(0, True)
                self.in_range_of_gate = None

        else:
            next_gate = self.outstanding_gates[0]
            if next_gate.type != "tp":
                return
            distance_to_gate = calculate_distance_lat_lon((last_position.latitude, last_position.longitude),
                                                          (next_gate.latitude, next_gate.longitude))
            # logger.info("Distance to gate is {} with inside_distance = {}".format(distance_to_gate, next_gate.inside_distance))
            if distance_to_gate < next_gate.inside_distance:
                # Moving into range of the gate, record that for use of the places
                self.in_range_of_gate = next_gate
                logger.info(
                    "{}: Moved into range of gate {} at {}".format(self.contestant, next_gate, last_position.time))

    def miss_outstanding_gates(self):
        for item in self.outstanding_gates:
            item.missed = True
        self.outstanding_gates = []

    def check_intersections(self):
        # Check takeoff if exists
        if self.takeoff_gate is not None and not self.takeoff_gate.has_been_passed():
            intersection_time = self.takeoff_gate.get_gate_intersection_time(self.projector, self.track)
            if intersection_time:
                self.takeoff_gate.passing_time = intersection_time
                self.takeoff_gate.extended_passing_time = intersection_time
                self.takeoff_gate.infinite_passing_time = intersection_time
                self.contestant.contestanttrack.update_gate_time(self.takeoff_gate.name, intersection_time)
                logger.info("{} {}: Passing takeoff line".format(self.contestant, intersection_time))
        if not self.starting_line.has_infinite_been_passed():
            # First check extended and see if we are in the correct direction
            # Implements https://www.fai.org/sites/default/files/documents/gac_2020_precision_flying_rules_final.pdf
            # A 2.2.14
            intersection_time = self.starting_line.get_gate_extended_intersection_time(self.projector, self.track)
            if intersection_time:
                if not self.starting_line.is_passed_in_correct_direction_track_to_next(self.track):
                    # Add penalty for crossing in the wrong direction
                    score = self.scorecard.get_bad_crossing_extended_gate_penalty_for_gate_type("sp",
                                                                                                self.contestant)
                    if score > 0:
                        self.update_score(self.starting_line, score,
                                          "crossing extended starting gate backwards",
                                          self.track[-1].latitude, self.track[-1].longitude, "anomaly",
                                          self.BACKWARD_STARTING_LINE_SCORE_TYPE)
            # First check extended and see if we are in the correct direction
            # Implements https://www.fai.org/sites/default/files/documents/gac_2020_precision_flying_rules_final.pdf
            # A 2.2.14
            intersection_time = self.starting_line.get_gate_infinite_intersection_time(self.projector, self.track)
            if intersection_time:
                if self.starting_line.is_passed_in_correct_direction_track_to_next(self.track):
                    # Start the clock
                    if self.takeoff_gate is not None and not self.takeoff_gate.has_been_passed():
                        self.takeoff_gate.missed = True
                    logger.info("{}: Passing start line {}".format(self.contestant, intersection_time))
                    self.starting_line.infinite_passing_time = intersection_time
                    # Recalculate gate times if adaptive
                    if self.contestant.adaptive_start:
                        self.recalculate_gates_times_from_start_time(round_time(intersection_time))
            else:
                return
        i = len(self.outstanding_gates) - 1
        crossed_gate = False

        while i >= 0:
            gate = self.outstanding_gates[i]
            intersection_time = gate.get_gate_intersection_time(self.projector, self.track)
            if intersection_time:
                logger.info("{} {}: Crossed gate {}".format(self.contestant, intersection_time, gate))
                self.contestant.contestanttrack.update_gate_time(gate.name, intersection_time)
                gate.passing_time = intersection_time
                gate.extended_passing_time = intersection_time
                gate.infinite_passing_time = intersection_time
                crossed_gate = True

            if crossed_gate:
                if gate.passing_time is None:
                    logger.info("{} {}: Missed gate {}".format(self.contestant, self.track[-1].time, gate))
                    gate.missed = True
                self.pop_gate(i,
                              not gate.missed)  # Only update the last gate with the one that was crossed, not the one we detect is missed because of it.
            i -= 1
        if not crossed_gate and len(self.outstanding_gates) > 0:
            extended_next_gate = self.outstanding_gates[0]  # type: Gate
            if extended_next_gate.type not in ("sp", "ildg",
                                               "ito", "ldg",
                                               "to") and not extended_next_gate.extended_passing_time and extended_next_gate.is_procedure_turn:
                intersection_time = extended_next_gate.get_gate_extended_intersection_time(self.projector, self.track)
                if intersection_time:
                    extended_next_gate.extended_passing_time = intersection_time
                    extended_next_gate.infinite_passing_time = intersection_time
                    logger.info("{} {}: Crossed extended gate {} (but maybe missed the gate)".format(self.contestant,
                                                                                                     intersection_time,
                                                                                                     extended_next_gate))

            if extended_next_gate.type not in (
                    "sp", "ildg", "ito", "ldg", "to") and not extended_next_gate.maybe_missed_time:
                intersection_time = extended_next_gate.get_gate_infinite_intersection_time(self.projector, self.track)
                if intersection_time and extended_next_gate.is_passed_in_correct_direction_track_from_previous(
                        self.track):
                    logger.info("{} {}: Crossed infinite gate {} (but maybe missed the gate)".format(self.contestant,
                                                                                                     intersection_time,
                                                                                                     extended_next_gate))
                    extended_next_gate.maybe_missed_time = self.track[-1].time
        if len(self.outstanding_gates) > 0:
            gate = self.outstanding_gates[0]
            time_limit = 2
            if gate.maybe_missed_time and (self.track[-1].time - gate.maybe_missed_time).total_seconds() > time_limit:
                logger.info("{} {}: Did not cross {} within {} seconds of infinite crossing, so missing gate".format(
                    self.contestant, self.track[-1].time,
                    gate, time_limit))
                gate.missed = True
                self.pop_gate(0)
        self.check_gate_in_range()
        if self.last_gate and self.last_gate.type == "fp":
            self.passed_finishpoint()

    def passed_finishpoint(self):
        for calculator in self.calculators:
            calculator.passed_finishpoint()

    def check_termination(self):
        already_terminated = self.track_terminated
        if len(self.outstanding_gates) == 0:
            if not already_terminated:
                logger.info("No more gates, terminating")
            self.track_terminated = True
        speed = self.get_speed()
        # Do not care about speed during low processing, we only care about the tracking interval from takeoff time
        # to finish by time
        if not self.live_processing and speed == 0 and self.last_gate is not None:
            if not already_terminated:
                logger.info("Speed is zero and not live processing, terminating")
            self.track_terminated = True
        now = datetime.datetime.now(datetime.timezone.utc)
        if self.live_processing and now > self.contestant.finished_by_time:
            if not already_terminated:
                logger.info("Live processing and past finish time, terminating")
            self.track_terminated = True
        if not already_terminated and self.track_terminated:
            self.miss_outstanding_gates()

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
                    score = self.scorecard.get_gate_timing_score_for_gate_type(gate.type, self.contestant,
                                                                               gate.expected_time, None)
                    self.update_score(gate, score, "missing gate", current_position.latitude,
                                      current_position.longitude, "anomaly", "gate_score",
                                      planned=gate.expected_time)
                    # Commented out because of A.2.2.16
                    # if gate.is_procedure_turn and not gate.extended_passing_time:
                    # Penalty if not crossing extended procedure turn turning point, then the procedure turn was per definition not performed
                    # score = self.scorecard.get_procedure_turn_penalty_for_gate_type(gate.type,
                    #                                                                 self.contestant)
                    # self.update_score(gate, score,
                    #                   "missing procedure turn",
                    #                   current_position.latitude, current_position.longitude, "anomaly")
            elif gate.passing_time is not None:
                index += 1
                if gate.time_check:
                    time_difference = (gate.passing_time - gate.expected_time).total_seconds()
                    # logger.info("Time difference at gate {}: {}".format(gate.name, time_difference))
                    self.contestant.contestanttrack.update_last_gate(gate.name, time_difference)
                    gate_score = self.scorecard.get_gate_timing_score_for_gate_type(gate.type, self.contestant,
                                                                                    gate.expected_time,
                                                                                    gate.passing_time)
                    self.update_score(gate, gate_score,
                                      "passing gate",
                                      current_position.latitude, current_position.longitude, "information",
                                      self.GATE_SCORE_TYPE,
                                      planned=gate.expected_time, actual=gate.passing_time)
                else:
                    self.update_score(gate, 0,
                                      "passing gate (no time check)",
                                      current_position.latitude, current_position.longitude, "information",
                                      self.GATE_SCORE_TYPE,
                                      planned=gate.expected_time, actual=gate.passing_time)

            else:
                finished = True
        self.last_gate_index += index

    def calculate_score(self):
        if self.track_terminated:
            return
        self.check_intersections()
        self.calculate_gate_score()
        self.check_gate_in_range()
        for calculator in self.calculators:
            if self.enroute:
                calculator.calculate_enroute(self.track, self.last_gate, self.in_range_of_gate)
            else:
                calculator.calculate_outside_route(self.track, self.last_gate)
        self.check_termination()

    def get_speed(self):
        previous_index = min(5, len(self.track))
        distance = distance_between_gates(self.track[-previous_index], self.track[-1]) / 1852
        time_difference = (self.track[-1].time - self.track[-previous_index].time).total_seconds() / 3600
        if time_difference == 0:
            time_difference = 0.01
        return distance / time_difference
