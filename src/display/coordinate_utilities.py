import datetime

import cartopy.crs as ccrs
import logging
import math
from typing import Tuple, Optional, List

import utm
from geopy.distance import geodesic, great_circle
import nvector as nv
import numpy as np

R = 6371000  # metres

logger = logging.getLogger(__name__)


def utm_from_lon(lon):
    """
    utm_from_lon - UTM zone for a longitude
    Not right for some polar regions (Norway, Svalbard, Antartica)
    :param float lon: longitude
    :return: UTM zone number
    :rtype: int
    """

    return np.floor((lon + 180) / 6) + 1


def utm_from_lat_lon(lat, lon) -> ccrs.CRS:
    """
    utm_from_lon - UTM zone for a longitude
    Not right for some polar regions (Norway, Svalbard, Antartica)
    :param float lon: longitude
    :return: UTM zone number
    :rtype: int
    """
    _, _, zone, letter = utm.from_latlon(lat, lon)
    print(zone)
    print(letter)
    return ccrs.UTM(zone, southern_hemisphere=lat < 0)


class UtmXy:
    def __init__(self, lat, lon):
        self.utm = utm_from_lat_lon(lat, lon)
        self.proj = ccrs.PlateCarree()

    def to_xy(self, lat, lon) -> Tuple[float, float]:
        return self.utm.transform_point(lon, lat, self.proj)

    def to_lat_lon(self, x, y) -> Tuple[float, float]:
        return tuple(reversed(self.proj.transform_point(x, y, self.utm)))


def to_rad(value) -> float:
    return value * math.pi / 180


def to_deg(value) -> float:
    return 180 * value / math.pi


def dot_v(A: np.ndarray, B: np.ndarray, axis=0) -> np.ndarray:
    """
    Return the dot product of each vector in A and B
    :param axis:
    :return:
    """
    # return np.einsum('ij,ij->j', norm_v(A),norm_v(B))
    #
    # todo: Should the matrixes be normalised first? It seems wrong.
    return (A * B).sum(axis=axis)


def norm_v(A: np.ndarray, axis=0) -> np.ndarray:
    return A / len_v(A, axis=axis)


def len_v(A: np.ndarray, axis=0) -> np.ndarray:
    return np.sqrt(dot_v(A, A, axis=axis))


def ang_v(A: np.ndarray, B: np.ndarray, axis=0, radians=True) -> np.ndarray:
    """
    Find the angle between arrays A and B along the provided axis
    """
    # return ang_v_test2(A, B, axis, radians)
    factor = 1
    A = norm_v(A)
    B = norm_v(B)
    if not radians:
        factor = 180 / np.pi
    # return np.math.atan2(np.linalg.det([A, B]), np.dot(A,B))*factor
    return np.arccos(np.clip(dot_v(A, B, axis=axis), -1, 1)) * factor


def bearing_difference(bearing1, bearing2) -> float:
    return (bearing2 - bearing1 + 540) % 360 - 180


def equirectangular_distance(
        start: Tuple[float, float], finish: Tuple[float, float]
) -> float:
    """

    :param start: degrees
    :param finish: degrees
    :return: Distance in metres
    """
    avg_lat = to_rad((start[0] + finish[0]) / 2)
    x = to_rad(finish[1] - start[1]) * math.cos(avg_lat)
    y = to_rad(finish[0] - start[0])
    return math.sqrt(x ** 2 + y ** 2) * R


def calculate_distance_lat_lon(
        start: Tuple[float, float], finish: Tuple[float, float]
) -> float:
    """

    :param start: degrees
    :param finish: degrees
    :return: Distance in metres
    """
    return geodesic(start, finish).km * 1000  # This is the most correct
    # return great_circle(start, finish).km * 1000  # This is closer to flight contest
    # This is what flight contest uses
    # latitude_difference = finish[0] - start[0]
    # longitude_difference = finish[1] - start[1]
    # latitude_distance = 60 * latitude_difference
    # longitude_distance = 60 * longitude_difference * math.cos(to_rad((start[0] + finish[0]) / 2))
    # return math.sqrt(latitude_distance ** 2 + longitude_distance ** 2)*1852


