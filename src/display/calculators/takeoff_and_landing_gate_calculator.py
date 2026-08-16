import datetime
import logging
from multiprocessing import Queue
from typing import List, Optional, Tuple

from display.calculators.calculator_utilities import round_time_minute

from display.calculators.calculator import (
    Calculator,
    OrchestratorState,
    OrchestratorEvent,
    TakeoffPassedEvent,
    LandingPassedEvent,
    GateMissedEvent,
    GatePassedEvent,
    StartingLinePassedEvent,
    AdaptiveStartEvent,
)
from display.calculators.positions_and_gates import Gate, MultiGate
from display.calculators.update_score_message import UpdateScoreMessage
from display.models.contestant_utility_models import ContestantReceivedPosition
from display.models import ANOMALY, INFORMATION
from display.utilities.cima_task_type_definitions import ANR_CATALOGUE
from display.utilities.route_building_utilities import calculate_extended_gate
from websocket_channels import WebsocketFacade

logger = logging.getLogger(__name__)

GATE_SCORE_TYPE = "gate_score"
ANR_TAKEOFF_TIMING_SCORE_TYPE = "anr_takeoff_timing"


class TakeoffAndLandingGateCalculator(Calculator):
    """
    Calculator responsible for takeoff and landing gates.
    These are implemented as MultiGates.
    """

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
        self.initiate_takeoff_and_landing_gates()

        self.scored_takeoff = False
        self.scored_landing = False
        self.websocket_facade = WebsocketFacade()

    def initiate_takeoff_and_landing_gates(self):
        self.takeoff_gate = (
            MultiGate(
                [
                    Gate(
                        takeoff_gate,
                        self.contestant.gate_times[takeoff_gate.name],
                        calculate_extended_gate(takeoff_gate, self.scorecard),
                    )
                    for takeoff_gate in self.route.takeoff_gates
                    if not getattr(takeoff_gate, "on_curved_segment", False)
                ]
            )
            if len(self.route.takeoff_gates) > 0
            else None
        )
        if self.takeoff_gate:
            for gate in self.takeoff_gate.gates:
                gate.pre_project(self.projector)

        self.landing_gate = (
            MultiGate(
                [
                    Gate(
                        landing_gate,
                        self.contestant.gate_times[landing_gate.name],
                        calculate_extended_gate(landing_gate, self.scorecard),
                    )
                    for landing_gate in self.route.landing_gates
                    if not getattr(landing_gate, "on_curved_segment", False)
                ]
            )
            if len(self.route.landing_gates) > 0
            else None
        )
        if self.landing_gate:
            for gate in self.landing_gate.gates:
                gate.pre_project(self.projector)

    def calculate_outside_route(
        self,
        track: List[ContestantReceivedPosition],
        state: OrchestratorState,
    ) -> List[OrchestratorEvent]:
        # Note: state.takeoff_gate/landing_gate might be None if Gatekeeper was refactored
        # but self.takeoff_gate/landing_gate are initialized in __init__
        return self._check_gates(track, state)

    def calculate_enroute(
        self,
        track: List[ContestantReceivedPosition],
        state: OrchestratorState,
    ) -> List[OrchestratorEvent]:
        return self._check_gates(track, state)

    def _check_gates(
        self, track: List[ContestantReceivedPosition], state: OrchestratorState
    ) -> List[OrchestratorEvent]:
        events = []
        # Check takeoff if exists
        if self.takeoff_gate is not None and not self.scored_takeoff:
            if not self.takeoff_gate.has_been_passed():
                intersection_time = self.takeoff_gate.get_gate_intersection_time(self.projector, track)
                if intersection_time:
                    intersected_gate = self.takeoff_gate.intersected_gate
                    events.append(TakeoffPassedEvent(intersected_gate, track[-1], intersection_time))

        # Handle landing gate after finish point
        if state.has_passed_finishpoint:
            if self.landing_gate is not None and not self.scored_landing:
                if not self.landing_gate.has_been_passed():
                    intersection_time = self.landing_gate.get_gate_intersection_time(self.projector, track)
                    if intersection_time:
                        intersected_gate = self.landing_gate.intersected_gate
                        events.append(LandingPassedEvent(intersected_gate, track[-1], intersection_time))
        return events

    def on_takeoff_passed(self, event: TakeoffPassedEvent):
        if self.scored_takeoff:
            return
        if not self.takeoff_gate:
            # No takeoff gate is authored for this route, so this event did not
            # originate from us (e.g. it's a speed-inferred takeoff for a
            # DURATION task). Leave scoring to whichever calculator owns that
            # inference; there is no declared gate here to time against.
            return
        self.scored_takeoff = True
        if self.takeoff_gate:
            self.takeoff_gate.pass_gate(event.intersection_time, event.position, gate=event.gate)
        logger.info(f"{self.contestant}: Scoring takeoff gate {event.gate}")
        gate_score = self.scorecard.get_gate_timing_score_for_gate_type(
            event.gate.type, event.gate.expected_time, event.intersection_time
        )
        self.transmit_actual_crossing(event.gate, event.position)
        score_type = GATE_SCORE_TYPE
        message = "passing takeoff gate"
        if getattr(self.contestant.navigation_task, "task_subtype", None) == ANR_CATALOGUE:
            score_type = ANR_TAKEOFF_TIMING_SCORE_TYPE
            message = "ANR takeoff timing"
        self.update_score(
            UpdateScoreMessage(
                event.intersection_time,
                event.gate,
                gate_score,
                message,
                event.position.latitude,
                event.position.longitude,
                ANOMALY if gate_score > 0 else INFORMATION,
                score_type,
                planned=event.gate.expected_time,
                actual=event.intersection_time,
            )
        )

    def on_landing_passed(self, event: LandingPassedEvent):
        if self.scored_landing:
            return
        if not self.landing_gate:
            # No landing gate is authored for this route (see on_takeoff_passed).
            return
        self.scored_landing = True
        if self.landing_gate:
            self.landing_gate.pass_gate(event.intersection_time, event.position, gate=event.gate)
        logger.info(f"{self.contestant}: Scoring landing gate {event.gate}")
        gate_score = self.scorecard.get_gate_timing_score_for_gate_type(
            event.gate.type, event.gate.expected_time, event.intersection_time
        )
        self.transmit_actual_crossing(event.gate, event.position)
        self.update_score(
            UpdateScoreMessage(
                event.intersection_time,
                event.gate,
                gate_score,
                "passed landing gate",
                event.position.latitude,
                event.position.longitude,
                ANOMALY if gate_score > 0 else INFORMATION,
                GATE_SCORE_TYPE,
                planned=event.gate.expected_time,
                actual=event.intersection_time,
            )
        )

    def on_gate_missed(self, event: GateMissedEvent):
        # Proactively miss takeoff gate if any route gate is missed
        if not self.scored_takeoff and self.takeoff_gate and event.gate.type != "to":
            if event.gate.type in ("sp", "tp", "fp", "secret"):
                logger.info(f"{self.contestant}: Missing takeoff gate because {event.gate} was missed")
                # Use 1 second before to ensure it appears before the gate miss in the log
                self._miss_takeoff(event.position.time - datetime.timedelta(seconds=5), event.position)

        # We only care if it's a takeoff gate being missed here.
        # Landing gate miss is handled in finalise or by actual gate miss.
        if event.gate.type == "to":
            self._miss_takeoff(event.event_time or event.position.time, event.position)

    def on_gate_passed(self, event: GatePassedEvent):
        # Proactively miss takeoff gate if any route gate is passed
        if self.takeoff_gate and not self.scored_takeoff:
            if event.gate.type in ("sp", "tp", "fp", "secret"):
                logger.info(f"{self.contestant}: Missing takeoff gate because {event.gate} was passed")
                # Use 1 second before to ensure it appears before the gate pass in the log
                self._miss_takeoff(event.intersection_time - datetime.timedelta(seconds=5), event.position)

    def on_starting_line_passed(self, event: StartingLinePassedEvent):
        # Proactively miss takeoff gate if starting line is passed
        if self.takeoff_gate and not self.scored_takeoff:
            logger.info(f"{self.contestant}: Missing takeoff gate because starting line was passed")
            # Use 1 second before to ensure it appears before the starting line crossing in the log
            self._miss_takeoff(event.intersection_time - datetime.timedelta(seconds=5), event.position)

    def on_adaptive_start(self, event: AdaptiveStartEvent):
        """
        Update expected times for takeoff and landing gates based on adaptive start time.
        """
        new_start_time = event.intersection_time
        gate_times = self.contestant.calculate_missing_gate_times({}, round_time_minute(new_start_time))

        if self.takeoff_gate:
            for gate in self.takeoff_gate.gates:
                if gate.name in gate_times:
                    gate.expected_time = gate_times[gate.name]

        if self.landing_gate:
            for gate in self.landing_gate.gates:
                if gate.name in gate_times:
                    gate.expected_time = gate_times[gate.name]

    def _miss_takeoff(self, event_time: datetime.datetime, position: ContestantReceivedPosition):
        logger.info(f"{self.contestant}: _miss_takeoff called")
        if self.scored_takeoff or not self.takeoff_gate:
            return
        self.scored_takeoff = True

        # Use first physical gate as representative for the MultiGate miss
        g = self.takeoff_gate.gates[0]

        score = self.scorecard.get_gate_timing_score_for_gate_type("to", g.expected_time, None)
        score_type = GATE_SCORE_TYPE
        message = "missing takeoff gate"
        if getattr(self.contestant.navigation_task, "task_subtype", None) == ANR_CATALOGUE:
            score_type = ANR_TAKEOFF_TIMING_SCORE_TYPE
            message = "ANR takeoff timing missed"
        self.update_score(
            UpdateScoreMessage(
                event_time,
                g,
                score,
                message,
                position.latitude if position else g.latitude,
                position.longitude if position else g.longitude,
                ANOMALY,
                score_type,
                planned=g.expected_time,
                actual=None,
            )
        )

    def _miss_landing(self, event_time: datetime.datetime, position: ContestantReceivedPosition):
        logger.info(f"{self.contestant}: _miss_landing called")
        if self.scored_landing or not self.landing_gate:
            return
        self.scored_landing = True

        # Use first physical gate as representative for the MultiGate miss
        g = self.landing_gate.gates[0]

        score = self.scorecard.get_gate_timing_score_for_gate_type("ldg", g.expected_time, None)
        self.update_score(
            UpdateScoreMessage(
                event_time,
                g,
                score,
                "missing landing gate",
                position.latitude if position else g.latitude,
                position.longitude if position else g.longitude,
                ANOMALY,
                GATE_SCORE_TYPE,
                planned=g.expected_time,
                actual=None,
            )
        )

    def finalise(self, track: List[ContestantReceivedPosition]):
        # MultiGate logic: if none passed, one miss penalty
        if not self.scored_takeoff and self.takeoff_gate:
            # Trigger miss for the first takeoff gate as representative of the MultiGate
            # Use 1 second before to ensure it appears before the rest of finalise in the log
            self._miss_takeoff(
                (track[-1].time if track else datetime.datetime.now(datetime.timezone.utc))
                - datetime.timedelta(seconds=1),
                track[-1] if track else None,
            )

        if not self.scored_landing and self.landing_gate:
            # Use 1 second after to ensure it appears after the rest of finalise in the log
            self._miss_landing(
                (track[-1].time if track else datetime.datetime.now(datetime.timezone.utc))
                + datetime.timedelta(seconds=1),
                track[-1] if track else None,
            )

    def transmit_actual_crossing(self, gate: Gate, position: ContestantReceivedPosition):
        """
        Update the gate score arrow in the frontend with information about the actual crossing time.
        """
        estimated_crossing_time = position.time
        if gate.passing_time:
            planned_time_to_crossing = (gate.passing_time - gate.expected_time).total_seconds()
            estimated_crossing_time = gate.passing_time
        else:
            planned_time_to_crossing = (position.time - gate.expected_time).total_seconds()

        score = self.scorecard.get_gate_timing_score_for_gate_type(
            gate.type, gate.expected_time, estimated_crossing_time
        )

        if self.live_processing:
            self.websocket_facade.transmit_seconds_to_crossing_time_and_crossing_estimate(
                self.contestant,
                gate.name,
                planned_time_to_crossing,
                round((estimated_crossing_time - gate.expected_time).total_seconds()),
                score,
                True,
                gate.missed,
            )
