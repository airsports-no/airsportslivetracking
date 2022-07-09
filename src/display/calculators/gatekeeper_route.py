import datetime
import logging
from multiprocessing.queues import Queue
from typing import List, TYPE_CHECKING, Optional, Callable, Tuple

import pytz

from display.calculators.calculator import Calculator
from display.calculators.calculator_utilities import round_time, distance_between_gates
from display.calculators.gatekeeper import Gatekeeper
from display.calculators.positions_and_gates import Gate, Position, MultiGate
from display.convert_flightcontest_gpx import calculate_extended_gate
from display.coordinate_utilities import line_intersect, fraction_of_leg, Projector, calculate_distance_lat_lon, \
    calculate_fractional_distance_point_lat_lon, cross_track_distance, nv_intersect
from display.models import ContestantTrack, Contestant
from display.waypoint import Waypoint

logger = logging.getLogger(__name__)

LOOP_TIME = 60


class GatekeeperRoute(Gatekeeper):
    GATE_SCORE_TYPE = "gate_score"
    BACKWARD_STARTING_LINE_SCORE_TYPE = "backwards_starting_line"

    def __init__(self, contestant: "Contestant", calculators: List[Callable],
                 live_processing: bool = True, queue_name_override: str = None):
        super().__init__(contestant, calculators, live_processing, queue_name_override=queue_name_override)
        self.last_backwards = None
        self.recalculation_completed = not self.contestant.adaptive_start
        self.starting_line = Gate(self.gates[0].waypoint, self.gates[0].expected_time,
                                  calculate_extended_gate(self.gates[0].waypoint, self.scorecard))
        self.projector = Projector(self.starting_line.latitude, self.starting_line.longitude)
        self.takeoff_gate = MultiGate([Gate(takeoff_gate,
                                            self.contestant.gate_times[takeoff_gate.name],
                                            calculate_extended_gate(takeoff_gate, self.scorecard)) for takeoff_gate in
                                       self.contestant.navigation_task.route.takeoff_gates]) if len(
            self.contestant.navigation_task.route.takeoff_gates) > 0 else None
        self.landing_gate = MultiGate([Gate(landing_gate,
                                            self.contestant.gate_times[landing_gate.name],
                                            calculate_extended_gate(landing_gate, self.scorecard)) for landing_gate in
                                       self.contestant.navigation_task.route.landing_gates]) if len(
            self.contestant.navigation_task.route.landing_gates) > 0 else None

        self.outstanding_gates = list(self.gates)
        if self.contestant.adaptive_start:
            self.takeoff_gate = None
        self.in_range_of_gate = None

    def recalculate_gates_times_from_start_time(self, start_time: datetime.datetime):
        gate_times = self.contestant.calculate_missing_gate_times({}, start_time)
        self.contestant.gate_times = gate_times
        logger.info(f"Recalculating gates times for contestant {self.contestant}: {self.contestant.gate_times}")
        for item in self.outstanding_gates:  # type: Gate
            item.expected_time = gate_times[item.name]
        if self.landing_gate is not None:
            self.landing_gate.set_expected_time(gate_times[self.landing_gate.name])
        self.recalculation_completed = True
        self.contestant.save()

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
                    # self.missed_gate(self.in_range_of_gate,self.track[-1])

                    self.pop_gate(0, True)
                self.in_range_of_gate = None

        else:
            next_gate = self.outstanding_gates[0]
            if next_gate.type not in ("secret", "sp", "fp", "tp"):
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
            logger.info(f"{self.contestant}: Missing outstanding gate {item}")
            item.missed = True
            item.maybe_missed_time = None
            item.maybe_missed_position = None
        self.outstanding_gates = []
        if self.landing_gate:
            if not self.landing_gate.has_been_passed():
                self.landing_gate.missed = True

    def check_intersections(self):
        """
        If adaptive start, the clock is started whenever the infinite starting line is crossed in the correct direction.
        Implements penalty when crossing extended starting line in the wrong direction.
        If the starting line is missed entirely, we will not look for missing gates until we actually cross a gate.
        That means that there will be no penalty is awarded until the contestant actually crosses a gate, at which
        point it will receive misses for all previous gates.
        """
        # Check takeoff if exists
        if self.takeoff_gate is not None and not self.takeoff_gate.has_been_passed():
            intersection_time = self.takeoff_gate.get_gate_intersection_time(self.projector, self.track)
            # Miss is handled by starting line check
            if intersection_time:
                gate = self.takeoff_gate.gates[0]  # We choose an arbitrary gate since they will have the same times
                current_position = self.track[-1]
                self.contestant.record_actual_gate_time(self.takeoff_gate.name, intersection_time)
                logger.info("{} {}: Passing takeoff line".format(self.contestant, intersection_time))
                gate_score = self.scorecard.get_gate_timing_score_for_gate_type(gate.type,
                                                                                gate.expected_time,
                                                                                gate.passing_time)
                self.transmit_actual_crossing(gate)
                self.update_score(gate, gate_score,
                                  "passing takeoff gate",
                                  current_position.latitude, current_position.longitude, "anomaly",
                                  self.GATE_SCORE_TYPE,
                                  planned=gate.expected_time, actual=gate.passing_time)

        if not self.starting_line.has_infinite_been_passed():
            # First check extended and see if we are in the correct direction
            # Implements https://www.fai.org/sites/default/files/documents/gac_2020_precision_flying_rules_final.pdf
            # A 2.2.14
            intersection_time = self.starting_line.get_gate_extended_intersection_time(self.projector, self.track)
            if intersection_time and not self.starting_line.is_passed_in_correct_direction_track(self.track):
                    # Add penalty for crossing in the wrong direction
                    score = self.scorecard.get_bad_crossing_extended_gate_penalty_for_gate_type("sp")
                    # Add a grace time to prevent multiple backwards penalties for a single crossing
                    if self.last_backwards is None or intersection_time > self.last_backwards + datetime.timedelta(
                            seconds=15):
                        self.last_backwards = intersection_time
                        if score > 0:
                            self.update_score(self.starting_line, score,
                                              "crossing extended starting gate backwards",
                                              self.track[-1].latitude, self.track[-1].longitude, "anomaly",
                                              self.BACKWARD_STARTING_LINE_SCORE_TYPE)
            else:
                # Handle resetting adaptive start, and record that the infinite line has been crossed
                intersection_time = self.starting_line.get_gate_infinite_intersection_time(self.projector, self.track)
                if intersection_time and self.starting_line.is_passed_in_correct_direction_track(self.track):
                    self.starting_line.pass_infinite_gate(intersection_time)
                    if self.contestant.adaptive_start:
                        self.recalculate_gates_times_from_start_time(round_time(intersection_time))

        i = len(self.outstanding_gates) - 1
        crossed_gate = False
        while i >= 0:
            gate = self.outstanding_gates[i]
            intersection_time = gate.get_gate_intersection_time(self.projector, self.track)
            if intersection_time:
                logger.info("{} {}: Crossed gate {}".format(self.contestant, intersection_time, gate))
                if not self.starting_line.has_infinite_been_passed():
                    self.starting_line.missed = True
                self.contestant.record_actual_gate_time(gate.name, intersection_time)
                gate.pass_gate(intersection_time)
                crossed_gate = True

            if crossed_gate:
                if gate.passing_time is None:
                    gate.missed = True
                    logger.info("{} {}: Missed gate {}".format(self.contestant, self.track[-1].time, gate))
                # Only update the last gate with the one that was crossed, not the one we detect is missed because of it.
                self.pop_gate(i,not gate.missed)
            i -= 1
        # Do not look for misses further out if we have not crossed the starting line at some point.
        if not crossed_gate and len(self.outstanding_gates) > 0 and self.starting_line.has_infinite_been_passed():
            extended_next_gate = self.outstanding_gates[0]  # type: Gate
            if extended_next_gate.type not in ("sp", "ildg",
                                               "ito", "ldg",
                                               "to") and not extended_next_gate.extended_passing_time and extended_next_gate.is_procedure_turn:
                intersection_time = extended_next_gate.get_gate_extended_intersection_time(self.projector, self.track)
                if intersection_time:
                    extended_next_gate.pass_extended_gate(intersection_time)
                    logger.info("{} {}: Crossed extended gate {} (but maybe missed the gate)".format(self.contestant,
                                                                                                     intersection_time,
                                                                                                     extended_next_gate))

            if extended_next_gate.type not in (
                    "sp", "ildg", "ito", "ldg", "to") and not extended_next_gate.maybe_missed_time:
                intersection_time = extended_next_gate.get_gate_infinite_intersection_time(self.projector, self.track)
                if intersection_time and extended_next_gate.is_passed_in_correct_direction_track(
                        self.track):
                    logger.info("{} {}: Crossed infinite gate {} (but maybe missed the gate)".format(self.contestant,
                                                                                                     intersection_time,
                                                                                                     extended_next_gate))
                    extended_next_gate.maybe_missed_time = self.track[-1].time
                    extended_next_gate.maybe_missed_position = self.track[-1]
        # Look for any gates  for which we have crossed the infinite line, but not crossed the gate within a few seconds
        if len(self.outstanding_gates) > 0:
            gate = self.outstanding_gates[0]
            time_limit = 0
            if gate.maybe_missed_time and (self.track[-1].time - gate.maybe_missed_time).total_seconds() > time_limit:
                logger.info("{} {}: Did not cross {} within {} seconds of infinite crossing, so missing gate".format(
                    self.contestant, self.track[-1].time,
                    gate, time_limit))
                gate.missed = True
                if gate.time_check:
                    self.transmit_actual_crossing(gate)
                self.pop_gate(0, True)
        self.check_gate_in_range()
        if self.last_gate and self.last_gate.type == "fp":
            self.passed_finishpoint()
        # Handle landing gate
        if self.has_passed_finishpoint:
            if self.landing_gate is not None and not self.landing_gate.has_been_passed():
                intersection_time = self.landing_gate.get_gate_intersection_time(self.projector, self.track)
                # Miss is handled by miss_outstanding_gates
                if intersection_time:
                    gate = self.landing_gate.gates[0]
                    current_position = self.track[-1]
                    self.contestant.record_actual_gate_time(self.landing_gate.name, intersection_time)
                    logger.info("{} {}: Passing landing line".format(self.contestant, intersection_time))
                    gate_score = self.scorecard.get_gate_timing_score_for_gate_type(gate.type,
                                                                                    gate.expected_time,
                                                                                    gate.passing_time)
                    self.transmit_actual_crossing(gate)
                    self.update_score(gate, gate_score,
                                      "passing landing gate",
                                      current_position.latitude, current_position.longitude, "anomaly",
                                      self.GATE_SCORE_TYPE,
                                      planned=gate.expected_time, actual=gate.passing_time)

    def transmit_actual_crossing(self, gate: Gate):
        estimated_crossing_time = self.track[-1].time
        if gate.passing_time:
            planned_time_to_crossing = (gate.passing_time - gate.expected_time).total_seconds()
            estimated_crossing_time = gate.passing_time
        else:
            planned_time_to_crossing = (self.track[-1].time - gate.expected_time).total_seconds()
        score = self.scorecard.get_gate_timing_score_for_gate_type(gate.type,
                                                                   gate.expected_time, estimated_crossing_time)

        self.websocket_facade.transmit_seconds_to_crossing_time_and_crossing_estimate(self.contestant, gate.name,
                                                                                      planned_time_to_crossing,
                                                                                      round((
                                                                                                    estimated_crossing_time - gate.expected_time).total_seconds()),
                                                                                      score,
                                                                                      True,
                                                                                      gate.missed)

    def transmit_second_to_crossing_time_and_crossing_estimate(self):
        gate, estimated_crossing_time = self.estimate_crossing_time_of_next_timed_gate()
        if estimated_crossing_time is None:
            return
        planned_time_to_crossing = (self.track[-1].time - gate.expected_time).total_seconds()
        score = self.scorecard.get_gate_timing_score_for_gate_type(gate.type,
                                                                   gate.expected_time, estimated_crossing_time)

        self.websocket_facade.transmit_seconds_to_crossing_time_and_crossing_estimate(self.contestant, gate.name,
                                                                                      planned_time_to_crossing,
                                                                                      round((
                                                                                                    estimated_crossing_time - gate.expected_time).total_seconds()),
                                                                                      score,
                                                                                      False,
                                                                                      False)

    def distance_to_gate_intersect(self, gate: Gate, average_duration_seconds: int = 10) -> Optional[float]:
        """
        Project a line from the current bearing (average over a few positions), calculate the intersection point with
        the gate and return the distance. If there is no intersection, return None

        :param gate:
        :return: Distance in NM
        """
        if len(self.track) > 1:
            index = len(self.track) - 2
            initial_time = self.track[-1].time
            while index >= 0:
                if (initial_time - self.track[index].time).total_seconds() > average_duration_seconds:
                    break
                index -= 1
            starting_point = (self.track[index].latitude, self.track[index].longitude)
            finish_point = (self.track[-1].latitude, self.track[-1].longitude)
            intersection = nv_intersect(starting_point, finish_point, *gate.gate_line)
            if intersection:
                return calculate_distance_lat_lon(finish_point, intersection)
        return None

    def estimate_crossing_time_of_next_timed_gate(self, average_duration_seconds: int = 20) -> Tuple[Optional[Gate],
                                                                                                     Optional[
                                                                                                         datetime.datetime]]:
        """
        Calculate the distance to the next gate, and the distance between the gates until the first timed gate.

        The time to the first gate is given by the current speed, while the time for the remaining legs is given by
        the planned speed

        :param average_duration_seconds:
        :return: Estimated crossing time
        """
        if len(self.outstanding_gates) > 0:
            gate = self.outstanding_gates[0]
            estimated_crossing_time = self.estimate_crossing_time(gate,
                                                                  average_duration_seconds=average_duration_seconds)
            if estimated_crossing_time is None:
                return None, None
            if abs((estimated_crossing_time - self.track[-1].time)).total_seconds() < 20:
                estimated_crossing_time = self.estimate_crossing_time(gate, average_duration_seconds=6)
            if estimated_crossing_time is None:
                return None, None
            if gate.time_check:
                return gate, estimated_crossing_time
            previous_planned_time = gate.expected_time
            if len(self.outstanding_gates) > 1:
                for gate in self.outstanding_gates[1:]:
                    duration = gate.expected_time - previous_planned_time
                    estimated_crossing_time += duration
                    if gate.time_check:
                        return gate, estimated_crossing_time
                    previous_planned_time = gate.expected_time
        return None, None

    def estimate_crossing_time(self, gate: Gate, average_duration_seconds: int = 20) -> Optional[datetime.datetime]:
        """
        Returns the number of seconds (negative is early) from the planned crossing time the contestant is estimated to
        cross the next timed gate given the average speed over the past few seconds

        :return: seconds
        """
        if len(self.track) > 0:
            speed = self.track[-1].speed
            count = 1
            initial_time = self.track[-1].time
            index = len(self.track) - 2
            while index >= 0:
                count += 1
                speed += self.track[index].speed
                if (initial_time - self.track[index].time).total_seconds() > average_duration_seconds:
                    break
                index -= 1
            average_speed = speed / count  # kt
            distance = abs(cross_track_distance(gate.gate_line[0][0], gate.gate_line[0][1], gate.gate_line[1][0],
                                                gate.gate_line[1][1], self.track[-1].latitude,
                                                self.track[-1].longitude) / 1852)  # NM
            # distance = calculate_distance_lat_lon((self.track[-1].latitude, self.track[-1].longitude),
            #                                       (gate.latitude, gate.longitude)) / 1852  # NM
            if average_speed > 0:
                time_to_intercept = distance / average_speed  # hours
                return self.track[-1].time + datetime.timedelta(hours=time_to_intercept)
        return None

    def notify_termination(self):
        super().notify_termination()
        logger.info(
            f"{self.contestant}: {'Live processing and past' if self.live_processing else 'Past'} finish time, terminating")
        self.miss_outstanding_gates()
        self.calculate_gate_score()
        self.calculate_landing_gate_miss()

    def calculate_takeoff_gate_miss(self):
        if self.takeoff_gate and self.takeoff_gate.missed:
            gate = self.takeoff_gate.gates[0]
            current_position = self.track[-1]
            score = self.scorecard.get_gate_timing_score_for_gate_type(gate.type,
                                                                       gate.expected_time, None)
            self.update_score(gate, score, "missing takeoff gate", current_position.latitude,
                              current_position.longitude, "anomaly", "gate_score",
                              planned=gate.expected_time)

    def calculate_landing_gate_miss(self):
        if self.landing_gate and self.landing_gate.missed:
            gate = self.landing_gate.gates[0]
            current_position = self.track[-1]
            score = self.scorecard.get_gate_timing_score_for_gate_type(gate.type,
                                                                       gate.expected_time, None)
            self.update_score(gate, score, "missing landing gate", current_position.latitude,
                              current_position.longitude, "anomaly", "gate_score",
                              planned=gate.expected_time)

    def calculate_gate_score(self):
        if not len(self.track):
            return
        if self.takeoff_gate is not None and not self.takeoff_gate.has_been_passed():
            self.takeoff_gate.missed = True
            self.calculate_takeoff_gate_miss()
        index = 0
        finished = False
        current_position = self.track[-1]
        for gate_index, gate in enumerate(self.gates[self.last_gate_index:]):  # type: Gate
            if finished:
                break
            if gate.missed:
                if self.last_gate_index + gate_index > 0:
                    previous_gate = self.gates[self.last_gate_index + gate_index - 1]
                else:
                    previous_gate = None
                self.missed_gate(previous_gate, gate, gate.maybe_missed_position or current_position)
                index += 1
                if gate.gate_check:
                    score = self.scorecard.get_gate_timing_score_for_gate_type(gate.type,
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
                time_difference = (gate.passing_time - gate.expected_time).total_seconds()
                self.contestant.contestanttrack.update_last_gate(gate.name, time_difference)
                if gate.time_check:
                    gate_score = self.scorecard.get_gate_timing_score_for_gate_type(gate.type,
                                                                                    gate.expected_time,
                                                                                    gate.passing_time)
                    self.transmit_actual_crossing(gate)
                    self.update_score(gate, gate_score,
                                      "passing gate",
                                      current_position.latitude, current_position.longitude, "anomaly",
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

    def check_gates(self):
        self.check_intersections()
        self.calculate_gate_score()
        if self.recalculation_completed:
            self.transmit_second_to_crossing_time_and_crossing_estimate()
        self.check_gate_in_range()
