from multiprocessing.queues import Queue

from display.calculators.anr_corridor_calculator import AnrCorridorCalculator
from display.calculators.backtracking_and_procedure_turns import BacktrackingAndProcedureTurnsCalculator
from display.calculators.gatekeeper import Gatekeeper
from display.calculators.gatekeeper_landing import GatekeeperLanding
from display.calculators.gatekeeper_route import GatekeeperRoute
from display.calculators.prohibited_zone_calculator import ProhibitedZoneCalculator

from display.models import Contestant, Scorecard


def calculator_factory(contestant: "Contestant", position_queue: Queue, live_processing: bool = True) -> "Gatekeeper":
    if contestant.navigation_task.scorecard.calculator == Scorecard.PRECISION:
        return GatekeeperRoute(contestant, position_queue,
                               [BacktrackingAndProcedureTurnsCalculator, ProhibitedZoneCalculator],
                               live_processing=live_processing)
    if contestant.navigation_task.scorecard.calculator == Scorecard.ANR_CORRIDOR:
        return GatekeeperRoute(contestant, position_queue,
                               [BacktrackingAndProcedureTurnsCalculator, AnrCorridorCalculator,
                                ProhibitedZoneCalculator],
                               live_processing=live_processing)
    if contestant.navigation_task.scorecard.calculator == Scorecard.LANDING:
        return GatekeeperLanding(contestant, position_queue, [], live_processing=live_processing)
