from multiprocessing import Queue

from display.calculators.anr_corridor_calculator import AnrCorridorCalculator
from display.calculators.backtracking_and_procedure_turns import BacktrackingAndProcedureTurnsCalculator
from display.calculators.gatekeeper import Gatekeeper
from display.calculators.gatekeeper_landing import GatekeeperLanding
from display.calculators.gatekeeper_poker import GatekeeperPoker
from display.calculators.gatekeeper_route import GatekeeperRoute
from display.calculators.penalty_zone_calculator import PenaltyZoneCalculator
from display.calculators.prohibited_zone_calculator import ProhibitedZoneCalculator

from display.models import Contestant, NavigationTask
from display.utilities.navigation_task_type_definitions import (
    CIMA_PRECISION,
    PRECISION,
    POKER,
    ANR_CORRIDOR,
    AIRSPORTS,
    AIRSPORT_CHALLENGE,
    LANDING,
)


def calculator_factory(contestant: "Contestant", score_processing_queue: Queue) -> "Gatekeeper":
    if contestant.navigation_task.scorecard.calculator in (PRECISION, CIMA_PRECISION):
        return GatekeeperRoute(
            contestant,
            score_processing_queue,
            [BacktrackingAndProcedureTurnsCalculator, ProhibitedZoneCalculator, PenaltyZoneCalculator],
        )
    if contestant.navigation_task.scorecard.calculator in (
        ANR_CORRIDOR,
        AIRSPORTS,
        AIRSPORT_CHALLENGE,
    ):
        return GatekeeperRoute(
            contestant,
            score_processing_queue,
            [
                BacktrackingAndProcedureTurnsCalculator,
                AnrCorridorCalculator,
                ProhibitedZoneCalculator,
                PenaltyZoneCalculator,
            ],
        )
    if contestant.navigation_task.scorecard.calculator == LANDING:
        return GatekeeperLanding(contestant, score_processing_queue, [])
    if contestant.navigation_task.scorecard.calculator == POKER:
        return GatekeeperPoker(contestant, score_processing_queue, [])
    return GatekeeperRoute(contestant, score_processing_queue, [])
