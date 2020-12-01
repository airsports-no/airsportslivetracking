import logging
import math
from typing import Tuple
from geopy import distance

R = 6371000  # metres

logger = logging.getLogger(__name__)


def calculate_distance_lat_lon(start: Tuple[float, float], finish: Tuple[float, float]) -> float:
    """

    :param start:
    :param finish:
    :return: Distance in metres
    """
    return distance.distance(start, finish).km * 1000


def calculate_bearing(start: Tuple[float, float], finish: Tuple[float, float]) -> float:
    la1 = start[0] * math.pi / 180
    lo1 = start[1] * math.pi / 180
    la2 = finish[0] * math.pi / 180
    lo2 = finish[1] * math.pi / 180
    y = math.sin(lo2 - lo1) * math.cos(la2)
    x = math.cos(la1) * math.sin(la2) - math.sin(la1) * math.cos(la2) * math.cos(lo2 - lo1)
    brng = math.atan2(y, x) * 180 / math.pi
    return (brng + 360) % 360


def calculate_fractional_distance_point_lat_lon(start: Tuple[float, float], finish: Tuple[float, float],
                                                fraction: float) -> Tuple[
    float, float]:
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


def line_intersect(x1, y1, x2, y2, x3, y3, x4, y4):
    # Check if none of the lines are of length 0
    if (x1 == x2 and y1 == y2) or (x3 == x4 and y3 == y4):
        return None

    denominator = ((y4 - y3) * (x2 - x1) - (x4 - x3) * (y2 - y1))
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


def fraction_of_leg(x1, y1, x2, y2, intersect_x, intersect_y):
    return calculate_distance_lat_lon((x1, y1), (intersect_x, intersect_y)) / calculate_distance_lat_lon((x1, y1),
                                                                                                         (x2, y2))


def get_heading_difference(heading1, heading2):
    """
    From first heading to 2nd heading
    :param heading1:
    :param heading2:
    :return:
    """
    return (heading2 - heading1 + 540) % 360 - 180


def cross_track_distance(lat1, lon1, lat2, lon2, lat, lon):
    angular_distance13 = calculate_distance_lat_lon((lat1, lon1), (lat, lon)) / R
    first_bearing = calculate_bearing((lat1, lon1), (lat, lon)) * math.pi / 180
    second_bearing = calculate_bearing((lat1, lon1), (lat2, lon2)) * math.pi / 180
    return math.asin(math.sin(angular_distance13) * math.sin(first_bearing - second_bearing)) * R


def along_track_distance(lat1, lon1, lat, lon, cross_track_distance):
    angular_distance13 = calculate_distance_lat_lon((lat1, lon1), (lat, lon)) / R
    try:
        return math.acos(math.cos(angular_distance13) / math.cos(cross_track_distance / R)) * R
    except:
        # try:
        #     logger.exception("Something failed when calculating along track distance: {} {} {}".format(
        #         math.cos(angular_distance13), math.cos(cross_track_distance),
        #         math.cos(angular_distance13) / math.cos(cross_track_distance / R)))
        # except:
        #     logger.exception("Failed even printing the error message")
        return 999999999999
