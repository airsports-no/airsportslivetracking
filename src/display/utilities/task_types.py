"""
The single source of truth for what a task type is: rule set -> task type -> one TaskTypeDefinition.

A task type carries everything the rest of the system needs to know about it: its stable key, the rule set and
catalogue code it belongs to, the coarse family stored in Scorecard.calculator, the live-calculator pipeline, the route
requirements, the declaration behaviour, the scoring baseline and the scorecard it is created from.

This module imports nothing from the rest of the display app, so any module can import it. The calculator pipeline is
stored as dotted class paths and imported on first use (calculators import models).

The keys are persisted (NavigationTask.task_subtype, EditableRoute.compatible_task_types and more) and exposed through
the API, so they never change. Task types without a catalogue number keep their historical "legacy_*" keys.
"""

from dataclasses import dataclass, field
from typing import Optional

from django.utils.module_loading import import_string

# The coarse families: the values of Scorecard.calculator and Scorecard.task_type.
PRECISION = "precision"
ANR_CORRIDOR = "anr_corridor"
AIRSPORTS = "airsports"
AIRSPORT_CHALLENGE = "airsportchallenge"
POKER = "poker"
LANDING = "landing"
FAMILY_CHOICES = (
    (PRECISION, "Precision"),
    (ANR_CORRIDOR, "ANR Corridor"),
    (AIRSPORTS, "Air Sports Race"),
    (AIRSPORT_CHALLENGE, "Air Sport Challenge"),
    (POKER, "Poker run"),
    (LANDING, "Landing"),
)

# Task type keys.
LEGACY_PRECISION = "legacy_precision"
LEGACY_ANR_CORRIDOR = "legacy_anr_corridor"
LEGACY_AIRSPORTS = "legacy_airsports"
LEGACY_AIRSPORT_CHALLENGE = "legacy_airsport_challenge"
LEGACY_POKER = "legacy_poker"
LEGACY_LANDING = "legacy_landing"
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

# Scorecards (by shortcut_name) the task types are created from.
CIMA_PRECISION_SCORECARD = "CIMA Precision"
CIMA_ANR_SCORECARD = "CIMA ANR"
AIR_SPORTS_RACE_2025_SCORECARD = "Air Sports Race 2025"


@dataclass(frozen=True)
class RuleSet:
    key: str
    display_name: str


RULE_SET_LEGACY = RuleSet("legacy", "Legacy")
RULE_SET_CIMA_ANNEX_4 = RuleSet("cima_annex_4", "CIMA Annex 4 (tasks 2.A1-2.B3)")
RULE_SET_ANNEX_9 = RuleSet("annex_9", "Air Sport Race Annex 9")
RULE_SETS: dict[str, RuleSet] = {r.key: r for r in (RULE_SET_LEGACY, RULE_SET_CIMA_ANNEX_4, RULE_SET_ANNEX_9)}

_CALCULATORS = "display.calculators."
_GATE = _CALCULATORS + "gate_calculator.GateCalculator"
_TAKEOFF_LANDING = _CALCULATORS + "takeoff_and_landing_gate_calculator.TakeoffAndLandingGateCalculator"
_BACKTRACKING = _CALCULATORS + "backtracking_and_procedure_turns.BacktrackingAndProcedureTurnsCalculator"
_PROHIBITED_ZONE = _CALCULATORS + "prohibited_zone_calculator.ProhibitedZoneCalculator"
_PENALTY_ZONE = _CALCULATORS + "penalty_zone_calculator.PenaltyZoneCalculator"
_CIRCLE = _CALCULATORS + "circle_calculator.CircleCalculator"
_SPEED_INFERRED_TAKEOFF_LANDING = (
    _CALCULATORS + "speed_inferred_takeoff_landing_calculator.SpeedInferredTakeoffLandingCalculator"
)
_DURATION = _CALCULATORS + "duration_calculator.DurationCalculator"
_ANR_CORRIDOR = _CALCULATORS + "anr_corridor_calculator.AnrCorridorCalculator"
_LANDING_PATTERN = _CALCULATORS + "landing_pattern_calculator.LandingPatternCalculator"
_POKER = _CALCULATORS + "poker_calculator.PokerCalculator"

