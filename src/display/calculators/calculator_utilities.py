import datetime
from typing import Tuple, List

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
