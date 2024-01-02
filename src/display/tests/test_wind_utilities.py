from unittest import TestCase

from parameterized import parameterized

from display.utilities.wind_utilities import calculate_wind_correction_angle, calculate_ground_speed_combined


class TestWindUtilities(TestCase):
    @parameterized.expand([
        (80, 70, 7, 132, -4.52),
        (245, 70, 7, 132, 5.28),
    ])
    def test_calculate_wind_correction_angle(self, true_track, airspeed, wind_speed, wind_direction, expected_angle):
        angle = calculate_wind_correction_angle(true_track, airspeed, wind_speed, wind_direction)
        self.assertAlmostEqual(expected_angle, angle, 2)


    @parameterized.expand([
        (80, 70, 7, 132, 65),
        (245, 70, 7, 132, 72)
    ])
    def test_calculate_ground_speed_combined(self, true_track, airspeed, wind_speed, wind_direction, expected_speed):
        speed = calculate_ground_speed_combined(true_track, airspeed, wind_speed, wind_direction)
        self.assertAlmostEqual(expected_speed, speed, 0)
