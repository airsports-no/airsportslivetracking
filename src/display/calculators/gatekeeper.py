import datetime
import logging
import threading
import time
from abc import abstractmethod, ABC
from queue import Queue
from typing import List, Optional, Callable, Tuple, Dict

import dateutil
from django.core.exceptions import ObjectDoesNotExist

from display.utilities.calculator_running_utilities import calculator_is_alive, calculator_is_terminated
from display.utilities.calculator_termination_utilities import is_termination_requested
from redis_queue import RedisQueue, RedisEmpty
from slack_facade import post_slack_message
from utilities.timed_queue import TimedQueue, TimedOut
from websocket_channels import WebsocketFacade

from display.utilities.traccar_factory import get_traccar_instance

from display.calculators.calculator_utilities import distance_between_gates
from display.calculators.positions_and_gates import Gate, Position
from display.utilities.route_building_utilities import calculate_extended_gate
from display.utilities.coordinate_utilities import (
    Projector,
    calculate_distance_lat_lon,
    calculate_fractional_distance_point_lat_lon,
)
from display.models import Contestant, TrackAnnotation, ScoreLogEntry, ContestantReceivedPosition
from display.waypoint import Waypoint

DANGER_LEVEL_REPORT_INTERVAL = 5
CHECK_BUFFERED_DATA_TIME_LIMIT = 6
logger = logging.getLogger(__name__)


class ScoreAccumulator:
    """
    A score accumulator keeps track of scores that have a maximum limit.
    """

    def __init__(self):
        self.related_score = {}

    def set_and_update_score(
        self, score: float, score_type: str, maximum_score: Optional[float], previous_score: Optional[float] = 0
    ) -> Tuple[float, bool]:
        """
        Returns the calculated score given the maximum limits. If there is no maximum limit, score is returned
        """
        capped = False
        score -= previous_score
        current_score_for_type = self.related_score.setdefault(score_type, 0)
        if maximum_score is not None and maximum_score > -1:
            if current_score_for_type + score >= maximum_score:
                score = maximum_score - current_score_for_type
                capped = True
        self.related_score[score_type] += score
        return score + previous_score, capped


LOOP_TIME = 60
CONTESTANT_REFRESH_INTERVAL = datetime.timedelta(seconds=15)


