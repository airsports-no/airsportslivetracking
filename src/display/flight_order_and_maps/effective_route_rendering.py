from __future__ import annotations

"""Shared contestant-aware route reconstruction helpers.

This module is the single sanctioned seam for rebuilding runtime waypoint
objects from compiled contestant/task payloads. Maps, flight orders, and
calculators should all come through here so declaration-aware routes keep one
consistent reconstruction contract.
"""

from typing import Any

from display.utilities.coordinate_utilities import calculate_bearing, calculate_distance_lat_lon
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


def _recompute_leg_geometry(waypoints):
    for index in range(0, len(waypoints) - 1):
        current_waypoint = waypoints[index]
        next_waypoint = waypoints[index + 1]
        current_waypoint.distance_next = calculate_distance_lat_lon(
            (current_waypoint.latitude, current_waypoint.longitude),
            (next_waypoint.latitude, next_waypoint.longitude),
        )
        current_waypoint.bearing_next = calculate_bearing(
            (current_waypoint.latitude, current_waypoint.longitude),
            (next_waypoint.latitude, next_waypoint.longitude),
        )
    for index in range(1, len(waypoints)):
        current_waypoint = waypoints[index]
        previous_waypoint = waypoints[index - 1]
        current_waypoint.distance_previous = calculate_distance_lat_lon(
            (current_waypoint.latitude, current_waypoint.longitude),
            (previous_waypoint.latitude, previous_waypoint.longitude),
        )
        current_waypoint.bearing_from_previous = calculate_bearing(
            (previous_waypoint.latitude, previous_waypoint.longitude),
            (current_waypoint.latitude, current_waypoint.longitude),
        )


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


def _build_compat_effective_route_waypoints_from_names(route_waypoints, effective_names: list[str]):
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
    _recompute_leg_geometry(effective_waypoints)
    return effective_waypoints or route_waypoints


def get_task_catalogue_targets(navigation_task, contestant=None) -> list[dict[str, Any]]:
    editable_route = getattr(navigation_task, "editable_route", None)
    if editable_route is None:
        return []

    payload = None
    if contestant is not None:
        config = getattr(contestant, "contestanttaskconfiguration", None)
        if config is not None and config.is_valid:
            candidate = config.compiled_effective_route_payload or {}
            if navigation_task.task_subtype == "unknown_legs":
                payload = candidate

    if payload and navigation_task.task_subtype == "unknown_legs":
        targets = []
        for segment in payload.get("segments", []):
            coordinates_by_name = segment.get("display_coordinates_by_name", {}) or {}
            for waypoint_name in segment.get("display_waypoint_names", []):
                coordinates = coordinates_by_name.get(waypoint_name)
                if isinstance(coordinates, list) and len(coordinates) == 2:
                    targets.append(
                        {
                            "name": waypoint_name,
                            "coordinates": coordinates,
                            "kind": "catalogue_turnpoint",
                        }
                    )
        for connector in payload.get("actual_route", {}).get("unknown_leg_connectors", []):
            from_coordinates = connector.get("from_coordinates")
            to_coordinates = connector.get("to_coordinates")
            if isinstance(from_coordinates, list) and len(from_coordinates) == 2:
                targets.append(
                    {
                        "name": connector.get("from") or "",
                        "coordinates": from_coordinates,
                        "kind": "unknown_leg_trigger",
                    }
                )
            if isinstance(to_coordinates, list) and len(to_coordinates) == 2:
                targets.append(
                    {
                        "name": f"{connector.get('from')}→{connector.get('to')}",
                        "coordinates": to_coordinates,
                        "kind": "unknown_leg_connector_end",
                    }
                )
        for gate in payload.get("hidden_gates", []):
            coordinates = gate.get("coordinates")
            if isinstance(coordinates, list) and len(coordinates) == 2:
                targets.append(
                    {
                        "name": gate.get("name") or "",
                        "coordinates": coordinates,
                        "kind": "hidden_gate",
                    }
                )
        return targets

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
                "kind": "catalogue_turnpoint",
            }
        )
    circle_feature_groups = [
        (editable_route.get_circle_center_markers(), "circle_center_marker"),
        (editable_route.get_circle_start_markers(), "circle_start_marker"),
        (editable_route.get_circle_entry_markers(), "circle_entry_marker"),
        (editable_route.get_circle_exit_markers(), "circle_exit_marker"),
    ]
    for features, kind in circle_feature_groups:
        for feature in features:
            properties = feature.get("properties", {})
            coordinates = feature.get("geometry", {}).get("coordinates", [])
            if len(coordinates) != 2:
                continue
            targets.append(
                {
                    "name": properties.get("name") or "",
                    "coordinates": coordinates,
                    "kind": kind,
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
                runtime_waypoints = [_serialised_waypoint_to_runtime_waypoint(item) for item in effective_waypoints if isinstance(item, dict)]
                _recompute_leg_geometry(runtime_waypoints)
                return runtime_waypoints
            # Names-only payloads are an older compatibility format; keep the
            # fallback centralized here so every downstream consumer agrees on
            # how that legacy data is rehydrated until the migration is fully
            # retired.
            return _build_compat_effective_route_waypoints_from_names(
                list(navigation_task.route.waypoints),
                contestant.get_effective_waypoint_names(),
            )
    return list(navigation_task.route.waypoints)
