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


def _clone_reference_waypoint(reference_waypoint, name: str):
    clone = type(reference_waypoint)(name)
    clone.latitude = reference_waypoint.latitude
    clone.longitude = reference_waypoint.longitude
    clone.elevation = getattr(reference_waypoint, "elevation", 0)
    clone.gate_line = getattr(reference_waypoint, "gate_line", [])
    clone.width = getattr(reference_waypoint, "width", 0)
    # Compatibility-only placeholder for older payloads that persisted names
    # without full waypoint semantics. Declared catalogue waypoints are gate
    # checks only; only SP/MP/FP are timed in contract navigation.
    clone.time_check = name in {"SP", "MP", "FP"}
    clone.gate_check = True
    clone.type = "tp"
    clone.distance_next = getattr(reference_waypoint, "distance_next", -1)
    clone.distance_previous = getattr(reference_waypoint, "distance_previous", -1)
    clone.bearing_next = getattr(reference_waypoint, "bearing_next", -1)
    clone.bearing_from_previous = getattr(reference_waypoint, "bearing_from_previous", -1)
    clone.end_curved = getattr(reference_waypoint, "end_curved", False)
    return clone


def _build_effective_route_waypoints_from_names(route_waypoints, effective_names: list[str]):
    if not effective_names:
        return route_waypoints
    if not route_waypoints:
        return []

    by_name = {item.name: item for item in route_waypoints}
    reference_waypoint = route_waypoints[min(1, len(route_waypoints) - 1)]

    # Compatibility fallback for older compiled payloads that only persisted
    # effective waypoint names. We clone the first interior waypoint geometry so
    # downstream calculators and renderers still receive gate-capable waypoint
    # objects until every declaration-bearing path writes full effective payloads.
    effective_waypoints = []
    for name in effective_names:
        if name in by_name:
            effective_waypoints.append(by_name[name])
        else:
            effective_waypoints.append(_clone_reference_waypoint(reference_waypoint, name))
    return effective_waypoints or route_waypoints


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
            return _build_effective_route_waypoints_from_names(
                list(navigation_task.route.waypoints),
                contestant.get_effective_waypoint_names(),
            )
    return list(navigation_task.route.waypoints)