class Gatekeeper(ABC):
    """
    The Gatekeeper is the main class for tracking contestants during flight. It is responsible for processing positions
    received from the Traccar service, interpolating missing positions on the track, and storing these to the database.
    It provides methods for updating the contestants score.

    As the name implies it is built around maintaining a list of gates and tracking the contestants progress through
    these gates. The rules for progressing through the gates must be implemented by a subclass.

    The gatekeeper supports a list of calculators  that can be used to score other aspects of the flight, like altitude
    constraints, penalty zones, prohibited zones, backtracking, et cetera.
    """

    GATE_SCORE_TYPE = "gate_score"
    BACKWARD_STARTING_LINE_SCORE_TYPE = "backwards_starting_line"

    def __init__(
        self,
        contestant: "Contestant",
        calculators: List[Callable],
        live_processing: bool = True,
        queue_name_override: str = None,
    ):
        calculator_is_alive(contestant.pk, 30)
        super().__init__()
        logger.info(f"{contestant}: Created gatekeeper")
        self.traccar = get_traccar_instance()
        self.latest_position_report = None
        self.live_processing = live_processing
        self.track_terminated = False
        self.contestant = contestant
        self.contestant_track = contestant.contestanttrack
        self.last_contestant_refresh = datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)
        self.position_queue = RedisQueue(queue_name_override or str(contestant.pk))
        self.score_processing_queue = Queue()
        self.last_termination_command_check = None
        self.track = []  # type: List[Position]
        self.score = 0
        self.has_passed_finishpoint = False
        self.last_gate_index = 0
        self.enroute = False
        self.process_event = threading.Event()
        self.contestant.reset_track_and_score()
        self.contestant.contestantreceivedposition_set.all().delete()
        self.contestant_track.set_calculator_started()
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
        self.websocket_facade = WebsocketFacade()
        self.timed_queue = TimedQueue()
        self.last_danger_level_report = 0
        self.finished_loading_initial_positions = (
            threading.Event()
        )  # Used to prevent the calculator from terminating while we are waiting for initial data if it starts after-the-fact.
        post_slack_message(
            str(self.contestant.navigation_task),
            f"Calculator started for {self.contestant} in navigation task <https://airsports.no{self.contestant.navigation_task.tracking_link}|{self.contestant.navigation_task}>",
        )
        logger.debug(f"{self.contestant}: Starting calculators")
        for calculator in calculators:
            self.calculators.append(
                calculator(
                    self.contestant,
                    self.scorecard,
                    self.gates,
                    self.contestant.navigation_task.route,
                    self.update_score,
                )
            )
        self.websocket_facade.transmit_delete_contestant(self.contestant)
        self.websocket_facade.transmit_contestant(self.contestant)
        threading.Thread(target=self.score_updater_thread, daemon=True).start()

    def score_updater_thread(self):
        """
        Thread function used to provide asynchronous update of scores. Updating the score may take some time and this
        will lead to a noticeable glitch in the calculator performance/tracking in the tracking map. Running this in a
        separate thread avoids this.
        """
        while True:
            score = self.score_processing_queue.get(True)
            logger.debug(f"Found score to be logged {score}")
            self.update_score_from_thread(*score)
            logger.debug(f"Finished logging score")
            self.score_processing_queue.task_done()

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

    def interpolate_track(self, last_position: Optional[Position], position: Position) -> List[Position]:
        """
        If last_position is provided, perform a linear interpolation for each second with missing position data between
        the time of last_position and position. Return the resulting list of positions.
        """
        if last_position is None:
            return [position]
        initial_time = last_position.time
        distance = calculate_distance_lat_lon(
            (last_position.latitude, last_position.longitude), (position.latitude, position.longitude)
        )
        if distance < 0.001:
            return [position]
        time_difference = int((position.time - initial_time).total_seconds())
        positions = []
        if time_difference > 2:
            fraction = 1 / time_difference
            for step in range(1, time_difference):
                new_position = calculate_fractional_distance_point_lat_lon(
                    (last_position.latitude, last_position.longitude),
                    (position.latitude, position.longitude),
                    step * fraction,
                )
                positions.append(
                    Position(
                        (initial_time + datetime.timedelta(seconds=step)),
                        new_position[0],
                        new_position[1],
                        position.altitude,
                        position.speed,
                        position.course,
                        position.battery_level,
                        0,
                        0,
                        interpolated=True,
                        calculator_received_time=datetime.datetime.now(datetime.timezone.utc),
                    )
                )
        positions.append(position)
        return positions

    def check_for_buffered_data_if_necessary(self, position_data: Dict) -> List[Dict]:
        """
        If there has been some time since the last position report before this is greater than
        CHECK_BUFFERED_DATA_TIME_LIMIT, check the traccar service to see if any data is available for the missing time
        interval and return this together with the last position.
        """
        if self.latest_position_report is None:
            latest_position_time = self.contestant.tracker_start_time
        else:
            latest_position_time = self.latest_position_report
        current_time = position_data["device_time"]
        time_difference = (current_time - latest_position_time).total_seconds()
        if time_difference > CHECK_BUFFERED_DATA_TIME_LIMIT:
            # Get positions in between
            positions = self.traccar.get_positions_for_device_id(
                position_data["deviceId"],
                latest_position_time + datetime.timedelta(seconds=1),
                current_time - datetime.timedelta(seconds=1),
            )
            for item in positions:
                item["device_time"] = dateutil.parser.parse(item["deviceTime"])
                item["server_time"] = dateutil.parser.parse(item["serverTime"])
                item["calculator_received_time"] = datetime.datetime.now(datetime.timezone.utc)

            if len(positions) > 0:
                logger.debug(
                    f"{self.contestant}:  Retrieved {len(positions)} additional positions for the interval {positions[0]['device_time'].strftime('%H:%M:%S')} - {positions[-1]['device_time'].strftime('%H:%M:%S')}"
                )
            return positions + [position_data]
        return [position_data]

    def enqueue_positions_thread(self):
        """
        Thread function which enqueues incoming positions in a timed queue. The time queue is used to delay the
        calculation by a user configurable duration. The time the queue is read by the main run function in the class.
        """
        logger.info(
            f"{self.contestant}: Starting delayed position queuer with {self.position_queue.size} waiting messages. Track terminated is {self.track_terminated}"
        )
        device_ids = self.traccar.get_device_ids_for_contestant(self.contestant)
        current_time = datetime.datetime.now(datetime.timezone.utc)
        device_positions = {}
        if self.live_processing:
            # Fetch any earlier positions for the contestant to ensure that we start from the beginning.
            for device_id in device_ids:
                positions = self.traccar.get_positions_for_device_id(
                    device_id, self.contestant.tracker_start_time, current_time
                )
                for item in positions:
                    item["device_time"] = dateutil.parser.parse(item["deviceTime"])
                    item["server_time"] = dateutil.parser.parse(item["serverTime"])
                    item["calculator_received_time"] = datetime.datetime.now(datetime.timezone.utc)
                device_positions[device_id] = positions
            try:
                # Select the longest track
                positions_to_use = sorted(device_positions.values(), key=lambda k: len(k), reverse=True)[0]
                logger.info(
                    f"{self.contestant}: Fetched {len(positions_to_use)} historic positions at start of calculator"
                )
                for position in positions_to_use:
                    self.timed_queue.put(position, datetime.datetime.now(datetime.timezone.utc))
            except IndexError:
                pass
        receiving = False
        while not self.track_terminated:
            try:
                position_data = self.position_queue.pop(True, timeout=30)
                if position_data is not None:
                    release_time = position_data["device_time"] + datetime.timedelta(
                        minutes=self.contestant.navigation_task.calculation_delay_minutes
                    )
                    if not receiving:
                        logger.info(f"{self.contestant}: Started receiving data")
                else:
                    logger.info(f"{self.contestant}: Delayed position queuer received None")
                    release_time = datetime.datetime.now(datetime.timezone.utc)
                self.timed_queue.put(position_data, release_time)
                if not receiving:
                    self.finished_loading_initial_positions.set()
                    receiving = True
            except RedisEmpty:
                self.check_termination()

    def refresh_scores(self):
        """
        Push all score information to the front end. This needs to be done at regular intervals in case the front end
        loses connectivity with the Web server.
        """
        self.websocket_facade.transmit_score_log_entry(self.contestant)
        self.websocket_facade.transmit_annotations(self.contestant)
        self.websocket_facade.transmit_basic_information(self.contestant)

    def run(self):
        """
        The main run function of the gatekeeper. This method reads incoming positions that have been optionally delayed
        by the timed queue, interpolates any missing positions, calculates the score given the new position data, and
        pushes the updated positions to the front end. The function terminates when self.track_terminated == True.
        """
        calculator_is_alive(self.contestant.pk, 30)
        logger.info(
            "Started gatekeeper for contestant {} {}-{}".format(
                self.contestant, self.contestant.takeoff_time, self.contestant.finished_by_time
            )
        )
        threading.Thread(target=self.enqueue_positions_thread, daemon=True).start()
        receiving = False
        number_of_positions = 0
        # Wait while the thread loads outstanding positions.
        self.finished_loading_initial_positions.wait()
        while not self.track_terminated:
            calculator_is_alive(self.contestant.pk, 30)
            now = datetime.datetime.now(datetime.timezone.utc)
            if self.live_processing and now > self.contestant.finished_by_time:
                data = self.timed_queue.peek()
                if data is None or data["device_time"] > now:
                    self.notify_termination()
                    break
            if now - self.last_contestant_refresh > CONTESTANT_REFRESH_INTERVAL:
                self.refresh_scores()
                try:
                    self.contestant.refresh_from_db()
                except ObjectDoesNotExist:
                    # Contestants has been deleted, terminate the calculator
                    logger.info(f"{self.contestant} has been deleted, terminating")
                    self.track_terminated = True
                    break
                self.last_contestant_refresh = now
            try:
                position_data = self.timed_queue.get(timeout=15)
            except TimedOut:
                # We have not received anything for 60 seconds, check if we should terminate
                self.check_termination()
                continue
            if position_data is None:
                # Signal the track processor that this is the end, and perform the track calculation
                logger.debug(f"End of position list after {number_of_positions} positions")
                self.notify_termination()
                continue
            if not receiving:
                logger.info(f"{self.contestant}: Started processing data")
                receiving = True
            # logger.debug(f"Processing position ID {position_data['id']} for device ID {position_data['deviceId']}")
            position_data["calculator_received_time"] = datetime.datetime.now(datetime.timezone.utc)
            number_of_positions += 1
            if self.live_processing:
                buffered_positions = self.check_for_buffered_data_if_necessary(position_data)
            else:
                buffered_positions = [position_data]
            all_positions = []
            generated_positions = []
            for buffered_position in buffered_positions:
                data = self.contestant.generate_position_block_for_contestant(
                    buffered_position, buffered_position["device_time"]
                )

                p = Position(**data)
                if self.latest_position_report is None:
                    self.latest_position_report = p.time
                else:
                    self.latest_position_report = max(self.latest_position_report, p.time)
                if len(self.track) > 0 and (
                    (p.latitude == self.track[-1].latitude and p.longitude == self.track[-1].longitude)
                    or self.track[-1].time >= p.time
                ):
                    # Old or duplicate position, ignoring
                    continue
                last_position = generated_positions[-1] if len(generated_positions) > 0 else None
                all_positions.append(p)
                for position in self.interpolate_track(last_position, p):
                    generated_positions.append(
                        ContestantReceivedPosition(
                            contestant=self.contestant,
                            time=position.time,
                            latitude=position.latitude,
                            longitude=position.longitude,
                            course=position.course,
                            speed=position.speed,
                            altitude=position.altitude,
                            processor_received_time=p.processor_received_time,
                            calculator_received_time=p.calculator_received_time,
                            websocket_transmitted_time=datetime.datetime.now(datetime.timezone.utc),
                            server_time=p.server_time,
                            interpolated=position.interpolated,
                        )
                    )
            ContestantReceivedPosition.objects.bulk_create(generated_positions)
            for position in all_positions:
                calculator_is_alive(self.contestant.pk, 30)
                self.track.append(position)
                if len(self.track) > 1:
                    self.calculate_score()

            self.websocket_facade.transmit_navigation_task_position_data(self.contestant, all_positions)
            self.check_termination()
        self.contestant_track.set_calculator_finished()
        while not self.position_queue.empty():
            self.position_queue.pop()
        self.score_processing_queue.join()
        logger.info("Terminating calculator for {}".format(self.contestant))
        calculator_is_terminated(self.contestant.pk)

    def update_score(
        self,
        gate: "Gate",
        score: float,
        message: str,
        latitude: float,
        longitude: float,
        annotation_type: str,
        score_type: str,
        maximum_score: Optional[float] = None,
        planned: Optional[datetime.datetime] = None,
        actual: Optional[datetime.datetime] = None,
    ) -> Tuple[int, int, float]:
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
        logger.debug(f"Received score to log: {message}")
        self.score_processing_queue.put(
            (gate, score, message, latitude, longitude, annotation_type, score_type, maximum_score, planned, actual)
        )

    def update_score_from_thread(
        self,
        gate: "Gate",
        score: float,
        message: str,
        latitude: float,
        longitude: float,
        annotation_type: str,
        score_type: str,
        maximum_score: Optional[float] = None,
        planned: Optional[datetime.datetime] = None,
        actual: Optional[datetime.datetime] = None,
    ):
        """
        Constructs the score structures required to update the contestants score. Optionally cap the score if it has a
        maximum value.
        """
        score, capped = self.accumulated_scores.set_and_update_score(score, score_type, maximum_score, 0)
        if planned is not None and actual is not None:
            offset = (actual - planned).total_seconds()
            # Must use round, this is the same as used in the score calculation
            offset_string = "{} s".format("+{}".format(round(offset)) if offset > 0 else round(offset))
        else:
            offset_string = ""
        if capped:
            message += " (capped)"
        planned_time = (
            planned.astimezone(self.contestant.navigation_task.contest.time_zone).strftime("%H:%M:%S")
            if planned
            else None
        )
        actual_time = (
            actual.astimezone(self.contestant.navigation_task.contest.time_zone).strftime("%H:%M:%S")
            if actual
            else None
        )
        string = "{}: {} points {}".format(gate.name, score, message)
        if offset_string:
            string += " ({})".format(offset_string)
        times_string = ""
        if planned and actual:
            times_string = "planned: {}\nactual: {}".format(planned_time, actual_time)
        elif planned:
            times_string = "planned: {}\nactual: --".format(planned_time)
        if len(times_string) > 0:
            string += f"\n{times_string}"
        logger.info("UPDATE_SCORE {}: {}{}".format(self.contestant, "", string))
        # Take into account that external events may have changed the score
        self.contestant_track.refresh_from_db()
        self.contestant.record_score_by_gate(gate.name, score)
        self.score = self.contestant_track.score
        logger.debug(f"Setting existing scores from contestant track: {self.score}")
        self.score += score
        entry = ScoreLogEntry.create_and_push(
            contestant=self.contestant,
            time=self.track[-1].time if len(self.track) > 0 else self.contestant.navigation_task.start_time,
            gate=gate.name,
            type=annotation_type,
            message=message,
            points=score,
            planned=planned,
            actual=actual,
            offset_string=offset_string,
            string=string,
            times_string=times_string,
        )
        TrackAnnotation.create_and_push(
            contestant=self.contestant,
            latitude=latitude,
            longitude=longitude,
            message=string,
            type=annotation_type,
            gate=gate.name,
            gate_type=gate.type,
            time=self.track[-1].time if len(self.track) > 0 else self.contestant.navigation_task.start_time,
            score_log_entry=entry,
        )
        if score != 0:
            self.contestant_track.update_score(self.score)

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
                gates.append(Gate(item, expected_times[item.name], calculate_extended_gate(item, self.scorecard)))
        return gates

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

    def update_enroute(self):
        """
        Update the current state to reflect whether the contestant is currently en route between a start and finish
        point or not.
        """
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
            self.contestant_track.set_passed_finish_gate()
            self.has_passed_finishpoint = True
            for calculator in self.calculators:
                calculator.passed_finishpoint(self.track, self.last_gate)

    def notify_termination(self):
        """
        Trigger termination of the run function.
        """
        logger.info(f"{self.contestant}: Setting termination flag")
        self.contestant_track.set_calculator_finished()
        self.track_terminated = True

    def check_termination(self):
        """
        Checks if termination has been manually triggered. If it has been triggered, create a score log entry to
        reflect this and notify termination.
        """
        if not self.track_terminated and self.is_termination_commanded():
            self.update_score(
                self.last_gate or self.gates[0],
                0,
                "manually terminated",
                self.track[-1].latitude if len(self.track) > 0 else self.gates[0].latitude,
                self.track[-1].longitude if len(self.track) > 0 else self.gates[0].longitude,
                "information",
                "",
            )
            self.notify_termination()

    def is_termination_commanded(self) -> bool:
        """
        Return true if manual termination has been requested.
        """
        termination_requested = is_termination_requested(self.contestant.pk)
        if termination_requested:
            logger.info(f"{self.contestant}: Termination request received")
            return True
        return False

    @abstractmethod
    def check_gates(self):
        raise NotImplementedError

    def missed_gate(self, previous_gate: Optional[Gate], gate: Gate, position: Position):
        """
        Called the missed_gate event in all calculators.
        """
        for calculator in self.calculators:
            calculator.missed_gate(previous_gate, gate, position)

    def calculate_score(self):
        """
        Calculate the score. Is called once for every received (or interpolated) position.
        """
        if self.track_terminated:
            return
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

    def get_speed(self):
        """
        Calculate the speed of the contestant based on the past few positions.
        """
        previous_index = min(5, len(self.track))
        distance = distance_between_gates(self.track[-previous_index], self.track[-1]) / 1852
        time_difference = (self.track[-1].time - self.track[-previous_index].time).total_seconds() / 3600
        if time_difference == 0:
            time_difference = 0.01
        return distance / time_difference
