"""
Canonical ruleset for whether an EditableRoute's authored content supports a given
navigation task subtype (legacy family or CIMA subtype).

This is the single source of truth consulted by:
- The route editor UI (compatibility badges / task-type selector).
- The React nav-task-creation flow (``NavigationTaskCreationFlow``, via the
  ``editableroutes-task-templates``/``editableroutes-task-compatibility`` API endpoints), which
  offers only compatible task types for a given route and vice versa.
- ``NavigationTaskEditableRoutReferenceSerialiser.validate()``, which re-checks compatibility
  server-side as the non-bypassable security boundary - the API filtering above is only a UX
  affordance.

``extract_route_primitives`` is also the implementation backing
``TaskCompiler._build_compiled_primitives`` (see ``display.services.task_compiler``) so the two
never drift apart - the compiler's persisted, task-scoped payload is a strict subset of the
primitives computed here.
"""

from dataclasses import dataclass

from django.core.exceptions import ValidationError

from display.utilities import route_requirements as rr
from display.utilities.gate_definitions import UNKNOWN_LEG
from display.utilities.route_requirements import RouteRequirement
from display.utilities.task_types import (
    TASK_TYPE_REGISTRY,
    default_task_type_key_for_family,
    find_task_type,
    get_task_type,
)

# Bump whenever the ruleset (the task types' route requirements, or the primitive extraction itself)
# changes in a way that could change the outcome for an already-saved route, so callers can tell a
# stale EditableRoute.compatible_task_types apart from a freshly computed one.
ROUTE_COMPATIBILITY_RULESET_VERSION = 4

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
        "curved_leg": [item["properties"].get("name") for item in editable_route.get_curved_leg_waypoints()],
        "duration_landing_area": [
            item.get("properties", {}).get("name") for item in editable_route.get_duration_landing_area_polygons()
        ],
    }


@dataclass(frozen=True)
class RequirementResult:
    """One route requirement evaluated against a route: what was found and whether that satisfies it."""

    key: str
    label: str
    minimum: int
    maximum: int | None
    found: int
    satisfied: bool
    # What is wrong when the requirement is not met.
    message: str

    def as_dict(self) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "minimum": self.minimum,
            "maximum": self.maximum,
            "found": self.found,
            "satisfied": self.satisfied,
            "message": self.message,
        }


def _is_authored(editable_route) -> bool:
    # Mirrors the guard in extract_route_primitives/EditableRoute.save(): a brand new/unsaved route (model default is
    # an empty list, not {"features": []}) crashes the feature accessors otherwise.
    return editable_route is not None and isinstance(editable_route.route, dict) and "features" in editable_route.route


def _count_fact(fact: str, primitives: dict[str, list], editable_route) -> int:
    """The number of [fact] in the route: a primitive's count or a fact derived from the route."""
    if fact == rr.NAMED_KNOWN_TIME_GATE:
        return len([name for name in primitives.get(rr.KNOWN_TIME_GATE, []) if name])
    if fact == rr.NAMED_CATALOGUE_TURNPOINT:
        return len([name for name in primitives.get(rr.CATALOGUE_TURNPOINT, []) if name])
    if fact == rr.NAMED_UNKNOWN_LEG:
        return len([name for name in primitives.get(rr.UNKNOWN_LEG, []) if name])
    if fact == rr.FREE_CATALOGUE_TURNPOINT:
        return len([name for name in primitives.get(rr.CATALOGUE_TURNPOINT, []) if name not in {"SP", "MP", "FP"}])
    if fact == rr.UNKNOWN_LEG_WITHOUT_EXTENSION:
        return _unknown_legs_without_extension(editable_route)
    return len(primitives.get(fact, []))


def _unknown_legs_without_extension(editable_route) -> int:
    """How many unknown-leg points have no extension (dummy branch) waypoint triggered from them."""
    if not _is_authored(editable_route):
        return 0
    triggered = {
        feature.get("properties", {}).get("triggerPointId")
        for feature in editable_route.get_features_type("dummy_branch_waypoint")
    }
    return sum(
        1
        for waypoint in editable_route.get_ordered_track_waypoints()
        if waypoint.get("properties", {}).get("pointType") == UNKNOWN_LEG
        and (not waypoint.get("properties", {}).get("id") or waypoint["properties"]["id"] not in triggered)
    )


def _count_ordering_violations(requirement: RouteRequirement, editable_route) -> int:
    if not _is_authored(editable_route):
        return 0
    waypoints = [
        (item.get("properties", {}).get("pointType"), item.get("properties", {}).get("name"))
        for item in editable_route.get_ordered_track_waypoints()
    ]
    return requirement.ordering.violations(waypoints)