# Order matters: the orchestrator runs the calculators in list order.
PIPELINE_PRECISION = (_GATE, _TAKEOFF_LANDING, _BACKTRACKING, _PROHIBITED_ZONE, _PENALTY_ZONE)
# Backtracking detection assumes monotonic progress along an ordered route; flying the circle around CM would look
# like backtracking, so 2.A7 has none.
PIPELINE_CIRCLE = (_GATE, _CIRCLE, _TAKEOFF_LANDING, _PROHIBITED_ZONE, _PENALTY_ZONE)
# The speed-inferred calculator is the fallback source of take-off and landing events for routes without authored
# take-off and landing gates.
PIPELINE_DURATION = (
    _GATE,
    _TAKEOFF_LANDING,
    _SPEED_INFERRED_TAKEOFF_LANDING,
    _DURATION,
    _BACKTRACKING,
    _PROHIBITED_ZONE,
    _PENALTY_ZONE,
)
PIPELINE_ANR_STYLE = (_GATE, _TAKEOFF_LANDING, _BACKTRACKING, _ANR_CORRIDOR, _PROHIBITED_ZONE, _PENALTY_ZONE)
PIPELINE_LANDING = (_LANDING_PATTERN,)
PIPELINE_POKER = (_POKER, _PROHIBITED_ZONE, _PENALTY_ZONE)
# Used when a scorecard names a family that has no task type.
PIPELINE_DEFAULT = (_GATE,)


@dataclass(frozen=True)
class TaskTypeDefinition:
    key: str
    rule_set: RuleSet
    # The name without the catalogue code; see display_name.
    title: str
    # The value stored in Scorecard.calculator / Scorecard.task_type.
    coarse_family: str
    calculator_pipeline: tuple[str, ...]
    # The number in the task catalogue, for example "2.A3". None for task types the catalogue does not have.
    catalogue_code: str | None = None
    # The task type a new task of the family gets when it does not name one (legacy tasks have no stored subtype).
    default_for_family: bool = False
    requires_contestant_configuration: bool = False
    # False when the route consists entirely of free-map markers, so no Route.waypoints can be derived from the
    # editable route's track and an empty placeholder Route is used instead.
    has_backbone: bool = True
    required_primitives: tuple[str, ...] = ()
    # Primitives that make a route incompatible with the task type (a corridor task cannot accept unknown legs).
    forbidden_primitives: tuple[str, ...] = ()
    declaration_schema_key: str | None = None
    # ContestantTaskConfiguration.is_valid stays False until the contestant has declared.
    declaration_required: bool = False
    # The declaration_payload key holding predicted gate times as absolute timestamps. Rescheduling the take-off after
    # such a declaration would leave the times stale, so the contestant's schedule is locked once they are declared.
    absolute_time_declaration_key: str | None = None
    # (score_sorting_direction, initial_score) of the task's scorecard copy; None when there is no fixed baseline.
    scoring_baseline: tuple[str, float] | None = None
    # Multiplier on every score message when the catalogue's fixed maximum is not the scorecard's initial score. 2.A8
    # starts at 2000 points and P = 1000 * Q / 2000, so the scorecard starts at 1000 and every penalty is halved.
    fixed_scale_factor: float | None = None
    # Whether the gate score is normalised against the worst possible gate deficit (2.A1-2.A5).
    gate_qmax_eligible: bool = False
    # Whether the achievement points are normalised against the sum of all targets (2.A6, 2.B2).
    achievement_qmax_eligible: bool = False
    scoring_modules: tuple[str, ...] = ()
    # The shortcut_name of the scorecard the task is created from. None offers the scorecards of the family that no
    # task type claims.
    scorecard_shortcut_name: str | None = None
    # Only set on the family's default task type, see family_default_scorecard_shortcut_name.
    _family_default_scorecard_shortcut_name: str | None = field(default=None, repr=False)

    @property
    def display_name(self) -> str:
        return f"{self.catalogue_code} {self.title}" if self.catalogue_code else self.title

    @property
    def family_default_scorecard_shortcut_name(self) -> str | None:
        """The scorecard a new task of this task type's family is preselected with, if the family has a default."""
        family_default = _FAMILY_DEFAULTS.get(self.coarse_family)
        return family_default._family_default_scorecard_shortcut_name if family_default else None

    def get_calculators(self) -> list[type]:
        return [import_string(path) for path in self.calculator_pipeline]


