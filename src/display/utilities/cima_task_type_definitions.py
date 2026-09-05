from dataclasses import dataclass

from display.utilities.navigation_task_type_definitions import (
    AIRSPORT_CHALLENGE,
    AIRSPORTS,
    ANR_CORRIDOR,
    LANDING,
    POKER,
    PRECISION,
)

CURVE_NAVIGATION_TIME_ESTIMATION = "curve_navigation_time_estimation"
PRECISION_NAVIGATION = "precision_navigation"
CONTRACT_NAVIGATION_TIME_CONTROLS = "contract_navigation_time_controls"
KNOWN_CIRCUIT = "known_circuit"
UNKNOWN_LEGS = "unknown_legs"
TURNPOINT_HUNT = "turnpoint_hunt"
CIRCLE = "circle"
ANR_CATALOGUE = "anr_catalogue"
LIMITED_FUEL_TURNPOINT_HUNT = "limited_fuel_turnpoint_hunt"
DURATION = "duration"

# Task subtypes with no authored route backbone: the route consists entirely
# of free-map markers (catalogue turnpoints, timed turnpoints, circle
# markers, take-off/landing gates, ...), so no Route.waypoints can be derived
# from the editable route's track. These get an empty placeholder Route
# instead of going through create_precision_route (which requires a track and
# returns None without one).
NO_BACKBONE_TASK_SUBTYPES = (CIRCLE, TURNPOINT_HUNT, LIMITED_FUEL_TURNPOINT_HUNT, DURATION)

LEGACY_PRECISION = "legacy_precision"
LEGACY_ANR_CORRIDOR = "legacy_anr_corridor"
LEGACY_AIRSPORTS = "legacy_airsports"
LEGACY_AIRSPORT_CHALLENGE = "legacy_airsport_challenge"
LEGACY_POKER = "legacy_poker"
LEGACY_LANDING = "legacy_landing"


@dataclass(frozen=True)
class TaskSubtypeDefinition:
    key: str
    display_name: str
    coarse_family: str
    requires_contestant_configuration: bool = False
    required_primitives: tuple[str, ...] = ()
    # Primitives that, if present on the route, make it incompatible with this
    # subtype (for example a corridor task type cannot accept dummy/unknown-leg
    # waypoints). See route_compatibility.get_blocking_reasons.
    forbidden_primitives: tuple[str, ...] = ()
    declaration_schema_key: str | None = None
    scoring_modules: tuple[str, ...] = ()


