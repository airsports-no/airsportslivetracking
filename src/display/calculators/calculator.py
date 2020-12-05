import logging
import threading
from datetime import timedelta
from typing import List, TYPE_CHECKING, Optional

from display.calculators.positions_and_gates import Gate, Position
from display.coordinate_utilities import line_intersect, fraction_of_leg
from display.models import ContestantTrack, Contestant

if TYPE_CHECKING:
    from influx_facade import InfluxFacade

logger = logging.getLogger(__name__)


class Calculator(threading.Thread):
    BEFORE_START = 0
    STARTED = 1
    FINISHED = 2
    TRACKING = 3

    TRACKING_MAP = {
        TRACKING: "Tracking",
        BEFORE_START: "Waiting...",
        FINISHED: "Finished",
        STARTED: "Started"
    }

    def __init__(self, contestant: "Contestant", influx: "InfluxFacade"):
        super().__init__()
        self.loop_time = 60
        self.contestant = contestant
        self.influx = influx
        self.track = []  # type: List[Position]
        self.pending_points = []
        self.score = 0
        self.score_by_gate = {}
        self.score_log = []
        self.tracking_state = self.BEFORE_START
        self.process_event = threading.Event()
        _, _ = ContestantTrack.objects.get_or_create(contestant=self.contestant)
        self.scorecard = self.contestant.scorecard
        self.gates = self.create_gates()
        self.outstanding_gates = list(self.gates)
        self.starting_line = Gate(self.contestant.contest.track.starting_line, self.gates[0].expected_time)

    def run(self):
        logger.info("Started calculator for contestant {}".format(self.contestant))
        while self.tracking_state != self.FINISHED:
            self.process_event.wait(self.loop_time)
            self.process_event.clear()
            while len(self.pending_points) > 0:
                self.track.append(self.pending_points.pop(0))
                if len(self.track) > 1:
                    self.calculate_score()
        logger.info("Terminating calculator for {}".format(self.contestant))

    def update_score(self, gate: "Gate", score: float, message: str, latitude: float, longitude: float,
                     annotation_type: str):
        logger.info("UPDATE_SCORE {}: {}".format(self.contestant, message))
        self.score += score
        try:
            self.score_by_gate[gate.name] += score
        except KeyError:
            self.score_by_gate[gate.name] = self.score
        self.influx.add_annotation(self.contestant, latitude, longitude, message, annotation_type,
                                   self.track[-1].time)  # TODO: Annotations with the same time
        self.score_log.append(message)
        self.contestant.contestanttrack.update_score(self.score_by_gate, self.score, self.score_log)

    def create_gates(self) -> List:
        waypoints = self.contestant.contest.track.waypoints
        expected_times = self.contestant.gate_times
        gates = []
        for item in waypoints:
            gates.append(Gate(item, expected_times[item.name]))
        return gates

    def add_positions(self, positions):
        self.pending_points.extend([Position(**position) for position in positions])
        self.process_event.set()

    def update_tracking_state(self, tracking_state: int):
        if tracking_state == self.tracking_state:
            return
        logger.info("{}: Changing state to {}".format(self.contestant, self.TRACKING_MAP[tracking_state]))
        self.tracking_state = tracking_state
        self.contestant.contestanttrack.updates_current_state(self.TRACKING_MAP[tracking_state])

    def get_intersect_time(self, gate: "Gate"):
        if len(self.track) > 1:
            segment = self.track[-2:]  # type: List[Position]
            intersection = line_intersect(segment[0].longitude, segment[0].latitude, segment[1].longitude,
                                          segment[1].latitude, gate.x1, gate.y1, gate.x2, gate.y2)

            if intersection:
                fraction = fraction_of_leg(segment[0].longitude, segment[0].latitude, segment[1].longitude,
                                           segment[1].latitude, intersection[0], intersection[1])
                time_difference = (segment[1].time - segment[0].time).total_seconds()
                return segment[0].time + timedelta(seconds=fraction * time_difference)
        return None

    def get_intersect_time_infinite_gate(self, gate: "Gate"):
        if len(self.track) > 1:
            segment = self.track[-2:]  # type: List[Position]
            intersection = line_intersect(segment[0].longitude, segment[0].latitude, segment[1].longitude,
                                          segment[1].latitude, gate.x1_infinite, gate.y1_infinite, gate.x2_infinite,
                                          gate.y2_infinite)
            if intersection:
                fraction = fraction_of_leg(segment[0].longitude, segment[0].latitude, segment[1].longitude,
                                           segment[1].latitude, intersection[0], intersection[1])
                time_difference = (segment[1].time - segment[0].time).total_seconds()
                return segment[0].time + timedelta(seconds=fraction * time_difference)
        return None

    def check_intersections(self, force_gate: Optional["Gate"] = None):
        # Check starting line
        if not self.starting_line.has_been_passed():
            intersection_time = self.get_intersect_time(self.starting_line)
            if intersection_time:
                logger.info("{}: Passing start line {}".format(self.contestant, intersection_time))
                self.update_tracking_state(self.STARTED)
                self.starting_line.passing_time = intersection_time
        i = len(self.outstanding_gates) - 1
        crossed_gate = False
        while i >= 0:
            gate = self.outstanding_gates[i]
            intersection_time = self.get_intersect_time(gate)
            if intersection_time:
                logger.info("{}: Crossed gate {}".format(self.contestant, gate))
                gate.passing_time = intersection_time
                crossed_gate = True
            if force_gate == gate:
                crossed_gate = True
            if crossed_gate:
                if gate.passing_time is None:
                    logger.info("{}: Missed gate {}".format(self.contestant, gate))
                    gate.missed = True
                self.outstanding_gates.pop(i)
            i -= 1
        if not crossed_gate and len(self.outstanding_gates) > 0:
            extended_next_gate = self.outstanding_gates[0]  # type: Gate
            intersection_time = self.get_intersect_time_infinite_gate(extended_next_gate)
            if intersection_time:
                logger.info("{}: Crossed extended gate {} (but maybe missed the gate)".format(self.contestant,
                                                                                              extended_next_gate))
                extended_next_gate.maybe_missed_time = self.track[-1].time
        if len(self.outstanding_gates) > 0:
            gate = self.outstanding_gates[0]
            if gate.maybe_missed_time and (self.track[-1].time - gate.maybe_missed_time).total_seconds() > 15:
                logger.info("{}: Did not cross {} within 60 seconds of extended crossing, so missing gate".format(
                    self.contestant,
                    gate))
                gate.missed = True
                self.outstanding_gates.pop(0)

    def calculate_score(self):
        pass
