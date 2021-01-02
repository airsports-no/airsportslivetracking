from display.coordinate_utilities import extend_line, get_procedure_turn_track


class Waypoint:
    def __init__(self, name: str):
        self.name = name
        self.latitude = 0  # type: float
        self.longitude = 0  # type: float
        self.elevation = 0  # type: float
        self.gate_line = []
        self._gate_line_infinite = None
        self.gate_line_extended = None
        self.width = 0  # type: float
        self.time_check = False
        self.gate_check = False
        self.planning_test = False
        self.end_curved = False
        self.type = ""
        self.distance_next = -1  # type: float
        self.distance_previous = -1  # type: float
        self.bearing_from_previous = -1
        self.bearing_next = -1  # type: float
        self.is_procedure_turn = False
        self.is_steep_turn = False

        self.inside_distance = 0
        self.outside_distance = 0

    @property
    def gate_line_infinite(self):
        if self._gate_line_infinite is None or len(self._gate_line_infinite) == 0:
            self._gate_line_infinite = extend_line(self.gate_line[0], self.gate_line[1], 40)
        return self._gate_line_infinite

    @gate_line_infinite.setter
    def gate_line_infinite(self, value):
        self._gate_line_infinite = value

    @property
    def procedure_turn_points(self):
        if self.is_procedure_turn:
            return get_procedure_turn_track(self.latitude, self.longitude, self.bearing_from_previous, self.bearing_next,
                                        0.2)
        return []

    def __str__(self):
        return "{}: {}, {}, {}".format(self.name, self.latitude, self.longitude, self.elevation)
