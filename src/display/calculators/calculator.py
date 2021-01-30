from abc import abstractmethod
from typing import List, Callable, Dict

from display.calculators.positions_and_gates import Position, Gate
from display.models import Contestant, Scorecard, Route


class Calculator:
    """
    Abstract class that defines the interface for all calculator types
    """

    def __init__(self, contestant: "Contestant", scorecard: "Scorecard", gates: List["Gate"], route: "Route",
                 update_score: Callable):
        self.contestant = contestant
        self.scorecard = scorecard
        self.gates = gates
        self.route = route
        self.update_score = update_score

    @abstractmethod
    def calculate_enroute(self, track: List["Position"], last_gate: "Gate", in_range_of_gate: "Gate"):
        pass

    @abstractmethod
    def calculate_outside_route(self, track: List["Position"], last_gate: "Gate"):
        pass

    @abstractmethod
    def passed_finishpoint(self):
        pass