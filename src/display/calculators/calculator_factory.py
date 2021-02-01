from typing import TYPE_CHECKING

from display.calculators.anr_corridor_calculator import AnrCorridorCalculator
from display.calculators.backtracking_and_procedure_turns import BacktrackingAndProcedureTurnsCalculator
from display.calculators.gatekeeper import Gatekeeper
from display.calculators.gatekeeper_route import GatekeeperRoute
from display.calculators.prohibited_zone_calculator import ProhibitedZoneCalculator

if TYPE_CHECKING:
    from influx_facade import InfluxFacade
from display.models import Contestant, Scorecard


def calculator_factory(contestant: "Contestant", influx: "InfluxFacade", live_processing: bool = True) -> "Gatekeeper":
    if contestant.navigation_task.scorecard.calculator == Scorecard.PRECISION:
        return GatekeeperRoute(contestant, influx, [BacktrackingAndProcedureTurnsCalculator, ProhibitedZoneCalculator],
                               live_processing=live_processing)
    if contestant.navigation_task.scorecard.calculator == Scorecard.ANR_CORRIDOR:
        return GatekeeperRoute(contestant, influx,
                               [BacktrackingAndProcedureTurnsCalculator, AnrCorridorCalculator,
                                ProhibitedZoneCalculator],
                               live_processing=live_processing)
