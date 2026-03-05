import datetime
import logging
from queue import Queue
from typing import List, Optional

from display.calculators.calculator import Calculator, GatekeeperState, GatekeeperEvent, GatePassedEvent, LandingPassedEvent
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

    def __init__(
        self,
        contestant,
        scorecard,
        gates,
        route,
        score_processing_queue,
        live_processing=True,
        projector=None,
    ):
        super().__init__(
            contestant,
            scorecard,
            gates,
            route,
            score_processing_queue,
            live_processing=live_processing,
            projector=projector,
        )
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
        state: GatekeeperState,
    ) -> List[GatekeeperEvent]:
        return self.check_intersections(track, state)

    def calculate_outside_route(
        self,
        track: List[ContestantReceivedPosition],
        state: GatekeeperState,
    ) -> List[GatekeeperEvent]:
        return self.check_intersections(track, state)

    def check_intersections(self, track: List[ContestantReceivedPosition], state: GatekeeperState) -> List[GatekeeperEvent]:
        events = []
        if state.landing_gate is not None and len(state.landing_gate.gates) > 0:
            intersection_time = state.landing_gate.get_gate_intersection_time(self.projector, track)
            if intersection_time:
                self.contestant.contestanttrack.updates_current_state("Tracking")
                if self.last_intersection is None or intersection_time > self.last_intersection + datetime.timedelta(
                    seconds=30
                ):
                    self.last_intersection = intersection_time
                    events.append(LandingPassedEvent(state.landing_gate.intersected_gate, track[-1], intersection_time))
        return events

    def passed_finishpoint(self, track: List[ContestantReceivedPosition], last_gate: "Gate"):
        pass

    def missed_gate(self, previous_gate: Optional[Gate], gate: Gate, position: ContestantReceivedPosition):
        pass

    def on_gate_passed(self, gate: Gate, position: ContestantReceivedPosition):
        logger.info(f"{self.contestant}: Scoring landing pattern round via gate {gate}")
        self.update_score(
            UpdateScoreMessage(
                position.time,
                gate,
                1,
                "passed landing line",
                position.latitude,
                position.longitude,
                ANOMALY,
                "landing_line",
            )
        )
