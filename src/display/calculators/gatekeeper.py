import datetime
import logging
import threading
import time
from queue import Queue
from typing import List, Optional, Callable

from display.calculators.update_score_message import UpdateScoreMessage
from display.models.contestant_utility_models import ContestantReceivedPosition
from websocket_channels import WebsocketFacade

from display.calculators.positions_and_gates import Gate, MultiGate
from display.calculators.calculator import (
    FinishLinePassedEvent,
    GatekeeperState,
    GatekeeperEvent,
    GatePassedEvent,
    GateMissedEvent,
    TakeoffPassedEvent,
    LandingPassedEvent,
    StartingLinePassedEvent,
    StartingLineExtendedPassedWrongDirectionEvent,
    PokerGatePassedEvent,
    AdaptiveStartEvent,
    EstimationUpdatedEvent,
    InRangeUpdatedEvent,
)
from display.utilities.route_building_utilities import calculate_extended_gate
from display.utilities.coordinate_utilities import Projector

from display.models import Contestant

DANGER_LEVEL_REPORT_INTERVAL = 5
CHECK_BUFFERED_DATA_TIME_LIMIT = 6


logger = logging.getLogger(__name__)


LOOP_TIME = 60


class Gatekeeper:
    """
    The Gatekeeper is the main class for scoring contestants during flight. As the name implies it is built around
    maintaining a list of gates and tracking the contestants progress through these gates.

    To score other aspects than gate passing, the gatekeeper supports a list of calculators. This can be used to score
    additional elements such as altitude constraints, penalty zones, prohibited zones, backtracking, et cetera.
    """

    def __init__(
        self,
        contestant: "Contestant",
        score_processing_queue: Queue,
        calculators: List[Callable],
        live_processing: bool = True,
        projector: Optional["Projector"] = None,
    ):
        super().__init__()
        logger.info(f"{contestant}: Created gatekeeper")
        self.contestant = contestant
        self.score_processing_queue = score_processing_queue
        self.live_processing = live_processing
        self.scorecard = self.contestant.navigation_task.scorecard

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

        # Use provided projector, or first waypoint for projector, fallback to first landing gate if no waypoints
        if projector:
            self.projector = projector
        elif len(self.gates) > 0:
            self.projector = Projector(self.gates[0].latitude, self.gates[0].longitude)
        elif self.landing_gate and len(self.landing_gate.gates) > 0:
            self.projector = Projector(self.landing_gate.gates[0].latitude, self.landing_gate.gates[0].longitude)
        else:
            self.projector = Projector(0, 0)

        # Pre-project all gates
        for gate in self.gates:
            gate.pre_project(self.projector)
        if self.takeoff_gate:
            for gate in self.takeoff_gate.gates:
                gate.pre_project(self.projector)
        if self.landing_gate:
            for gate in self.landing_gate.gates:
                gate.pre_project(self.projector)

        self.in_range_of_gate = None

        self.websocket_facade = WebsocketFacade()
        logger.debug(f"{self.contestant}: Starting calculators")

        self.estimated_next_timed_gate = None
        self.estimated_crossing_time = None
        self.recalculation_completed = not self.contestant.adaptive_start

        self.calculators = []
        for calculator in calculators:
            self.calculators.append(
                calculator(
                    self.contestant,
                    self.scorecard,
                    self.gates,
                    self.contestant.navigation_task.route,
                    self.score_processing_queue,
                    live_processing=self.live_processing,
                    projector=self.projector,
                )
            )

    def get_state(self) -> GatekeeperState:
        return GatekeeperState(
            last_gate=self.last_gate,
            outstanding_gates=list(self.outstanding_gates),
            in_range_of_gate=self.in_range_of_gate,
            projector=self.projector,
            takeoff_gate=self.takeoff_gate,
            landing_gate=self.landing_gate,
            has_passed_finishpoint=self.has_passed_finishpoint,
            recalculation_completed=self.recalculation_completed,
            estimated_next_timed_gate=self.estimated_next_timed_gate,
            estimated_crossing_time=self.estimated_crossing_time,
        )

    def recalculate_gates_times_from_start_time(self, start_time: datetime.datetime):
        """
        Calculate expected crossing times for all outstanding gates given the start time.
        """
        if self.recalculation_completed:
            return

        # For adaptive start, round to closest minute as per help text
        if self.contestant.adaptive_start:
            rounded_start_time = start_time.replace(second=0, microsecond=0)
            if start_time.second >= 30:
                rounded_start_time += datetime.timedelta(minutes=1)
            start_time = rounded_start_time

        gate_times = self.contestant.calculate_missing_gate_times({}, start_time)
        self.contestant.predefined_gate_times = gate_times
        self.contestant.save(update_fields=["predefined_gate_times"])

        logger.info(f"Recalculating gates times for contestant {self.contestant}: {gate_times}")

        for item in self.gates:
            if item.name in gate_times:
                item.expected_time = gate_times[item.name]

        if self.takeoff_gate is not None:
            for gate in self.takeoff_gate.gates:
                if gate.name in gate_times:
                    gate.expected_time = gate_times[gate.name]

        if self.landing_gate is not None:
            for gate in self.landing_gate.gates:
                if gate.name in gate_times:
                    gate.expected_time = gate_times[gate.name]

        self.recalculation_completed = True
        self.websocket_facade.transmit_contestant(self.contestant)

    def initiate_takeoff_and_landing_gates(self):
        self.takeoff_gate = (
            MultiGate(
                [
                    Gate(
                        takeoff_gate,
                        self.contestant.gate_times[takeoff_gate.name],
                        calculate_extended_gate(takeoff_gate, self.scorecard),
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
                        calculate_extended_gate(landing_gate, self.scorecard),
                    )
                    for landing_gate in self.contestant.navigation_task.route.landing_gates
                ]
            )
            if len(self.contestant.navigation_task.route.landing_gates) > 0
            else None
        )

    def has_the_contestant_passed_a_gate_and_landed(self) -> bool:
        """Should return true if the contestant has started a route and then landed, signifying that it has been completed"""
        return self.any_gate_passed() and self.landing_gate is not None and self.landing_gate.has_been_passed()

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
                        calculate_extended_gate(item, self.scorecard),
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

    def passed_finishpoint(self, trigger_time: Optional[datetime.datetime] = None):
        if not self.has_passed_finishpoint:
            self.contestant.contestanttrack.set_passed_finish_gate()
            self.has_passed_finishpoint = True
            event = FinishLinePassedEvent(self.get_last_gate(), self.track, event_time=trigger_time)
            for calculator in self.calculators:
                calculator.passed_finishpoint(event)

    def handle_event(self, event: GatekeeperEvent):
        """
        Update state based on event and notify all calculators.
        """
        if isinstance(event, GatePassedEvent):
            event.gate.pass_gate(event.intersection_time, event.position)
            self.contestant.record_actual_gate_time(event.gate.name, event.intersection_time)
            if event.gate in self.outstanding_gates:
                self.pop_gate(self.outstanding_gates.index(event.gate), True)
            else:
                self.previous_last_gate = self.last_gate
                self.last_gate = event.gate
                self.update_enroute()

            if event.gate.type == "fp":
                self.passed_finishpoint(trigger_time=event.intersection_time)

            for calculator in self.calculators:
                calculator.on_gate_passed(event)

        elif isinstance(event, GateMissedEvent):
            event.gate.missed = True
            if event.gate in self.outstanding_gates:
                self.pop_gate(self.outstanding_gates.index(event.gate), True)

            if event.gate.type == "fp":
                self.passed_finishpoint(trigger_time=event.event_time)

            for calculator in self.calculators:
                calculator.on_gate_missed(event)

        elif isinstance(event, TakeoffPassedEvent):
            event.gate.pass_gate(event.intersection_time, event.position)
            self.contestant.record_actual_gate_time(event.gate.name, event.intersection_time)
            if self.takeoff_gate:
                self.takeoff_gate.pass_gate(event.intersection_time, event.position)
            for calculator in self.calculators:
                calculator.on_takeoff_passed(event)

        elif isinstance(event, LandingPassedEvent):
            event.gate.pass_gate(event.intersection_time, event.position)
            self.contestant.record_actual_gate_time(event.gate.name, event.intersection_time)
            if self.landing_gate:
                self.landing_gate.pass_gate(event.intersection_time, event.position)
            for calculator in self.calculators:
                calculator.on_landing_passed(event)

        elif isinstance(event, AdaptiveStartEvent):
            self.recalculate_gates_times_from_start_time(event.intersection_time)

        elif isinstance(event, StartingLinePassedEvent):
            event.gate.pass_infinite_gate(event.intersection_time, event.position)

            if not self.enroute:
                self.enroute = True
                logger.info(f"{self.contestant}: Switching to enroute after starting line crossing")

            for calculator in self.calculators:
                calculator.on_starting_line_passed(event)

        elif isinstance(event, StartingLineExtendedPassedWrongDirectionEvent):
            for calculator in self.calculators:
                calculator.on_starting_line_extended_passed_wrong_direction(event)

        elif isinstance(event, PokerGatePassedEvent):
            for calculator in self.calculators:
                calculator.on_poker_gate_passed(event)

        elif isinstance(event, EstimationUpdatedEvent):
            self.estimated_next_timed_gate = event.gate
            self.estimated_crossing_time = event.estimated_time

        elif isinstance(event, InRangeUpdatedEvent):
            self.in_range_of_gate = event.gate

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
        if self.projector and (position.projected_x is None or position.projected_y is None):
            p_obj = self.projector.project_point(position.latitude, position.longitude)
            position.projected_x = p_obj.projected_x
            position.projected_y = p_obj.projected_y

        self.track.append(position)

        # Detection and state update phase
        state = self.get_state()
        for calculator in self.calculators:
            if self.enroute:
                events = calculator.calculate_enroute(self.track, state)
            else:
                events = calculator.calculate_outside_route(self.track, state)

            for event in events:
                self.handle_event(event)
                # Refresh state after event in case subsequent calculators need new state
                state = self.get_state()

        if self.last_gate and self.last_gate.type == "fp":
            self.passed_finishpoint()

        if self.live_processing and self.last_danger_level_report + DANGER_LEVEL_REPORT_INTERVAL < time.time():
            self.last_danger_level_report = time.time()
            self.report_calculator_danger_level()

    def finished_processing(self):
        """
        Perform anything required after the contestant has finished processing.
        """
        for calculator in self.calculators:
            if hasattr(calculator, "finalise"):
                calculator.finalise(self.track)
