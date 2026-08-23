from typing import List, Tuple

from display.utilities.coordinate_utilities import (
    extend_line,
    get_procedure_turn_track,
    calculate_bearing,
    bearing_difference,
)


class Waypoint:
    def __init__(self, name: str):
        self.name = name
        self.latitude = 0  # type: float
        self.longitude = 0  # type: float
        self.elevation = 0  # type: float
        self.gate_line = []  # [[lat,lon],[lat,lon]]
        self._original_gate_line = None
        self._gate_line_infinite = None
        self.gate_line_extended = None
        self.width = 0  # type: float
        self.time_check = False
        self.gate_check = False
        self.planning_test = False
        self.end_curved = False
        self.on_curved_segment = False
        self.type = ""
        self.distance_next = -1  # meters type: float
        self.distance_previous = -1  # meters type: float
        self.bearing_from_previous = -1
        self.bearing_next = -1  # type: float
        self.is_procedure_turn = False
        self.is_steep_turn = False

        self.control_latitude: float | None = None
        self.control_longitude: float | None = None

        self.inside_distance = 0
        self.outside_distance = 0

    @property
    def original_gate_line(self):
        if hasattr(self, "_original_gate_line"):
            return self._original_gate_line or self.gate_line
        return self.gate_line

    @original_gate_line.setter
    def original_gate_line(self, value):
        self._original_gate_line = value

    @property
    def gate_line_infinite(self):
        if self._gate_line_infinite is None or len(self._gate_line_infinite) == 0:
            self._gate_line_infinite = extend_line(self.gate_line[0], self.gate_line[1], 10)
        return self._gate_line_infinite

    @gate_line_infinite.setter
    def gate_line_infinite(self, value):
        self._gate_line_infinite = value

    @property
    def procedure_turn_points(self):
        if self.is_procedure_turn:
            return get_procedure_turn_track(
                self.latitude, self.longitude, self.bearing_from_previous, self.bearing_next, 0.2
            )
        return []

    @property
    def is_visible(self) -> bool:
        from display.utilities.gate_definitions import ANR_TP, TURNPOINT, STARTINGPOINT, FINISHPOINT

        if self.on_curved_segment:
            return False
        return self.type in (TURNPOINT, STARTINGPOINT, FINISHPOINT, ANR_TP)

    def __str__(self):
        return "{}: {}, {}, {}".format(self.name, self.latitude, self.longitude, self.elevation)

    def get_centre_track_segments(self) -> List[Tuple[float, float]]:
        """
        Generate track segments for each waypoint where the track goes through the centre of the corridor (if it exists)

        :param waypoint1:
        :param waypoint2:
        :return: Each waypoint is represented in a returned list of track segments
        """
        # Minute-mark and relative-timing calculations intentionally treat a
        # procedure turn as a one-minute pause at the turning point rather than
        # following the rendered procedure-turn geometry. The rendered turn can
        # vary with layout, but the planning contract is a fixed one-minute
        # offset before the next leg starts.
        return [(self.latitude, self.longitude)]

    def is_gate_line_pointing_right(self, original: bool = False):
        line = self.gate_line if not original else self.original_gate_line
        gate_line_bearing = calculate_bearing(line[0], line[1])
        waypoint_bearing = self.bearing_from_previous if self.bearing_from_previous >= 0 else self.bearing_next
        # This should be close to 90 if pointing right for a precision track
        return bearing_difference(waypoint_bearing, gate_line_bearing) > 0

    def get_gate_position_right_of_track(self, original: bool = False):
        line = self.gate_line if not original else self.original_gate_line
        if self.is_gate_line_pointing_right(original):
            return line[1]
        else:
            return line[0]

    def get_gate_position_left_of_track(self, original: bool = False):
        line = self.gate_line if not original else self.original_gate_line
        if self.is_gate_line_pointing_right(original):
            return line[0]
        else:
            return line[1]

    @property
    def is_left_turn(self) -> bool:
        return bearing_difference(self.bearing_from_previous, self.bearing_next) < 0

    @property
    def gate_heading(self) -> float:
        """
        The direction the gate is facing
        """
        gate_line_bearing = calculate_bearing(
            self.get_gate_position_right_of_track(), self.get_gate_position_left_of_track()
        )
        return (gate_line_bearing + 90) % 360

    @property
    def outer_corner_position(self) -> Tuple[Tuple[float, float], int]:
        gate_line_bearing = calculate_bearing(self.gate_line[0], self.gate_line[1])
        gate_right = 0 < gate_line_bearing < 180
        gate_down = 90 < gate_line_bearing < 270
        waypoint_bearing = self.bearing_from_previous if self.bearing_from_previous >= 0 else self.bearing_next
        right_of_track = bearing_difference(gate_line_bearing, waypoint_bearing) > 0
        is_left_turn = self.is_left_turn

        if is_left_turn:
            if right_of_track:
                label_index = 0
            else:
                label_index = 1
        else:
            if right_of_track:
                label_index = 1
            else:
                label_index = 0
        if gate_right:
            if label_index == 0:
                horizontal_offset = -1
            else:
                horizontal_offset = 1
        else:
            if label_index == 0:
                horizontal_offset = 1
            else:
                horizontal_offset = -1
        if gate_down:
            if label_index == 0:
                vertical_offset = -1
            else:
                vertical_offset = 1
        else:
            if label_index == 0:
                vertical_offset = 1
            else:
                vertical_offset = -1
        return self.gate_line[label_index], horizontal_offset, vertical_offset
