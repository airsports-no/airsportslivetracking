import logging
import math
from datetime import timedelta, datetime
from typing import Tuple, List, Optional

from display.models.contestant_utility_models import ContestantReceivedPosition
from display.utilities.coordinate_utilities import (
    fraction_of_leg,
    calculate_bearing,
    Projector,
    bearing_difference,
    point_to_line_distance,
    euclidean_point_to_line_distance,
)
from display.waypoint import Waypoint

logger = logging.getLogger(__name__)


class Gate:
    def __init__(
        self, gate: Waypoint, expected_time, gate_line_extended: Tuple[Tuple[float, float], Tuple[float, float]]
    ):
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
        self.infinite_passing_position = None
        self.missed = False
        self.maybe_missed_time = None
        self.maybe_missed_position = None
        self.expected_time = expected_time

    @property
    def is_visible(self) -> bool:
        return self.waypoint.is_visible

        self.projected_gate_line = None
        self.projected_gate_line_infinite = None
        self.projected_gate_line_extended = None
        self.center_x = None
        self.center_y = None
        self.gate_radius = 0

    def pre_project(self, projector: Projector):
        def project_line(line):
            if line is None:
                return None
            return (projector.project_point(line[0][0], line[0][1]), projector.project_point(line[1][0], line[1][1]))

        self.projected_gate_line = project_line(self.gate_line)
        self.projected_gate_line_infinite = project_line(self.gate_line_infinite)
        self.projected_gate_line_extended = project_line(self.gate_line_extended)

        if self.projected_gate_line:
            self.center_x = (self.projected_gate_line[0].projected_x + self.projected_gate_line[1].projected_x) / 2
            self.center_y = (self.projected_gate_line[0].projected_y + self.projected_gate_line[1].projected_y) / 2
            # Calculate half-width (radius) of the gate line
            self.gate_radius = (
                math.sqrt(
                    (self.projected_gate_line[0].projected_x - self.projected_gate_line[1].projected_x) ** 2
                    + (self.projected_gate_line[0].projected_y - self.projected_gate_line[1].projected_y) ** 2
                )
                / 2
            )

    def __str__(self):
        return self.name

    def pass_gate(self, passing_time: datetime, position: ContestantReceivedPosition):
        self.passing_time = passing_time
        self.extended_passing_time = passing_time
        self.infinite_passing_time = passing_time
        self.infinite_passing_position = position

    def pass_extended_gate(self, passing_time: datetime, position: ContestantReceivedPosition):
        self.extended_passing_time = passing_time
        self.infinite_passing_time = passing_time
        self.infinite_passing_position = position

    def pass_infinite_gate(self, passing_time: datetime, position: ContestantReceivedPosition):
        self.infinite_passing_time = passing_time
        self.infinite_passing_position = position

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
                calculate_bearing((track[-2].latitude, track[-2].longitude), (track[-1].latitude, track[-1].longitude))
            )
        return False

    def get_gate_intersection_time(
        self, projector: Projector, track: List[ContestantReceivedPosition]
    ) -> Optional[datetime]:
        if len(track) > 2:
            # Fast path: check distance to gate center
            # Threshold is gate radius + 500m buffer for aircraft movement between points
            last_pos = track[-1]
            if self.center_x is None:
                raise ValueError(f"Gate {self.name} is not projected")

            p_x = getattr(last_pos, "projected_x", None)
            p_y = getattr(last_pos, "projected_y", None)
            if p_x is None or p_y is None:
                raise ValueError(f"Position at {last_pos.time} is missing projected coordinates")

            dist_sq = (p_x - self.center_x) ** 2 + (p_y - self.center_y) ** 2
            threshold = self.gate_radius + 500
            if dist_sq > threshold**2:
                return None

            return get_intersect_time(
                projector,
                track[-3],
                track[-1],
                self.projected_gate_line[0],
                self.projected_gate_line[1],
            )
        return None

    def get_gate_infinite_intersection_time(
        self, projector: Projector, track: List[ContestantReceivedPosition]
    ) -> Optional[datetime]:
        if len(track) > 2:
            if not self.projected_gate_line_infinite:
                raise ValueError(f"Gate {self.name} infinite line is not projected")
            return get_intersect_time(
                projector,
                track[-3],
                track[-1],
                self.projected_gate_line_infinite[0],
                self.projected_gate_line_infinite[1],
            )
        return None

    def get_gate_extended_intersection_time(
        self, projector: Projector, track: List[ContestantReceivedPosition]
    ) -> Optional[datetime]:
        if len(track) > 2 and self.projected_gate_line_extended:
            return get_intersect_time(
                projector,
                track[-3],
                track[-1],
                self.projected_gate_line_extended[0],
                self.projected_gate_line_extended[1],
            )
        return None

    def get_distance_to_gate_line(self, latitude: float, longitude: float, projected_x=None, projected_y=None) -> float:
        """
        Calculates the distance from the current position to the nearest point of the gate line.
        """
        if projected_x is None or projected_y is None:
            raise ValueError(f"Missing projected coordinates for distance check to gate {self.name}")

        if self.projected_gate_line is None:
            raise ValueError(f"Gate {self.name} is not projected")

        return euclidean_point_to_line_distance(
            self.projected_gate_line[0].projected_x,
            self.projected_gate_line[0].projected_y,
            self.projected_gate_line[1].projected_x,
            self.projected_gate_line[1].projected_y,
            projected_x,
            projected_y,
        )


