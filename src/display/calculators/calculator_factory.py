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
    PRECISION,
    POKER,
    ANR_CORRIDOR,
    AIRSPORTS,
    AIRSPORT_CHALLENGE,
    LANDING,
)


def calculator_factory(
    contestant: "Contestant", live_processing: bool = True, queue_name_override: str = None
) -> "Gatekeeper":
    if contestant.navigation_task.scorecard.calculator == PRECISION:
        return GatekeeperRoute(
            contestant,
            [BacktrackingAndProcedureTurnsCalculator, ProhibitedZoneCalculator, PenaltyZoneCalculator],
            live_processing=live_processing,
            queue_name_override=queue_name_override,
        )
    if contestant.navigation_task.scorecard.calculator in (
        ANR_CORRIDOR,
        AIRSPORTS,
        AIRSPORT_CHALLENGE,
    ):
        return GatekeeperRoute(
            contestant,
            [
                BacktrackingAndProcedureTurnsCalculator,
                AnrCorridorCalculator,
                ProhibitedZoneCalculator,
                PenaltyZoneCalculator,
            ],
            live_processing=live_processing,
            queue_name_override=queue_name_override,
        )
    if contestant.navigation_task.scorecard.calculator == LANDING:
        return GatekeeperLanding(
            contestant, [], live_processing=live_processing, queue_name_override=queue_name_override
        )
    if contestant.navigation_task.scorecard.calculator == POKER:
        return GatekeeperPoker(contestant, [], live_processing=live_processing, queue_name_override=queue_name_override)
    return GatekeeperRoute(contestant, [], live_processing=live_processing, queue_name_override=queue_name_override)
