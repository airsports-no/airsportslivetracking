import logging
from abc import abstractmethod
from typing import List, Callable, Dict, Optional

from display.calculators.positions_and_gates import Position, Gate
from display.models import Contestant, Scorecard, Route
from websocket_channels import WebsocketFacade

logger = logging.getLogger(__name__)


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
        self.websocket_facade = WebsocketFacade()
        logger.debug(f"{contestant}: Starting calculator {self}")

    def extrapolate_position_forward(self, track: List["Position"], seconds_ahead: float) -> "Position":
        pass

    @abstractmethod
    def calculate_enroute(self, track: List["Position"], last_gate: "Gate", in_range_of_gate: "Gate"):
        pass

    @abstractmethod
    def calculate_outside_route(self, track: List["Position"], last_gate: "Gate"):
        pass

    @abstractmethod
    def passed_finishpoint(self, track: List["Position"], last_gate: "Gate"):
        pass

    @abstractmethod
    def missed_gate(self, previous_gate: Optional[Gate], gate: Gate, position: Position):
        pass
