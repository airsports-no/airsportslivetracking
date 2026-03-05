import datetime
import logging
from queue import Queue
from typing import List, Optional

from display.calculators.calculator import Calculator, GatekeeperState, GatekeeperEvent, PokerGatePassedEvent
from display.calculators.positions_and_gates import Gate
from display.calculators.update_score_message import UpdateScoreMessage
from display.models.contestant_utility_models import ContestantReceivedPosition
from display.models import PlayingCard
from display.calculators.calculator_utilities import PolygonHelper

logger = logging.getLogger(__name__)


class PokerCalculator(Calculator):
    """
    Calculator responsible for scoring poker gates.
    Each gate passed awards a random unique card.
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
        
        self.gate_polygons = []
        if len(self.gates) > 0:
            waypoint = self.gates[0].waypoint
            self.polygon_helper = PolygonHelper(waypoint.latitude, waypoint.longitude, projector=projector)
            self.waypoint_names = [gate.name for gate in self.gates]
            gate_zones = self.route.prohibited_set.filter(type="waypoint")
            for gate in gate_zones:
                self.gate_polygons.append((gate.name, self.polygon_helper.build_polygon(gate.path)))
            
            # Sort list of polygons according to list of waypoint names
            self.sorted_polygons = [
                (polygon_name, polygon, index)
                for index, gate_name in enumerate(self.waypoint_names)
                for polygon_name, polygon in self.gate_polygons
                if polygon_name == gate_name
            ]
        else:
            self.sorted_polygons = []
            
        self.first_gate = True

    def calculate_enroute(
        self,
        track: List[ContestantReceivedPosition],
        state: GatekeeperState,
    ) -> List[GatekeeperEvent]:
        return self.check_polygons(track[-1], state)

    def calculate_outside_route(
        self,
        track: List[ContestantReceivedPosition],
        state: GatekeeperState,
    ) -> List[GatekeeperEvent]:
        return self.check_polygons(track[-1], state)

    def check_polygons(self, position: ContestantReceivedPosition, state: GatekeeperState) -> List[GatekeeperEvent]:
        events = []
        if len(self.sorted_polygons) > 0:
            p_x = getattr(position, "projected_x", None)
            p_y = getattr(position, "projected_y", None)
            
            for polygon_name, polygon, waypoint_index in list(self.sorted_polygons):
                inside = self.polygon_helper.check_inside_polygons(
                    [(polygon_name, polygon)], position.latitude, position.longitude, p_x, p_y
                )
                if len(inside) > 0:
                    passed_gate = self.gates[waypoint_index]
                    events.append(PokerGatePassedEvent(passed_gate, position))
                    self.sorted_polygons.remove((polygon_name, polygon, waypoint_index))
                    if self.first_gate:
                        self.contestant.contestanttrack.updates_current_state("Tracking")
                        self.first_gate = False
                        break
                if self.first_gate:
                    break
        return events

    def passed_finishpoint(self, track: List[ContestantReceivedPosition], last_gate: "Gate"):
        pass

    def missed_gate(self, previous_gate: Optional[Gate], gate: Gate, position: ContestantReceivedPosition):
        pass

    def on_poker_gate_passed(self, gate: Gate, position: ContestantReceivedPosition):
        logger.info(f"{self.contestant}: Scoring poker gate {gate}")
        # Find the index of this gate in the full list
        try:
            waypoint_index = self.gates.index(gate)
        except ValueError:
            waypoint_index = 0
            
        PlayingCard.add_contestant_card(
            self.contestant,
            PlayingCard.get_random_unique_card(self.contestant),
            gate.name,
            waypoint_index,
        )