def calculate_speed_between_points(start: Tuple[float, float], finish: Tuple[float, float], time1: datetime.datetime,
                                   time2: datetime.datetime) -> float:
    distance = calculate_distance_lat_lon(start, finish) / 1852  # nm
    hours = (time2 - time1).total_seconds() / 3600
    return distance / hours


def calculate_bearing(start: Tuple[float, float], finish: Tuple[float, float]) -> float:
    la1 = start[0] * math.pi / 180
    lo1 = start[1] * math.pi / 180
    la2 = finish[0] * math.pi / 180
    lo2 = finish[1] * math.pi / 180
    y = math.sin(lo2 - lo1) * math.cos(la2)
    x = math.cos(la1) * math.sin(la2) - math.sin(la1) * math.cos(la2) * math.cos(
        lo2 - lo1
    )
    brng = math.atan2(y, x) * 180 / math.pi
    return (brng + 360) % 360


def calculate_fractional_distance_point_lat_lon(
        start: Tuple[float, float], finish: Tuple[float, float], fraction: float
) -> Tuple[float, float]:
    R = 6371000  # metres
    la1 = start[0] * math.pi / 180
    lo1 = start[1] * math.pi / 180
    la2 = finish[0] * math.pi / 180
    lo2 = finish[1] * math.pi / 180
    distance = calculate_distance_lat_lon(start, finish)
    angularDistance = distance / R
    a = math.sin((1 - fraction) * angularDistance) / math.sin(angularDistance)
    b = math.sin(fraction * angularDistance) / math.sin(angularDistance)
    x = a * math.cos(la1) * math.cos(lo1) + b * math.cos(la2) * math.cos(lo2)
    y = a * math.cos(la1) * math.sin(lo1) + b * math.cos(la2) * math.sin(lo2)
    z = a * math.sin(la1) + b * math.sin(la2)
    finalLatitude = math.atan2(z, math.sqrt(x * x + y * y)) * 180 / math.pi
    finalLongitude = math.atan2(y, x) * 180 / math.pi
    return (finalLatitude, finalLongitude)


def get_centre_of_line_lat_lon(
        start: Tuple[float, float], finish: Tuple[float, float]
) -> Tuple[float, float]:
    return calculate_fractional_distance_point_lat_lon(start, finish, 0.5)


def normalise_latitude(latitude: np.ndarray) -> np.ndarray:
    latitude = latitude * np.pi / 180
    return np.arctan(np.sin(latitude) / np.abs(np.cos(latitude))) * 180 / np.pi


def normalise_longitude(longitude: np.ndarray) -> np.ndarray:
    longitude = longitude * np.pi / 180
    return np.arctan2(np.sin(longitude), np.cos(longitude)) * 180 / np.pi


def project_position_lat_lon(
        start: Tuple[float, float], bearing: float, distance: float
) -> Tuple[float, float]:
    """

    :param start: Starting position to project from
    :param bearing: Direction to predicted point (degrees)
    :param distance: Distance to predict the point (m)
    :return:
    """
    earthRadiusInMetres = 6378137.0
    distanceInMetres = distance
    angularDistance = distanceInMetres / earthRadiusInMetres
    temporaryHeading = bearing * math.pi / 180
    latitude, longitude = start
    latitude *= math.pi / 180
    longitude *= math.pi / 180
    newLatitude = math.asin(
        math.sin(latitude) * math.cos(angularDistance)
        + math.cos(latitude) * math.sin(angularDistance) * math.cos(temporaryHeading)
    )
    newLongitude = longitude + math.atan2(
        math.sin(temporaryHeading) * math.sin(angularDistance) * math.cos(latitude),
        math.cos(angularDistance) - math.sin(latitude) * math.sin(newLatitude),
    )
    newLatitude *= 180 / np.pi
    newLongitude *= 180 / np.pi
    return normalise_latitude(newLatitude), normalise_longitude(newLongitude)


