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
class OrchestratorState:
    last_gate: Optional["Gate"]
    last_visible_gate: Optional["Gate"]
    next_gate: Optional["Gate"]
    in_range_of_gate: Optional["Gate"]
    projector: "Projector"
    has_passed_finishpoint: bool
    recalculation_completed: bool
    enroute: bool = True
    has_any_gate_passed: bool = False
    has_all_gates_passed: bool = False
    has_landed: bool = False
    estimated_next_timed_gate: Optional["Gate"] = None
    estimated_crossing_time: Optional[datetime.datetime] = None


class OrchestratorEvent:
    def __init__(self, position: ContestantReceivedPosition):
        self.position = position


class GateMissedEvent(OrchestratorEvent):
    def __init__(
        self,
        previous_gate: Optional["Gate"],
        gate: "Gate",
        position: ContestantReceivedPosition,
        event_time: Optional[datetime.datetime] = None,
    ):
        super().__init__(position)
        self.previous_gate = previous_gate
        self.gate = gate
        self.event_time = event_time


class TakeoffPassedEvent(OrchestratorEvent):
    def __init__(
        self,
        gate: "Gate",
        position: ContestantReceivedPosition,
        intersection_time: datetime.datetime,
        previous_gate: Optional["Gate"] = None,
    ):
        super().__init__(position)
        self.gate = gate
        self.intersection_time = intersection_time
        self.previous_gate = previous_gate


class LandingPassedEvent(OrchestratorEvent):
    def __init__(
        self,
        gate: "Gate",
        position: ContestantReceivedPosition,
        intersection_time: datetime.datetime,
        previous_gate: Optional["Gate"] = None,
    ):
        super().__init__(position)
        self.gate = gate
        self.intersection_time = intersection_time
        self.previous_gate = previous_gate


class GatePassedEvent(OrchestratorEvent):
    def __init__(
        self,
        gate: "Gate",
        position: ContestantReceivedPosition,
        intersection_time: datetime.datetime,
        previous_gate: Optional["Gate"] = None,
    ):
        super().__init__(position)
        self.gate = gate
        self.intersection_time = intersection_time
        self.previous_gate = previous_gate


class StartingLinePassedEvent(GatePassedEvent):
    def __init__(
        self,
        gate: "Gate",
        position: ContestantReceivedPosition,
        intersection_time: datetime.datetime,
    ):
        super().__init__(gate, position, intersection_time, previous_gate=None)


class StartingLineExtendedPassedWrongDirectionEvent(OrchestratorEvent):
    def __init__(self, gate: "Gate", position: ContestantReceivedPosition):
        super().__init__(position)
        self.gate = gate


class PokerGatePassedEvent(OrchestratorEvent):
    def __init__(self, gate: "Gate", position: ContestantReceivedPosition):
        super().__init__(position)
        self.gate = gate


class AdaptiveStartEvent(OrchestratorEvent):
    def __init__(
        self,
        intersection_time: datetime.datetime,
        position: ContestantReceivedPosition,
        gate_times: Optional[dict] = None,
    ):
        super().__init__(position)
        self.intersection_time = intersection_time
        self.gate_times = gate_times


class EstimationUpdatedEvent(OrchestratorEvent):
    def __init__(self, gate: "Gate", estimated_time: datetime.datetime, position: ContestantReceivedPosition):
        super().__init__(position)
        self.gate = gate
        self.estimated_time = estimated_time


class InRangeUpdatedEvent(OrchestratorEvent):
    def __init__(self, gate: Optional["Gate"], position: ContestantReceivedPosition):
        super().__init__(position)
        self.gate = gate


class NextGateExpectedEvent(OrchestratorEvent):
    def __init__(self, gate: Optional["Gate"], position: Optional[ContestantReceivedPosition] = None):
        super().__init__(position)
        self.gate = gate


class FinishLinePassedEvent(OrchestratorEvent):
    def __init__(
        self, last_gate: "Gate", track: List[ContestantReceivedPosition], event_time: Optional[datetime.datetime] = None
    ):
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
        route: "Route",
        score_processing_queue: Queue,
        live_processing: bool = True,
        projector: "Projector" = None,
    ):
        self.contestant = contestant
        self.scorecard = scorecard
        self.route = route
        self.score_processing_queue = score_processing_queue
        self.live_processing = live_processing
        self.projector = projector
        if self.projector is None:
            raise ValueError("Projector must be provided to the calculator")

        logger.debug(f"{contestant}: Starting calculator {self}")

    def update_score(self, update_score_message: UpdateScoreMessage) -> None:
        self.score_processing_queue.put_nowait(update_score_message)

    def get_danger_level_and_accumulated_score(self, track: List[ContestantReceivedPosition]) -> Tuple[float, float]:
        return 0, 0

    @abstractmethod
    def finalise(self, track: List[ContestantReceivedPosition]):
        pass

    def calculate_enroute(
        self,
        track: List[ContestantReceivedPosition],
        state: OrchestratorState,
    ) -> List[OrchestratorEvent]:
        return []

    def calculate_outside_route(
        self,
        track: List[ContestantReceivedPosition],
        state: OrchestratorState,
    ) -> List[OrchestratorEvent]:
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

    def on_adaptive_start(self, event: AdaptiveStartEvent):
        pass

    def on_next_gate_expected(self, event: NextGateExpectedEvent):
        pass
