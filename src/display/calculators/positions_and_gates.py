import logging
from datetime import timedelta, datetime
from typing import Tuple, List, Optional

from display.coordinate_utilities import line_intersect, fraction_of_leg, calculate_bearing, nv_intersect, \
    Projector, bearing_difference, cross_track_distance, calculate_distance_lat_lon, point_to_line_distance
from display.waypoint import Waypoint

logger = logging.getLogger(__name__)


class Position:
    def __init__(self, time, latitude, longitude, altitude, speed, course, battery_level, position_id, device_id,
                 interpolated: bool = False, processor_received_time=None, calculator_received_time=None,
                 server_time=None,
                 **kwargs):
        self.time = time
        self.latitude = latitude
        self.longitude = longitude
        self.altitude = altitude
        self.speed = speed
        self.course = course
        self.battery_level = battery_level
        self.position_id = position_id
        self.device_id = device_id
        self.progress = 0
        self.interpolated = interpolated
        self.processor_received_time = processor_received_time
        self.calculator_received_time = calculator_received_time
        self.server_time = server_time

    def __str__(self):
        return f"{self.time}: {self.latitude}, {self.longitude}, a: {self.altitude}, s: {self.speed}, c: {self.course}, bl: {self.battery_level}, pi: {self.position_id}, di: {self.device_id}, p: {self.progress}"


class Gate:
    def __init__(self, gate: Waypoint, expected_time,
                 gate_line_extended: Tuple[Tuple[float, float], Tuple[float, float]]):
        self.waypoint = gate
        self.name = gate.name
        self.gate_line = gate.gate_line  # [[lat,lon],[lat,lon]]
        self.gate_line_infinite = gate.gate_line_infinite
        self.gate_line_extended = gate_line_extended

        self.gate_heading = gate.gate_heading
        self.type = gate.type
        self.latitude = gate.latitude
        self.longitude = gate.longitude
        self.inside_distance = gate.inside_distance
        self.outside_distance = gate.outside_distance
        self.gate_check = gate.gate_check
        self.time_check = gate.time_check
        self.distance = gate.distance_next
        self.bearing = gate.bearing_next
        self.bearing_from_previous = gate.bearing_from_previous
        self.is_procedure_turn = gate.is_procedure_turn
        self.is_steep_turn = gate.is_steep_turn
        self.passing_time = None
        self.extended_passing_time = None
        self.infinite_passing_time = None
        self.missed = False
        self.maybe_missed_time = None
        self.maybe_missed_position = None
        self.expected_time = expected_time

    def __str__(self):
        return self.name

    def pass_gate(self, passing_time: datetime):
        self.passing_time = passing_time
        self.extended_passing_time = passing_time
        self.infinite_passing_time = passing_time

    def pass_extended_gate(self, passing_time: datetime):
        self.extended_passing_time = passing_time
        self.infinite_passing_time = passing_time

    def pass_infinite_gate(self, passing_time: datetime):
        self.infinite_passing_time = passing_time

    def has_been_passed(self):
        return self.missed or self.passing_time is not None

    def has_extended_been_passed(self):
        return self.missed or self.extended_passing_time is not None

    def has_infinite_been_passed(self):
        return self.missed or self.infinite_passing_time is not None

    def is_passed_in_correct_direction_bearing_to_next(self, track_bearing) -> bool:
        return abs(bearing_difference(track_bearing, self.gate_heading)) < 90

    def is_passed_in_correct_direction_track(self, track) -> bool:
        if len(track) > 1:
            return self.is_passed_in_correct_direction_bearing_to_next(
                calculate_bearing((track[-2].latitude, track[-2].longitude), (track[-1].latitude, track[-1].longitude)))
        return False

    def get_gate_intersection_time(self, projector: Projector, track: List[Position]) -> Optional[datetime]:
        if len(track) > 2:
            return get_intersect_time(projector, track[-3], track[-1], self.gate_line[0], self.gate_line[1])
        return None

    def get_gate_infinite_intersection_time(self, projector: Projector, track: List[Position]) -> Optional[datetime]:
        if len(track) > 2:
            return get_intersect_time(projector, track[-3], track[-1], self.gate_line_infinite[0],
                                      self.gate_line_infinite[1])
        return None

    def get_gate_extended_intersection_time(self, projector: Projector, track: List[Position]) -> Optional[datetime]:
        if len(track) > 2 and self.gate_line_extended:
            return get_intersect_time(projector, track[-3], track[-1], self.gate_line_extended[0],
                                      self.gate_line_extended[1])
        return None

    def get_distance_to_gate_line(self, latitude: float, longitude: float) -> float:
        """
        Calculates the distance from the current position to the nearest point of the gate line.

        :param latitude:
        :param longitude:
        :return:
        """
        return point_to_line_distance(*self.gate_line[0], *self.gate_line[1], latitude, longitude)


class MultiGate:
    def __init__(self, gates: List[Gate]):
        self.gates = gates
        self.intersected_gate = None
        self.missed = False

    @property
    def name(self):
        return self.intersected_gate.name if self.intersected_gate is not None else self.gates[0].name

    def has_been_passed(self) -> bool:
        return self.missed or any(gate.has_been_passed() for gate in self.gates)

    def set_expected_time(self, expected_time: datetime):
        for gate in self.gates:
            gate.expected_time = expected_time

    def get_gate_intersection_time(self, projector: Projector, track: List[Position]) -> Optional[datetime]:
        for gate in self.gates:
            intersection_time = gate.get_gate_intersection_time(projector, track)
            if intersection_time is not None:
                gate.passing_time = intersection_time
                gate.extended_passing_time = intersection_time
                gate.infinite_passing_time = intersection_time
                self.intersected_gate = gate
            return intersection_time
        return None


def round_seconds(stamp: datetime) -> datetime:
    new_stamp = stamp
    if stamp.microsecond >= 500000:
        new_stamp = stamp + timedelta(seconds=1)
    return new_stamp.replace(microsecond=0)


def get_intersect_time(projector: Projector, track_segment_start: Position, track_segment_finish: Position, gate_start,
                       gate_finish) -> \
        Optional[datetime]:
    # intersection = line_intersect(track_segment_start.longitude, track_segment_start.latitude,
    #                               track_segment_finish.longitude,
    #                               track_segment_finish.latitude, gate_start[1], gate_start[0], gate_finish[1],
    #                               gate_finish[0])
    intersection = projector.intersect((track_segment_start.latitude, track_segment_start.longitude),
                                       (track_segment_finish.latitude, track_segment_finish.longitude),
                                       gate_start, gate_finish)

    if intersection:
        fraction = fraction_of_leg((track_segment_start.latitude, track_segment_start.longitude),
                                   (track_segment_finish.latitude, track_segment_finish.longitude),
                                   intersection)
        time_difference = (track_segment_finish.time - track_segment_start.time).total_seconds()
        intersection_time = track_segment_start.time + timedelta(seconds=fraction * time_difference)
        # logger.info("Previous position time: {}".format(track_segment_start.time))
        # logger.info("Next position time: {}".format(track_segment_finish.time))
        # logger.info("Time difference is: {}".format(time_difference))
        # logger.info("Fraction is: {}".format(fraction))
        # logger.info("Which gives the time: {}".format(intersection_time))
        logger.info("Actual intersection time: {}".format(intersection_time))
        return round_seconds(intersection_time)
    return None
