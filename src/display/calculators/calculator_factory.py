from typing import TYPE_CHECKING

from display.calculators.anr_corridor_calculator import AnrCorridorCalculator
from display.calculators.backtracking_and_procedure_turns import BacktrackingAndProcedureTurnsCalculator
from display.calculators.gatekeeper import Gatekeeper

if TYPE_CHECKING:
    from influx_facade import InfluxFacade
    from display.calculators.calculator import Calculator
from display.models import Contestant, Scorecard


def calculator_factory(contestant: "Contestant", influx: "InfluxFacade", live_processing: bool = True) -> "Gatekeeper":
    if contestant.navigation_task.scorecard.calculator == Scorecard.PRECISION:
        return Gatekeeper(contestant, influx, [BacktrackingAndProcedureTurnsCalculator],
                          live_processing=live_processing)
    if contestant.navigation_task.scorecard.calculator == Scorecard.ANR_CORRIDOR:
        return Gatekeeper(contestant, influx, [BacktrackingAndProcedureTurnsCalculator, AnrCorridorCalculator],
                          live_processing=live_processing)
