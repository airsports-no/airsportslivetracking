from typing import List, Tuple

from display.coordinate_utilities import extend_line, get_procedure_turn_track, get_centre_of_line_lat_lon


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

        self._left_corridor_line = None
        self._right_corridor_line = None

        self.inside_distance = 0
        self.outside_distance = 0

    ######## Required for backwards compatibility
    @property
    def left_corridor_line(self):
        if hasattr(self, "_left_corridor_line"):
            return self._left_corridor_line
        return []
    
    @left_corridor_line.setter
    def left_corridor_line(self, value):
        self._left_corridor_line = value

    @property
    def right_corridor_line(self):
        if hasattr(self, "_right_corridor_line"):
            return self._right_corridor_line
        return []

    @right_corridor_line.setter
    def right_corridor_line(self, value):
        self._right_corridor_line = value
    #########################


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
            return get_procedure_turn_track(self.latitude, self.longitude, self.bearing_from_previous,
                                            self.bearing_next,
                                            0.2)
        return []

    def __str__(self):
        return "{}: {}, {}, {}".format(self.name, self.latitude, self.longitude, self.elevation)


    def get_centre_track_segments(self)->List[Tuple[float, float]]:
        """
        Generate track segments for each waypoint where the track goes through the centre of the corridor (if it exists)
    
        :param waypoint1:
        :param waypoint2:
        :return: Each waypoint is represented in a returned list of track segments
        """
        return [(self.latitude, self.longitude)]
        # Handling the centre track through a curve is not working correctly. We need to only deal with the actual
        # waypoint position. This is made evident from testing by Yago.
        # if self.right_corridor_line is None or len(self.right_corridor_line) == 0:
        #     return [(self.latitude, self.longitude)]
        # else:
        #     track = []
        #     for index in range(len(self.right_corridor_line)):
        #         track.append(get_centre_of_line_lat_lon(self.left_corridor_line[index], self.right_corridor_line[index]))
        #     return track
        #