_LEGACY_CORRIDOR_FORBIDDEN = ("dummy_waypoint", "unknown_leg")
_BACKBONE = ("route_path", "route_waypoint")
_FREE_TURNPOINTS = ("catalogue_turnpoint", "known_time_gate")

_DEFINITIONS = (
    TaskTypeDefinition(
        key=LEGACY_PRECISION,
        rule_set=RULE_SET_LEGACY,
        title="Legacy precision navigation",
        coarse_family=PRECISION,
        calculator_pipeline=PIPELINE_PRECISION,
        default_for_family=True,
        required_primitives=_BACKBONE,
    ),
    TaskTypeDefinition(
        key=LEGACY_ANR_CORRIDOR,
        rule_set=RULE_SET_LEGACY,
        title="Legacy ANR corridor",
        coarse_family=ANR_CORRIDOR,
        calculator_pipeline=PIPELINE_ANR_STYLE,
        default_for_family=True,
        required_primitives=_BACKBONE,
        forbidden_primitives=_LEGACY_CORRIDOR_FORBIDDEN,
    ),
    TaskTypeDefinition(
        key=LEGACY_AIRSPORTS,
        rule_set=RULE_SET_ANNEX_9,
        title="Legacy Air Sports Race",
        coarse_family=AIRSPORTS,
        calculator_pipeline=PIPELINE_ANR_STYLE,
        default_for_family=True,
        required_primitives=_BACKBONE,
        forbidden_primitives=_LEGACY_CORRIDOR_FORBIDDEN,
        _family_default_scorecard_shortcut_name=AIR_SPORTS_RACE_2025_SCORECARD,
    ),
    TaskTypeDefinition(
        key=LEGACY_AIRSPORT_CHALLENGE,
        rule_set=RULE_SET_ANNEX_9,
        title="Legacy Air Sport Challenge",
        coarse_family=AIRSPORT_CHALLENGE,
        calculator_pipeline=PIPELINE_ANR_STYLE,
        default_for_family=True,
        required_primitives=_BACKBONE,
        forbidden_primitives=_LEGACY_CORRIDOR_FORBIDDEN,
    ),
    TaskTypeDefinition(
        key=LEGACY_POKER,
        rule_set=RULE_SET_LEGACY,
        title="Legacy poker run",
        coarse_family=POKER,
        calculator_pipeline=PIPELINE_POKER,
        default_for_family=True,
        required_primitives=_BACKBONE,
    ),
    TaskTypeDefinition(
        key=LEGACY_LANDING,
        rule_set=RULE_SET_LEGACY,
        title="Legacy landing",
        coarse_family=LANDING,
        calculator_pipeline=PIPELINE_LANDING,
        default_for_family=True,
        required_primitives=("landing_gate",),
    ),
    TaskTypeDefinition(
        key=CURVE_NAVIGATION_TIME_ESTIMATION,
        rule_set=RULE_SET_CIMA_ANNEX_4,
        catalogue_code="2.A1",
        title="Curve navigation with time estimation",
        coarse_family=PRECISION,
        calculator_pipeline=PIPELINE_PRECISION,
        requires_contestant_configuration=True,
        # Hidden gates and known time gates are optional on the route, so there is no structural check for them.
        required_primitives=_BACKBONE,
        declaration_schema_key=CURVE_NAVIGATION_TIME_ESTIMATION,
        declaration_required=True,
        absolute_time_declaration_key="known_time_gate_predictions",
        scoring_baseline=("desc", 1000),
        gate_qmax_eligible=True,
        scoring_modules=("visible_time_gates", "hidden_gate_sequence", "backtracking"),
        scorecard_shortcut_name=CIMA_PRECISION_SCORECARD,
    ),
    TaskTypeDefinition(
        key=PRECISION_NAVIGATION,
        rule_set=RULE_SET_CIMA_ANNEX_4,
        catalogue_code="2.A2",
        title="Precision navigation",
        coarse_family=PRECISION,
        calculator_pipeline=PIPELINE_PRECISION,
        requires_contestant_configuration=True,
        required_primitives=_BACKBONE,
        declaration_schema_key=PRECISION_NAVIGATION,
        declaration_required=True,
        absolute_time_declaration_key="known_time_gate_predictions",
        scoring_baseline=("desc", 1000),
        gate_qmax_eligible=True,
        scoring_modules=("visible_eta", "hidden_gate_sequence", "backtracking"),
        scorecard_shortcut_name=CIMA_PRECISION_SCORECARD,
    ),
    TaskTypeDefinition(
        key=CONTRACT_NAVIGATION_TIME_CONTROLS,
        rule_set=RULE_SET_CIMA_ANNEX_4,
        catalogue_code="2.A3",
        title="Contract navigation with time controls",
        coarse_family=PRECISION,
        calculator_pipeline=PIPELINE_PRECISION,
        requires_contestant_configuration=True,
        required_primitives=("route_path", "route_waypoint", "catalogue_turnpoint"),
        declaration_schema_key=CONTRACT_NAVIGATION_TIME_CONTROLS,
        # The declared times are relative to take-off, so they follow the schedule.
        declaration_required=True,
        scoring_baseline=("desc", 1000),
        gate_qmax_eligible=True,
        scoring_modules=("declared_sequence", "mandatory_time_points", "backtracking"),
        scorecard_shortcut_name=CIMA_PRECISION_SCORECARD,
    ),
    TaskTypeDefinition(
        key=KNOWN_CIRCUIT,
        rule_set=RULE_SET_CIMA_ANNEX_4,
        catalogue_code="2.A4",
        title="Navigation over a known circuit",
        coarse_family=PRECISION,
        calculator_pipeline=PIPELINE_PRECISION,
        # The contestant may declare times for individual turnpoints, overriding the speed-derived time for that point.
        # Most points are speed-derived and move with the schedule, so only declared overrides lock the schedule.
        requires_contestant_configuration=True,
        required_primitives=_BACKBONE,
        absolute_time_declaration_key="turnpoint_time_overrides",
        scoring_baseline=("desc", 1000),
        gate_qmax_eligible=True,
        scoring_modules=("observation_evidence", "hidden_gate_sequence", "backtracking"),
        scorecard_shortcut_name=CIMA_PRECISION_SCORECARD,
    ),
    TaskTypeDefinition(
        key=UNKNOWN_LEGS,
        rule_set=RULE_SET_CIMA_ANNEX_4,
        catalogue_code="2.A5",
        title="Navigation with unknown legs",
        coarse_family=PRECISION,
        calculator_pipeline=PIPELINE_PRECISION,
        # The defining feature is a backbone waypoint of pointType "unknown_leg".
        required_primitives=("route_path", "route_waypoint", "unknown_leg"),
        scoring_baseline=("desc", 1000),
        gate_qmax_eligible=True,
        scoring_modules=("unknown_leg_sequence", "observation_evidence", "backtracking"),
        scorecard_shortcut_name=CIMA_PRECISION_SCORECARD,
    ),
    TaskTypeDefinition(
        key=TURNPOINT_HUNT,
        rule_set=RULE_SET_CIMA_ANNEX_4,
        catalogue_code="2.A6",
        title="Turnpoint hunt",
        coarse_family=PRECISION,
        calculator_pipeline=PIPELINE_PRECISION,
        requires_contestant_configuration=True,
        # Exactly three standalone timed turnpoints plus free catalogue turnpoints.
        has_backbone=False,
        required_primitives=_FREE_TURNPOINTS,
        declaration_schema_key=TURNPOINT_HUNT,
        declaration_required=True,
        absolute_time_declaration_key="compulsory_point_times",
        # Additive from zero: the maximum depends on how many photos and gates the organiser places.
        scoring_baseline=("desc", 0),
        achievement_qmax_eligible=True,
        scoring_modules=("predicted_sequence", "compulsory_timing_gates", "observation_evidence", "backtracking"),
        scorecard_shortcut_name=CIMA_PRECISION_SCORECARD,
    ),
    TaskTypeDefinition(
        key=CIRCLE,
        rule_set=RULE_SET_CIMA_ANNEX_4,
        catalogue_code="2.A7",
        title="Circle",
        coarse_family=PRECISION,
        calculator_pipeline=PIPELINE_CIRCLE,
        has_backbone=False,
        required_primitives=(
            "circle_center_marker",
            "circle_start_marker",
            "circle_entry_marker",
            "circle_exit_marker",
        ),
        # Pmax = 250, matching CIRCLE_MAXIMUM_SCORE in circle_calculator.py.
        scoring_baseline=("desc", 250),
        scoring_modules=("circle_entry", "circle_radius", "circle_direction", "altitude_spread"),
        scorecard_shortcut_name=CIMA_PRECISION_SCORECARD,
    ),
    TaskTypeDefinition(
        key=ANR_CATALOGUE,
        rule_set=RULE_SET_CIMA_ANNEX_4,
        catalogue_code="2.A8",
        title="Precision navigation Air Nav Race (ANR)",
        coarse_family=ANR_CORRIDOR,
        calculator_pipeline=PIPELINE_ANR_STYLE,
        # route_to_sp_path and route_from_fp_path are optional auxiliary features most routes never author.
        required_primitives=_BACKBONE,
        scoring_baseline=("desc", 1000),
        fixed_scale_factor=0.5,
        scoring_modules=("route_to_sp", "route_from_fp", "takeoff_timing", "quarantine"),
        scorecard_shortcut_name=CIMA_ANR_SCORECARD,
    ),
    TaskTypeDefinition(
        key=LIMITED_FUEL_TURNPOINT_HUNT,
        rule_set=RULE_SET_CIMA_ANNEX_4,
        catalogue_code="2.B2",
        title="Limited fuel turnpoint hunt",
        coarse_family=PRECISION,
        calculator_pipeline=PIPELINE_PRECISION,
        requires_contestant_configuration=True,
        has_backbone=False,
        required_primitives=_FREE_TURNPOINTS,
        declaration_schema_key=LIMITED_FUEL_TURNPOINT_HUNT,
        # The declaration is entirely optional (minimum_required=0), so it never fails validation.
        declaration_required=False,
        absolute_time_declaration_key="compulsory_point_times",
        scoring_baseline=("desc", 0),
        achievement_qmax_eligible=True,
        scoring_modules=(
            "all_gate_crossings",
            "compulsory_timing_gates",
            "observation_evidence",
            "fuel_compliance",
            "backtracking",
        ),
        scorecard_shortcut_name=CIMA_PRECISION_SCORECARD,
    ),
    TaskTypeDefinition(
        key=DURATION,
        rule_set=RULE_SET_CIMA_ANNEX_4,
        catalogue_code="2.B3",
        title="Duration",
        coarse_family=PRECISION,
        calculator_pipeline=PIPELINE_DURATION,
        # No take-off or landing gate is required: SpeedInferredTakeoffLandingCalculator is always part of the
        # pipeline as the fallback source of those events. There is no scoring baseline because the duration
        # calculator mixes an achievement with a penalty and has not been given signed score messages yet.
        has_backbone=False,
    ),
)