TASK_SUBTYPE_DEFINITIONS: dict[str, TaskSubtypeDefinition] = {
    LEGACY_PRECISION: TaskSubtypeDefinition(
        key=LEGACY_PRECISION,
        display_name="Legacy precision navigation",
        coarse_family=PRECISION,
        required_primitives=("route_path", "route_waypoint"),
    ),
    LEGACY_ANR_CORRIDOR: TaskSubtypeDefinition(
        key=LEGACY_ANR_CORRIDOR,
        display_name="Legacy ANR corridor",
        coarse_family=ANR_CORRIDOR,
        required_primitives=("route_path", "route_waypoint"),
        forbidden_primitives=("dummy_waypoint", "unknown_leg"),
    ),
    LEGACY_AIRSPORTS: TaskSubtypeDefinition(
        key=LEGACY_AIRSPORTS,
        display_name="Legacy Air Sports Race",
        coarse_family=AIRSPORTS,
        required_primitives=("route_path", "route_waypoint"),
        forbidden_primitives=("dummy_waypoint", "unknown_leg"),
    ),
    LEGACY_AIRSPORT_CHALLENGE: TaskSubtypeDefinition(
        key=LEGACY_AIRSPORT_CHALLENGE,
        display_name="Legacy Air Sport Challenge",
        coarse_family=AIRSPORT_CHALLENGE,
        required_primitives=("route_path", "route_waypoint"),
        forbidden_primitives=("dummy_waypoint", "unknown_leg"),
    ),
    LEGACY_POKER: TaskSubtypeDefinition(
        key=LEGACY_POKER,
        display_name="Legacy poker run",
        coarse_family=POKER,
        required_primitives=("route_path", "route_waypoint"),
    ),
    LEGACY_LANDING: TaskSubtypeDefinition(
        key=LEGACY_LANDING,
        display_name="Legacy landing",
        coarse_family=LANDING,
        required_primitives=("landing_gate",),
    ),
    CURVE_NAVIGATION_TIME_ESTIMATION: TaskSubtypeDefinition(
        key=CURVE_NAVIGATION_TIME_ESTIMATION,
        display_name="2.A1 Curve navigation with time estimation",
        coarse_family=PRECISION,
        requires_contestant_configuration=True,
        # known_time_gate/hidden_gate are not required on the route itself for typical
        # precision-like navigation tasks - there is no structural check for them.
        required_primitives=("route_path", "route_waypoint"),
        declaration_schema_key=CURVE_NAVIGATION_TIME_ESTIMATION,
        scoring_modules=("visible_time_gates", "hidden_gate_sequence", "backtracking"),
    ),
    PRECISION_NAVIGATION: TaskSubtypeDefinition(
        key=PRECISION_NAVIGATION,
        display_name="2.A2 Precision navigation",
        coarse_family=PRECISION,
        requires_contestant_configuration=True,
        # Hidden gates are never required on the route itself - they are optional, not a
        # structural prerequisite (applies to every task type, not just this one).
        required_primitives=("route_path", "route_waypoint"),
        declaration_schema_key=PRECISION_NAVIGATION,
        scoring_modules=("visible_eta", "hidden_gate_sequence", "backtracking"),
    ),
    CONTRACT_NAVIGATION_TIME_CONTROLS: TaskSubtypeDefinition(
        key=CONTRACT_NAVIGATION_TIME_CONTROLS,
        display_name="2.A3 Contract navigation with time controls",
        coarse_family=PRECISION,
        requires_contestant_configuration=True,
        required_primitives=("route_path", "route_waypoint", "catalogue_turnpoint"),
        declaration_schema_key=CONTRACT_NAVIGATION_TIME_CONTROLS,
        scoring_modules=("declared_sequence", "mandatory_time_points", "backtracking"),
    ),
    KNOWN_CIRCUIT: TaskSubtypeDefinition(
        key=KNOWN_CIRCUIT,
        display_name="2.A4 Navigation over a known circuit",
        coarse_family=PRECISION,
        # The contestant may optionally declare specific times at individual
        # turnpoints, overriding the declared-groundspeed-derived time for
        # just that point (see KnownCircuitStrategy).
        requires_contestant_configuration=True,
        # Observation photos and hidden gates are never required on the route itself - they are
        # optional, not a structural prerequisite.
        required_primitives=("route_path", "route_waypoint"),
        scoring_modules=("observation_evidence", "hidden_gate_sequence", "backtracking"),
    ),
    UNKNOWN_LEGS: TaskSubtypeDefinition(
        key=UNKNOWN_LEGS,
        display_name="2.A5 Navigation with unknown legs",
        coarse_family=PRECISION,
        requires_contestant_configuration=False,
        # Observation photos are optional evidence, not a structural prerequisite. The defining
        # feature of an unknown-legs route is a backbone waypoint of pointType "unknown_leg" -
        # see TaskCompiler._validate_unknown_legs_structure, which already enforces this.
        required_primitives=("route_path", "route_waypoint", "unknown_leg"),
        scoring_modules=("unknown_leg_sequence", "observation_evidence", "backtracking"),
    ),
    TURNPOINT_HUNT: TaskSubtypeDefinition(
        key=TURNPOINT_HUNT,
        display_name="2.A6 Turnpoint hunt",
        coarse_family=PRECISION,
        requires_contestant_configuration=True,
        # No route backbone: exactly three standalone timed turnpoints
        # (known_time_gate primitive) plus free catalogue turnpoints.
        required_primitives=("catalogue_turnpoint", "known_time_gate"),
        declaration_schema_key=TURNPOINT_HUNT,
        scoring_modules=("predicted_sequence", "compulsory_timing_gates", "observation_evidence", "backtracking"),
    ),
    CIRCLE: TaskSubtypeDefinition(
        key=CIRCLE,
        display_name="2.A7 Circle",
        coarse_family=PRECISION,
        requires_contestant_configuration=False,
        required_primitives=(
            "circle_center_marker",
            "circle_start_marker",
            "circle_entry_marker",
            "circle_exit_marker",
        ),
        scoring_modules=("circle_entry", "circle_radius", "circle_direction", "altitude_spread"),
    ),
    ANR_CATALOGUE: TaskSubtypeDefinition(
        key=ANR_CATALOGUE,
        display_name="2.A8 Precision navigation Air Nav Race (ANR)",
        coarse_family=ANR_CORRIDOR,
        requires_contestant_configuration=False,
        # route_to_sp_path/route_from_fp_path are optional auxiliary compliance features (see
        # anr_corridor_calculator.py) that most routes never author - they are not required for
        # a route to support this task type.
        required_primitives=("route_path", "route_waypoint"),
        scoring_modules=("route_to_sp", "route_from_fp", "takeoff_timing", "quarantine"),
    ),
    LIMITED_FUEL_TURNPOINT_HUNT: TaskSubtypeDefinition(
        key=LIMITED_FUEL_TURNPOINT_HUNT,
        display_name="2.B2 Limited fuel turnpoint hunt",
        coarse_family=PRECISION,
        requires_contestant_configuration=True,
        # No route backbone: exactly three standalone timed turnpoints
        # (known_time_gate primitive) plus free catalogue turnpoints.
        required_primitives=("catalogue_turnpoint", "known_time_gate"),
        declaration_schema_key=LIMITED_FUEL_TURNPOINT_HUNT,
        scoring_modules=(
            "all_gate_crossings",
            "compulsory_timing_gates",
            "observation_evidence",
            "fuel_compliance",
            "backtracking",
        ),
    ),
    DURATION: TaskSubtypeDefinition(
        key=DURATION,
        display_name="2.B3 Duration",
        coarse_family=PRECISION,
        requires_contestant_configuration=False,
        # No takeoff_gate/landing_gate requirement: calculator_factory.py always adds
        # SpeedInferredTakeoffLandingCalculator for DURATION tasks specifically as "a fallback
        # source of TakeoffPassedEvent/LandingPassedEvent for routes with no authored
        # takeoff/landing gates" - the route-editor wizard guide already documents both gates as
        # optional for this reason (see taskTemplates.ts's cima_b3 template).
    ),
}


