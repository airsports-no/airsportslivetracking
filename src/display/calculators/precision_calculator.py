import logging
from datetime import timedelta
from typing import Optional, TYPE_CHECKING, List

from display.calculators.calculator import Calculator
from display.calculators.calculator_utilities import distance_between_gates, cross_track_gate, along_track_gate, \
    bearing_between
from display.coordinate_utilities import line_intersect, fraction_of_leg, get_heading_difference
from display.models import Contestant

if TYPE_CHECKING:
    from influx_facade import InfluxFacade
    from display.calculators.positions_and_gates import Gate, Position

logger = logging.getLogger(__name__)


class PrecisionCalculator(Calculator):
    DEVIATING = 4
    BACKTRACKING = 5
    PROCEDURE_TURN = 6
    FAILED_PROCEDURE_TURN = 7
    TRACKING_MAP = dict(Calculator.TRACKING_MAP)
    TRACKING_MAP.update({
        BACKTRACKING: "Backtracking",
        PROCEDURE_TURN: "Procedure turn",
        FAILED_PROCEDURE_TURN: "Failed procedure turn",
        DEVIATING: "Deviating",
    })

    def __init__(self, contestant: "Contestant", influx: "InfluxFacade"):
        super().__init__(contestant, influx)
        self.current_procedure_turn_gate = None
        self.current_procedure_turn_directions = []
        self.current_procedure_turn_slices = []
        self.current_procedure_turn_bearing_difference = 0
        self.current_procedure_turn_start_time = None

        self.last_gate = 0
        self.last_bearing = None
        self.current_speed_estimate = 0
        self.previous_gate_distances = None
        self.inside_gates = None

    def calculate_distance_to_outstanding_gates(self, current_position):
        gate_distances = [{"distance": distance_between_gates(current_position, gate), "gate": gate} for gate in
                          self.outstanding_gates]
        return sorted(gate_distances, key=lambda k: k["distance"])

    def check_if_gate_has_been_missed(self):
        if not self.starting_line.has_been_passed():
            return
        current_position = self.track[-1]
        distances = self.calculate_distance_to_outstanding_gates(current_position)
        # logger.info("Distances: {}".format(distances))
        if len(distances) == 0:
            return
        if self.inside_gates is None:
            self.inside_gates = {gate.name: False for gate in self.outstanding_gates}
        # logger.info("inside_gates: {}".format(self.inside_gates))
        insides = {}
        for item in distances:
            insides[item["gate"].name] = item["distance"] < item["gate"].inside_distance or (
                    item["distance"] < item["gate"].outside_distance and self.inside_gates[item["gate"].name])
            # if insides[item["gate"].name]:
            #     logger.info("Inside gate: {}".format(item["gate"].name))
        have_seen_inside = False
        for gate in self.outstanding_gates:  # type: Gate
            if have_seen_inside:
                # logger.info("Have seen inside, setting gate {} to False".format(gate.name))
                insides[gate.name] = False
                self.inside_gates[gate.name] = False
            if self.inside_gates[gate.name] and not insides[gate.name]:
                logger.info("Have left the vicinity of gate {}".format(gate.name))
                self.update_score(gate, 0, "Left the vicinity of gate {} without passing it".format(gate),
                                  current_position.latitude, current_position.longitude, "anomaly")
                self.check_intersections(force_gate=gate)

            if insides[gate.name]:
                have_seen_inside = True
        self.inside_gates = insides

    def calculate_score(self):
        self.check_if_gate_has_been_missed()
        self.check_intersections()
        self.calculate_gate_score()
        self.calculate_track_score()

    def update_current_leg(self, current_leg):
        if current_leg:
            self.contestant.contestanttrack.update_current_leg(current_leg.name)
        else:
            self.contestant.contestanttrack.update_current_leg("")

    def calculate_gate_score(self):
        index = 0
        finished = False
        current_position = self.track[-1]
        for gate in self.gates[self.last_gate:]:
            if finished:
                break
            if gate.missed:
                index += 1
                string = "{} points for missing gate {}".format(self.scorecard.missed_gate, gate)
                self.update_score(gate, self.scorecard.missed_gate, string, current_position.latitude,
                                  current_position.longitude, "anomaly")
                if gate.is_procedure_turn:
                    self.update_score(gate, self.scorecard.missed_gate,
                                      "{} for missing procedure turn at {}".format(
                                          self.scorecard.missed_procedure_turn,
                                          gate),
                                      current_position.latitude, current_position.longitude, "anomaly")
            elif gate.passing_time is not None:
                index += 1
                time_difference = (gate.passing_time - gate.expected_time).total_seconds()
                self.contestant.contestanttrack.update_last_gate(gate.name, time_difference)
                absolute_time_difference = abs(time_difference)
                if absolute_time_difference > self.scorecard.gate_perfect_limit_seconds:
                    gate_score = min(self.scorecard.maximum_gate_score, round(
                        absolute_time_difference - self.scorecard.gate_perfect_limit_seconds) * self.scorecard.gate_timing_per_second)
                    self.update_score(gate, gate_score,
                                      "{} points for passing gate {} of by {}s".format(gate_score, gate,
                                                                                       round(time_difference)),
                                      current_position.latitude, current_position.longitude, "information")
                else:
                    self.update_score(gate, 0,
                                      "{} points for passing gate {} of by {}s".format(0, gate,
                                                                                       round(time_difference)),
                                      current_position.latitude, current_position.longitude, "information")
            else:
                finished = True
        self.last_gate += index

    def guess_current_leg(self):
        current_position = self.track[-1]
        inside_legs = []
        turning_points = [gate for gate in self.gates if gate.is_turning_point]
        for index in range(1, len(turning_points)):
            previous_gate = turning_points[index - 1]  # type: Gate
            next_gate = turning_points[index]  # type: Gate
            if next_gate.has_been_passed():
                continue
            cross_track = cross_track_gate(previous_gate, next_gate, current_position)
            absolute_cross = abs(cross_track)
            distance_from_start = along_track_gate(previous_gate, cross_track, current_position)
            distance_from_finish = along_track_gate(next_gate, -cross_track, current_position)
            if distance_from_finish + distance_from_start <= next_gate.distance * 1.05:
                inside_legs.append({"gate": next_gate, "cross_track": absolute_cross})
        return sorted(inside_legs, key=lambda k: k["cross_track"])

    def sort_out_best_leg(self, best_guesses, bearing) -> Optional["Gate"]:
        inside_leg_distance = 1000
        current_leg = None
        minimum_distance = None
        for guess in best_guesses:
            if guess["cross_track"] < inside_leg_distance and abs(
                    get_heading_difference(bearing, guess["gate"].bearing)) < 60:
                current_leg = guess["gate"]
                break
            if minimum_distance is None or guess["cross_track"] < minimum_distance:
                minimum_distance = guess["cross_track"]
                current_leg = guess["gate"]
        return current_leg

    def get_turning_point_before_now(self, index) -> Optional["Gate"]:
        gates = [gate for gate in self.gates if gate.is_turning_point and (
                gate.has_been_passed() and (not gate.passing_time or gate.passing_time < self.track[index].time))]
        if len(gates):
            return gates[-1]
        return None

    def get_turning_point_after_now(self, index) -> Optional["Gate"]:
        gates = [gate for gate in self.gates if gate.is_turning_point and not gate.missed and (
                not gate.passing_time or gate.passing_time > self.track[index].time)]
        if len(gates):
            return gates[0]
        return None

    def calculate_current_leg(self) -> "Gate":
        gate_range = 4000
        current_position_index = len(self.track) - 1
        current_position = self.track[-1]
        previous_position = self.track[-2]
        next_gate = self.get_turning_point_after_now(current_position_index)
        distance_to_next = 999999999999999
        if next_gate:
            # if self.contestant.contestant_number == 7:
            #     logger.info("next_gate: {}".format(next_gate))
            distance_to_next = distance_between_gates(current_position, next_gate)
        last_gate = self.get_turning_point_before_now(current_position_index)
        distance_to_last = 999999999999999
        if last_gate:
            # if self.contestant.contestant_number == 7:
            #     logger.info("last_gate: {}".format(last_gate))

            distance_to_last = distance_between_gates(current_position, last_gate)
        bearing = bearing_between(previous_position, current_position)
        best_guess = self.sort_out_best_leg(self.guess_current_leg(), bearing)
        if best_guess == next_gate:
            # if self.contestant.contestant_number == 7:
            #     logger.info("Best guess == next_gate")
            current_leg = next_gate
        else:
            if distance_to_next < gate_range:
                # if self.contestant.contestant_number == 7:
                #     logger.info("Best guess is close to next_gate")

                current_leg = next_gate
            elif distance_to_last < gate_range:
                # if self.contestant.contestant_number == 7:
                #     logger.info("Best guess is close to last_gate")

                current_leg = next_gate
            else:
                # if self.contestant.contestant_number == 7:
                #     logger.info("Sticking with best guess {}".format(best_guess))

                current_leg = best_guess
        return current_leg

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
        if not self.starting_line.has_been_passed() and not self.any_gate_passed():
            return
        last_position = self.track[-1]  # type: Position
        finish_index = len(self.track) - 1
        speed = self.get_speed()
        if (speed == 0 or last_position.time > self.contestant.finished_by_time) and not self.all_gates_passed():
            self.miss_outstanding_gates()
            logger.info("{}: Speed is 0, terminating".format(self.contestant))
            self.update_tracking_state(self.FINISHED)
            return
        look_back = 2
        start_index = max(finish_index - look_back, 0)
        current_leg = self.calculate_current_leg()
        self.update_current_leg(current_leg)
        first_position = self.track[start_index]
        next_gate_last = self.get_turning_point_after_now(finish_index)
        if not next_gate_last:
            logger.info("{}: No more turning points, terminating".format(self.contestant))
            self.update_tracking_state(self.FINISHED)
            self.contestant.contestanttrack.set_calculator_finished()
            return
        last_gate_first = self.get_turning_point_before_now(start_index)  # Gate we passed a few steps earlier
        last_gate_last = self.get_turning_point_before_now(finish_index)  # Gate we just passed

        bearing = bearing_between(first_position, last_position)
        if current_leg:
            bearing_difference = abs(get_heading_difference(bearing, current_leg.bearing))
        else:
            bearing_difference = abs(get_heading_difference(bearing, next_gate_last.bearing))
            current_leg = next_gate_last
        if last_gate_last and last_gate_first != last_gate_last and last_gate_last.is_procedure_turn and self.tracking_state not in (
                self.FAILED_PROCEDURE_TURN, self.PROCEDURE_TURN):
            self.update_tracking_state(self.PROCEDURE_TURN)
            self.current_procedure_turn_slices = []
            self.current_procedure_turn_directions = []
            self.current_procedure_turn_gate = last_gate_last
            self.current_procedure_turn_bearing_difference = get_heading_difference(last_gate_last.bearing,
                                                                                    next_gate_last.bearing)
            if self.current_procedure_turn_bearing_difference > 0:
                self.current_procedure_turn_bearing_difference -= 360
            else:
                self.current_procedure_turn_bearing_difference += 360

            self.current_procedure_turn_start_time = last_position.time
        if self.tracking_state == self.PROCEDURE_TURN:
            if self.last_bearing:
                self.current_procedure_turn_slices.append(get_heading_difference(self.last_bearing, bearing))
                total_turn = sum(self.current_procedure_turn_slices)
                logger.info(
                    "{}: Turned a total of {} degrees as part of procedure turn of {} at gate {} ".format(
                        self.contestant, total_turn,
                        self.current_procedure_turn_bearing_difference,
                        self.current_procedure_turn_gate))
                if abs(total_turn - self.current_procedure_turn_bearing_difference) < 60:
                    self.update_tracking_state(self.TRACKING)
                    logger.info("{}: Procedure turn completed successfully".format(self.contestant))

                if (last_position.time - self.current_procedure_turn_start_time).total_seconds() > 180:
                    if abs(total_turn - self.current_procedure_turn_bearing_difference) >= 60:
                        self.update_tracking_state(self.FAILED_PROCEDURE_TURN)
                        self.update_score(next_gate_last, self.scorecard.missed_procedure_turn,
                                          "{} points for incorrect procedure turn at {}".format(
                                              self.scorecard.missed_procedure_turn, self.current_procedure_turn_gate),
                                          last_position.latitude, last_position.longitude, "anomaly")
        else:
            if bearing_difference > 90:
                if self.tracking_state == self.TRACKING:
                    self.update_tracking_state(self.BACKTRACKING)
                    self.update_score(next_gate_last, self.scorecard.backtracking,
                                      "{} points for backtracking at {} {}".format(self.scorecard.backtracking,
                                                                                   current_leg, next_gate_last),
                                      last_position.latitude, last_position.longitude, "anomaly")
            else:
                self.update_tracking_state(self.TRACKING)
        self.last_bearing = bearing

    def get_speed(self):
        previous_index = min(5, len(self.track))
        distance = distance_between_gates(self.track[-previous_index], self.track[-1]) / 1852
        time_difference = (self.track[-1].time - self.track[-previous_index].time).total_seconds() / 3600
        if time_difference == 0:
            time_difference = 0.01
        return distance / time_difference
