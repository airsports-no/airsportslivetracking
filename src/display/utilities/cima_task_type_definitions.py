from dataclasses import dataclass

from display.utilities.navigation_task_type_definitions import (
    AIRSPORTS,
    AIRSPORT_CHALLENGE,
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
    declaration_schema_key: str | None = None
    scoring_modules: tuple[str, ...] = ()


TASK_SUBTYPE_DEFINITIONS: dict[str, TaskSubtypeDefinition] = {
    LEGACY_PRECISION: TaskSubtypeDefinition(
        key=LEGACY_PRECISION,
        display_name="Legacy precision navigation",
        coarse_family=PRECISION,
    ),
    LEGACY_ANR_CORRIDOR: TaskSubtypeDefinition(
        key=LEGACY_ANR_CORRIDOR,
        display_name="Legacy ANR corridor",
        coarse_family=ANR_CORRIDOR,
    ),
    LEGACY_AIRSPORTS: TaskSubtypeDefinition(
        key=LEGACY_AIRSPORTS,
        display_name="Legacy Air Sports Race",
        coarse_family=AIRSPORTS,
    ),
    LEGACY_AIRSPORT_CHALLENGE: TaskSubtypeDefinition(
        key=LEGACY_AIRSPORT_CHALLENGE,
        display_name="Legacy Air Sport Challenge",
        coarse_family=AIRSPORT_CHALLENGE,
    ),
    LEGACY_POKER: TaskSubtypeDefinition(
        key=LEGACY_POKER,
        display_name="Legacy poker run",
        coarse_family=POKER,
    ),
    LEGACY_LANDING: TaskSubtypeDefinition(
        key=LEGACY_LANDING,
        display_name="Legacy landing",
        coarse_family=LANDING,
    ),
    CURVE_NAVIGATION_TIME_ESTIMATION: TaskSubtypeDefinition(
        key=CURVE_NAVIGATION_TIME_ESTIMATION,
        display_name="2.A1 Curve navigation with time estimation",
        coarse_family=PRECISION,
        requires_contestant_configuration=True,
        required_primitives=("route_path", "known_time_gate", "hidden_gate"),
        declaration_schema_key=CURVE_NAVIGATION_TIME_ESTIMATION,
        scoring_modules=("visible_time_gates", "hidden_gate_sequence", "backtracking"),
    ),
    PRECISION_NAVIGATION: TaskSubtypeDefinition(
        key=PRECISION_NAVIGATION,
        display_name="2.A2 Precision navigation",
        coarse_family=PRECISION,
        requires_contestant_configuration=True,
        required_primitives=("route_path", "route_waypoint", "hidden_gate"),
        declaration_schema_key=PRECISION_NAVIGATION,
        scoring_modules=("visible_eta", "hidden_gate_sequence", "backtracking"),
    ),
    CONTRACT_NAVIGATION_TIME_CONTROLS: TaskSubtypeDefinition(
        key=CONTRACT_NAVIGATION_TIME_CONTROLS,
        display_name="2.A3 Contract navigation with time controls",
        coarse_family=PRECISION,
        requires_contestant_configuration=True,
        required_primitives=("catalogue_turnpoint",),
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
        required_primitives=("route_path", "hidden_gate", "observation_photo"),
        scoring_modules=("observation_evidence", "hidden_gate_sequence", "backtracking"),
    ),
    UNKNOWN_LEGS: TaskSubtypeDefinition(
        key=UNKNOWN_LEGS,
        display_name="2.A5 Navigation with unknown legs",
        coarse_family=PRECISION,
        requires_contestant_configuration=False,
        required_primitives=("route_path", "observation_photo"),
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
        required_primitives=("circle_center_marker", "circle_start_marker", "circle_entry_marker", "circle_exit_marker"),
        scoring_modules=("circle_entry", "circle_radius", "circle_direction", "altitude_spread"),
    ),
    ANR_CATALOGUE: TaskSubtypeDefinition(
        key=ANR_CATALOGUE,
        display_name="2.A8 Precision navigation Air Nav Race (ANR)",
        coarse_family=ANR_CORRIDOR,
        requires_contestant_configuration=False,
        required_primitives=("route_path", "route_to_sp_path", "route_from_fp_path"),
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
        scoring_modules=("all_gate_crossings", "compulsory_timing_gates", "observation_evidence", "fuel_compliance", "backtracking"),
    ),
    DURATION: TaskSubtypeDefinition(
        key=DURATION,
        display_name="2.B3 Duration",
        coarse_family=PRECISION,
        requires_contestant_configuration=False,
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
        raise ValueError(
            f"Task subtype '{subtype}' is not compatible with coarse family '{coarse_family}'"
        )


def get_default_task_subtype_for_family(coarse_family: str) -> str | None:
    return LEGACY_DEFAULT_SUBTYPE_BY_FAMILY.get(coarse_family)
