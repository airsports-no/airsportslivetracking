import datetime
from typing import List, Tuple

from display.utilities.coordinate_utilities import calculate_distance_lat_lon, calculate_bearing
from display.utilities.wind_utilities import calculate_ground_speed_combined

PROCEDURE_TURN_DURATION=datetime.timedelta(minutes=1)

def get_segment_time(start, finish, air_speed, wind_speed, wind_direction) -> datetime.timedelta:
    bearing = calculate_bearing(start, finish)
    distance = calculate_distance_lat_lon(start, finish)
    ground_speed = calculate_ground_speed_combined(bearing, air_speed, wind_speed, wind_direction)
    return datetime.timedelta(hours=(distance / 1852) / ground_speed)


def calculate_and_get_relative_gate_times(
    route, air_speed, wind_speed, wind_direction, leg_speeds: dict = None
) -> List[Tuple[str, datetime.timedelta]]:
    """
    Used to calculate the gate times for a contestant when it is created.
    leg_speeds: Optional dictionary mapping gate name (start of leg) to ground speed in Knots.
    """
    waypoints = list(filter(lambda waypoint: waypoint.type not in ("dummy",), route.waypoints))  # type: List[Waypoint]
    if len(waypoints) == 0:
        return []
    centre_tracks = []
    crossing_time = datetime.timedelta(minutes=0)
    crossing_times = [(waypoints[0].name, crossing_time)]
    for waypoint in waypoints:
        centre_tracks.append(waypoint.get_centre_track_segments())
    
    leg_speeds = leg_speeds or {}

    for index in range(0, len(waypoints) - 1):
        current_gate_name = waypoints[index].name
        
        # Determine speed for this leg
        # If leg_speed is provided, it is typically Ground Speed.
        # Otherwise, calculate Ground Speed from Air Speed + Wind.
        declared_speed = leg_speeds.get(current_gate_name)

        current_gate = centre_tracks[index]
        next_gate = centre_tracks[index + 1]
        start_index = len(current_gate) // 2
        finish_index = len(next_gate) // 2
        
        for track_index in range(start_index, len(current_gate) - 1):
            if declared_speed:
                dist = calculate_distance_lat_lon(current_gate[track_index], current_gate[track_index + 1])
                crossing_time += datetime.timedelta(hours=(dist / 1852) / declared_speed)
            else:
                crossing_time += get_segment_time(
                    current_gate[track_index], current_gate[track_index + 1], air_speed, wind_speed, wind_direction
                )
                
        # Main leg segment
        if declared_speed:
            dist = calculate_distance_lat_lon(current_gate[-1], next_gate[0])
            crossing_time += datetime.timedelta(hours=(dist / 1852) / declared_speed)
        else:
            crossing_time += get_segment_time(current_gate[-1], next_gate[0], air_speed, wind_speed, wind_direction)
            
        for track_index in range(0, finish_index):
            if declared_speed:
                 dist = calculate_distance_lat_lon(next_gate[track_index], next_gate[track_index + 1])
                 crossing_time += datetime.timedelta(hours=(dist / 1852) / declared_speed)
            else:
                crossing_time += get_segment_time(
                    next_gate[track_index], next_gate[track_index + 1], air_speed, wind_speed, wind_direction
                )
                
        crossing_times.append((waypoints[index + 1].name, crossing_time))
        if waypoints[index + 1].is_procedure_turn:
            crossing_time += PROCEDURE_TURN_DURATION
    return crossing_times