TASK_TYPE_REGISTRY: dict[str, TaskTypeDefinition] = {definition.key: definition for definition in _DEFINITIONS}
assert len(TASK_TYPE_REGISTRY) == len(_DEFINITIONS), "Duplicate task type key"

_FAMILY_DEFAULTS: dict[str, TaskTypeDefinition] = {
    definition.coarse_family: definition for definition in _DEFINITIONS if definition.default_for_family
}


class UnknownTaskType(ValueError):
    pass


def get_task_type(key: str) -> TaskTypeDefinition:
    try:
        return TASK_TYPE_REGISTRY[key]
    except KeyError as exc:
        raise UnknownTaskType(f"Unknown task type '{key}'") from exc


def find_task_type(key: str | None) -> Optional[TaskTypeDefinition]:
    """The task type for [key], or None when the key is empty or not defined."""
    return TASK_TYPE_REGISTRY.get(key) if key else None


def task_types_in_rule_set(rule_set: RuleSet | str) -> list[TaskTypeDefinition]:
    rule_set_key = rule_set.key if isinstance(rule_set, RuleSet) else rule_set
    return [definition for definition in _DEFINITIONS if definition.rule_set.key == rule_set_key]


def task_types_in_family(coarse_family: str) -> list[TaskTypeDefinition]:
    return [definition for definition in _DEFINITIONS if definition.coarse_family == coarse_family]


def default_task_type_for_family(coarse_family: str) -> Optional[TaskTypeDefinition]:
    return _FAMILY_DEFAULTS.get(coarse_family)


def task_type_for(navigation_task) -> Optional[TaskTypeDefinition]:
    """
    The task type of a navigation task: its stored subtype, or the family's default when it has none. None when there
    is neither. Raises UnknownTaskType for a stored subtype that is not defined.
    """
    key = navigation_task.effective_task_subtype
    return get_task_type(str(key)) if key else None
