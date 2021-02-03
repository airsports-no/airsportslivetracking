import datetime
from typing import Optional, Dict, List, Tuple

from display.waypoint import Waypoint
from display.wind_utilities import calculate_ground_speed_combined


def calculate_and_get_relative_gate_times(route, air_speed, wind_speed, wind_direction) -> List[Tuple[str, datetime.timedelta]]:
    gates = route.waypoints  # type: List[Waypoint]
    if len(gates) == 0:
        return []
    crossing_times = []
    crossing_time = datetime.timedelta(minutes=0)
    crossing_times.append((gates[0].name, crossing_time))
    for index in range(len(gates) - 1):
        gate = gates[index]
        next_gate = gates[index + 1]
        ground_speed = calculate_ground_speed_combined(gate.bearing_next, air_speed, wind_speed, wind_direction)
        crossing_time += datetime.timedelta(
            hours=(gate.distance_next / 1852) / ground_speed)
        crossing_times.append((next_gate.name, crossing_time))
        if next_gate.is_procedure_turn:
            crossing_time += datetime.timedelta(minutes=1)
    return crossing_times
