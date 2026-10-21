import numpy as np


def calculate_wind_correction_angle(true_track, airspeed, wind_speed, wind_direction):
    opposite_wind = wind_direction + 180
    relative_angle = true_track - opposite_wind
    return calculate_wind_correction_angle_relative_angle(airspeed, wind_speed, relative_angle)


def calculate_wind_correction_angle_relative_angle(airspeed, wind_speed, relative_angle):
    relative_angle = relative_angle * np.pi / 180
    angle = np.arcsin(wind_speed * np.sin(relative_angle) / airspeed)
    return -angle * 180 / np.pi


def calculate_ground_speed(true_track, airspeed, wind_correction_angle, wind_speed, wind_direction):
    opposite_wind = wind_direction + 180
    relative_angle = true_track - opposite_wind
    return calculate_ground_speed_relative_angle(airspeed, wind_correction_angle, wind_speed, relative_angle)


def calculate_ground_speed_relative_angle(airspeed, wind_correction_angle, wind_speed, relative_angle):
    wind_correction_angle = wind_correction_angle * np.pi / 180
    relative_angle = relative_angle * np.pi / 180
    ground_speed = airspeed * np.cos(wind_correction_angle) + wind_speed * np.cos(relative_angle)
    return ground_speed


def calculate_ground_speed_combined(true_track, airspeed, wind_speed, wind_direction):
    wind_correction_angle = calculate_wind_correction_angle(true_track, airspeed, wind_speed, wind_direction)
    return calculate_ground_speed(true_track, airspeed, wind_correction_angle, wind_speed, wind_direction)


def calculate_heading_for_ground_speed(true_track, ground_speed, wind_speed, wind_direction):
    """The true heading that makes good [ground_speed] along [true_track] in the wind (blowing from [wind_direction])."""
    track = true_track * np.pi / 180
    wind_towards = (wind_direction + 180) * np.pi / 180
    air_east = ground_speed * np.sin(track) - wind_speed * np.sin(wind_towards)
    air_north = ground_speed * np.cos(track) - wind_speed * np.cos(wind_towards)
    return (np.arctan2(air_east, air_north) * 180 / np.pi) % 360
