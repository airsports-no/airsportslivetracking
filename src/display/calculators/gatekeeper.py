import datetime
import logging
import threading
from abc import abstractmethod
from multiprocessing.queues import Queue
from queue import Empty
from typing import List, TYPE_CHECKING, Optional, Callable, Tuple

import pytz
from django.core.cache import cache

from display.calculators.calculator_utilities import round_time, distance_between_gates
from display.calculators.positions_and_gates import Gate, Position
from display.convert_flightcontest_gpx import calculate_extended_gate
from display.coordinate_utilities import line_intersect, fraction_of_leg, Projector, calculate_distance_lat_lon, \
    calculate_fractional_distance_point_lat_lon
from display.models import ContestantTrack, Contestant
from display.waypoint import Waypoint

from influx_facade import InfluxFacade

logger = logging.getLogger(__name__)


class ScoreAccumulator:
    def __init__(self):
        self.related_score = {}

    def set_and_update_score(self, score: float, score_type: str, maximum_score: Optional[float]) -> Tuple[float, bool]:
        """
        Returns the calculated score given the maximum limits. If there is no maximum limit, score is returned
        """
        capped = False
        current_score_for_type = self.related_score.setdefault(score_type, 0)
        if maximum_score is not None and maximum_score > -1:
            if current_score_for_type + score >= maximum_score:
                score = maximum_score - current_score_for_type
                capped = True
        self.related_score[score_type] += score
        return score, capped


LOOP_TIME = 60
CONTESTANT_REFRESH_INTERVAL = datetime.timedelta(seconds=30)


