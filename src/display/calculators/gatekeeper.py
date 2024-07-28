import datetime
import logging
import threading
import time
from abc import abstractmethod, ABC
from queue import Queue
from typing import List, Optional, Callable

from display.calculators.update_score_message import UpdateScoreMessage
from display.models.contestant_utility_models import ContestantReceivedPosition
from websocket_channels import WebsocketFacade

from display.calculators.positions_and_gates import Gate, MultiGate
from display.utilities.route_building_utilities import calculate_extended_gate
from display.utilities.coordinate_utilities import Projector

from display.models import Contestant

DANGER_LEVEL_REPORT_INTERVAL = 5
CHECK_BUFFERED_DATA_TIME_LIMIT = 6


logger = logging.getLogger(__name__)


LOOP_TIME = 60


class Gatekeeper(ABC):
    """
    The Gatekeeper is the main class for scoring contestants during flight. As the name implies it is built around
    maintaining a list of gates and tracking the contestants progress through these gates. This abstract class
    instantiates the gates from the root and the optional takeoff and landing gates. It is then up to the gatekeeper
    subclasses to enforce the rules that govern gate passing (e.g. should they be in sequence, et cetera) and calculate
    the gate scores and any other scores related to the flight.

    To score other aspects than gate passing, the gatekeeper supports a list of calculators. This can be used to score
    additional elements such as altitude constraints, penalty zones, prohibited zones, backtracking, et cetera.
    """

    def __init__(
        self,
        contestant: "Contestant",
        score_processing_queue: Queue,
        calculators: List[Callable],
    ):
        super().__init__()
        logger.info(f"{contestant}: Created gatekeeper")
        self.contestant = contestant
        self.score_processing_queue = score_processing_queue

        self.track: list[ContestantReceivedPosition] = []
        self.has_passed_finishpoint = False
        self.last_gate_index = 0
        self.last_danger_level_report = 0
        self.enroute = False

        self.gates = self.create_gates()
        self.takeoff_gate = None
        self.landing_gate = None
        self.initiate_takeoff_and_landing_gates()
        self.outstanding_gates = list(self.gates)
        self.position_update_lock = threading.Lock()

        self.last_gate = None  # type: Optional[Gate]
        self.previous_last_gate = None  # type: Optional[Gate]
        self.projector = Projector(self.gates[0].latitude, self.gates[0].longitude)
        self.in_range_of_gate = None
        self.websocket_facade = WebsocketFacade()
        logger.debug(f"{self.contestant}: Starting calculators")

        self.calculators = []
        for calculator in calculators:
            self.calculators.append(
                calculator(
                    self.contestant,
                    self.contestant.navigation_task.scorecard,
                    self.gates,
                    self.contestant.navigation_task.route,
                    self.score_processing_queue,
                )
            )

    def initiate_takeoff_and_landing_gates(self):
        self.takeoff_gate = (
            MultiGate(
                [
                    Gate(
                        takeoff_gate,
                        self.contestant.gate_times[takeoff_gate.name],
                        calculate_extended_gate(takeoff_gate, self.contestant.navigation_task.scorecard),
                    )
                    for takeoff_gate in self.contestant.navigation_task.route.takeoff_gates
                ]
            )
            if len(self.contestant.navigation_task.route.takeoff_gates) > 0
            else None
        )
        self.landing_gate = (
            MultiGate(
                [
                    Gate(
                        landing_gate,
                        self.contestant.gate_times[landing_gate.name],
                        calculate_extended_gate(landing_gate, self.contestant.navigation_task.scorecard),
                    )
                    for landing_gate in self.contestant.navigation_task.route.landing_gates
                ]
            )
            if len(self.contestant.navigation_task.route.landing_gates) > 0
            else None
        )

    def has_the_contestant_passed_a_gate_and_landed(self) -> bool:
        """Should return true if the contestant has started a route and then landed, signifying that it has been completed"""
        return False

    def create_gates(self) -> List[Gate]:
        """
        Helper function to create gates from the waypoints defined in a route
        """
        waypoints = self.contestant.navigation_task.route.waypoints
        expected_times = self.contestant.gate_times
        gates = []
        for item in waypoints:  # type: Waypoint
            # Dummy gates are not part of the actual route
            if item.type != "dummy":
                gates.append(
                    Gate(
                        item,
                        expected_times[item.name],
                        calculate_extended_gate(item, self.contestant.navigation_task.scorecard),
                    )
                )
        return gates

    def update_score(self, update_score_message: UpdateScoreMessage) -> None:
        self.score_processing_queue.put_nowait(update_score_message)

    def pop_gate(self, index, update_last: bool = True):
        """
        Remove the gate at the index from the list of outstanding gates.
        """
        gate = self.outstanding_gates.pop(index)
        if update_last:
            self.previous_last_gate = self.last_gate
            logger.info(f"Updating last gate to {gate}")
            self.last_gate = gate
        self.update_enroute()

    def get_last_gate(self) -> Gate:
        """
        The last gate that was passed, or the first gate. Assumes that there is at least one gate in the route.
        """
        return self.last_gate or self.gates[0] or self.takeoff_gate or self.landing_gate

    def any_gate_passed(self):
        """
        Returns True if any gate has been passed (or missed)
        """
        return any([gate.has_been_passed() for gate in self.gates])

    def all_gates_passed(self):
        """
        Returns True if all gates have been passed (or missed)
        """
        return all([gate.has_been_passed() for gate in self.gates])

    def update_enroute(self, override_enroute: bool = False):
        """
        Update the current state to reflect whether the contestant is currently en route between a start and finish
        point or not.
        """
        if self.enroute and self.last_gate is not None and self.last_gate.type in ["ldg", "ifp", "fp"]:
            self.enroute = False
            logger.info("Switching to not enroute")
            return
        if not self.enroute and (
            (self.last_gate is not None and self.last_gate.type in ["sp", "isp", "tp", "secret"]) or override_enroute
        ):
            self.enroute = True
            logger.info("Switching to enroute")

    def passed_finishpoint(self):
        if not self.has_passed_finishpoint:
            self.contestant.contestanttrack.set_passed_finish_gate()
            self.has_passed_finishpoint = True
            for calculator in self.calculators:
                calculator.passed_finishpoint(self.track, self.last_gate)

    @abstractmethod
    def check_gates(self):
        raise NotImplementedError

    def execute_missed_gate(self, previous_gate: Optional[Gate], gate: Gate, position: ContestantReceivedPosition):
        """
        Call the missed_gate event in all calculators.
        """
        for calculator in self.calculators:
            calculator.missed_gate(previous_gate, gate, position)

    def report_calculator_danger_level(self):
        """
        Transmit the current danger level to the front end
        """
        danger_levels = [0]
        accumulated_scores = [0]
        for calculator in self.calculators:
            danger_level, accumulated_score = calculator.get_danger_level_and_accumulated_score(self.track)
            danger_levels.append(danger_level)
            accumulated_scores.append(accumulated_score)
        final_danger_level = max(danger_levels)
        final_accumulated_score = sum(accumulated_scores)
        self.websocket_facade.transmit_danger_estimate_and_accumulated_penalty(
            self.contestant, final_danger_level, final_accumulated_score
        )

    def calculate_score(self, position: ContestantReceivedPosition):
        """
        Calculate the score. Is called once for every received (or interpolated) position.
        """
        self.track.append(position)
        self.check_gates()
        for calculator in self.calculators:
            if self.enroute:
                calculator.calculate_enroute(
                    self.track,
                    self.last_gate,
                    self.in_range_of_gate,
                    self.outstanding_gates[0] if len(self.outstanding_gates) > 0 else None,
                )
            else:
                calculator.calculate_outside_route(self.track, self.last_gate)
        if self.last_danger_level_report + DANGER_LEVEL_REPORT_INTERVAL < time.time():
            self.last_danger_level_report = time.time()
            self.report_calculator_danger_level()

    def finished_processing(self):
        """
        Perform anything required after the contestant has finished processing.
        """
        pass
