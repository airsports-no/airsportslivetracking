from plistlib import Dict

from display.coordinate_utilities import calculate_distance_lat_lon


def get_distance_to_other_gates(gate, waypoints) -> Dict:
    distances = {}
    for current_gate in waypoints:
        if gate["name"] != current_gate["name"]:
            distances[gate["name"]] = calculate_distance_lat_lon(
                (gate["latitude"], gate["longitude"]),
                (current_gate["latitude"], current_gate["longitude"]))
    return distances


