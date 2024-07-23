import logging
from abc import abstractmethod
from multiprocessing import Queue
from typing import List, Optional, Tuple

from display.calculators.positions_and_gates import Gate
from display.calculators.update_score_message import UpdateScoreMessage
from display.models import Contestant, Scorecard, Route
from display.models.contestant_utility_models import ContestantReceivedPosition
from display.utilities.gate_definitions import SECRETPOINT

logger = logging.getLogger(__name__)


class Calculator:
    """
    Abstract class that defines the interface for all calculator types
    """

    def __init__(
        self,
        contestant: "Contestant",
        scorecard: "Scorecard",
        gates: List["Gate"],
        route: "Route",
        score_processing_queue: Queue,
    ):
        self.contestant = contestant
        self.scorecard = scorecard
        self.gates = gates
        self.route = route
        self.score_processing_queue = score_processing_queue
        logger.debug(f"{contestant}: Starting calculator {self}")

    def update_score(self, update_score_message: UpdateScoreMessage) -> None:
        self.score_processing_queue.put_nowait(update_score_message)

    def get_danger_level_and_accumulated_score(self, track: List[ContestantReceivedPosition]) -> Tuple[float, float]:
        return 0, 0

    def get_last_non_secret_gate(self, last_gate: "Gate") -> Optional["Gate"]:
        started = False
        for gate in reversed(self.gates):
            if not started and gate == last_gate:
                started = True
            if started and gate.type != SECRETPOINT:
                return gate
        # Assume that the first gate is never secret.
        try:
            return self.gates[0]
        except IndexError:
            return last_gate

    @abstractmethod
    def calculate_enroute(
        self,
        track: List[ContestantReceivedPosition],
        last_gate: "Gate",
        in_range_of_gate: "Gate",
        next_gate: Optional["Gate"],
    ):
        pass

    @abstractmethod
    def calculate_outside_route(self, track: List[ContestantReceivedPosition], last_gate: "Gate"):
        pass

    @abstractmethod
    def passed_finishpoint(self, track: List[ContestantReceivedPosition], last_gate: "Gate"):
        pass

    @abstractmethod
    def missed_gate(self, previous_gate: Optional[Gate], gate: Gate, position: ContestantReceivedPosition):
        pass
