import datetime
from typing import Optional

import numpy as np

from display.utilities.coordinate_utilities import calculate_distance_lat_lon
from track_analyser.gps_track import GPSTrack


def get_track_differences(
        track1: GPSTrack,
        track2: GPSTrack,
        start_time: Optional[datetime.datetime] = None,
        finish_time: Optional[datetime.datetime] = None,
):
    if not start_time:
        start_time = max([track1.start_time, track2.start_time])
    if not finish_time:
        finish_time = min([track1.finish_time, track2.finish_time])
    assert track1.step.total_seconds() % track2.step.total_seconds() == 0
    step = max([track1.step, track2.step])
    current_time = start_time
    differences = []
    while current_time < finish_time:
        differences.append(
            calculate_distance_lat_lon(
                track1.get_normalised_position_at_time(current_time),
                track2.get_normalised_position_at_time(current_time),
            )
        )
        current_time += step
    return np.array(differences)


def get_track_differences_time(
        track1: GPSTrack,
        track2: GPSTrack,
        start_time: Optional[datetime.datetime] = None,
        finish_time: Optional[datetime.datetime] = None,
):
    if not start_time:
        start_time = max([track1.start_time, track2.start_time])
    if not finish_time:
        finish_time = min([track1.finish_time, track2.finish_time])
    assert track1.step.total_seconds() % track2.step.total_seconds() == 0
    step = max([track1.step, track2.step])
    current_time = start_time
    differences = []
    while current_time < finish_time:
        time_distance = 0
        if track1.get_normalised_speed_at_time(current_time) + track2.get_normalised_speed_at_time(current_time) > 1:
            time_distance = calculate_distance_lat_lon(
                track1.get_normalised_position_at_time(current_time),
                track2.get_normalised_position_at_time(current_time),
            ) / ((track1.get_normalised_speed_at_time(current_time) + track2.get_normalised_speed_at_time(
                current_time)) / 2)
        differences.append(
            time_distance
        )
        current_time += step
    return np.array(differences)
