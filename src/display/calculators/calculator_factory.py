from queue import Queue
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from display.utilities.coordinate_utilities import Projector

from display.calculators.anr_corridor_calculator import AnrCorridorCalculator
from display.calculators.backtracking_and_procedure_turns import BacktrackingAndProcedureTurnsCalculator
from display.calculators.gate_calculator import GateCalculator
from display.calculators.circle_calculator import CircleCalculator
from display.calculators.duration_calculator import DurationCalculator
from display.calculators.orchestrator import Orchestrator
from display.calculators.takeoff_and_landing_gate_calculator import TakeoffAndLandingGateCalculator
from display.calculators.landing_pattern_calculator import LandingPatternCalculator
from display.calculators.penalty_zone_calculator import PenaltyZoneCalculator
from display.calculators.poker_calculator import PokerCalculator
from display.calculators.prohibited_zone_calculator import ProhibitedZoneCalculator
from display.calculators.speed_inferred_takeoff_landing_calculator import SpeedInferredTakeoffLandingCalculator

from display.models import Contestant
from display.utilities.cima_task_type_definitions import CIRCLE, DURATION
from display.utilities.navigation_task_type_definitions import (
    PRECISION,
    POKER,
    ANR_CORRIDOR,
    AIRSPORTS,
    AIRSPORT_CHALLENGE,
    LANDING,
)


def _build_precision_calculators(contestant: "Contestant"):
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


def calculator_factory(
    contestant: "Contestant",
    score_processing_queue: Queue,
    live_processing: bool = True,
    projector: Optional["Projector"] = None,
) -> "Orchestrator":
    if contestant.navigation_task.scorecard.calculator == PRECISION:
        return Orchestrator(
            contestant,
            score_processing_queue,
            _build_precision_calculators(contestant),
            live_processing=live_processing,
            projector=projector,
        )

    if contestant.navigation_task.scorecard.calculator in (
        ANR_CORRIDOR,
        AIRSPORTS,
        AIRSPORT_CHALLENGE,
    ):
        return Orchestrator(
            contestant,
            score_processing_queue,
            [
                GateCalculator,
                TakeoffAndLandingGateCalculator,
                BacktrackingAndProcedureTurnsCalculator,
                AnrCorridorCalculator,
                ProhibitedZoneCalculator,
                PenaltyZoneCalculator,
            ],
            live_processing=live_processing,
            projector=projector,
        )

    if contestant.navigation_task.scorecard.calculator == LANDING:
        return Orchestrator(
            contestant,
            score_processing_queue,
            [LandingPatternCalculator],
            live_processing=live_processing,
            projector=projector,
        )

    if contestant.navigation_task.scorecard.calculator == POKER:
        return Orchestrator(
            contestant,
            score_processing_queue,
            [
                PokerCalculator,
                ProhibitedZoneCalculator,
                PenaltyZoneCalculator,
            ],
            live_processing=live_processing,
            projector=projector,
        )

    return Orchestrator(
        contestant,
        score_processing_queue,
        [GateCalculator],
        live_processing=live_processing,
        projector=projector,
    )

