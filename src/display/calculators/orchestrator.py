import datetime
import logging
import threading
import time
from queue import Queue
from typing import List, Optional, Callable

from display.calculators.positions_and_gates import Gate
from display.calculators.update_score_message import UpdateScoreMessage
from display.models.contestant_utility_models import ContestantReceivedPosition
from websocket_channels import WebsocketFacade

from display.calculators.calculator import (
    FinishLinePassedEvent,
    OrchestratorState,
    OrchestratorEvent,
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
    NextGateExpectedEvent,
)
from display.utilities.coordinate_utilities import Projector

from display.models import Contestant

DANGER_LEVEL_REPORT_INTERVAL = 5


logger = logging.getLogger(__name__)


class Orchestrator:
    """
    The Orchestrator is the main class for scoring contestants during flight.
    It manages the overall state and coordinates between different specialized calculators.
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
        logger.info(f"{contestant}: Created orchestrator")
        self.contestant = contestant
        self.score_processing_queue = score_processing_queue
        self.live_processing = live_processing
        self.scorecard = self.contestant.navigation_task.scorecard

        self.track: list[ContestantReceivedPosition] = []
        self.has_passed_finishpoint = False
        self.last_danger_level_report = 0
        self.enroute = False

        # Semantic status flags updated by events
        self.has_any_gate_passed = False
        self.has_all_gates_passed = False
        self.has_landed = False

        self.position_update_lock = threading.Lock()

        self.last_gate: Optional[Gate] = None
        self.last_visible_gate: Optional[Gate] = None
        self.next_gate: Optional[Gate] = None
        self.previous_last_gate: Optional[Gate] = None

        # Use provided projector, or first waypoint for projector, fallback to origin.
        if projector:
            self.projector = projector
        else:
            # Fallback to navigation task starting point if possible
            waypoints = self.contestant.navigation_task.route.waypoints
            if waypoints:
                self.projector = Projector(waypoints[0].latitude, waypoints[0].longitude)
            else:
                self.projector = Projector(0, 0)

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
                    self.contestant.navigation_task.route,
                    self.score_processing_queue,
                    live_processing=self.live_processing,
                    projector=self.projector,
                )
            )

    def get_state(self) -> OrchestratorState:
        return OrchestratorState(
            last_gate=self.last_gate,
            last_visible_gate=self.last_visible_gate,
            next_gate=self.next_gate,
            in_range_of_gate=self.in_range_of_gate,
            projector=self.projector,
            has_passed_finishpoint=self.has_passed_finishpoint,
            recalculation_completed=self.recalculation_completed,
            enroute=self.enroute,
            has_any_gate_passed=self.has_any_gate_passed,
            has_all_gates_passed=self.has_all_gates_passed,
            has_landed=self.has_landed,
            estimated_next_timed_gate=self.estimated_next_timed_gate,
            estimated_crossing_time=self.estimated_crossing_time,
        )

    def has_the_contestant_passed_a_gate_and_landed(self) -> bool:
        """Should return true if the contestant has started a route and then landed, signifying that it has been completed"""
        return self.has_any_gate_passed and self.has_landed

    def update_score(self, update_score_message: UpdateScoreMessage) -> None:
        self.score_processing_queue.put_nowait(update_score_message)

    def get_last_gate(self) -> Gate | None:
        """
        The last gate that was passed, or the first gate.
        """
        if self.last_gate:
            return self.last_gate

        # If nothing passed yet, the next expected gate is conceptually the "base" gate (the first one)
        return self.next_gate

    def update_enroute(self, override_enroute: bool = False):
        """
        Update the current state to reflect whether the contestant is currently en route between a start and finish
        point or not.
        """
        if self.enroute and self.last_gate is not None and self.last_gate.type in ["ldg", "ifp", "fp"]:
            self.enroute = False
            logger.info("Switching to not enroute")
            return
        if (
            not self.enroute
            and not self.has_passed_finishpoint
            and (
                (self.last_gate is not None and self.last_gate.type in ["sp", "isp", "tp", "secret"]) or override_enroute
            )
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

    def handle_event(self, event: OrchestratorEvent):
        """
        Update state based on event and notify all calculators.
        """
        if isinstance(event, StartingLinePassedEvent):
            self.has_any_gate_passed = True
            self.contestant.record_actual_gate_time(event.gate.name, event.intersection_time)
            self.previous_last_gate = self.last_gate
            self.last_gate = event.gate
            self.last_visible_gate = event.gate  # SP is always visible

            # Clear in_range if this is the gate we were in range of
            if self.in_range_of_gate == event.gate:
                self.in_range_of_gate = None

            if not self.enroute:
                self.enroute = True
                logger.info(f"{self.contestant}: Switching to enroute after starting line crossing")

            self.update_enroute()
            self.websocket_facade.transmit_contestant(self.contestant)

            for calculator in self.calculators:
                calculator.on_starting_line_passed(event)

        elif isinstance(event, AdaptiveStartEvent):
            self.recalculation_completed = True
            # Update the contestant model with the recalculated gate times so they are persisted and used for future lookups
            self.contestant.predefined_gate_times = event.gate_times

            # Use update() to bypass signals that might reset gate times and bypass clean() checks
            Contestant.objects.filter(pk=self.contestant.pk).update(
                predefined_gate_times=self.contestant.predefined_gate_times,
            )

            self.websocket_facade.transmit_contestant(self.contestant)
            for calculator in self.calculators:
                calculator.on_adaptive_start(event)

        elif isinstance(event, GatePassedEvent):
            self.has_any_gate_passed = True
            self.contestant.record_actual_gate_time(event.gate.name, event.intersection_time)
            if not event.gate.waypoint.on_curved_segment:
                self.previous_last_gate = self.last_gate
                self.last_gate = event.gate
                if event.gate.is_visible:
                    self.last_visible_gate = event.gate

            # Clear in_range if this is the gate we were in range of
            if self.in_range_of_gate == event.gate:
                self.in_range_of_gate = None

            self.update_enroute()
            self.websocket_facade.transmit_contestant(self.contestant)

            for calculator in self.calculators:
                calculator.on_gate_passed(event)

            if event.gate.type == "fp":
                self.passed_finishpoint(trigger_time=event.intersection_time)

        elif isinstance(event, GateMissedEvent):
            self.has_any_gate_passed = True
            if not event.gate.waypoint.on_curved_segment:
                self.previous_last_gate = self.last_gate
                self.last_gate = event.gate
                if event.gate.is_visible:
                    self.last_visible_gate = event.gate

            # Clear in_range if this is the gate we were in range of
            if self.in_range_of_gate == event.gate:
                self.in_range_of_gate = None

            self.update_enroute()

            for calculator in self.calculators:
                calculator.on_gate_missed(event)

            if event.gate.type == "fp":
                self.passed_finishpoint(trigger_time=event.event_time)

        elif isinstance(event, TakeoffPassedEvent):
            self.has_any_gate_passed = True
            if not event.gate.waypoint.on_curved_segment:
                self.last_gate = event.gate
            self.contestant.record_actual_gate_time(event.gate.name, event.intersection_time)
            for calculator in self.calculators:
                calculator.on_takeoff_passed(event)

        elif isinstance(event, LandingPassedEvent):
            self.has_any_gate_passed = True
            self.has_landed = True
            if not event.gate.waypoint.on_curved_segment:
                self.last_gate = event.gate
            self.contestant.record_actual_gate_time(event.gate.name, event.intersection_time)
            for calculator in self.calculators:
                calculator.on_landing_passed(event)

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

        elif isinstance(event, NextGateExpectedEvent):
            self.next_gate = event.gate
            if self.next_gate is None:
                self.has_all_gates_passed = True
            for calculator in self.calculators:
                calculator.on_next_gate_expected(event)

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
            calculator.finalise(self.track)