def extend_line(
        start: Tuple[float, float], finish: Tuple[float, float], distance: float
) -> Optional[Tuple[Tuple[float, float], Tuple[float, float]]]:
    """

    :param start: degrees
    :param finish: degrees
    :param distance: nauticalMiles
    :return:
    """
    if distance == 0:
        return None
    line_length = calculate_distance_lat_lon(start, finish)
    distance_scale = 1852 * distance / (2 * line_length)
    new_finish = calculate_fractional_distance_point_lat_lon(
        start, finish, 1 + distance_scale
    )
    new_start = calculate_fractional_distance_point_lat_lon(
        finish, start, 1 + distance_scale
    )
    return new_start, new_finish


def line_intersect(x1, y1, x2, y2, x3, y3, x4, y4):
    # Check if none of the lines are of length 0
    if (x1 == x2 and y1 == y2) or (x3 == x4 and y3 == y4):
        return None

    denominator = (y4 - y3) * (x2 - x1) - (x4 - x3) * (y2 - y1)
    # Lines are parallel
    if denominator == 0:
        return None
    ua = ((x4 - x3) * (y1 - y3) - (y4 - y3) * (x1 - x3)) / denominator
    ub = ((x2 - x1) * (y1 - y3) - (y2 - y1) * (x1 - x3)) / denominator

    # is the intersection along the segments
    if ua < 0 or ua > 1 or ub < 0 or ub > 1:
        return None

    # Return a object with the x and y coordinates of the intersection
    x = x1 + ua * (x2 - x1)
    y = y1 + ua * (y2 - y1)

    return x, y


import pyproj
from pyproj import CRS, Transformer
from shapely.geometry import Point
from shapely.ops import transform
from functools import partial


class Projector:
    def __init__(self, latitude, longitude):
        WGS84 = CRS.from_string("epsg:4326")
        proj4str = "+proj=aeqd +lat_0=%s +lon_0=%s +x_0=0 +y_0=0" % (
            latitude,
            longitude,
        )
        AEQD = CRS.from_proj4(proj4str)
        self.to_projection = Transformer.from_crs(WGS84, AEQD, always_xy=True)
        self.from_projection = Transformer.from_crs(AEQD, WGS84, always_xy=True)

    def intersect(self, start1, stop1, start2, stop2):
        start1 = self.to_projection.transform(*reversed(start1))
        stop1 = self.to_projection.transform(*reversed(stop1))
        start2 = self.to_projection.transform(*reversed(start2))
        stop2 = self.to_projection.transform(*reversed(stop2))

        intersection = line_intersect(*start1, *stop1, *start2, *stop2)
        if intersection is None:
            return None
        converted = self.from_projection.transform(*intersection)
        return converted[1], converted[0]


def nv_intersect(start1, stop1, start2, stop2, on_segments: bool = False):
    pointA1 = nv.GeoPoint(start1[0], start1[1], degrees=True)
    pointA2 = nv.GeoPoint(stop1[0], stop1[1], degrees=True)
    pointB1 = nv.GeoPoint(start2[0], start2[1], degrees=True)
    pointB2 = nv.GeoPoint(stop2[0], stop2[1], degrees=True)
    pathA = nv.GeoPath(pointA1, pointA2)
    pathB = nv.GeoPath(pointB1, pointB2)
    if pathA == pathB:
        return None
    c = pathA.intersect(pathB)
    c_geo = c.to_geo_point()
    m1 = (c_geo.latitude_deg - start1[0]) / (c_geo.longitude_deg - start1[1])
    m2 = (c_geo.latitude_deg - stop1[0]) / (c_geo.longitude_deg - stop1[1])
    if m1 == m2 or not on_segments:
        return c_geo.latitude_deg, c_geo.longitude_deg
    return None


def fraction_of_leg(start, finish, intersect_point):
    return calculate_distance_lat_lon(
        start, intersect_point
    ) / calculate_distance_lat_lon(start, finish)


def get_heading_difference(heading1, heading2):
    """
    From first heading to 2nd heading
    :param heading1:
    :param heading2:
    :return:
    """
    return (heading2 - heading1 + 540) % 360 - 180


def cross_track_distance(lat1, lon1, lat2, lon2, lat, lon) -> float:
    """

    :param lat1:
    :param lon1:
    :param lat2:
    :param lon2:
    :param lat:
    :param lon:
    :return: The cross track distance in metres
    """
    angular_distance13 = calculate_distance_lat_lon((lat1, lon1), (lat, lon)) / R
    first_bearing = calculate_bearing((lat1, lon1), (lat, lon)) * math.pi / 180
    second_bearing = calculate_bearing((lat1, lon1), (lat2, lon2)) * math.pi / 180
    return (
            math.asin(
                math.sin(angular_distance13) * math.sin(first_bearing - second_bearing)
            )
            * R
    )