class MultiGate:
    def __init__(self, gates: List[Gate]):
        self.gates: list[Gate] = gates
        self.intersected_gate: Gate | None = None
        self.missed: bool = False

    def pass_gate(self, passing_time: datetime, position: ContestantReceivedPosition, gate: Optional[Gate] = None):
        if gate is not None:
            self.intersected_gate = gate
        assert self.intersected_gate is not None, "Setting passing time when the multi gate has not had an intersection"
        self.intersected_gate.passing_time = passing_time
        self.intersected_gate.extended_passing_time = passing_time
        self.intersected_gate.infinite_passing_time = passing_time
        self.intersected_gate.infinite_passing_position = position

    @property
    def name(self):
        return self.intersected_gate.name if self.intersected_gate is not None else self.gates[0].name

    def has_been_passed(self) -> bool:
        return self.missed or any(gate.has_been_passed() for gate in self.gates)

    def set_expected_time(self, expected_time: datetime):
        for gate in self.gates:
            gate.expected_time = expected_time

    def get_gate_intersection_time(
        self, projector: Projector, track: List[ContestantReceivedPosition]
    ) -> Optional[datetime]:
        for gate in self.gates:
            intersection_time = gate.get_gate_intersection_time(projector, track)
            if intersection_time is not None:
                gate.passing_time = intersection_time
                gate.extended_passing_time = intersection_time
                gate.infinite_passing_time = intersection_time
                gate.infinite_passing_position = track[-1]
                self.intersected_gate = gate
                return intersection_time
        return None


def round_seconds(stamp: datetime) -> datetime:
    if stamp.microsecond >= 500000:
        return stamp.replace(microsecond=0) + timedelta(seconds=1)
    return stamp.replace(microsecond=0)


def get_intersect_time(
    projector: Projector,
    track_segment_start: ContestantReceivedPosition,
    track_segment_finish: ContestantReceivedPosition,
    gate_start,
    gate_finish,
) -> Optional[datetime]:
    # intersection = line_intersect(track_segment_start.longitude, track_segment_start.latitude,
    #                               track_segment_finish.longitude,
    #                               track_segment_finish.latitude, gate_start[1], gate_start[0], gate_finish[1],
    #                               gate_finish[0])
    intersection = projector.intersect(
        track_segment_start,
        track_segment_finish,
        gate_start,
        gate_finish,
    )

    if intersection:
        fraction = fraction_of_leg(
            (track_segment_start.latitude, track_segment_start.longitude),
            (track_segment_finish.latitude, track_segment_finish.longitude),
            intersection,
        )
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
