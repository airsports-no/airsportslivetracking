import logging
from typing import List, Optional, Sequence

from display.calculators.calculator import (
    Calculator,
    LandingPassedEvent,
    OrchestratorEvent,
    OrchestratorState,
    TakeoffPassedEvent,
)
from display.calculators.positions_and_gates import Gate
from display.models.contestant_utility_models import ContestantReceivedPosition
from display.utilities.coordinate_utilities import calculate_bearing, project_position_lat_lon
from display.utilities.route_building_utilities import build_waypoint, calculate_extended_gate

logger = logging.getLogger(__name__)

# Matches the proactive-termination heuristic in contestant_processor.py, which
# infers landing from the same near-zero-speed/consecutive-sample pattern.
NEAR_ZERO_SPEED_THRESHOLD_KT = 6
SUSTAINED_SAMPLE_COUNT = 60
SYNTHETIC_GATE_WIDTH_M = 200


class SpeedInferredTakeoffLandingCalculator(Calculator):
    """2.B3 Duration fallback: infers takeoff/landing from the track's speed profile
    for routes that don't author explicit takeoff/landing gates.

    Takeoff is detected as soon as speed rises above threshold after a sustained
    near-zero hold (so the recorded time tracks the actual liftoff moment). Landing
    is detected once low speed has been sustained for a full window while airborne
    (so a brief slowdown mid-flight doesn't get mistaken for touchdown) - the same
    "reaches a sustained streak" trigger used by the proactive termination
    heuristic in contestant_processor.py.

    Each side is only active when that side's gates are genuinely absent from the
    route, so routes that do author takeoff/landing gates are entirely unaffected -
    including the case where only one side is authored: on_takeoff_passed tracks
    airborne state from a real takeoff gate too, so landing inference still works
    when takeoff is authored but landing is not (and vice versa, implicitly, since
    inference for an authored side is simply never attempted).
    """

    def __init__(self, contestant, scorecard, route, score_processing_queue, live_processing=True, projector=None):
        super().__init__(
            contestant, scorecard, route, score_processing_queue, live_processing=live_processing, projector=projector
        )
        self.infer_takeoff = len(self.route.takeoff_gates) == 0
        self.infer_landing = len(self.route.landing_gates) == 0
        self.airborne = False
        self.scored_takeoff = False
        self.scored_landing = False
        self.consecutive_low_speed = 0

    def on_takeoff_passed(self, event: TakeoffPassedEvent):
        # Track airborne state even when takeoff itself was detected by a real
        # authored gate (TakeoffAndLandingGateCalculator), so landing inference
        # still works when only the landing side is missing gates.
        self.airborne = True
        self.scored_takeoff = True

    def on_landing_passed(self, event: LandingPassedEvent):
        self.scored_landing = True

    def _build_synthetic_gate(self, position: ContestantReceivedPosition, previous_position, gate_type: str, name: str) -> Gate:
        if previous_position is not None and (
            (position.latitude, position.longitude) != (previous_position.latitude, previous_position.longitude)
        ):
            bearing = calculate_bearing(
                (previous_position.latitude, previous_position.longitude), (position.latitude, position.longitude)
            )
        else:
            bearing = 0
        perpendicular_bearing = (bearing + 90) % 360
        half_width = SYNTHETIC_GATE_WIDTH_M / 2
        point_a = project_position_lat_lon((position.latitude, position.longitude), perpendicular_bearing, half_width)
        point_b = project_position_lat_lon(
            (position.latitude, position.longitude), (perpendicular_bearing + 180) % 360, half_width
        )
        waypoint = build_waypoint(name, position.latitude, position.longitude, gate_type, SYNTHETIC_GATE_WIDTH_M, True, True)
        waypoint.gate_line = [point_a, point_b]
        gate = Gate(waypoint, position.time, calculate_extended_gate(waypoint, self.scorecard))
        gate.pre_project(self.projector)
        return gate

    def calculate_enroute(
        self, track: Sequence[ContestantReceivedPosition], state: OrchestratorState
    ) -> List[OrchestratorEvent]:
        return self._check_transitions(track)

    def calculate_outside_route(
        self, track: Sequence[ContestantReceivedPosition], state: OrchestratorState
    ) -> List[OrchestratorEvent]:
        return self._check_transitions(track)

    def _check_transitions(self, track: Sequence[ContestantReceivedPosition]) -> List[OrchestratorEvent]:
        if not track:
            return []
        position = track[-1]
        speed = position.speed if position.speed is not None else 0
        events: List[OrchestratorEvent] = []

        # Takeoff is edge-detected (the first fast sample right after a sustained
        # hold) so the recorded time tracks the actual liftoff moment. Landing
        # uses the same "reaches a sustained streak" trigger as the proactive
        # termination heuristic in contestant_processor.py rather than edge
        # detection, so a momentary slowdown mid-flight can't be mistaken for
        # touchdown - only a full sustained window of near-zero speed counts.
        was_sustained_low = self.consecutive_low_speed >= SUSTAINED_SAMPLE_COUNT

        if speed < NEAR_ZERO_SPEED_THRESHOLD_KT:
            self.consecutive_low_speed += 1
        else:
            self.consecutive_low_speed = 0

        previous_position: Optional[ContestantReceivedPosition] = track[-2] if len(track) >= 2 else None

        if (
            self.infer_takeoff
            and not self.scored_takeoff
            and not self.airborne
            and was_sustained_low
            and speed >= NEAR_ZERO_SPEED_THRESHOLD_KT
        ):
            self.airborne = True
            self.scored_takeoff = True
            gate = self._build_synthetic_gate(position, previous_position, "to", "Inferred takeoff")
            logger.info(f"{self.contestant}: Inferring takeoff from speed profile at {position.time}")
            events.append(TakeoffPassedEvent(gate, position, position.time))
        elif (
            self.infer_landing
            and not self.scored_landing
            and self.airborne
            and self.consecutive_low_speed == SUSTAINED_SAMPLE_COUNT
        ):
            self.scored_landing = True
            gate = self._build_synthetic_gate(position, previous_position, "ldg", "Inferred landing")
            logger.info(f"{self.contestant}: Inferring landing from speed profile at {position.time}")
            events.append(LandingPassedEvent(gate, position, position.time))

        return events

    def finalise(self, track: Sequence[ContestantReceivedPosition]):
        return None