class Gatekeeper:
    GATE_SCORE_TYPE = "gate_score"
    BACKWARD_STARTING_LINE_SCORE_TYPE = "backwards_starting_line"

    def __init__(self, contestant: "Contestant", position_queue: Queue, calculators: List[Callable],
                 live_processing: bool = True):
        super().__init__()
        self.live_processing = live_processing
        self.track_terminated = False
        self.contestant = contestant
        self.contestant.calculator_started = True
        self.contestant.save()
        self.last_contestant_refresh = datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)
        self.position_queue = position_queue
        self.last_termination_command_check = None
        self.influx = InfluxFacade()
        self.track = []  # type: List[Position]
        self.score = 0
        self.score_by_gate = {}
        self.has_passed_finishpoint = False
        self.last_gate_index = 0
        self.enroute = False
        self.process_event = threading.Event()
        _, _ = ContestantTrack.objects.get_or_create(contestant=self.contestant)
        self.scorecard = self.contestant.navigation_task.scorecard
        self.gates = self.create_gates()
        self.outstanding_gates = list(self.gates)
        self.position_update_lock = threading.Lock()
        self.last_gate = None  # type: Optional[Gate]
        self.previous_last_gate = None  # type: Optional[Gate]
        self.accumulated_scores = ScoreAccumulator()
        self.projector = Projector(self.gates[0].latitude, self.gates[0].longitude)
        self.in_range_of_gate = None
        self.calculators = []
        for calculator in calculators:
            self.calculators.append(
                calculator(self.contestant, self.scorecard, self.gates, self.contestant.navigation_task.route,
                           self.update_score))

    def interpolate_track(self, position: Position) -> List[Position]:
        if len(self.track) == 0:
            return [position]
        initial_time = self.track[-1].time
        distance = calculate_distance_lat_lon((self.track[-1].latitude, self.track[-1].longitude),
                                              (position.latitude, position.longitude))
        if distance < 0.001:
            return [position]
        time_difference = int((position.time - initial_time).total_seconds())
        positions = []
        if time_difference > 2:
            fraction = 1 / time_difference
            for step in range(1, time_difference):
                new_position = calculate_fractional_distance_point_lat_lon(
                    (self.track[-1].latitude, self.track[-1].longitude), (position.latitude, position.longitude),
                    step * fraction)
                positions.append(
                    Position((initial_time + datetime.timedelta(seconds=step)).isoformat(), new_position[0],
                             new_position[1],
                             position.altitude, position.speed, position.course, position.battery_level))
        positions.append(position)
        return positions

    def run(self):
        logger.info("Started calculator for contestant {} {}-{}".format(self.contestant, self.contestant.takeoff_time,
                                                                        self.contestant.finished_by_time))
        while not self.track_terminated:
            now = datetime.datetime.now(datetime.timezone.utc)
            if now - self.last_contestant_refresh > CONTESTANT_REFRESH_INTERVAL:
                self.contestant.refresh_from_db()
                self.last_contestant_refresh = now
            try:
                data = self.position_queue.get(timeout=30)
            except Empty:
                # We have not received anything for 60 seconds, check if we should terminate
                self.check_termination()
                continue
            if data is None:
                # Signal the track processor that this is the end, and perform the track calculation
                self.track_terminated = True
                continue
            p = Position(data["time"], **data["fields"])
            if len(self.track) > 0 and (
                    (p.latitude == self.track[-1].latitude and p.longitude == self.track[-1].longitude) or self.track[
                -1].time >= p.time):
                # Old or duplicate position, ignoring
                continue
            progress = self.contestant.calculate_progress(p.time)
            if self.live_processing:
                self.influx.put_position_data_for_contestant(self.contestant, [data], progress)
            for position in self.interpolate_track(p):
                self.track.append(position)
                if len(self.track) > 1:
                    self.calculate_score()
        self.contestant.contestanttrack.set_calculator_finished()
        while not self.position_queue.empty():
            self.position_queue.get_nowait()
        logger.info("Terminating calculator for {}".format(self.contestant))

    def update_score(self, gate: "Gate", score: float, message: str, latitude: float, longitude: float,
                     annotation_type: str, score_type: str, maximum_score: Optional[float] = None,
                     planned: Optional[datetime.datetime] = None,
                     actual: Optional[datetime.datetime] = None):
        """

        :param gate: The last gate which indicates the current leg
        :param score: The penalty awarded
        :param message: A brief description of why the penalty is awarded
        :param latitude: The position of the contestant
        :param longitude: The position of the contestant
        :param annotation_type: information or anomaly
        :param score_type: Keyword that is linked to maximum score. Schools are accumulated for each keyword and compared to maximum if supplied
        :param maximum_score: Maximum score for the score type over the entire task
        :param planned: The planned passing time if gate
        :param actual: The actual passing time if gate
        :return:
        """
        score, capped = self.accumulated_scores.set_and_update_score(score, score_type, maximum_score)
        if planned is not None and actual is not None:
            offset = (actual - planned).total_seconds()
            offset_string = "{} s".format("+{}".format(int(offset)) if offset > 0 else int(offset))
        else:
            offset_string = None
        if capped:
            message += " (capped)"
        internal_message = {
            "gate": gate.name,
            "message": message,
            "points": score,
            "planned": planned.astimezone(self.contestant.navigation_task.contest.time_zone).strftime(
                "%H:%M:%S %z") if planned else None,
            "actual": actual.astimezone(self.contestant.navigation_task.contest.time_zone).strftime(
                "%H:%M:%S %z") if actual else None,
            "offset_string": offset_string
        }
        string = "{}: {} points {}".format(gate.name, score, message)
        if offset_string:
            string += " ({})".format(offset_string)
        if planned and actual:
            string += "\n(planned: {}, actual: {})".format(internal_message["planned"], internal_message["actual"])
        elif planned:
            string += "\n(planned: {}, actual: --)".format(internal_message["planned"])
        internal_message["string"] = string
        logger.info("UPDATE_SCORE {}: {}".format(self.contestant, string))
        # Take into account that external events may have changed the score
        self.contestant.contestanttrack.refresh_from_db()
        self.score = self.contestant.contestanttrack.score
        self.score += score
        try:
            self.score_by_gate[gate.name] += score
        except KeyError:
            self.score_by_gate[gate.name] = self.score
        self.influx.add_annotation(self.contestant, latitude, longitude, string, annotation_type,
                                   self.track[-1].time)  # TODO: Annotations with the same time
        self.contestant.contestanttrack.score_log.append(internal_message)
        self.contestant.contestanttrack.update_score(self.score_by_gate, self.score,
                                                     self.contestant.contestanttrack.score_log)

    def create_gates(self) -> List[Gate]:
        waypoints = self.contestant.navigation_task.route.waypoints
        expected_times = self.contestant.gate_times
        gates = []
        for item in waypoints:  # type: Waypoint
            gates.append(Gate(item, expected_times[item.name],
                              calculate_extended_gate(item, self.scorecard, self.contestant)))
        return gates

    def pop_gate(self, index, update_last: bool = True):
        gate = self.outstanding_gates.pop(index)
        if update_last:
            self.previous_last_gate = self.last_gate
            logger.info(f"Updating last gate to {gate}")
            self.last_gate = gate
        self.update_enroute()

    def any_gate_passed(self):
        return any([gate.has_been_passed() for gate in self.gates])

    def all_gates_passed(self):
        return all([gate.has_been_passed() for gate in self.gates])

    def update_enroute(self):
        logger.info(f"last_gate: {self.last_gate} {self.last_gate.type}")
        if self.enroute and self.last_gate is not None and self.last_gate.type in ["ldg", "ifp", "fp"]:
            self.enroute = False
            logger.info("Switching to not enroute")
            return
        if not self.enroute and self.last_gate is not None and self.last_gate.type in ["sp", "isp", "tp", "secret"]:
            self.enroute = True
            logger.info("Switching to enroute")

    def passed_finishpoint(self):
        if not self.has_passed_finishpoint:
            self.has_passed_finishpoint = True
            for calculator in self.calculators:
                calculator.passed_finishpoint(self.track, self.last_gate)

    def check_termination(self):
        if not self.track_terminated:
            self.track_terminated = self.is_termination_commanded()
            if self.track_terminated:
                self.update_score(self.last_gate or self.gates[0], 0, "manually terminated",
                                  self.track[-1].latitude if len(self.track) > 0 else self.gates[0].latitude,
                                  self.track[-1].longitude if len(self.track) > 0 else self.gates[0].longitude,
                                  "information", "")

    def is_termination_commanded(self) -> bool:
        now = datetime.datetime.now(datetime.timezone.utc)
        if self.last_termination_command_check is None or now > self.last_termination_command_check + datetime.timedelta(
                seconds=15):
            self.last_termination_command_check = now
            termination_requested = cache.get(self.contestant.termination_request_key)
            return termination_requested is not None
        return False

    @abstractmethod
    def check_gates(self):
        raise NotImplementedError

    def missed_gate(self, previous_gate: Optional[Gate], gate: Gate, position: Position):
        for calculator in self.calculators:
            calculator.missed_gate(previous_gate, gate, position)

    def calculate_score(self):
        if self.track_terminated:
            return
        self.check_gates()
        for calculator in self.calculators:
            if self.enroute:
                calculator.calculate_enroute(self.track, self.last_gate, self.in_range_of_gate)
            else:
                calculator.calculate_outside_route(self.track, self.last_gate)
        self.check_termination()

    def get_speed(self):
        previous_index = min(5, len(self.track))
        distance = distance_between_gates(self.track[-previous_index], self.track[-1]) / 1852
        time_difference = (self.track[-1].time - self.track[-previous_index].time).total_seconds() / 3600
        if time_difference == 0:
            time_difference = 0.01
        return distance / time_difference
