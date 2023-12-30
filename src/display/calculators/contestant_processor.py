import datetime
import logging
import threading
from abc import ABC
from queue import Queue
from typing import List, Optional, Tuple, Dict

from dateutil import parser
from django.core.exceptions import ObjectDoesNotExist

from display.calculators.calculator_factory import calculator_factory
from display.calculators.update_score_message import UpdateScoreMessage
from display.utilities.calculator_running_utilities import calculator_is_alive, calculator_is_terminated
from display.utilities.calculator_termination_utilities import is_termination_requested
from redis_queue import RedisQueue, RedisEmpty
from slack_facade import post_slack_message
from utilities.timed_queue import TimedQueue, TimedOut
from websocket_channels import WebsocketFacade

from display.utilities.traccar_factory import get_traccar_instance

from display.calculators.positions_and_gates import Position
from display.utilities.coordinate_utilities import (
    calculate_distance_lat_lon,
    calculate_fractional_distance_point_lat_lon,
)
from display.models import Contestant, TrackAnnotation, ScoreLogEntry, ContestantReceivedPosition

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
        Returns the calculated score given the maximum limits for the score type. If there is no maximum limit, score
        is returned. The second return parameter indicates whether the score has been capped to a maximum value or not.
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


class ContestantProcessor:
    """
    The ContestantProcessor is the main class for tracking contestants during flight. It is responsible for processing positions
    received from the Traccar service, interpolating missing positions on the track, and storing these to the database.
    It provides methods for updating the contestants score. It instantiates a Gatekeeper which is responsible for
    scoring the contestants track.
    """

    def __init__(
        self,
        contestant: "Contestant",
        live_processing: bool = True,
        queue_name_override: str = None,
    ):
        calculator_is_alive(contestant.pk, 30)
        super().__init__()
        logger.info(f"{contestant}: Created contestant processor")
        self.contestant = contestant
        self.live_processing = live_processing

        self.position_queue = RedisQueue(queue_name_override or str(contestant.pk))
        self.traccar = get_traccar_instance()
        self.previous_position = None
        self.track_terminated = False
        self.contestant_track = contestant.contestanttrack
        self.last_contestant_refresh = datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)
        self.score_processing_queue = Queue()
        self.last_termination_command_check = None
        self.score = 0
        self.process_event = threading.Event()
        self.contestant.reset_track_and_score()
        self.contestant.contestantreceivedposition_set.all().delete()
        self.contestant_track.set_calculator_started()
        self.scorecard = self.contestant.navigation_task.scorecard
        self.position_update_lock = threading.Lock()
        self.accumulated_scores = ScoreAccumulator()
        self.websocket_facade = WebsocketFacade()
        self.timed_queue = TimedQueue()
        self.finished_loading_initial_positions = (
            threading.Event()
        )  # Used to prevent the calculator from terminating while we are waiting for initial data if it starts after-the-fact.
        post_slack_message(
            str(self.contestant.navigation_task),
            f"Calculator started for {self.contestant} in navigation task <https://airsports.no{self.contestant.navigation_task.tracking_link}|{self.contestant.navigation_task}>",
        )
        self.websocket_facade.transmit_delete_contestant(self.contestant)
        self.websocket_facade.transmit_contestant(self.contestant)
        threading.Thread(target=self.score_updater_thread, daemon=True).start()
        self.gatekeeper = calculator_factory(self.contestant, self.score_processing_queue)

    def score_updater_thread(self):
        """
        Thread function used to provide asynchronous update of scores. Updating the score may take some time and this
        will lead to a noticeable glitch in the calculator performance/tracking in the tracking map. Running this in a
        separate thread avoids this.
        """
        while True:
            score = self.score_processing_queue.get(True)
            self.update_score_from_thread(score)
            self.score_processing_queue.task_done()

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
        if self.previous_position is None:
            latest_position_time = self.contestant.tracker_start_time
        else:
            latest_position_time = self.previous_position.time
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
                item["device_time"] = parser.parse(item["deviceTime"])
                item["server_time"] = parser.parse(item["serverTime"])
                item["calculator_received_time"] = datetime.datetime.now(datetime.timezone.utc)

            if len(positions) > 0:
                logger.debug(
                    f"{self.contestant}:  Retrieved {len(positions)} additional positions for the interval {positions[0]['device_time'].strftime('%H:%M:%S')} - {positions[-1]['device_time'].strftime('%H:%M:%S')}"
                )
            return positions + [position_data]
        return [position_data]

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
                self.check_termination_is_commanded(self.previous_position)
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
                positions_to_process = self.check_for_buffered_data_if_necessary(position_data)
            else:
                positions_to_process = [position_data]
            all_positions = []
            generated_positions = []
            for position_to_process in positions_to_process:
                data = self.contestant.generate_position_block_for_contestant(
                    position_to_process, position_to_process["device_time"]
                )

                p = Position(**data)
                if self.previous_position and (
                    (p.latitude == self.previous_position.latitude and p.longitude == self.previous_position.longitude)
                    or self.previous_position.time >= p.time
                ):
                    # Old or duplicate position, ignoring
                    continue
                all_positions.append(p)
                for position in self.interpolate_track(self.previous_position, p):
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
                self.previous_position = p
            ContestantReceivedPosition.objects.bulk_create(generated_positions)
            for position in all_positions:
                calculator_is_alive(self.contestant.pk, 30)
                self.gatekeeper.calculate_score(position)

            self.websocket_facade.transmit_navigation_task_position_data(self.contestant, all_positions)
            self.should_i_terminate()
            self.check_termination_is_commanded(self.previous_position)
        self.gatekeeper.finished_processing()
        self.contestant_track.set_calculator_finished()
        while not self.position_queue.empty():
            self.position_queue.pop()
        self.score_processing_queue.join()
        logger.info("Terminating calculator for {}".format(self.contestant))
        calculator_is_terminated(self.contestant.pk)

    def should_i_terminate(self):
        """
        Check if the time has passed the finished by time and terminate the  processor if this is the case
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        if self.live_processing and now > self.contestant.finished_by_time:
            if not self.track_terminated:
                self.notify_termination()

    def notify_termination(self):
        """
        Trigger termination of the run function.
        """
        logger.info(f"{self.contestant}: Setting termination flag")
        self.contestant_track.set_calculator_finished()
        self.track_terminated = True

    def check_termination_is_commanded(self, position: Optional[Position]):
        """
        Checks if termination has been manually triggered. If it has been triggered, create a score log entry to
        reflect this and notify termination.
        """
        if not self.track_terminated and self.is_termination_commanded():
            last_gate = self.gatekeeper.get_last_gate()
            self.score_processing_queue.put_nowait(
                UpdateScoreMessage(
                    position.time if position else self.contestant.navigation_task.start_time,
                    last_gate,
                    0,
                    "manually terminated",
                    position.latitude if position else last_gate.latitude,
                    position.longitude if position else last_gate.longitude,
                    "information",
                    "",
                )
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
                    item["device_time"] = parser.parse(item["deviceTime"])
                    item["server_time"] = parser.parse(item["serverTime"])
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
                self.check_termination_is_commanded(self.previous_position)

    def update_score_from_thread(self, update_score_message: UpdateScoreMessage):
        """
        Constructs the score structures required to update the contestants score. Optionally cap the score if it has a
        maximum value.
        """
        score, capped = self.accumulated_scores.set_and_update_score(
            update_score_message.score, update_score_message.score_type, update_score_message.maximum_score, 0
        )
        if update_score_message.planned is not None and update_score_message.actual is not None:
            offset = (update_score_message.actual - update_score_message.planned).total_seconds()
            # Must use round, this is the same as used in the score calculation
            offset_string = "{} s".format("+{}".format(round(offset)) if offset > 0 else round(offset))
        else:
            offset_string = ""
        if capped:
            update_score_message.message += " (capped)"
        planned_time = (
            update_score_message.planned.astimezone(self.contestant.navigation_task.contest.time_zone).strftime(
                "%H:%M:%S"
            )
            if update_score_message.planned
            else None
        )
        actual_time = (
            update_score_message.actual.astimezone(self.contestant.navigation_task.contest.time_zone).strftime(
                "%H:%M:%S"
            )
            if update_score_message.actual
            else None
        )
        string = "{}: {} points {}".format(update_score_message.gate.name, score, update_score_message.message)
        if offset_string:
            string += " ({})".format(offset_string)
        times_string = ""
        if update_score_message.planned and update_score_message.actual:
            times_string = "planned: {}\nactual: {}".format(planned_time, actual_time)
        elif update_score_message.planned:
            times_string = "planned: {}\nactual: --".format(planned_time)
        if len(times_string) > 0:
            string += f"\n{times_string}"
        logger.info("UPDATE_SCORE {}: {}{}".format(self.contestant, "", string))
        # Take into account that external events may have changed the score
        self.contestant_track.refresh_from_db()
        self.contestant.record_score_by_gate(update_score_message.gate.name, score)
        self.score = self.contestant_track.score
        logger.debug(f"Setting existing scores from contestant track: {self.score}")
        self.score += score
        entry = ScoreLogEntry.create_and_push(
            contestant=self.contestant,
            time=update_score_message.time,
            gate=update_score_message.gate.name,
            type=update_score_message.annotation_type,
            message=update_score_message.message,
            points=score,
            planned=update_score_message.planned,
            actual=update_score_message.actual,
            offset_string=offset_string,
            string=string,
            times_string=times_string,
        )
        TrackAnnotation.create_and_push(
            contestant=self.contestant,
            latitude=update_score_message.latitude,
            longitude=update_score_message.longitude,
            message=string,
            type=update_score_message.annotation_type,
            gate=update_score_message.gate.name,
            gate_type=update_score_message.gate.type,
            time=update_score_message.time,
            score_log_entry=entry,
        )
        if score != 0:
            self.contestant_track.update_score(self.score)
