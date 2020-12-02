import logging
import dateutil

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
    def __init__(self, gate, expected_time):
        self.name = gate["name"]
        gate_line = gate["gate_line"]
        self.x1 = gate_line[0]
        self.y1 = gate_line[1]
        self.x2 = gate_line[2]
        self.y2 = gate_line[3]
        gate_line_infinite = gate["gate_line_infinite"]
        self.x1_infinite = gate_line_infinite[0]
        self.y1_infinite = gate_line_infinite[1]
        self.x2_infinite = gate_line_infinite[2]
        self.y2_infinite = gate_line_infinite[3]

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
        self.maybe_missed_time = None
        self.expected_time = expected_time

    def __str__(self):
        return self.name

    def has_been_passed(self):
        return self.missed or self.passing_time is not None
