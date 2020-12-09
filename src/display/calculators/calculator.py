import logging
import threading
from datetime import timedelta
from typing import List, TYPE_CHECKING, Optional

from display.calculators.positions_and_gates import Gate, Position
from display.convert_flightcontest_gpx import calculate_extended_gate
from display.coordinate_utilities import line_intersect, fraction_of_leg
from display.models import ContestantTrack, Contestant
from display.waypoint import Waypoint

if TYPE_CHECKING:
    from influx_facade import InfluxFacade

logger = logging.getLogger(__name__)


class Calculator(threading.Thread):
    BEFORE_START = 0
    STARTED = 1
    FINISHED = 2
    TRACKING = 3
    TAKEOFF = 4

    TRACKING_MAP = {
        TRACKING: "Tracking",
        BEFORE_START: "Waiting...",
        FINISHED: "Finished",
        STARTED: "Started",
        TAKEOFF: "Takeoff"
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
        self.position_update_lock = threading.Lock()

        self.starting_line = self.gates[0]
        self.takeoff_gate = Gate(self.contestant.navigation_task.track.takeoff_gate,
                                 self.contestant.takeoff_time,
                                 calculate_extended_gate(self.contestant.navigation_task.track.takeoff_gate,
                                                         self.scorecard)) if self.contestant.navigation_task.track.takeoff_gate else None
        self.landing_gate = Gate(self.contestant.navigation_task.track.landing_gate,
                                 self.contestant.finished_by_time,
                                 calculate_extended_gate(self.contestant.navigation_task.track.landing_gate,
                                                         self.scorecard)) if self.contestant.navigation_task.track.landing_gate else None
        self.outstanding_gates = list(self.gates)

    def run(self):
        logger.info("Started calculator for contestant {}".format(self.contestant))
        while self.tracking_state != self.FINISHED:
            self.process_event.wait(self.loop_time)
            self.process_event.clear()
            while len(self.pending_points) > 0:
                with self.position_update_lock:
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

    def create_gates(self) -> List[Gate]:
        waypoints = self.contestant.navigation_task.track.waypoints
        expected_times = self.contestant.gate_times
        gates = []
        for item in waypoints:  # type: Waypoint
            gates.append(Gate(item, expected_times[item.name], calculate_extended_gate(item, self.scorecard)))
        return gates

    def add_positions(self, positions):
        with self.position_update_lock:
            self.pending_points.extend([Position(**position) for position in positions])
        self.process_event.set()

    def update_tracking_state(self, tracking_state: int):
        if tracking_state == self.tracking_state:
            return
        logger.info("{}: Changing state to {}".format(self.contestant, self.TRACKING_MAP[tracking_state]))
        self.tracking_state = tracking_state
        self.contestant.contestanttrack.updates_current_state(self.TRACKING_MAP[tracking_state])

    def check_extended_intersections(self):
        i = len(self.outstanding_gates) - 1
        crossed_gate = False
        while i >= 0:
            gate = self.outstanding_gates[i]  # type
            intersection_time = gate.get_gate_extended_intersection_time(self.track)
            if intersection_time:
                gate.crossed_

    def check_intersections(self, force_gate: Optional["Gate"] = None):
        # Check takeoff if exists
        if self.takeoff_gate is not None:
            if not self.takeoff_gate.has_been_passed():
                intersection_time = self.takeoff_gate.get_gate_intersection_time(self.track)
                if intersection_time:
                    logger.info("{}: Passing takeoff line {}".format(self.contestant, intersection_time))
                    self.update_tracking_state(self.TAKEOFF)
                    self.takeoff_gate.passing_time = intersection_time
                else:
                    return
        i = len(self.outstanding_gates) - 1
        crossed_gate = False
        while i >= 0:
            gate = self.outstanding_gates[i]
            intersection_time = gate.get_gate_intersection_time(self.track)
            if intersection_time:
                logger.info("{}: Crossed gate {} at {}".format(self.contestant, gate, intersection_time))
                gate.passing_time = intersection_time
                gate.extended_passing_time = intersection_time
                crossed_gate = True
            if force_gate == gate:
                crossed_gate = True
            if crossed_gate:
                if gate.passing_time is None:
                    logger.info("{}: Missed gate {}".format(self.contestant, gate))
                    gate.missed = True
                self.outstanding_gates.pop(i)
            i -= 1
        if len(self.outstanding_gates) > 0:
            extended_next_gate = self.outstanding_gates[0]  # type: Gate
            if extended_next_gate.type != "sp":
                intersection_time = extended_next_gate.get_gate_extended_intersection_time(self.track)
                if intersection_time:
                    extended_next_gate.extended_passing_time = intersection_time
        if not crossed_gate and len(self.outstanding_gates) > 0:
            extended_next_gate = self.outstanding_gates[0]  # type: Gate
            if extended_next_gate.type != "sp":
                intersection_time = extended_next_gate.get_gate_infinite_intersection_time(self.track)
                if intersection_time and extended_next_gate.is_passed_in_correct_direction_track(self.track):
                    logger.info("{}: Crossed extended gate {} (but maybe missed the gate) at {}".format(self.contestant,
                                                                                                        extended_next_gate,
                                                                                                        self.track[
                                                                                                            -1].time))
                    extended_next_gate.maybe_missed_time = self.track[-1].time
        if len(self.outstanding_gates) > 0:
            gate = self.outstanding_gates[0]
            time_limit = 10
            if gate.maybe_missed_time and (self.track[-1].time - gate.maybe_missed_time).total_seconds() > time_limit:
                logger.info("{}: Did not cross {} within {} seconds of extended crossing, so missing gate".format(
                    self.contestant,
                    gate, time_limit))
                gate.missed = True
                self.outstanding_gates.pop(0)

    def calculate_score(self):
        pass
