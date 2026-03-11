import numpy as np
from shapely.geometry import Polygon, Point, LineString

import datetime
from typing import Optional, List, Tuple, Dict, TYPE_CHECKING

from display.models.contestant_utility_models import ContestantReceivedPosition
from display.utilities.coordinate_utilities import (
    calculate_bearing,
    bearing_difference,
    to_rad,
)


def distance_between_gates(gate1, gate2):
    # This might still need to stay lat/lon if used outside calculation loop for general distance
    from display.utilities.coordinate_utilities import calculate_distance_lat_lon

    return calculate_distance_lat_lon((gate1.latitude, gate1.longitude), (gate2.latitude, gate2.longitude))


def bearing_between(gate1, gate2):
    return calculate_bearing((gate1.latitude, gate1.longitude), (gate2.latitude, gate2.longitude))


def load_track_points_traccar_csv(points: list[tuple[datetime.datetime, float, float]]):
    positions = []
    for point in points:
        positions.append(
            {
                "time": point[0].isoformat(),
                "latitude": point[1],
                "longitude": point[2],
                "altitude": 0,
                "speed": 0,
                "course": 0,
                "battery_level": 100,
            }
        )
    return positions


def round_time_minute(dt=None, round_to=60):
    """Round a datetime object to any time laps in seconds
    dt : datetime.datetime object, default now.
    roundTo : Closest number of seconds to round to, default 1 minute.
    """
    if dt is None:
        dt = datetime.datetime.now()
    seconds = (dt.replace(tzinfo=None) - dt.min).seconds
    rounding = (seconds + round_to / 2) // round_to * round_to
    return dt + datetime.timedelta(0, rounding - seconds, -dt.microsecond)


def round_time_second(obj: datetime.datetime) -> datetime.datetime:
    if obj.microsecond >= 500_000:
        obj += datetime.timedelta(seconds=1)
    return obj.replace(microsecond=0)


def project_position(
    latitude: float, longitude: float, course: float, turning_rate: float, speed: float, seconds: float
) -> tuple[float, float]:
    """

    :param seconds: Number of seconds into the future to project the position
    :param latitude:
    :param longitude:
    :param turning_rate: degrees/second
    :param speed: knots
    :return: new position
    """
    from display.utilities.coordinate_utilities import project_position_lat_lon

    speed_per_second = speed / 3600  # nm/s
    if turning_rate == 0:
        distance = speed_per_second * seconds  # nm
        return project_position_lat_lon((latitude, longitude), course, distance * 1852)

    total_angle = turning_rate * seconds  # degrees
    circle_time = 360 / turning_rate  # seconds
    circumference = speed_per_second * circle_time  # nm
    circle_radius = circumference / (2 * np.pi)  # nm
    distance = 2 * circle_radius * np.sin(np.deg2rad(total_angle / 2))  # nm
    projected_heading = course + total_angle  # degrees
    return project_position_lat_lon((latitude, longitude), projected_heading, distance * 1852)


if TYPE_CHECKING:
    from display.utilities.coordinate_utilities import Projector


def time_to_intersection(
    track: List[ContestantReceivedPosition],
    projector: "Projector",
    gate_line: Tuple[Tuple[float, float], Tuple[float, float]],
) -> Optional[datetime.datetime]:
    """
    Returns the time the track intersects the gate line, or None if no intersection is found.
    """
    if len(track) < 2:
        return None

    p1 = track[-2]
    p2 = track[-1]

    # Use projected coordinates if available, otherwise project them
    if p1.projected_x is None or p1.projected_y is None:
        proj1 = projector.project_point(p1.latitude, p1.longitude)
        p1_x, p1_y = proj1.projected_x, proj1.projected_y
    else:
        p1_x, p1_y = p1.projected_x, p1.projected_y

    if p2.projected_x is None or p2.projected_y is None:
        proj2 = projector.project_point(p2.latitude, p2.longitude)
        p2_x, p2_y = proj2.projected_x, proj2.projected_y
    else:
        p2_x, p2_y = p2.projected_x, p2.projected_y

    # Project gate line
    g1_proj = projector.project_point(gate_line[0][0], gate_line[0][1])
    g2_proj = projector.project_point(gate_line[1][0], gate_line[1][1])
    g1_x, g1_y = g1_proj.projected_x, g1_proj.projected_y
    g2_x, g2_y = g2_proj.projected_x, g2_proj.projected_y

    # Line intersection math
    denom = (p2_x - p1_x) * (g2_y - g1_y) - (p2_y - p1_y) * (g2_x - g1_x)
    if denom == 0:
        return None

    ua = ((g2_x - g1_x) * (p1_y - g1_y) - (g2_y - g1_y) * (p1_x - g1_x)) / denom
    ub = ((p2_x - p1_x) * (p1_y - g1_y) - (p2_y - p1_y) * (p1_x - g1_x)) / denom

    if 0 <= ua <= 1 and 0 <= ub <= 1:
        # Intersection found between p1 and p2
        seconds_diff = (p2.time - p1.time).total_seconds()
        intersection_time = p1.time + datetime.timedelta(seconds=ua * seconds_diff)
        return intersection_time

    return None


