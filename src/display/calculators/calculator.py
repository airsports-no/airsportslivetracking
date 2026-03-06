import datetime
import logging
from abc import abstractmethod, ABC
from multiprocessing import Queue
from typing import List, Optional, Tuple, TYPE_CHECKING
from dataclasses import dataclass

from display.calculators.update_score_message import UpdateScoreMessage
from display.models import Contestant, Scorecard, Route
from display.models.contestant_utility_models import ContestantReceivedPosition
from display.utilities.gate_definitions import SECRETPOINT

if TYPE_CHECKING:
    from display.calculators.positions_and_gates import Gate, MultiGate
    from display.utilities.coordinate_utilities import Projector


logger = logging.getLogger(__name__)


@dataclass
class GatekeeperState:
    last_gate: Optional["Gate"]
    outstanding_gates: List["Gate"]
    in_range_of_gate: Optional["Gate"]
    projector: "Projector"
    takeoff_gate: Optional["MultiGate"]
    landing_gate: Optional["MultiGate"]
    has_passed_finishpoint: bool
    recalculation_completed: bool
    estimated_next_timed_gate: Optional["Gate"] = None
    estimated_crossing_time: Optional[datetime.datetime] = None


class GatekeeperEvent:
    def __init__(self, position: ContestantReceivedPosition):
        self.position = position


class GatePassedEvent(GatekeeperEvent):
    def __init__(self, gate: "Gate", position: ContestantReceivedPosition, intersection_time: datetime.datetime):
        super().__init__(position)
        self.gate = gate
        self.intersection_time = intersection_time


class GateMissedEvent(GatekeeperEvent):
    def __init__(self, previous_gate: Optional["Gate"], gate: "Gate", position: ContestantReceivedPosition, event_time: Optional[datetime.datetime] = None):
        super().__init__(position)
        self.previous_gate = previous_gate
        self.gate = gate
        self.event_time = event_time


class TakeoffPassedEvent(GatekeeperEvent):
    def __init__(self, gate: "Gate", position: ContestantReceivedPosition, intersection_time: datetime.datetime):
        super().__init__(position)
        self.gate = gate
        self.intersection_time = intersection_time


class LandingPassedEvent(GatekeeperEvent):
    def __init__(self, gate: "Gate", position: ContestantReceivedPosition, intersection_time: datetime.datetime):
        super().__init__(position)
        self.gate = gate
        self.intersection_time = intersection_time


class StartingLinePassedEvent(GatekeeperEvent):
    def __init__(self, gate: "Gate", position: ContestantReceivedPosition, intersection_time: datetime.datetime):
        super().__init__(position)
        self.gate = gate
        self.intersection_time = intersection_time


class StartingLineExtendedPassedWrongDirectionEvent(GatekeeperEvent):
    def __init__(self, gate: "Gate", position: ContestantReceivedPosition):
        super().__init__(position)
        self.gate = gate


class PokerGatePassedEvent(GatekeeperEvent):
    def __init__(self, gate: "Gate", position: ContestantReceivedPosition):
        super().__init__(position)
        self.gate = gate


class AdaptiveStartEvent(GatekeeperEvent):
    def __init__(self, intersection_time: datetime.datetime, position: ContestantReceivedPosition):
        super().__init__(position)
        self.intersection_time = intersection_time


class EstimationUpdatedEvent(GatekeeperEvent):
    def __init__(self, gate: "Gate", estimated_time: datetime.datetime, position: ContestantReceivedPosition):
        super().__init__(position)
        self.gate = gate
        self.estimated_time = estimated_time


class InRangeUpdatedEvent(GatekeeperEvent):
    def __init__(self, gate: Optional["Gate"], position: ContestantReceivedPosition):
        super().__init__(position)
        self.gate = gate


class FinishLinePassedEvent(GatekeeperEvent):
    def __init__(self, last_gate: "Gate", track: List[ContestantReceivedPosition], event_time: Optional[datetime.datetime] = None):
        super().__init__(track[-1] if track else None)
        self.last_gate = last_gate
        self.track = track
        self.event_time = event_time



class Calculator(ABC):
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
        live_processing: bool = True,
        projector: Optional["Projector"] = None,
    ):
        self.contestant = contestant
        self.scorecard = scorecard
        self.gates = gates
        self.route = route
        self.score_processing_queue = score_processing_queue
        self.live_processing = live_processing
        self.projector = projector
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

    def calculate_enroute(
        self,
        track: List[ContestantReceivedPosition],
        state: GatekeeperState,
    ) -> List[GatekeeperEvent]:
        return []

    def calculate_outside_route(
        self,
        track: List[ContestantReceivedPosition],
        state: GatekeeperState,
    ) -> List[GatekeeperEvent]:
        return []

    def passed_finishpoint(self, event: FinishLinePassedEvent):
        pass

    def on_gate_missed(self, event: GateMissedEvent):
        pass

    def on_gate_passed(self, event: GatePassedEvent):
        pass

    def on_takeoff_passed(self, event: TakeoffPassedEvent):
        pass

    def on_landing_passed(self, event: LandingPassedEvent):
        pass

    def on_starting_line_passed(self, event: StartingLinePassedEvent):
        pass

    def on_starting_line_extended_passed_wrong_direction(self, event: StartingLineExtendedPassedWrongDirectionEvent):
        pass

    def on_poker_gate_passed(self, event: PokerGatePassedEvent):
        pass

