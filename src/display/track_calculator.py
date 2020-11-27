import logging
import threading
from datetime import datetime, timedelta
from typing import List, Optional

import dateutil

from display.coordinate_utilities import line_intersect, fraction_of_leg, cross_track_distance, along_track_distance, \
    get_heading_difference, calculate_distance_lat_lon, calculate_bearing
from display.models import Contestant, ContestantTrack
from influx_facade import InfluxFacade

logger = logging.getLogger(__name__)


class Scorecard:
    missed_gate = 100
    gate_timing_per_second = 3
    gate_perfect_limit_seconds = 2
    maximum_gate_score = 100
    backtracking = 200
    missed_procedure_turn = 200
    below_minimum_altitude = 500
    takeoff_time_limit_seconds = 60
    missed_takeoff_gate = 100


class Position:
    def __init__(self, time, latitude, longitude, altitude, speed, course, battery_level):
        self.time = dateutil.parser.parse(time)
        self.latitude = latitude
        self.longitude = longitude
        self.altitude = altitude
        self.speed = speed
        self.course = course
        self.battery_level = battery_level


class Gate:
    def __init__(self, gate, expected_time):
        self.name = gate["name"]
        gate_line = gate["gate_line"]
        self.x1 = gate_line[0]
        self.y1 = gate_line[1]
        self.x2 = gate_line[2]
        self.y2 = gate_line[3]
        self.latitude = gate["latitude"]
        self.longitude = gate["longitude"]
        self.inside_distance = gate["inside_distance"]
        self.outside_distance = gate["outside_distance"]
        self.is_turning_point = gate.get("type", "unknown") == "tp"
        if self.is_turning_point:
            self.distance = gate.get("distance", -1)
            self.bearing = gate.get("bearing", -1)
        self.is_procedure_turn = gate.get("is_procedure_turn", False)
        self.turn_direction = gate.get("turn_direction", "")
        self.passing_time = None
        self.missed = False
        self.expected_time = expected_time

    def __str__(self):
        return self.name

    def has_been_passed(self):
        return self.missed or self.passing_time is not None


