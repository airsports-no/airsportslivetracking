"""
Canonical ruleset for whether an EditableRoute's authored content supports a given
navigation task subtype (legacy family or CIMA subtype).

This is the single source of truth consulted by:
- The route editor UI (compatibility badges / task-type selector).
- The route-to-task wizard (``RouteToTaskWizard`` / ``ContestSelectForm``), which offers only
  compatible task types for a given route.
- The contest-first task wizard (``NewNavigationTaskWizard``), which offers only compatible
  routes for a given task type.

``extract_route_primitives`` is also the implementation backing
``TaskCompiler._build_compiled_primitives`` (see ``display.services.task_compiler``) so the two
never drift apart - the compiler's persisted, task-scoped payload is a strict subset of the
primitives computed here.
"""

from display.utilities.cima_task_type_definitions import TASK_SUBTYPE_DEFINITIONS

# Bump whenever the ruleset (required/forbidden primitives, or the primitive extraction itself)
# changes in a way that could change the outcome for an already-saved route, so callers can tell a
# stale EditableRoute.compatible_task_types apart from a freshly computed one.
ROUTE_COMPATIBILITY_RULESET_VERSION = 1

# The keys TaskCompiler._build_compiled_primitives has historically returned, in that order. Kept
# here so the compiler can subset extract_route_primitives() without changing its persisted
# compiled_payload contract.
LEGACY_COMPILER_PRIMITIVE_KEYS = (
    "catalogue_turnpoint",
    "circle_center_marker",
    "circle_start_marker",
    "circle_entry_marker",
    "circle_exit_marker",
    "route_to_sp_path",
    "route_from_fp_path",
    "known_time_gate",
    "hidden_gate",
    "unknown_leg",
    "dummy_branch_waypoint",
    "observation_photo",
)


def extract_route_primitives(editable_route) -> dict[str, list]:
    """
    Compute, for an EditableRoute, the presence (by name) of every primitive kind the
    compatibility ruleset and TaskCompiler know about. Safe to call on a route that has never
    been attached to a NavigationTask.
    """
    if editable_route is None or not isinstance(editable_route.route, dict) or "features" not in editable_route.route:
        # Mirrors the guard in EditableRoute.save(): a brand new/unsaved route (model default is
        # an empty list, not {"features": []}) has no primitives yet.
        return {}
    return {
        "route_path": ["track"] if editable_route.get_track() is not None else [],
        "route_waypoint": [item.get("properties", {}).get("name") for item in editable_route.get_track_waypoints()],
        "takeoff_gate": [item.get("properties", {}).get("name") for item in editable_route.get_takeoff_gates()],
        "landing_gate": [item.get("properties", {}).get("name") for item in editable_route.get_landing_gates()],
        "catalogue_turnpoint": [item["properties"].get("name") for item in editable_route.get_catalogue_turnpoints()],
        "circle_center_marker": [item["properties"].get("name") for item in editable_route.get_circle_center_markers()],
        "circle_start_marker": [item["properties"].get("name") for item in editable_route.get_circle_start_markers()],
        "circle_entry_marker": [item["properties"].get("name") for item in editable_route.get_circle_entry_markers()],
        "circle_exit_marker": [item["properties"].get("name") for item in editable_route.get_circle_exit_markers()],
        "route_to_sp_path": [
            item.get("properties", {}).get("name") or f"route_to_sp_{index}"
            for index, item in enumerate(editable_route.get_route_to_sp_paths(), start=1)
        ],
        "route_from_fp_path": [
            item.get("properties", {}).get("name") or f"route_from_fp_{index}"
            for index, item in enumerate(editable_route.get_route_from_fp_paths(), start=1)
        ],
        "known_time_gate": [item["properties"].get("name") for item in editable_route.get_known_time_gates()],
        "hidden_gate": [item["properties"].get("name") for item in editable_route.get_hidden_gates()],
        "unknown_leg": [item["properties"].get("name") for item in editable_route.get_unknown_leg_waypoints()],
        "dummy_waypoint": [item["properties"].get("name") for item in editable_route.get_dummy_waypoints()],
        "dummy_branch_waypoint": [
            item.get("properties", {}).get("name")
            for item in editable_route.get_features_type("dummy_branch_waypoint")
            if item.get("properties", {}).get("name")
        ],
        "observation_photo": [item["properties"].get("name") for item in editable_route.get_observation_photos()],
    }


def get_blocking_reasons(primitives: dict[str, list], subtype_key: str) -> list[str]:
    """
    Return a list of human-readable reasons ``subtype_key`` is incompatible with a route whose
    primitives are ``primitives`` (as returned by extract_route_primitives). Empty list means
    compatible.
    """
    definition = TASK_SUBTYPE_DEFINITIONS.get(subtype_key)
    if definition is None:
        return [f"Unknown task subtype '{subtype_key}'"]
    reasons = []
    for primitive in definition.required_primitives:
        if not primitives.get(primitive):
            reasons.append(f"Missing required route feature: {primitive}")
    for primitive in definition.forbidden_primitives:
        if primitives.get(primitive):
            reasons.append(f"Route feature not allowed for this task type: {primitive}")
    return reasons


def get_compatible_task_subtypes(editable_route) -> list[str]:
    """
    Return the keys of every task subtype (legacy shim or CIMA) this route's authored content
    satisfies the requirements of. This is the canonical compatibility set - it is what wizards
    filter task type / route choices against.
    """
    primitives = extract_route_primitives(editable_route)
    return [key for key in TASK_SUBTYPE_DEFINITIONS if not get_blocking_reasons(primitives, key)]


def infer_intended_task_subtypes(editable_route, active_template_subtype: str | None = None) -> list[str]:
    """
    Suggest an initial value for EditableRoute.intended_task_types, for the user to review.

    If the route was authored against a specific task template in the route editor's "Task Route
    Guide", that subtype is the strongest signal of intent - but only if the route actually
    satisfies it. Otherwise fall back to the full computed-compatible set, which the user can then
    narrow down in the UI.
    """
    compatible = get_compatible_task_subtypes(editable_route)
    if active_template_subtype and active_template_subtype in compatible:
        return [active_template_subtype]
    return compatible
