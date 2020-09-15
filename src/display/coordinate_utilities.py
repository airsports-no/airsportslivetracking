import math
from typing import Tuple


def calculate_distance_lat_lon(start: Tuple[float, float], finish: Tuple[float, float]) -> float:
    """

    :param start:
    :param finish:
    :return: Distance in kilometres
    """
    lat1 = start[0] * math.pi / 180
    lon1 = start[1] * math.pi / 180
    lat2 = finish[0] * math.pi / 180
    lon2 = finish[1] * math.pi / 180
    R = 6371000  # metres
    deltaLatitude = (lat2 - lat1)
    deltaLongitude = (lon2 - lon1)

    a = math.sin(deltaLatitude / 2) * math.sin(deltaLatitude / 2) + math.cos(lat1) * math.cos(lat2) * math.sin(
        deltaLongitude / 2) * math.sin(deltaLongitude / 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    d = R * c
    return d / 1000


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
