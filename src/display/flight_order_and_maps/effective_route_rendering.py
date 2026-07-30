from __future__ import annotations

from typing import Any

from display.utilities.route_building_utilities import build_waypoint


def _serialised_waypoint_to_runtime_waypoint(item: dict):
    waypoint = build_waypoint(
        item.get("name"),
        item.get("latitude"),
        item.get("longitude"),
        item.get("type"),
        item.get("width", 0.1),
        item.get("time_check", False),
        item.get("gate_check", False),
    )
    waypoint.gate_line = item.get("gate_line") or []
    waypoint.distance_next = item.get("distance_next", -1)
    waypoint.distance_previous = item.get("distance_previous", -1)
    waypoint.bearing_next = item.get("bearing_next", -1)
    waypoint.bearing_from_previous = item.get("bearing_from_previous", -1)
    waypoint.inside_distance = item.get("inside_distance", 0)
    waypoint.outside_distance = item.get("outside_distance", 0)
    waypoint.is_procedure_turn = item.get("is_procedure_turn", False)
    waypoint.is_steep_turn = item.get("is_steep_turn", False)
    waypoint.end_curved = item.get("end_curved", False)
    waypoint.elevation = item.get("elevation", 0)
    return waypoint


def get_task_catalogue_targets(navigation_task) -> list[dict[str, Any]]:
    editable_route = getattr(navigation_task, "editable_route", None)
    if editable_route is None:
        return []
    targets = []
    for feature in editable_route.get_catalogue_turnpoints():
        properties = feature.get("properties", {})
        coordinates = feature.get("geometry", {}).get("coordinates", [])
        if len(coordinates) != 2:
            continue
        targets.append(
            {
                "name": properties.get("name") or "",
                "coordinates": coordinates,
            }
        )
    return targets


def get_effective_route_waypoints(navigation_task, contestant=None, include_contestant_declarations: bool = True):
    if contestant is not None and include_contestant_declarations:
        config = getattr(contestant, "contestanttaskconfiguration", None)
        if config is not None and config.is_valid:
            payload = config.compiled_effective_route_payload or {}
            effective_waypoints = payload.get("effective_waypoints") or []
            if isinstance(effective_waypoints, list) and effective_waypoints:
                return [_serialised_waypoint_to_runtime_waypoint(item) for item in effective_waypoints if isinstance(item, dict)]
    return list(navigation_task.route.waypoints)