def along_track_distance(lat1, lon1, lat, lon, cross_track_distance):
    angular_distance13 = calculate_distance_lat_lon((lat1, lon1), (lat, lon)) / R
    try:
        return (
                math.acos(math.cos(angular_distance13) / math.cos(cross_track_distance / R))
                * R
        )
    except:
        # try:
        #     logger.exception("Something failed when calculating along track distance: {} {} {}".format(
        #         math.cos(angular_distance13), math.cos(cross_track_distance),
        #         math.cos(angular_distance13) / math.cos(cross_track_distance / R)))
        # except:
        #     logger.exception("Failed even printing the error message")
        return 999999999999


def get_procedure_turn_track(
        latitude, longitude, bearing_in, bearing_out, turn_radius
) -> List[Tuple[float, float]]:
    """

    :param latitude: TP degrees
    :param longitude: TP degrees
    :param bearing_in: degrees inbound track
    :param bearing_out: degrees outbound track
    :param turn_radius: Radius of procedure turn in NM
    :return: List of (lat, lon) points that make up the turn
    """
    turn_radius *= 1852
    bearing_difference = get_heading_difference(bearing_in, bearing_out)
    if bearing_difference > 0:
        bearing_difference -= 360
    else:
        bearing_difference += 360
    inner_angle_rad = to_rad(abs(bearing_difference) - 180)
    centre_distance = turn_radius / np.sin(inner_angle_rad / 2)
    tangent_distance = centre_distance * np.cos(inner_angle_rad / 2)
    circle_resolution = np.pi / 20
    slice_angle = np.pi + inner_angle_rad
    slice_length = 2 * turn_radius * np.sin(circle_resolution / 2)
    initial_point = project_position_lat_lon(
        (latitude, longitude), bearing_in, tangent_distance
    )
    points_list = [(latitude, longitude), initial_point]
    current_angle = 0
    if bearing_difference > 0:
        while current_angle < slice_angle:
            current_angle += circle_resolution
            bearing = (bearing_in + to_deg(current_angle)) % 360
            nextpoint = project_position_lat_lon(points_list[-1], bearing, slice_length)
            points_list.append(nextpoint)
    else:
        while current_angle > -slice_angle:
            current_angle -= circle_resolution
            bearing = (bearing_in + to_deg(current_angle)) % 360
            nextpoint = project_position_lat_lon(points_list[-1], bearing, slice_length)
            points_list.append(nextpoint)

    points_list.append((latitude, longitude))
    return points_list


def rotate_vector_angle(x, y, degrees):
    # Rotation is counterclockwise for positive angles, so negate the angle to make it make sense
    rad = -to_rad(degrees)
    return np.array(
        [x * np.cos(rad) - y * np.sin(rad), x * np.sin(rad) + y * np.cos(rad)]
    )


