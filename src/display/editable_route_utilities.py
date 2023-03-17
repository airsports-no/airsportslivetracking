"""
All geoJSON features use longitude, latitude coordinate order.
"""
from typing import Optional


def create_track_block(
    positions: list[tuple[float, float]],
    widths: Optional[list[float]] = None,
    names: Optional[list[str]] = None,
    types: Optional[list[str]] = None,
) -> dict:
    """Given a list of lat, lon pairs, construct a editable route json track block"""
    track_points = []
    for index, position in enumerate(positions):
        track_points.append(
            {
                "name": names[index]
                if names
                else "SP"
                if index == 0
                else "FP"
                if index == len(positions) - 1
                else f"TP {index}",
                "gateType": types[index]
                if types
                else "sp"
                if index == 0
                else "fp"
                if index == len(positions) - 1
                else "tp",
                "timeCheck": True,
                "gateWidth": widths[index] if widths else 1,
                "position": {"lat": position[0], "lng": position[1]},
            }
        )
    return {
        "name": "Track",
        "layer_type": "polyline",
        "track_points": track_points,
        "feature_type": "track",
        "tooltip_position": [0, 0],
        "geojson": {
            "type": "Feature",
            "properties": {},
            "geometry": {
                "type": "LineString",
                "coordinates": [[item["position"]["lng"], item["position"]["lat"]] for item in track_points],
            },
        },
    }


def _create_gate(positions: tuple[tuple[float, float], tuple[float, float]], name: str, feature_type: str) -> dict:
    """[[longitude, latitude], [longitude, latitude]]"""
    return {
        "name": name,
        "layer_type": "polyline",
        "track_points": [],
        "feature_type": feature_type,
        "tooltip_position": [0, 0],
        "geojson": {
            "type": "Feature",
            "properties": {},
            "geometry": {"type": "LineString", "coordinates": [list(positions[0]), list(positions[1])]},
        },
    }


def create_takeoff_gate(positions: tuple[tuple[float, float], tuple[float, float]]) -> dict:
    """Create a take of gate given a pair of lat, lon positions that make up the gates"""
    return _create_gate(positions, "Takeoff gate", "to")


def create_landing_gate(positions: tuple[tuple[float, float], tuple[float, float]]) -> dict:
    """Create a take of gate given a pair of lat, lon positions that make up the gates"""
    return _create_gate(positions, "Landing gate", "ldg")


def _create_polygon(positions: list[tuple[float, float]], name: str, feature_type: str) -> dict:
    """
    Coordinate list should be latitude, longitude
    """
    return {
        "name": name,
        "layer_type": "polygon",
        "track_points": [],
        "feature_type": feature_type,
        "tooltip_position": [0, 0],
        "geojson": {
            "type": "Feature",
            "properties": {},
            "geometry": {
                "type": "Polygon",
                "coordinates": [positions],  # Apparently a list of list of positions, i.e. multiple polygons. Should be lat, lon
            },
        },
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
    return _create_polygon(positions, name, "gate")
