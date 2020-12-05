import logging
import dateutil

from display.convert_flightcontest_gpx import Waypoint

logger = logging.getLogger(__name__)


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
    def __init__(self, gate: Waypoint, expected_time):
        self.name = gate.name
        gate_line = gate.gate_line
        self.y1, self.x1 = gate_line[0]
        self.y2, self.x2 = gate_line[1]
        gate_line_infinite = gate.gate_line_infinite
        self.y1_infinite, self.x1_infinite = gate_line_infinite[0]
        self.y2_infinite, self.x2_infinite = gate_line_infinite[1]
        self.type = gate.type
        self.latitude = gate.latitude
        self.longitude = gate.longitude
        self.inside_distance = gate.inside_distance
        self.outside_distance = gate.outside_distance
        self.gate_check = gate.gate_check
        self.time_check = gate.time_check
        self.distance = gate.distance_next
        self.bearing = gate.bearing_next
        self.is_procedure_turn = gate.is_procedure_turn
        self.passing_time = None
        self.missed = False
        self.maybe_missed_time = None
        self.expected_time = expected_time

    def __str__(self):
        return self.name

    def has_been_passed(self):
        return self.missed or self.passing_time is not None
