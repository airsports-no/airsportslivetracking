"""
Utilities for creating and manipulating EditableRoute GeoJSON structures.

Data Format:
The EditableRoute stores data in a GeoJSON FeatureCollection format.
Each Feature in the collection represents a route element:
- "route_path": A LineString representing the connected track.
- "route_waypoint": Points representing waypoints along the track.
- "takeoff_gate" / "landing_gate": LineStrings for TO/LDG gates.
- "zone": Polygons for prohibited, info, penalty, or gate zones.

Coordinate System:
GeoJSON uses [longitude, latitude] order.
Internal Python logic typically uses (latitude, longitude) tuples.
"""
from typing import Optional
import uuid


def create_track_block(
    positions: list[tuple[float, float]],
    widths: Optional[list[float]] = None,
    names: Optional[list[str]] = None,
    types: Optional[list[str]] = None,
) -> list[dict]:
    """
    Given a list of (latitude, longitude) pairs, construct a list of GeoJSON features 
    representing the route path and its waypoints.
    """
    features = []

    # Route Path
    features.append({
        "type": "Feature",
        "properties": {
            "featureType": "route_path"
        },
        "geometry": {
            "type": "LineString",
            # GeoJSON expects [lon, lat]
            "coordinates": [[p[1], p[0]] for p in positions]
        }
    })

    # Waypoints
    for index, position in enumerate(positions):
        if names and index < len(names):
            name = names[index]
        else:
            name = "Start" if index == 0 else "Finish" if index == len(positions) - 1 else f"WP {index + 1}"

        if types and index < len(types):
            pt_type = types[index]
        else:
            pt_type = "sp" if index == 0 else "fp" if index == len(positions) - 1 else "tp"

        width = widths[index] if widths and index < len(widths) else 1852

        features.append({
            "type": "Feature",
            "properties": {
                "id": str(uuid.uuid4()),
                "name": name,
                "pointType": pt_type,
                "featureType": "route_waypoint",
                "width": width,
                "isTiming": False,
                "isPassing": True,
                "sequence": index,
                "segmentType": "straight"
            },
            "geometry": {
                "type": "Point",
                # GeoJSON expects [lon, lat]
                "coordinates": [position[1], position[0]]
            }
        })

    return features


def _create_gate(positions: tuple[tuple[float, float], tuple[float, float]], name: str, feature_type: str, gate_type: str) -> dict:
    """Helper to create a gate feature. Input positions are (lat, lon)."""
    return {
        "type": "Feature",
        "properties": {
            "id": str(uuid.uuid4()),
            "name": name,
            "gateType": gate_type,
            "featureType": feature_type,
            "width": 50
        },
        "geometry": {
            "type": "LineString",
            # GeoJSON expects [lon, lat]
            "coordinates": [[positions[0][1], positions[0][0]], [positions[1][1], positions[1][0]]]
        }
    }


def create_takeoff_gate(positions: tuple[tuple[float, float], tuple[float, float]]) -> dict:
    """Create a take of gate given a pair of lat, lon positions that make up the gates"""
    return _create_gate(positions, "Takeoff gate", "takeoff_gate", "takeoff")


def create_landing_gate(positions: tuple[tuple[float, float], tuple[float, float]]) -> dict:
    """Create a take of gate given a pair of lat, lon positions that make up the gates"""
    return _create_gate(positions, "Landing gate", "landing_gate", "landing")


def _create_polygon(positions: list[tuple[float, float]], name: str, polygon_type: str) -> dict:
    """
    Helper to create a polygon feature. Input positions are (lat, lon).
    """
    coords = [[p[1], p[0]] for p in positions]
    if coords and coords[0] != coords[-1]:
        coords.append(coords[0])
    return {
        "type": "Feature",
        "properties": {
            "id": str(uuid.uuid4()),
            "name": name,
            "polygonType": polygon_type,
            "featureType": "zone"
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [coords]
        }
    }


def create_prohibited_zone(positions: list[tuple[float, float]], name: str) -> dict:
    """Create a prohibited zone polygon"""
    return _create_polygon(positions, name, "prohibited")


def create_information_zone(positions: list[tuple[float, float]], name: str) -> dict:
    """Create a information zone polygon"""
    return _create_polygon(positions, name, "info")


def create_penalty_zone(positions: list[tuple[float, float]], name: str) -> dict:
    """Create a penalty zone polygon"""
    return _create_polygon(positions, name, "penalty")


def create_gate_polygon(positions: list[tuple[float, float]], name: str) -> dict:
    """Create a gate polygon used for poker run"""
    return _create_polygon(positions, name, "waypoint")


def get_quadratic_bezier_points(
    p1: tuple[float, float],
    p2: tuple[float, float],
    control: tuple[float, float],
    num_points: int = 20,
) -> list[tuple[float, float]]:
    """
    Calculate points along a quadratic Bezier curve.
    Inputs and outputs are (latitude, longitude).
    """
    points = []
    for i in range(num_points + 1):
        t = i / num_points
        lat = (1 - t) * (1 - t) * p1[0] + 2 * (1 - t) * t * control[0] + t * t * p2[0]
        lng = (1 - t) * (1 - t) * p1[1] + 2 * (1 - t) * t * control[1] + t * t * p2[1]
        points.append((lat, lng))
    return points