class PolygonHelper:
    def __init__(self, projector):
        self.projector = projector
        self._bounds_cache = {}

    def build_polygon(self, path):
        """
        path is expected to be a list of [lng, lat] coordinates (GeoJSON style)
        """
        line = []
        for element in path:
            p = self.projector.project_point(element[1], element[0])
            line.append((p.projected_x, p.projected_y))
        return Polygon(line)

    def check_inside_polygons(
        self,
        polygons: list[tuple[int, Polygon]],
        projected_x: Optional[float] = None,
        projected_y: Optional[float] = None,
    ) -> list[int]:
        """
        Returns a list of PKs of the polygons the position is inside.
        """
        if projected_x is None or projected_y is None:
            raise ValueError(f"Position is missing projected coordinates")
        x, y = projected_x, projected_y

        p = Point(x, y)
        incursions = []
        for zone_pk, poly in polygons:
            if poly not in self._bounds_cache:
                self._bounds_cache[poly] = poly.bounds

            minx, miny, maxx, maxy = self._bounds_cache[poly]
            if not (minx <= x <= maxx and miny <= y <= maxy):
                continue
            if poly.contains(p):
                incursions.append(zone_pk)
        return incursions

    def distance_from_point_to_polygons(
        self,
        polygons: list[tuple[str, Polygon]],
        projected_x: Optional[float] = None,
        projected_y: Optional[float] = None,
    ) -> dict[str, float]:
        """
        Returns a mapping of polygon IDs to Euclidean distance in meters.
        """
        if projected_x is None or projected_y is None:
            raise ValueError(f"Position is missing projected coordinates")
        x, y = projected_x, projected_y

        p = Point(x, y)
        distances = {}
        for name, polygon in polygons:
            distances[name] = polygon.exterior.distance(p)
        return distances

    def time_to_intersection(
        self,
        polygons: list[tuple[str, Polygon]],
        bearing: float,
        speed: float,
        turning_rate: float,
        lookahead_seconds: int,
        lookahead_step: int = 2,
        from_inside: bool = False,
        projected_x: float = None,
        projected_y: float = None,
    ) -> dict[str, float]:
        """
        Returns the number of seconds until a possible intersect of any polygon from the current position with projected speed and turning rate
        """
        if projected_x is None or projected_y is None:
            raise ValueError(f"Position is missing projected coordinates")
        start_x, start_y = projected_x, projected_y

        speed_per_second = 1852 * speed / 3600  # m/s
        intersection_times = {}

        # Fast distance check first
        distances = self.distance_from_point_to_polygons(polygons, projected_x, projected_y)
        maximum_distance = speed_per_second * lookahead_seconds

        remaining_polygons = []
        for name, poly in polygons:
            if distances.get(name, float("inf")) <= maximum_distance:
                remaining_polygons.append((name, poly))
            else:
                intersection_times[name] = lookahead_seconds

        if not remaining_polygons:
            return intersection_times

        current_x, current_y = start_x, start_y
        current_bearing = bearing

        for second in range(lookahead_step, lookahead_seconds + 1, lookahead_step):
            if len(intersection_times) == len(polygons):
                break

            # Project path in metric space directly!
            # Use basic trigonometry on the metric AEQD plane.
            # Bearing is from North, clockwise.
            # x = east, y = north
            current_bearing = (current_bearing + turning_rate * lookahead_step) % 360
            dist = speed_per_second * lookahead_step

            next_x = current_x + dist * np.sin(np.deg2rad(current_bearing))
            next_y = current_y + dist * np.cos(np.deg2rad(current_bearing))

            line_segment = LineString([(current_x, current_y), (next_x, next_y)])

            current_x, current_y = next_x, next_y

            for name, poly in remaining_polygons:
                if name not in intersection_times:
                    intersects = line_segment.intersects(poly)
                    if (not from_inside and intersects) or (from_inside and not intersects):
                        intersection_times[name] = second

        return intersection_times


def get_shortest_intersection_time(
    track: list[ContestantReceivedPosition],
    polygon_helper: PolygonHelper,
    zone_polygons: list[tuple[str, Polygon]],
    lookahead_seconds: int,
    from_inside: bool = False,
) -> float:
    if len(track) > 3:
        last_pos = track[-1]
        prev_pos = track[-3]

        time_diff = (last_pos.time - prev_pos.time).total_seconds()
        if time_diff > 0:
            turning_rate = bearing_difference(prev_pos.course, last_pos.course) / time_diff
        else:
            turning_rate = 0

        intersection_times = polygon_helper.time_to_intersection(
            zone_polygons,
            last_pos.course,
            last_pos.speed,
            turning_rate,
            lookahead_seconds,
            from_inside=from_inside,
            projected_x=getattr(last_pos, "projected_x", None),
            projected_y=getattr(last_pos, "projected_y", None),
        )
        return min([lookahead_seconds] + list(intersection_times.values()))
    return lookahead_seconds
