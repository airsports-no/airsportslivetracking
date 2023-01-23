import numpy as np
from shapely.geometry import Polygon, Point, LineString

import cartopy.crs as ccrs
import datetime
from typing import Tuple, List, Dict

from display.calculators.positions_and_gates import Position
from display.coordinate_utilities import cross_track_distance, along_track_distance, calculate_distance_lat_lon, \
    calculate_bearing, utm_from_lat_lon, project_position_lat_lon, bearing_difference


def cross_track_gate(gate1, gate2, position) -> float:
    """

    :param gate1:
    :param gate2:
    :param position:
    :return: The cross track distance in metres
    """
    return cross_track_distance(gate1.latitude, gate1.longitude, gate2.latitude, gate2.longitude, position.latitude,
                                position.longitude)


def along_track_gate(gate1, cross_track_distance, position):
    return along_track_distance(gate1.latitude, gate1.longitude, position.latitude,
                                position.longitude, cross_track_distance)


def distance_between_gates(gate1, gate2):
    return calculate_distance_lat_lon((gate1.latitude, gate1.longitude), (gate2.latitude, gate2.longitude))


def bearing_between(gate1, gate2):
    return calculate_bearing((gate1.latitude, gate1.longitude), (gate2.latitude, gate2.longitude))


def load_track_points_traccar_csv(points: List[Tuple[datetime.datetime, float, float]]):
    positions = []
    for point in points:
        positions.append(
            {"time": point[0].isoformat(),
             "latitude": point[1], "longitude": point[2],
             "altitude": 0, "speed": 0, "course": 0, "battery_level": 100})
    return positions


def round_time_minute(dt=None, round_to=60):
    """Round a datetime object to any time laps in seconds
    dt : datetime.datetime object, default now.
    roundTo : Closest number of seconds to round to, default 1 minute.
    Author: Thierry Husson 2012 - Use it as you want but don't blame me.
    """
    if dt is None: dt = datetime.datetime.now()
    seconds = (dt.replace(tzinfo=None) - dt.min).seconds
    rounding = (seconds + round_to / 2) // round_to * round_to
    return dt + datetime.timedelta(0, rounding - seconds, -dt.microsecond)

def round_time_second(obj: datetime.datetime) -> datetime.datetime:
    if obj.microsecond >= 500_000:
        obj += datetime.timedelta(seconds=1)
    return obj.replace(microsecond=0)

class PolygonHelper:
    def __init__(self, latitude, longitude):
        self.pc = ccrs.PlateCarree()
        self.utm = utm_from_lat_lon(latitude, longitude)

    def build_polygon(self, path):
        line = []
        for element in path:
            line.append(self.utm.transform_point(*list(reversed(element)), self.pc))
        return Polygon(line)

    def check_inside_polygons(self, polygons: List[Tuple[str, Polygon]], latitude, longitude) -> List[str]:
        """
        Returns a list of names of the prohibited zone is the position is inside
        """
        x, y = self.utm.transform_point(longitude, latitude, self.pc)
        p = Point(x, y)
        incursions = []
        for name, zone in polygons:
            if zone.contains(p):
                incursions.append(name)
        return incursions

    def distance_from_point_to_polygons(self, polygons: List[Tuple[str, Polygon]], latitude, longitude) -> Dict[
        str, float]:
        """

        :param polygons:
        :param latitude:
        :param longitude:
        :return:  distance in metres
        """
        x, y = self.utm.transform_point(longitude, latitude, self.pc)
        p = Point(x, y)
        distances = {}
        for name, polygon in polygons:
            distances[name] = polygon.exterior.distance(p)
        return distances

    def time_to_intersection(self, polygons: List[Tuple[str, Polygon]], latitude: float, longitude: float,
                             bearing: float, speed: float, turning_rate: float, lookahead_seconds: int,
                             lookahead_step: int = 2, from_inside: bool = False) -> Dict[
        str, float]:
        """
        Returns the number of seconds until a possible intersect of any polygon from the current position with projected speed and turning rate

        :param reverse: If true, the searches performed backwards. This finds the last item that is within the polygon and can be used to find the intersection from inside a polygon looking out
        :param polygons:
        :param latitude:
        :param longitude:
        :param bearing: degrees
        :param speed: knots
        :param turning_rate: degrees per second
        :param lookahead_seconds: How far ahead to extrapolate the trajectory
        """
        previous_longitude = longitude
        previous_latitude = latitude
        speed_per_second = 1852 * speed / 3600  # m/s
        intersection_times = {}
        maximum_distance = speed_per_second * lookahead_seconds
        distances = self.distance_from_point_to_polygons(polygons, latitude, longitude)
        for name, distance in distances.items():
            if distance > maximum_distance:
                intersection_times[name] = None
        for second in range(lookahead_step, lookahead_seconds, lookahead_step):
            if len(intersection_times) == len(polygons):
                break
            projected_latitude, projected_longitude = project_position_lat_lon((previous_latitude, previous_longitude),
                                                                               (bearing + second * turning_rate) % 360,
                                                                               speed_per_second * lookahead_step)
            line_string = LineString(
                self.utm.transform_points(self.pc, np.array([previous_longitude, projected_longitude]),
                                          np.array([previous_latitude, projected_latitude])))
            previous_latitude = projected_latitude
            previous_longitude = projected_longitude
            for name, polygon in polygons:
                if name not in intersection_times:
                    if (not from_inside and line_string.intersects(polygon)) or (
                            from_inside and not line_string.intersects(polygon)):
                        intersection_times[name] = second
        for key in list(intersection_times.keys()):
            if not intersection_times[key]:
                del intersection_times[key]
        return intersection_times


def project_position(latitude: float, longitude: float, course: float, turning_rate: float, speed: float,
                     seconds: float) -> Tuple[
    float, float]:
    """

    :param seconds: Number of seconds into the future to project the position
    :param latitude:
    :param longitude:
    :param turning_rate: degrees/second
    :param speed: knots
    :return: new position
    """
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


def get_shortest_intersection_time(track: List["Position"], polygon_helper: PolygonHelper,
                                   zone_polygons: List[Tuple[str, Polygon]], lookahead_seconds: int,
                                   from_inside: bool = False) -> float:
    if len(track) > 3:
        turning_rate = bearing_difference(track[-3].course, track[-1].course) / (
                track[-1].time - track[-3].time).total_seconds()
        intersection_times = polygon_helper.time_to_intersection(zone_polygons, track[-1].latitude,
                                                                 track[-1].longitude, track[-1].course,
                                                                 track[-1].speed, turning_rate,
                                                                 lookahead_seconds, from_inside=from_inside)
        # for zone, distance in intersection_times.items():
        #     logger.debug(f"{zone}:{distance}")
        return min([lookahead_seconds] + list(intersection_times.values()))
    return lookahead_seconds
