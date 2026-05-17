import datetime
import logging
from queue import Queue
from typing import List, Optional, Tuple

from display.calculators.calculator import (
    Calculator,
    OrchestratorState,
    OrchestratorEvent,
    PokerGatePassedEvent,
    GateMissedEvent,
    FinishLinePassedEvent,
)
from display.calculators.positions_and_gates import Gate
from display.models import Contestant, Scorecard, Route, PlayingCard
from display.models.contestant_utility_models import ContestantReceivedPosition

logger = logging.getLogger(__name__)


class PokerCalculator(Calculator):
    """ """

    def calculate_outside_route(
        self, track: List[ContestantReceivedPosition], state: OrchestratorState
    ) -> List[OrchestratorEvent]:
        return self.check_distance(track[-1], state)

    def finalise(self, track: List[ContestantReceivedPosition]):
        pass

    def get_danger_level_and_accumulated_score(self, track: List[ContestantReceivedPosition]) -> Tuple[float, float]:
        return 0, 0

    def get_last_non_secret_gate(self, last_gate: "Gate") -> Optional["Gate"]:
        from display.utilities.gate_definitions import SECRETPOINT
        
        # If no last_gate provided, try to find the first one from our list
        gate_to_start_from = last_gate
        if gate_to_start_from is None:
            if hasattr(self, "gates") and self.gates:
                gate_to_start_from = self.gates[0]
            else:
                return None

        started = False
        for gate in reversed(self.gates):
            if not started and gate == gate_to_start_from:
                started = True
            if started and gate.type != SECRETPOINT:
                return gate
        
        return gate_to_start_from

    def create_gates(self) -> List["Gate"]:
        """
        Helper function to create gates from the waypoints defined in a route
        """
        from display.calculators.positions_and_gates import Gate
        from display.utilities.route_building_utilities import calculate_extended_gate

        waypoints = self.contestant.navigation_task.route.waypoints
        expected_times = self.contestant.gate_times
        gates = []
        for item in waypoints:  # type: Waypoint
            # Dummy gates are not part of the actual route
            if item.type != "dummy" and not getattr(item, "on_curved_segment", False):
                gates.append(
                    Gate(
                        item,
                        expected_times[item.name],
                        calculate_extended_gate(item, self.scorecard),
                    )
                )
        return gates

    def initiate_gates(self):
        self.gates = self.create_gates()
        for gate in self.gates:
            gate.pre_project(self.projector)

    def __init__(
        self,
        contestant: "Contestant",
        scorecard: "Scorecard",
        route: "Route",
        score_processing_queue: Queue,
        live_processing: bool = True,
        projector=None,
    ):
        super().__init__(
            contestant,
            scorecard,
            route,
            score_processing_queue,
            live_processing=live_processing,
            projector=projector,
        )
        self.initiate_gates()
        self.waypoint_names = [gate.name for gate in self.gates]
        self.passed_gates = set()

    def on_gate_missed(self, event: GateMissedEvent):
        pass

    def passed_finishpoint(self, event: FinishLinePassedEvent):
        pass

    def calculate_enroute(
        self,
        track: List[ContestantReceivedPosition],
        state: OrchestratorState,
    ) -> List[OrchestratorEvent]:
        return self.check_distance(track[-1], state)

    def check_distance(self, position: ContestantReceivedPosition, state: OrchestratorState) -> List[OrchestratorEvent]:
        p_x = getattr(position, "projected_x", None)
        p_y = getattr(position, "projected_y", None)
        
        if p_x is None or p_y is None:
            return []

        events = []
        # Detection: use distance to the gate center relative to gate width
        for gate in self.gates:
            if gate.name not in self.passed_gates:
                if gate.center_x is not None and gate.center_y is not None:
                    dist_sq = (p_x - gate.center_x) ** 2 + (p_y - gate.center_y) ** 2
                    # gate.gate_radius represents half the gate width
                    if dist_sq <= gate.gate_radius ** 2:
                        self.passed_gates.add(gate.name)
                        events.append(PokerGatePassedEvent(gate, position))
        return events

    def on_poker_gate_passed(self, event: PokerGatePassedEvent):
        # Assign a random card when a poker gate is passed
        try:
            waypoint_index = self.waypoint_names.index(event.gate.name)
        except ValueError:
            waypoint_index = 0

        PlayingCard.add_contestant_card(
            self.contestant,
            PlayingCard.get_random_unique_card(self.contestant),
            event.gate.name,
            waypoint_index,
            pos=event.position
        )
