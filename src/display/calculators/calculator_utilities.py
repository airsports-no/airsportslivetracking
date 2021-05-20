from shapely.geometry import Polygon, Point

import cartopy.crs as ccrs
import datetime
from typing import Tuple, List, Dict

from display.coordinate_utilities import cross_track_distance, along_track_distance, calculate_distance_lat_lon, \
    calculate_bearing


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


def round_time(dt=None, round_to=60):
    """Round a datetime object to any time laps in seconds
    dt : datetime.datetime object, default now.
    roundTo : Closest number of seconds to round to, default 1 minute.
    Author: Thierry Husson 2012 - Use it as you want but don't blame me.
    """
    if dt is None: dt = datetime.datetime.now()
    seconds = (dt.replace(tzinfo=None) - dt.min).seconds
    rounding = (seconds + round_to / 2) // round_to * round_to
    return dt + datetime.timedelta(0, rounding - seconds, -dt.microsecond)


class PolygonHelper:
    def __init__(self):
        self.pc = ccrs.PlateCarree()
        self.epsg = ccrs.epsg(3857)

    def build_polygon(self, zone):
        line = []
        for element in zone.path:
            line.append(self.epsg.transform_point(*list(reversed(element)), ccrs.PlateCarree()))
        return Polygon(line)

    def check_inside_polygons(self, polygons: Dict[str, Polygon], latitude, longitude) -> List[str]:
        """
        Returns a list of names of the prohibited zone is the position is inside
        """
        x, y = self.epsg.transform_point(longitude, latitude, self.pc)
        p = Point(x, y)
        incursions = []
        for name, zone in polygons.items():
            if zone.contains(p):
                incursions.append(name)
        return incursions
