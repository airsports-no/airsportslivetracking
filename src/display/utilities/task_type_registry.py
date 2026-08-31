"""
Single source of truth for what a task type's live-calculator pipeline looks like, replacing
the if/elif chain that used to live directly in calculator_factory.py. Adding a new task type's
scoring pipeline is now "add one TaskTypeSpec entry" instead of finding and editing that chain.

Scope note (see the scorecard-system review roadmap): this registry deliberately does NOT also
cover the route-builder dispatch (EditableRoute.create_route vs NavigationTask.refresh_editable_route)
or the task-type display name used outside Scorecard.calculator's own choices.

Follow-up investigation on the display-name question found the "AirSport Challenge" vs
"Air Sport Challenge" difference was a plain typo (fixed: NAVIGATION_TASK_TYPES now reads "Air
Sport Challenge", matching task_information.FAMILY_DISPLAY_NAMES, the scorecard name settled on
in the earlier duplicate-scorecard merge, and CIMA's own LEGACY_AIRSPORT_CHALLENGE.display_name).
"Precision" (NAVIGATION_TASK_TYPES, seen only in the organizer-facing task-creation wizard's
dropdown) vs "Precision navigation" (FAMILY_DISPLAY_NAMES, shown as the prominent heading in the
pilot/spectator-facing TaskInfoModal) was left alone - a terse dropdown option vs. a fuller
heading is a defensible intentional split, not the same class of accidental drift.

Follow-up on the route-builder dispatch question: refresh_editable_route (navigation_task.py)
was missing the NO_BACKBONE_TASK_SUBTYPES branch and the LANDING case that create_route
(editable_route.py) has, so "Reload route" reported success while silently doing nothing for
those task types - fixed by adding the equivalent branches to refresh_editable_route directly
(not by merging the two dispatches into one, since create_route also validates/derives
rounded_corners/corridor_width from wizard input that refresh_editable_route has no equivalent
of - they remain two separate functions with the same per-task-type behavior, not one shared
dispatch table). See test_refresh_editable_route_landing_and_no_backbone.py.
"""

from typing import TYPE_CHECKING, Callable

from display.calculators.anr_corridor_calculator import AnrCorridorCalculator
from display.calculators.backtracking_and_procedure_turns import BacktrackingAndProcedureTurnsCalculator
from display.calculators.circle_calculator import CircleCalculator
from display.calculators.duration_calculator import DurationCalculator
from display.calculators.gate_calculator import GateCalculator
from display.calculators.landing_pattern_calculator import LandingPatternCalculator
from display.calculators.penalty_zone_calculator import PenaltyZoneCalculator
from display.calculators.poker_calculator import PokerCalculator
from display.calculators.prohibited_zone_calculator import ProhibitedZoneCalculator
from display.calculators.speed_inferred_takeoff_landing_calculator import SpeedInferredTakeoffLandingCalculator
from display.calculators.takeoff_and_landing_gate_calculator import TakeoffAndLandingGateCalculator
from display.utilities.cima_task_type_definitions import CIRCLE, DURATION
from display.utilities.navigation_task_type_definitions import (
    AIRSPORT_CHALLENGE,
    AIRSPORTS,
    ANR_CORRIDOR,
    LANDING,
    NAVIGATION_TASK_TYPES,
    POKER,
    PRECISION,
)

if TYPE_CHECKING:
    from display.calculators.calculator import Calculator
    from display.models import Contestant

CalculatorListBuilder = Callable[["Contestant"], list[type["Calculator"]]]

# NAVIGATION_TASK_TYPES stays the single hand-authored source for these labels (it also feeds
# Scorecard.calculator's Django choices) - this just avoids typing the strings a second time.
_DISPLAY_NAMES = dict(NAVIGATION_TASK_TYPES)


class TaskTypeSpec:
    def __init__(self, calculator: str, build_calculators: CalculatorListBuilder):
        self.calculator = calculator
        self.display_name = _DISPLAY_NAMES[calculator]
        self.build_calculators = build_calculators


def _build_precision_calculators(contestant: "Contestant") -> list:
    calculators = [
        GateCalculator,
        TakeoffAndLandingGateCalculator,
        BacktrackingAndProcedureTurnsCalculator,
        ProhibitedZoneCalculator,
        PenaltyZoneCalculator,
    ]
    # Ordering matters here: circle scoring consumes gate events early in the
    # precision pipeline, while duration scoring depends on the regular gate
    # calculators still running afterwards.
    if contestant.navigation_task.task_subtype == CIRCLE:
        # Backtracking/procedure-turn detection assumes monotonic progress
        # along an ordered route. A circle's SP-X-CM-WP effective waypoints
        # are a synthetic sequence for gate-crossing detection only - flying
        # the circle itself (looping back around CM) would look exactly like
        # backtracking to this calculator, so it does not apply to 2.A7.
        calculators.remove(BacktrackingAndProcedureTurnsCalculator)
        calculators.insert(1, CircleCalculator)
    if contestant.navigation_task.task_subtype == DURATION:
        # SpeedInferredTakeoffLandingCalculator is a fallback source of
        # TakeoffPassedEvent/LandingPassedEvent for routes with no authored
        # takeoff/landing gates; the orchestrator fans those events out to every
        # calculator (including DurationCalculator) regardless of list position,
        # so this placement is just grouped with DurationCalculator for readability.
        calculators.insert(2, SpeedInferredTakeoffLandingCalculator)
        calculators.insert(3, DurationCalculator)
    return calculators


def _build_anr_style_calculators(contestant: "Contestant") -> list:
    return [
        GateCalculator,
        TakeoffAndLandingGateCalculator,
        BacktrackingAndProcedureTurnsCalculator,
        AnrCorridorCalculator,
        ProhibitedZoneCalculator,
        PenaltyZoneCalculator,
    ]


def _build_landing_calculators(contestant: "Contestant") -> list:
    return [LandingPatternCalculator]


def _build_poker_calculators(contestant: "Contestant") -> list:
    return [
        PokerCalculator,
        ProhibitedZoneCalculator,
        PenaltyZoneCalculator,
    ]


def _build_default_calculators(contestant: "Contestant") -> list:
    return [GateCalculator]


# Matches the previous if/elif order in calculator_factory.py exactly - PRECISION first (its
# subtype branching is the most involved), then the three ANR-style types sharing one pipeline,
# then LANDING, then POKER.
TASK_TYPES: dict[str, TaskTypeSpec] = {
    PRECISION: TaskTypeSpec(PRECISION, _build_precision_calculators),
    ANR_CORRIDOR: TaskTypeSpec(ANR_CORRIDOR, _build_anr_style_calculators),
    AIRSPORTS: TaskTypeSpec(AIRSPORTS, _build_anr_style_calculators),
    AIRSPORT_CHALLENGE: TaskTypeSpec(AIRSPORT_CHALLENGE, _build_anr_style_calculators),
    LANDING: TaskTypeSpec(LANDING, _build_landing_calculators),
    POKER: TaskTypeSpec(POKER, _build_poker_calculators),
}

# calculator_factory.py's fallback for any scorecard.calculator value with no TASK_TYPES entry
# (e.g. a legacy/custom value) - preserved as-is, not folded into TASK_TYPES since it isn't
# keyed by a real task type.
DEFAULT_CALCULATOR_BUILDER: CalculatorListBuilder = _build_default_calculators
