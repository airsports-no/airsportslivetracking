"""
All geoJSON features use longitude, latitude coordinate order.
"""
from typing import Optional
import uuid


def create_track_block(
    positions: list[tuple[float, float]],
    widths: Optional[list[float]] = None,
    names: Optional[list[str]] = None,
    types: Optional[list[str]] = None,
) -> list[dict]:
    """Given a list of lat, lon pairs, construct a list of geojson features for track and waypoints."""
    features = []

    # Route Path
    features.append({
        "type": "Feature",
        "properties": {
            "featureType": "route_path"
        },
        "geometry": {
            "type": "LineString",
            "coordinates": [[p[1], p[0]] for p in positions]
        }
    })

    # Waypoints
    for index, position in enumerate(positions):
        if names and index < len(names):
            name = names[index]
        else:
            if index == 0: name = "Start"
            elif index == len(positions) - 1: name = "Finish"
            else: name = f"WP {index + 1}"

        if types and index < len(types):
            pt_type = types[index]
        else:
            if index == 0: pt_type = "sp"
            elif index == len(positions) - 1: pt_type = "fp"
            else: pt_type = "tp"

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
                "coordinates": [position[1], position[0]]
            }
        })

    return features


def _create_gate(positions: tuple[tuple[float, float], tuple[float, float]], name: str, feature_type: str, gate_type: str) -> dict:
    """[[longitude, latitude], [longitude, latitude]]"""
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
    Coordinate list should be latitude, longitude
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
    """Calculate points along a quadratic Bezier curve."""
    points = []
    for i in range(num_points + 1):
        t = i / num_points
        lat = (1 - t) * (1 - t) * p1[0] + 2 * (1 - t) * t * control[0] + t * t * p2[0]
        lng = (1 - t) * (1 - t) * p1[1] + 2 * (1 - t) * t * control[1] + t * t * p2[1]
        points.append((lat, lng))
    return points
