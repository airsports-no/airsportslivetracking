import numpy as np


def calculate_wind_correction_angle(true_track, airspeed, wind_speed, wind_direction):
    opposite_wind = wind_direction + 180
    relative_angle = true_track - opposite_wind
    return calculate_wind_correction_angle_relative_angle(airspeed, wind_speed, relative_angle)


def calculate_wind_correction_angle_relative_angle(airspeed, wind_speed, relative_angle):
    relative_angle = relative_angle * np.pi / 180
    angle = np.arcsin(wind_speed * np.sin(relative_angle) / airspeed)
    return angle * 180 / np.pi


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
