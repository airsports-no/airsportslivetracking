"""
The single source of truth for what a task type is: rule set -> task type -> one TaskTypeDefinition.

A task type carries everything the rest of the system needs to know about it: its stable key, the rule set and
catalogue code it belongs to, the coarse family stored in Scorecard.calculator, the live-calculator pipeline, the route
requirements, the declaration behaviour, the scoring model and the scorecard it is created from.

This module imports nothing from the rest of the display app except the plain gate type constants, so any module can
import it. The calculator pipeline is
stored as dotted class paths and imported on first use (calculators import models).

The keys are persisted (NavigationTask.task_subtype, EditableRoute.compatible_task_types and more) and exposed through
the API, so they never change. Task types without a catalogue number keep their historical "legacy_*" keys.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

from django.utils.module_loading import import_string

from display.utilities import route_requirements as rr
from display.utilities.gate_definitions import (
    CIRCLE_ENTRY,
    CIRCLE_EXIT,
    CIRCLE_START,
    FINISHPOINT,
    LANDING_GATE,
    STARTINGPOINT,
    TAKEOFF_GATE,
    TURNPOINT,
)
from display.utilities.route_requirements import RouteRequirement, WaypointOrdering, WaypointSpec

logger = logging.getLogger(__name__)

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

# How a task turns what happened in the flight into a score (Scorecard.config["scoring_model"]).
# "penalties": the score is the sum of the penalties (or, on a descending scorecard, the initial score minus them); the
# lowest total wins. "quality": the contestant has a raw quality score Q (the starting quality minus penalties plus
# achievements) and the task score P is derived from the Q of all contestants of the task (FAI Section 10, Annex 3).
SCORING_PENALTIES = "penalties"
SCORING_QUALITY = "quality"
SCORING_MODELS = ((SCORING_PENALTIES, "Penalties"), (SCORING_QUALITY, "Quality (normalised task score)"))

# What Q is divided by (Scorecard.config["qmax_policy"], quality model only).
QMAX_BEST_IN_TASK = "best_in_task"  # P = task_value x Q / (the best Q of the task)
QMAX_THEORETICAL = "theoretical"  # P = task_value x Q / (the contestant's own theoretical maximum Q)
QMAX_ABSOLUTE = "absolute"  # P is a fixed scale of Q, independent of the other contestants
QMAX_POLICIES = (
    (QMAX_BEST_IN_TASK, "Best in task"),
    (QMAX_THEORETICAL, "Theoretical maximum"),
    (QMAX_ABSOLUTE, "Absolute"),
)

# The task value (maximum task score) the organiser may announce for a quality task (Annex 3, 2.3.4).
DEFAULT_TASK_VALUE = 1000.0
MIN_TASK_VALUE = 500.0
MAX_TASK_VALUE = 1500.0

# Where the raw quality Q of a contestant starts.
QUALITY_START_GATE_DEFICIT = "gate_deficit"  # the worst possible gate deficit of the contestant's own route (2.A1-2.A5)
QUALITY_START_FIXED = "fixed"  # TaskTypeDefinition.fixed_quality (2.A7, 2.A8)
QUALITY_START_ACHIEVEMENT = "achievement"  # zero: the contestant earns points (2.A6, 2.B2, 2.B3)

# The percentage of the task score one backtrack costs in 2.A1-2.A5 (Annex 4: "a 50% penalty will be imposed").
CIMA_BACKTRACKING_PERCENTAGE = 50.0

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
    # What the route must contain (and must not), as data; evaluated by display.services.route_compatibility both when
    # the route editor reports which task types a route suits and when a task is compiled.
    route_requirements: tuple[RouteRequirement, ...] = ()
    declaration_schema_key: str | None = None
    # ContestantTaskConfiguration.is_valid stays False until the contestant has declared.
    declaration_required: bool = False
    # The declaration_payload key holding predicted gate times as absolute timestamps. Rescheduling the take-off after
    # such a declaration would leave the times stale, so the contestant's schedule is locked once they are declared.
    absolute_time_declaration_key: str | None = None
    # The default scoring model of the task's scorecard copy (see SCORING_QUALITY). A task whose scorecard stores no
    # scoring_model behaves as this.
    scoring_model: str = SCORING_PENALTIES
    # The default qmax_policy of a quality task.
    qmax_policy: str = QMAX_BEST_IN_TASK
    # Where Q starts (quality model only). The starting quality is also the theoretical maximum of the deficit-style
    # tasks; for the achievement-style tasks the theoretical maximum is the sum of everything that can be earned.
    quality_start: str = QUALITY_START_ACHIEVEMENT
    # The starting quality of QUALITY_START_FIXED: 250 for the circle (Pmax), 2000 for the ANR.
    fixed_quality: float | None = None
    # The absolute scale of QMAX_ABSOLUTE: P = task_value x Q / absolute_reference (2.A8: 1000 x Q / 2000). None: P = Q
    # (2.A7, whose formula value is the score).
    absolute_reference: float | None = None
    scoring_modules: tuple[str, ...] = ()
    # The shortcut_name of the scorecard the task is created from. None offers the scorecards of the family that no
    # task type claims.
    scorecard_shortcut_name: str | None = None
    # The gate types the scorecard has to cover when the route has no backbone to read them from (see has_backbone).
    gate_types_without_backbone: tuple[str, ...] = ()
    # A hidden gate crossed a second time, in either direction, or first crossed against the route is invalidated:
    # it is worth what a gate not correctly crossed is worth (2.A1, 2.A2, 2.A4, 2.A5; Annex 4 "crossing the same gate
    # more than once in any direction invalidates the gate").
    repeated_hidden_gate_crossing_invalidates: bool = False
    # Backtracking costs a percentage of the task score instead of flat points (2.A1-2.A5: "a 50% penalty will be
    # imposed for backtracking"). The value is the percentage used when the task's scorecard stores none
    # (Scorecard.backtracking_penalty_percentage); 0 uses the flat points of the scorecard, which a stored 0 also does.
    # Only task types that set this are affected by the scorecard setting.
    backtracking_penalty_percentage: float = 0.0
    # Backtracking is defined as in FAI Section 10, 4.24.5: it only counts inside the corridor around the active leg,
    # whose width is the gate width, and not within the turn point radius (see display.calculators.backtracking_geometry).
    # Legacy rule sets keep their grace distances and times.
    backtracking_within_corridor: bool = False
    # Turnpoints are targets that earn points when collected: compulsory timing gates, target values, the order they
    # were collected in, the sequence bonus and the maximum duration (2.A6, 2.B2).
    scores_turnpoint_hunt_targets: bool = False
    # The flight is penalised for gates passed after the declared fuel endurance (2.B2).
    has_fuel_deadline: bool = False
    # Legs flown faster or slower than the declared speed are penalised (2.A4).
    scores_speed_keeping: bool = False
    # Points declared after the middle point are invalid when flown before the middle point's time (2.A3).
    has_post_mp_rule: bool = False
    # The gate times follow from the declared period T, not from the route's legs, so they move along with an adaptive
    # start (2.A3).
    gate_times_from_declared_period: bool = False
    # The map without a selected contestant shows only the backbone waypoints (SP, MP, FP) as circles, without legs or
    # catalogue points; the declared route is drawn once a contestant is selected (2.A3).
    general_map_shows_backbone_only: bool = False
    # The route-to-SP and route-from-FP corridors are checked before the start and after the finish (2.A8).
    has_auxiliary_route_checks: bool = False
    # The take-off gate is scored as take-off timing under its own score type (2.A8).
    scores_takeoff_timing: bool = False
    # The crew does not know the route legs in advance: the flight order only gives the start and finish times, and
    # the targets come from the compiled payload (2.A5).
    has_unknown_legs: bool = False
    # The observation photos the crew registers (not the route's waypoint photos) earn points per observation (2.A4,
    # 2.A5), where legacy tasks deduct a penalty per missed observation.
    observation_photos_award_points: bool = False
    # Dotted path of the ContestantTaskCompilerStrategy that validates the declaration and builds the contestant's
    # effective route; None for task types without declarations or per-contestant route changes.
    contestant_compiler_strategy: str | None = None
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

    @property
    def is_legacy(self) -> bool:
        """The task types that stand in for tasks created before task types existed: the family defaults."""
        return self.default_for_family

    @property
    def has_backtracking_detection(self) -> bool:
        return _BACKTRACKING in self.calculator_pipeline

    @property
    def scores_circle(self) -> bool:
        return _CIRCLE in self.calculator_pipeline

    @property
    def scores_duration(self) -> bool:
        return _DURATION in self.calculator_pipeline

    def get_calculators(self) -> list[type]:
        return [import_string(path) for path in self.calculator_pipeline]


_CONTESTANT_STRATEGIES = "display.services.contestant_task_compiler."

_ROUTE_PATH = rr.present(rr.ROUTE_PATH, "Route path")
_ROUTE_WAYPOINT = rr.present(rr.ROUTE_WAYPOINT, "Route waypoint")
_BACKBONE = (_ROUTE_PATH, _ROUTE_WAYPOINT)
_LEGACY_CORRIDOR_FORBIDDEN = (
    rr.forbidden(rr.DUMMY_WAYPOINT, "Dummy waypoints"),
    rr.forbidden(rr.UNKNOWN_LEG, "Unknown-leg points"),
)
# The route starts at SP and finishes at FP.
_STARTS_AT_SP_ENDS_AT_FP = WaypointOrdering(first=WaypointSpec(STARTINGPOINT), last=WaypointSpec(FINISHPOINT))
_FREE_TURNPOINTS_REQUIREMENTS = (
    rr.forbidden(
        rr.ROUTE_PATH,
        "Route path",
        message=(
            "Turnpoint hunt requires no route backbone. Place the compulsory points as standalone timed turnpoints "
            "instead."
        ),
    ),
    rr.exactly(
        rr.NAMED_KNOWN_TIME_GATE,
        "Compulsory (timed) points",
        3,
        key=rr.KNOWN_TIME_GATE,
        message="Turnpoint hunt requires exactly three compulsory (timed) points.",
    ),
    rr.present(
        rr.NAMED_CATALOGUE_TURNPOINT,
        "Free catalogue targets",
        key=rr.CATALOGUE_TURNPOINT,
        message="Turnpoint hunt requires at least one free catalogue target.",
    ),
)

_DEFINITIONS = (
    TaskTypeDefinition(
        key=LEGACY_PRECISION,
        rule_set=RULE_SET_LEGACY,
        title="Legacy precision navigation",
        coarse_family=PRECISION,
        calculator_pipeline=PIPELINE_PRECISION,
        default_for_family=True,
        route_requirements=_BACKBONE,
    ),
    TaskTypeDefinition(
        key=LEGACY_ANR_CORRIDOR,
        rule_set=RULE_SET_LEGACY,
        title="Legacy ANR corridor",
        coarse_family=ANR_CORRIDOR,
        calculator_pipeline=PIPELINE_ANR_STYLE,
        default_for_family=True,
        route_requirements=_BACKBONE + _LEGACY_CORRIDOR_FORBIDDEN,
    ),
    TaskTypeDefinition(
        key=LEGACY_AIRSPORTS,
        rule_set=RULE_SET_ANNEX_9,
        title="Legacy Air Sports Race",
        coarse_family=AIRSPORTS,
        calculator_pipeline=PIPELINE_ANR_STYLE,
        default_for_family=True,
        route_requirements=_BACKBONE + _LEGACY_CORRIDOR_FORBIDDEN,
        _family_default_scorecard_shortcut_name=AIR_SPORTS_RACE_2025_SCORECARD,
    ),
    TaskTypeDefinition(
        key=LEGACY_AIRSPORT_CHALLENGE,
        rule_set=RULE_SET_ANNEX_9,
        title="Legacy Air Sport Challenge",
        coarse_family=AIRSPORT_CHALLENGE,
        calculator_pipeline=PIPELINE_ANR_STYLE,
        default_for_family=True,
        route_requirements=_BACKBONE + _LEGACY_CORRIDOR_FORBIDDEN,
    ),
    TaskTypeDefinition(
        key=LEGACY_POKER,
        rule_set=RULE_SET_LEGACY,
        title="Legacy poker run",
        coarse_family=POKER,
        calculator_pipeline=PIPELINE_POKER,
        default_for_family=True,
        route_requirements=_BACKBONE,
    ),
    TaskTypeDefinition(
        key=LEGACY_LANDING,
        rule_set=RULE_SET_LEGACY,
        title="Legacy landing",
        coarse_family=LANDING,
        calculator_pipeline=PIPELINE_LANDING,
        default_for_family=True,
        route_requirements=(rr.present(rr.LANDING_GATE, "Landing gate"),),
    ),
    TaskTypeDefinition(
        key=CURVE_NAVIGATION_TIME_ESTIMATION,
        rule_set=RULE_SET_CIMA_ANNEX_4,
        catalogue_code="2.A1",
        title="Curve navigation with time estimation",
        coarse_family=PRECISION,
        calculator_pipeline=PIPELINE_PRECISION,
        requires_contestant_configuration=True,
        # Hidden gates and known time gates are optional on the route; the defining feature is a curved leg.
        route_requirements=_BACKBONE
        + (rr.present(rr.CURVED_LEG, "Curved legs", message="Curve navigation requires at least one curved leg."),),
        declaration_schema_key=CURVE_NAVIGATION_TIME_ESTIMATION,
        declaration_required=True,
        absolute_time_declaration_key="known_time_gate_predictions",
        scoring_model=SCORING_QUALITY,
        quality_start=QUALITY_START_GATE_DEFICIT,
        scoring_modules=("visible_time_gates", "hidden_gate_sequence", "backtracking"),
        scorecard_shortcut_name=CIMA_PRECISION_SCORECARD,
        backtracking_penalty_percentage=CIMA_BACKTRACKING_PERCENTAGE,
        backtracking_within_corridor=True,
        repeated_hidden_gate_crossing_invalidates=True,
        contestant_compiler_strategy=_CONTESTANT_STRATEGIES + "CurveOrPrecisionNavigationStrategy",
    ),
    TaskTypeDefinition(
        key=PRECISION_NAVIGATION,
        rule_set=RULE_SET_CIMA_ANNEX_4,
        catalogue_code="2.A2",
        title="Precision navigation",
        coarse_family=PRECISION,
        calculator_pipeline=PIPELINE_PRECISION,
        requires_contestant_configuration=True,
        route_requirements=(
            _ROUTE_PATH,
            rr.RouteRequirement(
                "route_waypoints",
                rr.ROUTE_WAYPOINT,
                "Route waypoints (SP, turn points, FP)",
                minimum=3,
                message="Precision navigation requires a start, at least one intermediate turn point, and a finish.",
            ),
            rr.forbidden(
                rr.ROUTE_WAYPOINT_ORDER_VIOLATIONS,
                "Route starts at SP and finishes at FP",
                key="route_waypoint_order",
                ordering=_STARTS_AT_SP_ENDS_AT_FP,
                depends_on=("route_waypoints",),
                message="Precision navigation route waypoints must start at SP and finish at FP.",
            ),
        ),
        declaration_schema_key=PRECISION_NAVIGATION,
        declaration_required=True,
        absolute_time_declaration_key="known_time_gate_predictions",
        scoring_model=SCORING_QUALITY,
        quality_start=QUALITY_START_GATE_DEFICIT,
        scoring_modules=("visible_eta", "hidden_gate_sequence", "backtracking"),
        scorecard_shortcut_name=CIMA_PRECISION_SCORECARD,
        backtracking_penalty_percentage=CIMA_BACKTRACKING_PERCENTAGE,
        backtracking_within_corridor=True,
        repeated_hidden_gate_crossing_invalidates=True,
        contestant_compiler_strategy=_CONTESTANT_STRATEGIES + "CurveOrPrecisionNavigationStrategy",
    ),
    TaskTypeDefinition(
        key=CONTRACT_NAVIGATION_TIME_CONTROLS,
        rule_set=RULE_SET_CIMA_ANNEX_4,
        catalogue_code="2.A3",
        title="Contract navigation with time controls",
        coarse_family=PRECISION,
        calculator_pipeline=PIPELINE_PRECISION,
        requires_contestant_configuration=True,
        route_requirements=(
            _ROUTE_PATH,
            rr.exactly(
                rr.ROUTE_WAYPOINT,
                "Route waypoints (SP, MP, FP)",
                3,
                key="route_waypoints",
                message="Contract navigation requires exactly three route waypoints: SP, MP, and FP.",
            ),
            rr.forbidden(
                rr.ROUTE_WAYPOINT_ORDER_VIOLATIONS,
                "Route waypoints in the order SP, MP, FP",
                key="route_waypoint_order",
                ordering=WaypointOrdering(
                    exact=(
                        WaypointSpec(STARTINGPOINT, "SP"),
                        WaypointSpec(TURNPOINT, "MP"),
                        WaypointSpec(FINISHPOINT, "FP"),
                    )
                ),
                depends_on=("route_waypoints",),
                message="Contract navigation route waypoints must be authored in order as SP, MP, and FP.",
            ),
            rr.present(
                rr.FREE_CATALOGUE_TURNPOINT,
                "Free catalogue waypoints",
                key=rr.CATALOGUE_TURNPOINT,
                message="Contract navigation requires at least one free catalogue waypoint.",
            ),
        ),
        declaration_schema_key=CONTRACT_NAVIGATION_TIME_CONTROLS,
        # The declared times are relative to take-off, so they follow the schedule.
        declaration_required=True,
        scoring_model=SCORING_QUALITY,
        quality_start=QUALITY_START_GATE_DEFICIT,
        scoring_modules=("declared_sequence", "mandatory_time_points", "backtracking"),
        scorecard_shortcut_name=CIMA_PRECISION_SCORECARD,
        backtracking_penalty_percentage=CIMA_BACKTRACKING_PERCENTAGE,
        backtracking_within_corridor=True,
        has_post_mp_rule=True,
        general_map_shows_backbone_only=True,
        gate_times_from_declared_period=True,
        contestant_compiler_strategy=_CONTESTANT_STRATEGIES + "ContractNavigationStrategy",
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
        route_requirements=_BACKBONE,
        absolute_time_declaration_key="turnpoint_time_overrides",
        scoring_model=SCORING_QUALITY,
        quality_start=QUALITY_START_GATE_DEFICIT,
        scoring_modules=("observation_evidence", "hidden_gate_sequence", "backtracking"),
        scorecard_shortcut_name=CIMA_PRECISION_SCORECARD,
        backtracking_penalty_percentage=CIMA_BACKTRACKING_PERCENTAGE,
        backtracking_within_corridor=True,
        repeated_hidden_gate_crossing_invalidates=True,
        scores_speed_keeping=True,
        observation_photos_award_points=True,
        contestant_compiler_strategy=_CONTESTANT_STRATEGIES + "KnownCircuitStrategy",
    ),
    TaskTypeDefinition(
        key=UNKNOWN_LEGS,
        rule_set=RULE_SET_CIMA_ANNEX_4,
        catalogue_code="2.A5",
        title="Navigation with unknown legs",
        coarse_family=PRECISION,
        calculator_pipeline=PIPELINE_PRECISION,
        # The defining feature is a backbone waypoint of pointType "unknown_leg".
        route_requirements=(
            _ROUTE_PATH,
            rr.RouteRequirement(
                "route_waypoints",
                rr.ROUTE_WAYPOINT,
                "Route waypoints (SP, trigger segment, FP)",
                minimum=3,
                message="Unknown legs requires at least a start point, one trigger segment, and a finish point.",
            ),
            rr.forbidden(
                rr.ROUTE_WAYPOINT_ORDER_VIOLATIONS,
                "Route starts at SP and finishes at FP",
                key="route_waypoint_order",
                ordering=_STARTS_AT_SP_ENDS_AT_FP,
                depends_on=("route_waypoints",),
                message="Unknown legs route waypoints must start at SP and finish at FP.",
            ),
            rr.present(rr.NAMED_UNKNOWN_LEG, "Unknown-leg points", key=rr.UNKNOWN_LEG),
            rr.forbidden(
                rr.UNKNOWN_LEG_WITHOUT_EXTENSION,
                "Unknown-leg points without an extension waypoint",
                key="unknown_leg_extension",
                depends_on=("route_waypoints",),
                message="Unknown legs requires at least one extension waypoint after each unknown-leg point.",
            ),
        ),
        scoring_model=SCORING_QUALITY,
        quality_start=QUALITY_START_GATE_DEFICIT,
        scoring_modules=("unknown_leg_sequence", "observation_evidence", "backtracking"),
        scorecard_shortcut_name=CIMA_PRECISION_SCORECARD,
        backtracking_penalty_percentage=CIMA_BACKTRACKING_PERCENTAGE,
        backtracking_within_corridor=True,
        repeated_hidden_gate_crossing_invalidates=True,
        has_unknown_legs=True,
        observation_photos_award_points=True,
        contestant_compiler_strategy=_CONTESTANT_STRATEGIES + "UnknownLegsStrategy",
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
        route_requirements=_FREE_TURNPOINTS_REQUIREMENTS,
        declaration_schema_key=TURNPOINT_HUNT,
        declaration_required=True,
        absolute_time_declaration_key="compulsory_point_times",
        # Additive from zero: the maximum depends on how many photos and gates the organiser places.
        scoring_model=SCORING_QUALITY,
        scoring_modules=("predicted_sequence", "compulsory_timing_gates", "observation_evidence", "backtracking"),
        scorecard_shortcut_name=CIMA_PRECISION_SCORECARD,
        scores_turnpoint_hunt_targets=True,
        contestant_compiler_strategy=_CONTESTANT_STRATEGIES + "TurnpointHuntStrategy",
        gate_types_without_backbone=(TURNPOINT,),
    ),
    TaskTypeDefinition(
        key=CIRCLE,
        rule_set=RULE_SET_CIMA_ANNEX_4,
        catalogue_code="2.A7",
        title="Circle",
        coarse_family=PRECISION,
        calculator_pipeline=PIPELINE_CIRCLE,
        has_backbone=False,
        route_requirements=(
            rr.exactly(rr.CIRCLE_START_MARKER, "Circle start marker (SP)", 1),
            rr.exactly(rr.CIRCLE_CENTER_MARKER, "Circle centre marker (CM)", 1),
            rr.exactly(rr.CIRCLE_ENTRY_MARKER, "Circle entry marker (X)", 1),
            rr.exactly(rr.CIRCLE_EXIT_MARKER, "Circle exit marker (WP)", 1),
        ),
        # Pmax = 250, matching CIRCLE_MAXIMUM_SCORE in circle_calculator.py. The formula value is the score.
        scoring_model=SCORING_QUALITY,
        qmax_policy=QMAX_ABSOLUTE,
        quality_start=QUALITY_START_FIXED,
        fixed_quality=250,
        scoring_modules=("circle_entry", "circle_radius", "circle_direction", "altitude_spread"),
        scorecard_shortcut_name=CIMA_PRECISION_SCORECARD,
        contestant_compiler_strategy=_CONTESTANT_STRATEGIES + "CircleStrategy",
        gate_types_without_backbone=(CIRCLE_START, CIRCLE_ENTRY, CIRCLE_EXIT),
    ),
    TaskTypeDefinition(
        key=ANR_CATALOGUE,
        rule_set=RULE_SET_CIMA_ANNEX_4,
        catalogue_code="2.A8",
        title="Precision navigation Air Nav Race (ANR)",
        coarse_family=ANR_CORRIDOR,
        calculator_pipeline=PIPELINE_ANR_STYLE,
        # route_to_sp_path and route_from_fp_path are optional auxiliary features most routes never author.
        route_requirements=_BACKBONE,
        # Q = 2000 - penalties and P = 1000 x Q / 2000.
        scoring_model=SCORING_QUALITY,
        qmax_policy=QMAX_ABSOLUTE,
        quality_start=QUALITY_START_FIXED,
        fixed_quality=2000,
        absolute_reference=2000,
        scoring_modules=("route_to_sp", "route_from_fp", "takeoff_timing", "quarantine"),
        scorecard_shortcut_name=CIMA_ANR_SCORECARD,
        has_auxiliary_route_checks=True,
        scores_takeoff_timing=True,
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
        route_requirements=_FREE_TURNPOINTS_REQUIREMENTS,
        declaration_schema_key=LIMITED_FUEL_TURNPOINT_HUNT,
        # The declaration is entirely optional (minimum_required=0), so it never fails validation.
        declaration_required=False,
        absolute_time_declaration_key="compulsory_point_times",
        scoring_model=SCORING_QUALITY,
        scoring_modules=(
            "all_gate_crossings",
            "compulsory_timing_gates",
            "observation_evidence",
            "fuel_compliance",
            "backtracking",
        ),
        scorecard_shortcut_name=CIMA_PRECISION_SCORECARD,
        scores_turnpoint_hunt_targets=True,
        has_fuel_deadline=True,
        contestant_compiler_strategy=_CONTESTANT_STRATEGIES + "TurnpointHuntStrategy",
        gate_types_without_backbone=(TURNPOINT,),
    ),
    TaskTypeDefinition(
        key=DURATION,
        rule_set=RULE_SET_CIMA_ANNEX_4,
        catalogue_code="2.B3",
        title="Duration",
        coarse_family=PRECISION,
        calculator_pipeline=PIPELINE_DURATION,
        # No take-off or landing gate is required: SpeedInferredTakeoffLandingCalculator is always part of the
        # pipeline as the fallback source of those events.
        has_backbone=False,
        scoring_model=SCORING_QUALITY,
        route_requirements=(rr.present(rr.DURATION_LANDING_AREA, "Duration landing area"),),
        contestant_compiler_strategy=_CONTESTANT_STRATEGIES + "DurationStrategy",
        gate_types_without_backbone=(TAKEOFF_GATE, LANDING_GATE),
    ),
)

TASK_TYPE_REGISTRY: dict[str, TaskTypeDefinition] = {definition.key: definition for definition in _DEFINITIONS}
assert len(TASK_TYPE_REGISTRY) == len(_DEFINITIONS), "Duplicate task type key"

_FAMILY_DEFAULTS: dict[str, TaskTypeDefinition] = {
    definition.coarse_family: definition for definition in _DEFINITIONS if definition.default_for_family
}


# What a task without a (known) task type behaves like: every behaviour flag off.
UNSPECIFIED_TASK_TYPE = TaskTypeDefinition(
    key="", rule_set=RULE_SET_LEGACY, title="Unspecified", coarse_family="", calculator_pipeline=PIPELINE_DEFAULT
)

# The scorecard (by shortcut_name) a new task of a family is given unless the organiser picks another one: it is listed
# first in the scorecard picker, which preselects the first entry. A family without an entry lists the newest scorecard
# first (Scorecard.Meta.ordering).
DEFAULT_SCORECARD_SHORTCUT_NAMES = {
    family: definition.family_default_scorecard_shortcut_name
    for family, _label in FAMILY_CHOICES
    if (definition := _FAMILY_DEFAULTS.get(family)) is not None
    and definition.family_default_scorecard_shortcut_name is not None
}

# The shortcut_names of the scorecards that a task type claims for itself.
TASK_TYPE_SCORECARD_SHORTCUT_NAMES = frozenset(
    definition.scorecard_shortcut_name for definition in _DEFINITIONS if definition.scorecard_shortcut_name is not None
)

_FAMILY_LABELS = dict(FAMILY_CHOICES)


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


def find_task_type_for(navigation_task) -> Optional[TaskTypeDefinition]:
    """Like task_type_for, but None (not an error) for a stored subtype that is not defined."""
    return find_task_type(navigation_task.effective_task_subtype)


def task_type_or_unspecified(key: str | None) -> TaskTypeDefinition:
    """The task type for [key], for asking what it does: UNSPECIFIED_TASK_TYPE when there is none or it is not defined."""
    return find_task_type(key) or UNSPECIFIED_TASK_TYPE


def stored_task_type(navigation_task) -> TaskTypeDefinition:
    """
    The task type the task stores in task_subtype, for asking what it does. A task that stores none (legacy tasks) or
    one that is not defined gets UNSPECIFIED_TASK_TYPE, which does none of the special things.
    """
    return task_type_or_unspecified(getattr(navigation_task, "task_subtype", None))


def default_task_type_key_for_family(coarse_family: str) -> Optional[str]:
    definition = _FAMILY_DEFAULTS.get(coarse_family)
    return definition.key if definition else None


def validate_subtype_family_compatibility(subtype: str | None, coarse_family: str) -> None:
    if subtype in (None, ""):
        return
    definition = find_task_type(subtype)
    if definition is None:
        raise ValueError(f"Unknown task subtype '{subtype}'")
    if definition.coarse_family != coarse_family:
        raise ValueError(f"Task subtype '{subtype}' is not compatible with coarse family '{coarse_family}'")


def scorecard_suits_task_subtype(shortcut_name: str, subtype: str | None) -> bool:
    """
    Whether a task of [subtype] may be created from the original scorecard [shortcut_name]: a task type with its own
    scorecard only from that one, any other task (legacy, or a task type without one) only from a scorecard no task
    type claims. The coarse family is checked separately (Scorecard.task_type).
    """
    definition = find_task_type(subtype)
    if definition is not None and definition.scorecard_shortcut_name is not None:
        return shortcut_name == definition.scorecard_shortcut_name
    return shortcut_name not in TASK_TYPE_SCORECARD_SHORTCUT_NAMES


def describe_task_subtype(navigation_task) -> Optional[dict]:
    """
    The task's coarse family (e.g. "precision"/"Precision") and its specific subtype (e.g. "2.A1 Curve navigation with
    time estimation") for display, e.g. on TaskCard.tsx and in the apps' Register today list. None when the task has no
    subtype, or one that is not (or no longer) defined, so that one odd task cannot break a whole list.
    """
    try:
        definition = navigation_task.subtype_definition
    except ValueError:
        logger.warning(
            "Navigation task %s has an unknown task subtype %r", navigation_task.pk, navigation_task.task_subtype
        )
        return None
    if definition is None:
        return None
    return {
        "key": definition.key,
        "display_name": definition.display_name,
        "coarse_family": definition.coarse_family,
        "coarse_family_label": _FAMILY_LABELS.get(definition.coarse_family, definition.coarse_family),
        "requires_contestant_configuration": definition.requires_contestant_configuration,
    }


def get_calculators_for_task(navigation_task) -> list[type]:
    """
    The calculators to run for a navigation task, in order: those of the task's stored task type when it belongs to the
    family of its scorecard, else of the family's default task type, else (a family no task type has) the gate
    calculator alone.
    """
    family = navigation_task.scorecard.calculator
    default = _FAMILY_DEFAULTS.get(family)
    if default is None:
        return [import_string(path) for path in PIPELINE_DEFAULT]
    definition = find_task_type(navigation_task.task_subtype)
    if definition is None or definition.coarse_family != family:
        definition = default
    return definition.get_calculators()