def create_rounded_corridor_corner(
        bisecting_line: Tuple[Tuple[float, float], Tuple[float, float]],
        corridor_width: float,
        corner_degrees: float,
) -> Tuple[List[Tuple[float, float]], List[Tuple[float, float]], Tuple[Tuple[float, float], Tuple[float, float]]]:
    """
    Create a rounded line for the left and right corridor walls for the turn described by the bisecting line

    :param left_turn: If left turn, the first coordinate of the bisecting line is the inside corner, otherwise the
    second coordinate is the inside corner
    :param corridor_width: The width of the corridor NM
    :param corner_degrees: The number of degrees for the turn
    :param bisecting_line: The line that bisects the middle of the turn
    :return: List of points that make up the left-hand corridor line, list of points that make up the right-hand corridor line (lon, lat), the new gate line
    """
    if corner_degrees == 0:
        return [bisecting_line[0]], [bisecting_line[1]]
    print(f"bisecting_line: {bisecting_line}")
    print(f"turn_degrees: {corner_degrees}")
    corridor_width_metres = corridor_width * 1852
    left_turn = corner_degrees < 0
    turn_degrees = corner_degrees
    if left_turn:
        bisection_bearing = calculate_bearing(*bisecting_line)
        circle_centre = bisecting_line[0]
        circle_perimeter = bisecting_line[1]
    else:
        bisection_bearing = calculate_bearing(*list(reversed(bisecting_line)))
        circle_centre = bisecting_line[1]
        circle_perimeter = bisecting_line[0]
    corrected_gate_line_perimeter = calculate_fractional_distance_point_lat_lon(circle_centre, circle_perimeter,
                                                                                corridor_width_metres / calculate_distance_lat_lon(
                                                                                    circle_centre, circle_perimeter))
    corrected_gate_line = (circle_centre, corrected_gate_line_perimeter)
    initial_offset = -1 * turn_degrees / 2
    pc = ccrs.PlateCarree()
    utm = utm_from_lat_lon(*circle_centre)
    centre = np.array(utm.transform_point(*reversed(circle_centre), pc))
    perimeter = np.array(utm.transform_point(*reversed(circle_perimeter), pc))

    unit_circle = perimeter - centre
    bisection_length = len_v(unit_circle)

    bisection_corridor_difference = (bisection_length - corridor_width_metres) / 2
    # We override everything to set the inner portion of the turn to be just the angle. This makes the turn lineup better with the other terms.focus of

    bisection_corridor_difference = 1
    unit_circle = norm_v(unit_circle)
    # turn_radius = bisection_length / 2
    turn_radius = 0

    new_centre = (
                         norm_v(rotate_vector_angle(unit_circle[0], unit_circle[1], 180)) * turn_radius
                 ) + centre

    track_point = unit_circle

    starting_point = norm_v(
        rotate_vector_angle(track_point[0], track_point[1], initial_offset)
    )
    outer_edge = []
    inner_edge = []
    for angle in np.arange(0, turn_degrees, turn_degrees / 10):
        rotated = norm_v(
            rotate_vector_angle(starting_point[0], starting_point[1], angle)
        )
        outer_edge.append(
            (
                    rotated
                    * (turn_radius + bisection_corridor_difference + corridor_width_metres)
            )
            + new_centre
        )
        inner_edge.append(
            (rotated * (turn_radius + bisection_corridor_difference)) + new_centre
        )
    if left_turn:
        left_edge = np.array(inner_edge)
        right_edge = np.array(outer_edge)
    else:
        right_edge = np.array(inner_edge)
        left_edge = np.array(outer_edge)
    print(f"left_edge: {left_edge}")
    print(f"left_edge.shape: {left_edge.shape}")
    left_edge_lonlat = pc.transform_points(utm, left_edge[:, 0], left_edge[:, 1])
    right_edge_lonlat = pc.transform_points(utm, right_edge[:, 0], right_edge[:, 1])
    left_edge_lonlat[:, [0, 1]] = left_edge_lonlat[:, [1, 0]]
    right_edge_lonlat[:, [0, 1]] = right_edge_lonlat[:, [1, 0]]
    print(f"left_edge_lonlat: {left_edge_lonlat}")
    print(f"left_edge_lonlat.shape: {left_edge_lonlat.shape}")
    return left_edge_lonlat[:, :2].tolist(), right_edge_lonlat[:, :2].tolist(), corrected_gate_line


def create_bisecting_line_between_segments(x1, y1, x2, y2, x3, y3, length):
    """

    :param x1:
    :param y1:
    :param x2:
    :param y2:
    :param x3:
    :param y3:
    :param length: metres
    :return:
    """
    transformer = UtmXy(y2, x2)
    x1, y1 = transformer.to_xy(y1, x1)
    x2, y2 = transformer.to_xy(y2, x2)
    x3, y3 = transformer.to_xy(y3, x3)
    d1 = norm_v(np.array([x2 - x1, y2 - y1])) * length / 2
    d2 = norm_v(np.array([x2 - x3, y2 - y3])) * length / 2
    dx, dy = d1[0] + d2[0], d1[1] + d2[1]
    y1, x1 = transformer.to_lat_lon(x2 + dx, y2 + dy)
    y2, x2 = transformer.to_lat_lon(x2 - dx, y2 - dy)
    return [[x1, y1], [x2, y2]]