def evaluate_route_requirements(
    primitives: dict[str, list], definition, editable_route=None
) -> list[RequirementResult]:
    """
    Evaluate every route requirement of the task type [definition] against a route whose primitives are [primitives]
    (as returned by extract_route_primitives). [editable_route] is needed for the requirements that look at more than
    the primitives (the order of the waypoints, the extension waypoints of unknown legs); without it those count as met.
    A requirement that depends on another (see RouteRequirement.depends_on) counts as met until that one is.

    This is the one place that decides whether a route suits a task type: the route editor's compatibility check, the
    persisted EditableRoute.compatible_task_types, the API that creates a task and TaskCompiler's validation all use it.
    """
    results: dict[str, RequirementResult] = {}
    for requirement in definition.route_requirements:
        if any(key in results and not results[key].satisfied for key in requirement.depends_on):
            found = 0
        elif requirement.ordering is not None:
            found = _count_ordering_violations(requirement, editable_route)
        else:
            found = _count_fact(requirement.fact, primitives, editable_route)
        satisfied = requirement.is_met_by(found)
        # A met requirement still carries the message it would fail with, for the route editor to show as its hint.
        failing_count = found if not satisfied else (requirement.minimum - 1 if requirement.minimum else found + 1)
        results[requirement.key] = RequirementResult(
            key=requirement.key,
            label=requirement.label,
            minimum=requirement.minimum,
            maximum=requirement.maximum,
            found=found,
            satisfied=satisfied,
            message=requirement.failure_message(failing_count),
        )
    return list(results.values())


def get_unmet_requirements(editable_route, subtype_key: str) -> list[RequirementResult]:
    """The route requirements of the task type [subtype_key] that [editable_route] does not meet."""
    definition = get_task_type(subtype_key)
    results = evaluate_route_requirements(extract_route_primitives(editable_route), definition, editable_route)
    return [result for result in results if not result.satisfied]


def get_blocking_reasons(primitives: dict[str, list], subtype_key: str, editable_route=None) -> list[str]:
    """
    Return a list of human-readable reasons ``subtype_key`` is incompatible with a route whose
    primitives are ``primitives`` (as returned by extract_route_primitives). Empty list means
    compatible.

    The reasons are the failure messages of the task type's unmet route requirements
    (evaluate_route_requirements). This is the single canonical compatibility calculation, consulted by
    get_compatible_task_subtypes (route editor compatibility API, persisted EditableRoute.compatible_task_types,
    task-template picker), assert_route_compatible_with_task_type (the API creation path) and TaskCompiler alike, so
    they can't drift apart. ``editable_route`` is optional only so callers that only have primitives on hand keep
    working; every caller that has the route available should pass it, as the order of the waypoints and the
    extension waypoints of unknown legs can only be checked with it.
    """
    definition = find_task_type(subtype_key)
    if definition is None:
        return [f"Unknown task subtype '{subtype_key}'"]
    return [
        result.message
        for result in evaluate_route_requirements(primitives, definition, editable_route)
        if not result.satisfied
    ]


def get_compatible_task_subtypes(editable_route) -> list[str]:
    """
    Return the keys of every task subtype (legacy shim or CIMA) this route's authored content
    satisfies the requirements of. This is the canonical compatibility set - it is what wizards
    filter task type / route choices against.
    """
    primitives = extract_route_primitives(editable_route)
    return [key for key in TASK_TYPE_REGISTRY if not get_blocking_reasons(primitives, key, editable_route)]


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


def effective_subtype_key(task_type: str, task_subtype: str | None) -> str:
    """The task subtype key the compatibility ruleset should be checked against: the explicit
    CIMA subtype if one was chosen, otherwise the legacy shim for the coarse task_type family."""
    return task_subtype or default_task_type_key_for_family(task_type) or task_type


def no_compatible_routes_message(subtype_key: str) -> str:
    """
    Explain why the internal_route/editable_route picker is empty for the already-chosen task
    type, instead of just rendering an empty dropdown with no explanation.
    """
    definition = get_task_type(subtype_key)
    # The requirements on how the route is arranged are not features it has or lacks.
    features = [requirement for requirement in definition.route_requirements if requirement.ordering is None]
    required = [requirement.key for requirement in features if requirement.minimum > 0]
    forbidden = [
        requirement.key
        for requirement in features
        if requirement.maximum == 0 and requirement.fact != rr.UNKNOWN_LEG_WITHOUT_EXTENSION
    ]
    parts = []
    if required:
        parts.append("requires: " + ", ".join(dict.fromkeys(required)))
    if forbidden:
        parts.append("must not have: " + ", ".join(dict.fromkeys(forbidden)))
    requirement_text = "; ".join(parts) if parts else "no specific route features"
    return (
        "None of the routes you can edit currently support this task type "
        f"(it {requirement_text}). Edit an existing route to add what's missing, or create a new one."
    )


def assert_route_compatible_with_task_type(editable_route, task_type: str, task_subtype: str | None):
    """
    Defense in depth: re-check compatibility server-side before building a Route, so a
    hand-crafted request cannot bypass the filtered task_template/editable_route choices offered
    by any UI (Django wizard forms or the API-driven React flows alike).
    """
    subtype_key = effective_subtype_key(task_type, task_subtype)
    primitives = extract_route_primitives(editable_route)
    reasons = get_blocking_reasons(primitives, subtype_key, editable_route)
    if reasons:
        raise ValidationError(
            f"Route '{editable_route.name}' is not compatible with the selected task type: " + "; ".join(reasons)
        )
