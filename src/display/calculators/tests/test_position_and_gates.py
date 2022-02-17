from unittest.mock import Mock

from unittest import TestCase

from display.calculators.positions_and_gates import Gate
from display.coordinate_utilities import calculate_distance_lat_lon


class TestGate(TestCase):
    def get_distance_to_gate_line(self):
        gate = Gate(Mock(), Mock(), Mock())
        gate.gate_line = [[-10.1, -55.5], [-15.2, -45.1]]
        distance = gate.get_distance_to_gate_line(-10.5, -62.5)
        self.assertEqual(768019.6114461364, distance)

        gate.gate_line = [[40.5, 60.5], [50.5, 80.5]]
        distance = gate.get_distance_to_gate_line(51, 69)
        self.assertEqual(479774.0365302198, distance)

        gate.gate_line = [[21.72, 35.61], [23.65, 40.7]]
        distance = gate.get_distance_to_gate_line(25, 42)
        self.assertEqual(199416.02934336077, distance)

        gate.gate_line = [[60, 11], [61, 11]]
        distance = gate.get_distance_to_gate_line(59, 11)
        self.assertEqual(calculate_distance_lat_lon((60, 11), (59, 11)), distance)
        distance = gate.get_distance_to_gate_line(62, 11)
        self.assertEqual(calculate_distance_lat_lon((62, 11), (61, 11)), distance)
        distance = gate.get_distance_to_gate_line(60.5, 11)
        self.assertEqual(0, distance)
        distance = gate.get_distance_to_gate_line(60.5, 11.5)
        self.assertEqual(27440.794591463346, distance)
