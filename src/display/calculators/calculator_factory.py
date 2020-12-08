from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from influx_facade import InfluxFacade
    from display.calculators.calculator import Calculator
from display.calculators.precision_calculator import PrecisionCalculator
from display.models import Contest


def calculator_factory(contestant: "Contestant", influx: "InfluxFacade") -> "Calculator":
    if contestant.contest.contest_calculator_type == Contest.PRECISION:
        return PrecisionCalculator(contestant, influx)
