class Waypoint:
    def __init__(self, name: str):
        self.name = name
        self.latitude = 0  # type: float
        self.longitude = 0  # type: float
        self.elevation = 0  # type: float
        self.gate_line = []
        self.gate_line_infinite = None
        self.gate_line_extended = None
        self.width = 0  # type: float
        self.time_check = False
        self.gate_check = False
        self.planning_test = False
        self.end_curved = False
        self.type = ""
        self.distance_next = -1  # type: float
        self.bearing_next = -1  # type: float
        self.is_procedure_turn = False

        self.inside_distance = 0
        self.outside_distance = 0

    def __str__(self):
        return "{}: {}, {}, {}".format(self.name, self.latitude, self.longitude, self.elevation)