def create_bisecting_line_between_segments_corridor_width_lonlat(
        x1, y1, x2, y2, x3, y3, corridor_width
):
    """

    :param x1:
    :param y1:
    :param x2:
    :param y2:
    :param x3:
    :param y3:
    :param length: metres
    :return:
    """
    b1 = calculate_bearing((y1, x1), (y2, x2))
    b2 = calculate_bearing((y2, x2), (y3, x3))
    diff = bearing_difference(b1, b2)
    transformer = UtmXy(y2, x2)
    x1, y1 = transformer.to_xy(y1, x1)
    x2, y2 = transformer.to_xy(y2, x2)
    x3, y3 = transformer.to_xy(y3, x3)
    s, f = create_bisecting_line_between_segments_corridor_width_xy(
        x1, y1, x2, y2, x3, y3, corridor_width
    )
    y1, x1 = transformer.to_lat_lon(*s)
    y2, x2 = transformer.to_lat_lon(*f)
    line = [[x1, y1], [x2, y2]]
    if diff < 0:
        line.reverse()
    return line


def create_bisecting_line_between_segments_corridor_width_xy(
        x1, y1, x2, y2, x3, y3, corridor_width
):
    """

    :param x1:
    :param y1:
    :param x2:
    :param y2:
    :param x3:
    :param y3:
    :param length: metres
    :return: lon, lat
    """
    l1 = np.array([x1, y1])
    l2 = np.array([x2, y2])
    l3 = np.array([x3, y3])
    a = l2 - l1
    b = l2 - l3
    bisection_angle = ang_v(a, b) / 2
    # print(f'bisection_angle: {bisection_angle}')
    segment_length = (corridor_width / 2) / np.sin(bisection_angle)
    # print(f'segment_length: {segment_length}')
    d = norm_v(norm_v(a) + norm_v(b))
    if any(np.isnan(d)):
        return create_perpendicular_line_at_end_xy(x1, y1, x2, y2, corridor_width)
    d *= segment_length
    x1, y1 = x2 + d[0], y2 + d[1]
    x2, y2 = x2 - d[0], y2 - d[1]
    return [[x1, y1], [x2, y2]]


def create_perpendicular_line_at_end_lonlat(x1, y1, x2, y2, length):
    """

    :param x1:
    :param y1:
    :param x2:
    :param y2:
    :param length: metres
    :return: Line with coordinate order longitude, Latitude
    """
    transformer = UtmXy(y1, x1)
    x1, y1 = transformer.to_xy(y1, x1)
    x2, y2 = transformer.to_xy(y2, x2)
    l1, l2 = create_perpendicular_line_at_end_xy(x1, y1, x2, y2, length)
    y1, x1 = transformer.to_lat_lon(*l1)
    y2, x2 = transformer.to_lat_lon(*l2)
    return [[x1, y1], [x2, y2]]


def create_perpendicular_line_at_end_xy(x1, y1, x2, y2, length):
    """

    :param x1:
    :param y1:
    :param x2:
    :param y2:
    :param length: metres
    :return:
    """
    l1 = np.array([x1, y1])
    l2 = np.array([x2, y2])
    a = norm_v(l2 - l1)
    b = norm_v(np.array([-a[1], a[0]])) * length / 2
    # slope = (y2 - y1) / (x2 - x1)
    # dy = math.sqrt((length / 2) ** 2 / (slope ** 2 + 1))
    # dx = -slope * dy
    # x1, y1 = x2 + dx, y2 + dy
    # x2, y2 = x2 - dx, y2 - dy
    x1, y1 = x2 + b[0], y2 + b[1]
    x2, y2 = x2 - b[0], y2 - b[1]
    return [[x1, y1], [x2, y2]]


def calculate_bounding_box(
        centre: Tuple[float, float], radius: float
) -> Tuple[float, float, float, float]:
    """

    :param centre: degrees
    :param radius: metres
    :return: most_south, most_west, most_north, most_east
    """
    dy = 360 * radius / R
    dx = dy * np.cos(to_rad(centre[0]))
    return centre[0] - dy, centre[1] - dx, centre[0] + dy, centre[1] + dx