LEGACY_DEFAULT_SUBTYPE_BY_FAMILY: dict[str, str] = {
    PRECISION: LEGACY_PRECISION,
    ANR_CORRIDOR: LEGACY_ANR_CORRIDOR,
    AIRSPORTS: LEGACY_AIRSPORTS,
    AIRSPORT_CHALLENGE: LEGACY_AIRSPORT_CHALLENGE,
    POKER: LEGACY_POKER,
    LANDING: LEGACY_LANDING,
}


def get_task_subtype_definition(key: str) -> TaskSubtypeDefinition:
    try:
        return TASK_SUBTYPE_DEFINITIONS[key]
    except KeyError as exc:
        raise ValueError(f"Unknown task subtype '{key}'") from exc


def is_valid_task_subtype(key: str | None) -> bool:
    if key in (None, ""):
        return True
    return key in TASK_SUBTYPE_DEFINITIONS


def get_task_subtypes_for_family(coarse_family: str) -> list[TaskSubtypeDefinition]:
    return [item for item in TASK_SUBTYPE_DEFINITIONS.values() if item.coarse_family == coarse_family]


def validate_subtype_family_compatibility(subtype: str | None, coarse_family: str) -> None:
    if subtype in (None, ""):
        return
    definition = get_task_subtype_definition(subtype)
    if definition.coarse_family != coarse_family:
        raise ValueError(f"Task subtype '{subtype}' is not compatible with coarse family '{coarse_family}'")


def get_default_task_subtype_for_family(coarse_family: str) -> str | None:
    return LEGACY_DEFAULT_SUBTYPE_BY_FAMILY.get(coarse_family)


# The catalogue's per-task maximum score, for subtypes where that maximum is a fixed constant
# (not route-/declaration-dependent) and where the scoring calculator has been confirmed to emit
# properly-signed penalty magnitudes (see contestant_processor.update_score_from_thread's
# desc-sign handling): (score_sorting_direction, initial_score).
#
# - 2.A1-2.A5 (CURVE_NAVIGATION_TIME_ESTIMATION..UNKNOWN_LEGS): the catalogue normalizes every
#   one of these onto a fixed 0-1000 scale ("P = 1000 x Q / Qmax") - gate_calculator.py /
#   backtracking_and_procedure_turns.py, which score all of them, only ever emit positive
#   penalty magnitudes (no positive "achievement" values mixed in), so this is a safe default.
# - CIRCLE (2.A7): Pmax = 250 (documentation/cima/cima_task_catalog.md), matches
#   circle_calculator.py's CIRCLE_MAXIMUM_SCORE.
# - ANR_CATALOGUE (2.A8): "the competitor will start with 2.000 points" (cima_task_catalog.md).
#   anr_corridor_calculator.py only ever emits positive penalty magnitudes.
#
# Deliberately excluded - do not add without also confirming/fixing the underlying calculator:
# - TURNPOINT_HUNT / LIMITED_FUEL_TURNPOINT_HUNT (2.A6/2.B2): the catalogue's maximum is
#   additive and route-dependent (100/photo + 200/gate + a sequence bonus - grows with however
#   many photos/gates the organizer places), not a fixed constant: there is no single correct
#   default here yet, and no calculator computing it from the route. The organizer can still set
#   a value manually via the scorecard editor's General group.
# - DURATION (2.B3): duration_calculator.py mixes a positive "achievement" value (more minutes
#   flown = better, meant to add) with a positive-penalty landing-area-outside deduction (meant
#   to subtract) using the same unconditional-positive convention as circle_calculator.py used
#   to before its fix - flipping this default without first giving duration_calculator.py the
#   same treatment would make an out-of-area landing score *better* under a descending scorecard.
CIMA_SCORING_BASELINE: dict[str, tuple[str, float]] = {
    CURVE_NAVIGATION_TIME_ESTIMATION: ("desc", 1000),
    PRECISION_NAVIGATION: ("desc", 1000),
    CONTRACT_NAVIGATION_TIME_CONTROLS: ("desc", 1000),
    KNOWN_CIRCUIT: ("desc", 1000),
    UNKNOWN_LEGS: ("desc", 1000),
    CIRCLE: ("desc", 250),
    ANR_CATALOGUE: ("desc", 2000),
}


def get_cima_scoring_baseline(subtype: str | None) -> tuple[str, float] | None:
    """
    (score_sorting_direction, initial_score) to apply to a freshly-copied task scorecard for the
    given CIMA task subtype, or None if this subtype has no known fixed-maximum default (legacy
    tasks, an unrecognised/blank subtype, and the subtypes documented above as deliberately
    excluded all return None here - callers should leave the copied scorecard untouched).
    """
    if subtype in (None, ""):
        return None
    return CIMA_SCORING_BASELINE.get(subtype)