class Calculator(threading.Thread):
    TRACKING = 0
    BACKTRACKING = 1
    PROCEDURE_TURN = 2
    FAILED_PROCEDURE_TURN = 3
    DEVIATING = 4
    BEFORE_START = 5
    FINISHED = 6
    STARTED = 7

    TRACKING_MAP = {
        TRACKING: "Tracking",
        BACKTRACKING: "Backtracking",
        PROCEDURE_TURN: "Procedure turn",
        FAILED_PROCEDURE_TURN: "Failed procedure turn",
        DEVIATING: "Deviating",
        BEFORE_START: "Waiting...",
        FINISHED: "Finished",
        STARTED: "Started"
    }

    def __init__(self, contestant: Contestant, influx: InfluxFacade):
        super().__init__()
        self.contestant = contestant
        self.influx = influx
        self.track = []
        self.process_event = threading.Event()
        self.loop_time = 60
        self.last_processed = 0
        self.score = 0
        self.score_log = []
        self.current_procedure_turn_gate = None
        self.current_procedure_turn_directions = []
        self.last_gate = 0
        self.last_bearing = None
        self.current_speed_estimate = 0
        self.previous_gate_distances = None
        self.tracking_state = self.BEFORE_START
        self.inside_gates = None
        self.scorecard = None
        self.score_by_gate = {}
        self.gates = []
        self.outstanding_gates = []
        self.starting_line = None
        self.start()
        logger.info("Started calculator for contestant {}".format(contestant))

    def create_gates(self) -> List:
        waypoints = self.contestant.contest.track.waypoints
        expected_times = self.contestant.gate_times
        gates = []
        for item in waypoints:
            gates.append(Gate(item, expected_times[item["name"]]))
        return gates

    def add_positions(self, positions):
        self.track.extend([Position(**position) for position in positions])
        self.process_event.set()

    def run(self):
        if not ContestantTrack.objects.filter(contestant=self.contestant):
            ContestantTrack.objects.create(contestant=self.contestant)
        self.scorecard = self.contestant.scorecard
        self.gates = self.create_gates()
        self.outstanding_gates = list(self.gates)
        self.starting_line = Gate(self.contestant.contest.track.starting_line, self.gates[0].expected_time)

        # while datetime.now().astimezone() < self.contestant.finished_by_time and self.tracking_state != self.FINISHED:
        while self.tracking_state != self.FINISHED:
            self.process_event.wait(self.loop_time)
            self.process_event.clear()
            while self.last_processed < len(self.track):
                if len(self.track) > 1:
                    self.calculate_score()
                self.last_processed = len(self.track)
        logger.info("Terminating calculator for {}".format(self.contestant))

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

    def get_intersect_time(self, gate: Gate):
        if len(self.track) > 1:
            segment = self.track[-2:]  # type: List[Position]
            intersection = line_intersect(segment[0].longitude, segment[0].latitude, segment[1].longitude,
                                          segment[1].latitude, gate.x1, gate.y1, gate.x2, gate.y2)
            if intersection:
                fraction = fraction_of_leg(segment[0].longitude, segment[0].latitude, segment[1].longitude,
                                           segment[1].latitude, intersection[0], intersection[1])
                time_difference = (segment[1].time - segment[0].time).total_seconds()
                return segment[0].time + timedelta(seconds=fraction * time_difference)
        return None

    def check_intersections(self, force_gate: Optional[Gate] = None):
        # Check starting line
        if not self.starting_line.has_been_passed():
            intersection_time = self.get_intersect_time(self.starting_line)
            if intersection_time:
                logger.info("{}: Passing start line".format(self.contestant))
                self.update_tracking_state(self.STARTED)
                self.starting_line.passing_time = intersection_time
        i = len(self.outstanding_gates) - 1
        crossed_gate = False
        while i >= 0:
            gate = self.outstanding_gates[i]
            intersection_time = self.get_intersect_time(gate)
            if intersection_time:
                logger.info("{}: Crossed gate {}".format(self.contestant, gate))
                gate.passing_time = intersection_time
                crossed_gate = True
            if force_gate == gate:
                crossed_gate = True
            if crossed_gate:
                if gate.passing_time is None:
                    logger.info("{}: Missed gate {}".format(self.contestant, gate))
                    gate.missed = True
                self.outstanding_gates.pop(i)
            i -= 1

    def update_score(self, gate: Gate, score: float, message: str, latitude: float, longitude: float,
                     annotation_type: str):
        logger.info("UPDATE_SCORE {}: {}".format(self.contestant, message))
        self.score += score
        try:
            self.score_by_gate[gate.name] += score
        except KeyError:
            self.score_by_gate[gate.name] = self.score
        self.influx.add_annotation(self.contestant, latitude, longitude, message, annotation_type,
                                   self.track[-1].time)  # TODO: Annotations with the same time
        self.score_log.append(message)
        self.contestant.contestanttrack.update_score(self.score_by_gate, self.score, self.score_log)

    def update_tracking_state(self, tracking_state: int):
        if tracking_state == self.tracking_state:
            return
        logger.info("{}: Changing state to {}".format(self.contestant, self.TRACKING_MAP[tracking_state]))
        self.tracking_state = tracking_state
        self.contestant.contestanttrack.updates_current_state(self.TRACKING_MAP[tracking_state])

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
                                      "{} for missing procedure turn at gate {}".format(
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
            # if self.contestant.contestant_number == 17:
            #     logger.info("{}: Possible leg: {} - {}".format(self.contestant, next_gate, cross_track))
            #     logger.info("distance_from_finish: {}, distance_from_start: {}, leg_length: {}".format(distance_from_finish, distance_from_start, next_gate.distance))
            if distance_from_finish + distance_from_start <= next_gate.distance * 1.05:
                inside_legs.append({"gate": next_gate, "cross_track": absolute_cross})
        return sorted(inside_legs, key=lambda k: k["cross_track"])

    def sort_out_best_leg(self, best_guesses, bearing) -> Optional[Gate]:
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
        # if self.contestant.contestant_number == 7:
        #     logger.info("Best guess leg: {}".format(current_leg))
        return current_leg

    def get_turning_point_before_now(self, index) -> Optional[Gate]:
        gates = [gate for gate in self.gates if gate.is_turning_point and (
                gate.has_been_passed() and (not gate.passing_time or gate.passing_time < self.track[index].time))]
        if len(gates):
            return gates[-1]
        return None

    def get_turning_point_after_now(self, index) -> Optional[Gate]:
        gates = [gate for gate in self.gates if gate.is_turning_point and not gate.missed and (
                not gate.passing_time or gate.passing_time > self.track[index].time)]
        if len(gates):
            return gates[0]
        return None

    def calculate_current_leg(self) -> Gate:
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
        last_position = self.track[-1]
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
            return
        last_gate_first = self.get_turning_point_before_now(start_index)
        last_gate_last = self.get_turning_point_before_now(finish_index)

        bearing = bearing_between(first_position, last_position)
        if current_leg:
            bearing_difference = abs(get_heading_difference(bearing, current_leg.bearing))
        else:
            bearing_difference = abs(get_heading_difference(bearing, next_gate_last.bearing))
            current_leg = next_gate_last
        if last_gate_last and last_gate_first and last_gate_last.is_procedure_turn and not last_gate_first.is_procedure_turn and self.tracking_state != self.FAILED_PROCEDURE_TURN:
            self.update_tracking_state(self.PROCEDURE_TURN)
            self.current_procedure_turn_gate = last_gate_last
        if self.tracking_state == self.PROCEDURE_TURN:
            if self.last_bearing:
                turn_direction = "cw" if get_heading_difference(self.last_bearing, bearing) > 0 else "ccw"
                self.current_procedure_turn_directions.append(turn_direction)
            if bearing_difference < 50:
                self.update_tracking_state(self.TRACKING)
                if self.current_procedure_turn_gate.turn_direction not in self.current_procedure_turn_directions:
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


def cross_track_gate(gate1, gate2, position):
    return cross_track_distance(gate1.latitude, gate1.longitude, gate2.latitude, gate2.longitude, position.latitude,
                                position.longitude)


def along_track_gate(gate1, cross_track_distance, position):
    return along_track_distance(gate1.latitude, gate1.longitude, position.latitude,
                                position.longitude, cross_track_distance)


def distance_between_gates(gate1, gate2):
    return calculate_distance_lat_lon((gate1.latitude, gate1.longitude), (gate2.latitude, gate2.longitude))


def bearing_between(gate1, gate2):
    return calculate_bearing((gate1.latitude, gate1.longitude), (gate2.latitude, gate2.longitude))
