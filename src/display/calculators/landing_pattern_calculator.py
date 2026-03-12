import datetime
import logging
from queue import Queue
from typing import List, Optional

from display.calculators.calculator import Calculator, OrchestratorState, OrchestratorEvent, GatePassedEvent, LandingPassedEvent, GateMissedEvent, FinishLinePassedEvent
from display.calculators.positions_and_gates import Gate
from display.calculators.update_score_message import UpdateScoreMessage
from display.models.contestant_utility_models import ContestantReceivedPosition
from display.models import ANOMALY
from display.utilities.coordinate_utilities import Projector

logger = logging.getLogger(__name__)


class LandingPatternCalculator(Calculator):
    """
    Calculator responsible for scoring rounds in a landing pattern.
    Each round awards 1 point.
    """

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
            # Only use landing gates for landing pattern rounds
            if item.type == "ldg":
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
        contestant,
        scorecard,
        route,
        score_processing_queue,
        live_processing=True,
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
        self.last_intersection = None
        # Initialize projector if landing gates exist, else fallback to provided or origin.
        if self.projector:
            pass # Use passed one
        elif self.route.landing_gates and len(self.route.landing_gates) > 0:
            first_gate = self.route.landing_gates[0]
            self.projector = Projector(first_gate.latitude, first_gate.longitude)
        else:
            self.projector = Projector(0, 0)

    def calculate_enroute(
        self,
        track: List[ContestantReceivedPosition],
        state: OrchestratorState,
    ) -> List[OrchestratorEvent]:
        return self.check_intersections(track, state)

    def calculate_outside_route(
        self,
        track: List[ContestantReceivedPosition],
        state: OrchestratorState,
    ) -> List[OrchestratorEvent]:
        return self.check_intersections(track, state)

    def check_intersections(self, track: List[ContestantReceivedPosition], state: OrchestratorState) -> List[OrchestratorEvent]:
        events = []
        # LandingPatternCalculator should ideally manage its own landing multi-gate 
        # or just check against route landing gates directly.
        if self.gates and len(self.gates) > 0:
            # For simplicity, check first landing gate
            gate = self.gates[0]
            intersection_time = gate.get_gate_intersection_time(state.projector, track)
            if intersection_time:
                self.contestant.contestanttrack.updates_current_state("Tracking")
                if self.last_intersection is None or intersection_time > self.last_intersection + datetime.timedelta(
                    seconds=30
                ):
                    self.last_intersection = intersection_time
                    events.append(LandingPassedEvent(gate, track[-1], intersection_time))
        return events

    def passed_finishpoint(self, event: FinishLinePassedEvent):
        pass

    def on_gate_missed(self, event: GateMissedEvent):
        pass

    def on_landing_passed(self, event: LandingPassedEvent):
        logger.info(f"{self.contestant}: Scoring landing pattern round via gate {event.gate}")
        self.update_score(
            UpdateScoreMessage(
                event.intersection_time,
                event.gate,
                0.0,
                "passed landing line",
                event.position.latitude,
                event.position.longitude,
                ANOMALY,
                "landing_line",
            )
        )

    def finalise(self, track: List[ContestantReceivedPosition]):
        pass
