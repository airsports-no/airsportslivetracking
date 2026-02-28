import inspect
from display.calculators.prohibited_zone_calculator import ProhibitedZoneCalculator
from display.calculators.penalty_zone_calculator import PenaltyZoneCalculator
from display.calculators.anr_corridor_calculator import AnrCorridorCalculator

print(f"ProhibitedZoneCalculator: {inspect.signature(ProhibitedZoneCalculator.__init__)}")
print(f"PenaltyZoneCalculator: {inspect.signature(PenaltyZoneCalculator.__init__)}")
print(f"AnrCorridorCalculator: {inspect.signature(AnrCorridorCalculator.__init__)}")
