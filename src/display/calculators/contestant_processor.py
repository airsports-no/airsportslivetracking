import datetime
import logging
import redis
import threading
import time
import traceback
from queue import Queue
from typing import List, Optional, Tuple, Dict

from django.core.exceptions import ObjectDoesNotExist
from django.db.utils import IntegrityError

from display.calculators.calculator_factory import calculator_factory
from display.calculators.cima_score_normalization import get_cima_gate_qmax
from display.calculators.gate_calculator import GATE_SCORE_TYPE
from display.calculators.update_score_message import UpdateScoreMessage
from display.models.contestant_track import ContestantTrack
from display.utilities.calculator_running_utilities import calculator_is_alive, calculator_is_terminated
from display.utilities.calculator_termination_utilities import is_termination_requested
from display.utilities.tracking_definitions import TrackingService
from redis_queue import RedisQueue, RedisEmpty
from slack_facade import post_slack_competition_message
from traccar_facade import augment_positions_from_traccar
from utilities.timed_queue import TimedQueue, TimedOut
from websocket_channels import WebsocketFacade
from django.db.models import F

from display.utilities.traccar_factory import get_traccar_instance

from display.utilities.coordinate_utilities import (
    Projector,
    calculate_bearing,
    calculate_distance_lat_lon,
)
from display.models import Contestant, TrackAnnotation, ScoreLogEntry, ContestantReceivedPosition

DANGER_LEVEL_REPORT_INTERVAL = 5
CHECK_BUFFERED_DATA_TIME_LIMIT = 6
# Poll interval while waiting for enqueue_positions_thread's (unbounded) initial Traccar history
# fetch to finish, so the "running" heartbeat gets refreshed instead of expiring on a slow fetch.
INITIAL_POSITION_LOAD_HEARTBEAT_POLL_SECONDS = 15
# Minimum horizontal distance (metres) between two positions before we trust a
# track-derived bearing. Below this, GPS jitter dominates and the bearing is
# unreliable, so we leave the heading at 0 rather than emitting noise.
MIN_DISTANCE_FOR_BEARING_M = 5.0
logger = logging.getLogger(__name__)


class ScoreAccumulator:
    """
    A score accumulator keeps track of scores that have a maximum limit.
    """

    def __init__(self):
        self.related_score = {}

    def set_and_update_score(self, score: float, score_type: str, maximum_score: Optional[float]) -> Tuple[float, bool]:
        """
        Returns the calculated score given the maximum limits for the score type. If there is no maximum limit, score
        is returned. The second return parameter indicates whether the score has been capped to a maximum value or not.
        """
        capped = False
        current_score_for_type = self.related_score.setdefault(score_type, 0)
        if maximum_score is not None:
            if (maximum_score > 0 and current_score_for_type + score >= maximum_score) or (
                maximum_score < 0 and current_score_for_type + score <= maximum_score
            ):
                score = maximum_score - current_score_for_type
                capped = True
        self.related_score[score_type] += score
        return score, capped


LOOP_TIME = 60
CONTESTANT_REFRESH_INTERVAL = datetime.timedelta(seconds=15)
# Upper bound on how stale ContestantReceivedPosition can get relative to what has
# already been broadcast over the websocket. Without this, positions only get
# bulk_created once positions_to_save exceeds 100 entries, which at typical ~1Hz
# reporting is ~100s of already-live-transmitted track that a REST client (e.g. a
# browser tab backgrounded and then resumed) cannot yet backfill via the /slice/
# endpoint, even though continuously-connected clients already have it via the
# websocket push.
POSITION_SAVE_INTERVAL = datetime.timedelta(seconds=10)


class ContestantProcessor:
    """
    The ContestantProcessor is the main class for tracking contestants during flight. It is responsible for processing positions
    received from the Traccar service, interpolating missing positions on the track, and storing these to the database.
    It provides methods for updating the contestants score. It instantiates an Orchestrator which is responsible for
    scoring the contestants track.
    """

    def __init__(
        self,
        contestant: "Contestant",
        live_processing: bool = True,
        queue_name_override: str | None = None,
        recalculate: bool = False,
    ):
        calculator_is_alive(contestant.pk, 30)
        super().__init__()
        logger.info(f"{contestant}: Created contestant processor (recalculate={recalculate})")
        self.contestant = contestant
        self.contestant.live_processing = live_processing
        self.live_processing = live_processing

        self.position_queue = RedisQueue(queue_name_override or str(contestant.pk))
        self.traccar = get_traccar_instance()
        self.previous_position = None
        self.track_terminated = False
        self.contestant_track: ContestantTrack = contestant.contestanttrack

        # Idempotent restart logic: Only reset if there is no existing data or recalculate is requested.
        # If data exists, we are likely a pod restart and should catch up silently.
        existing_positions = self.contestant.contestantreceivedposition_set.all().order_by("time")
        if existing_positions.exists() and not recalculate:
            logger.info(f"{self.contestant}: Existing positions found, performing idempotent restart")
            self.latest_recorded_time = existing_positions.last().time
            self.contestant_track.refresh_from_db()
            # We don't reset the track_version or delete positions here
        else:
            if recalculate:
                logger.info(f"{self.contestant}: Recalculate requested, performing clean start")
            else:
                logger.info(f"{self.contestant}: No existing positions, performing clean start")
            self.latest_recorded_time = datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)
            # reset_track_and_score now also deletes positions and increments track_version
            self.contestant.reset_track_and_score()

        self.suppress_side_effects = False # Will be toggled in run()
        
        # We always start local scoring from the initial score because we replay the full track 
        # from the beginning (tracker_start_time). During catch-up (latest_recorded_time > min), 
        # suppress_side_effects ensures we don't double-count in the database.
        self.score = self.contestant.navigation_task.scorecard.initial_score

        self.last_contestant_refresh = datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)
        self.score_processing_queue = Queue()
        self.last_termination_check = datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)
        self.termination_requested_cached = None
        self.process_event = threading.Event()
        
        self.contestant_track.set_calculator_started()
        self.scorecard = self.contestant.navigation_task.scorecard
        self.scorecard.refresh_from_db()
        self.time_zone = self.contestant.navigation_task.contest.time_zone
        self.gate_scores = {}  # Cache for GateCumulativeScore objects
        self.position_update_lock = threading.Lock()
        self.accumulated_scores = ScoreAccumulator()
        self.websocket_facade = WebsocketFacade()
        self.timed_queue = TimedQueue()
        self.projector = self.contestant.navigation_task.get_projector()
        self.delay = datetime.timedelta(minutes=self.contestant.navigation_task.calculation_delay_minutes)
        self.consecutive_low_speed_positions = 0
        self.finished_loading_initial_positions = (
            threading.Event()
        )  # Used to prevent the calculator from terminating while we are waiting for initial data if it starts after-the-fact.

        if self.latest_recorded_time == datetime.datetime.min.replace(tzinfo=datetime.timezone.utc):
            post_slack_competition_message(
                str(self.contestant.navigation_task),
                f"{'Live' if self.live_processing else 'Batch'} calculator started for {self.contestant} in navigation task <https://app.airsports.no{self.contestant.navigation_task.tracking_link}|{self.contestant.navigation_task}>",
            )
            self.websocket_facade.transmit_delete_contestant(self.contestant)
            self.websocket_facade.transmit_contestant(self.contestant)

        self.score_thread = threading.Thread(target=self.score_updater_thread, daemon=True)
        self.score_thread.start()
        self.orchestrator = calculator_factory(
            self.contestant,
            self.score_processing_queue,
            live_processing=self.live_processing,
            projector=self.projector,
        )

    def score_updater_thread(self):
        from queue import Empty

        while True:
            try:
                score = self.score_processing_queue.get(timeout=1)
                if score is None:
                    self.score_processing_queue.task_done()
                    break
                try:
                    self.update_score_from_thread(score)
                except Exception:
                    logger.exception("Failed processing score message in thread")
                finally:
                    self.score_processing_queue.task_done()
            except Empty:
                continue
        logger.info(f"{self.contestant}: score_updater_thread exiting")

    def fill_in_missing_course(
        self,
        last_position: Optional[ContestantReceivedPosition],
        position: ContestantReceivedPosition,
    ) -> None:
        """
        Some upstream tracking sources do not populate the course/heading field, in
        which case ``generate_position_block_for_contestant`` defaults it to 0. A
        constant 0 heading makes every aircraft on the live map point north, which
        is misleading. When we have a previous position available (the calculator,
        unlike the position processor, has the track) we can derive the heading
        from the great-circle bearing between the two points.

        We only fill in the course when:

        * the incoming course is exactly 0 (we trust any non-zero value already
          provided by the tracker — including legitimate due-north headings, which
          we accept as a reasonable trade-off), and
        * a previous position exists.

        When the horizontal distance between the two positions is below
        ``MIN_DISTANCE_FOR_BEARING_M`` metres, GPS jitter dominates and the
        derived bearing would be unreliable. In that case we fall back to the
        previous position's course (whether tracker-provided or itself derived
        from the track on an earlier step) so that a near-stationary aircraft
        keeps its last known heading rather than snapping back to north. If the
        previous course is also 0 we have nothing better to use and leave the
        heading at 0.
        """
        if position.course != 0:
            return
        if last_position is None:
            return
        start = (last_position.latitude, last_position.longitude)
        finish = (position.latitude, position.longitude)
        if calculate_distance_lat_lon(start, finish) < MIN_DISTANCE_FOR_BEARING_M:
            if last_position.course != 0:
                position.course = last_position.course
            return
        position.course = calculate_bearing(start, finish)

    def interpolate_track(
        self, last_position: Optional[ContestantReceivedPosition], position: ContestantReceivedPosition
    ) -> List[ContestantReceivedPosition]:
        """
        If last_position is provided, perform a linear interpolation for each second with missing position data between
        the time of last_position and position. Return the resulting list of positions.
        """
        if last_position is None:
            return [position]
        initial_time = last_position.time

        time_difference = int((position.time - initial_time).total_seconds())
        positions = []
        if time_difference > 1.2:
            fraction = 1 / time_difference
            for step in range(1, time_difference):
                new_position = self.projector.fractional_point_on_line(
                    (last_position.latitude, last_position.longitude),
                    (position.latitude, position.longitude),
                    step * fraction,
                )
                p = ContestantReceivedPosition(
                    contestant=position.contestant,
                    time=initial_time + datetime.timedelta(seconds=step),
                    latitude=new_position[0],
                    longitude=new_position[1],
                    altitude=position.altitude,
                    speed=position.speed,
                    course=position.course,
                    battery_level=position.battery_level,
                    interpolated=True,
                    calculator_received_time=datetime.datetime.now(datetime.timezone.utc),
                )
                # Pre-project interpolated position
                p_obj = self.projector.project_point(p.latitude, p.longitude)
                p.projected_x = p_obj.projected_x
                p.projected_y = p_obj.projected_y
                positions.append(p)
        positions.append(position)
        return positions

    def check_for_buffered_data_if_necessary(self, position_data: Dict) -> List[Dict]:
        """
        If there has been some time since the last position report before this is greater than
        CHECK_BUFFERED_DATA_TIME_LIMIT, check the traccar service to see if any data is available for the missing time
        interval and return this together with the last position.
        """
        if self.previous_position is None or self.contestant.tracking_service != TrackingService.TRACCAR:
            # If there is no previous data we are at the beginning, which means that we have already fetched whatever
            # is missing before this in the enqueue positions thread.
            return [position_data]
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
            augment_positions_from_traccar(positions)

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
        try:
            self.contestant.refresh_from_db()
            self.contestant_track.refresh_from_db()
            # Synchronize local score state with database to account for manual manager adjustments
            self.score = self.contestant_track.score
        except ObjectDoesNotExist:
            logger.info(f"{self.contestant}: Object deleted during refresh, terminating")
            self.track_terminated = True
            return

        self.websocket_facade.transmit_score_log_entry(self.contestant)
        self.websocket_facade.transmit_annotations(self.contestant)
        self.websocket_facade.transmit_basic_information(self.contestant)

    def save_positions(self, positions: List[ContestantReceivedPosition]):
        """
        Bulk-inserts positions, terminating the calculator instead of raising if the contestant
        was deleted since these positions were computed. self.contestant is only refreshed every
        CONTESTANT_REFRESH_INTERVAL, so a deletion can otherwise go undetected until an insert
        referencing the now-missing contestant_id hits an IntegrityError (see GH #707).
        """
        try:
            ContestantReceivedPosition.objects.bulk_create(positions)
        except IntegrityError:
            logger.info(f"{self.contestant}: Contestant deleted during position save, terminating")
            self.track_terminated = True

    def run(self):
        """
        The main run function of the orchestrator. This method reads incoming positions that have been optionally delayed
        by the timed queue, interpolates any missing positions, calculates the score given the new position data, and
        pushes the updated positions to the front end. The function terminates when self.track_terminated == True.
        """
        calculator_is_alive(self.contestant.pk, 30)
        logger.info(
            "Started orchestrator for contestant {} {}-{}".format(
                self.contestant, self.contestant.takeoff_time, self.contestant.finished_by_time
            )
        )
        # Check if termination is already requested
        if self.is_termination_commanded():
            logger.info(f"{self.contestant}: Termination request received before processing started")
            self.notify_termination("Termination requested before processing started")
            return
        self.queuer_thread = threading.Thread(target=self.enqueue_positions_thread, daemon=True)
        self.queuer_thread.start()
        receiving = False
        number_of_positions = 0
        # Wait while the thread loads outstanding positions, refreshing the "running" heartbeat
        # periodically so a slow Traccar history fetch (unbounded, see enqueue_positions_thread)
        # doesn't outlast the heartbeat's 30s TTL. Without this, a fetch exceeding 30s expires the
        # key, is_calculator_running() reports False while this processor is still starting up, and
        # a broker redelivery (acks-late/visibility timeout, expected per run_live_contestant_calculator's
        # own docstring) spins up a second ContestantProcessor for the same contestant against the same
        # Redis queue, splitting positions between two divergent tracks (same failure class as the
        # shutdown-window race fixed for GH #29, just the other end of the run).
        while not self.finished_loading_initial_positions.wait(timeout=INITIAL_POSITION_LOAD_HEARTBEAT_POLL_SECONDS):
            calculator_is_alive(self.contestant.pk, 30)

        # Check for termination again after wait
        if self.is_termination_commanded():
            logger.info(f"{self.contestant}: Termination request received after initial positions wait")
            self.notify_termination("Termination requested after initial positions wait")
            return
        self.last_status_check = datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)
        positions_to_save = []
        last_position_flush = datetime.datetime.now(datetime.timezone.utc)
        while not self.track_terminated:
            # Only check for manual termination every 5 seconds or when waiting for data
            now = datetime.datetime.now(datetime.timezone.utc)
            if now - self.last_termination_check > datetime.timedelta(seconds=5):
                self.check_termination_is_commanded(self.previous_position)

            if self.track_terminated:
                break

            if now - self.last_status_check > datetime.timedelta(seconds=5):
                calculator_is_alive(self.contestant.pk, 30)
                self.should_i_terminate()
                self.last_status_check = now

            if now - self.last_contestant_refresh > CONTESTANT_REFRESH_INTERVAL:
                if not self.suppress_side_effects:
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
                # We have not received anything for some time, check if we should terminate
                self.check_termination_is_commanded(self.previous_position)
                continue
            if position_data is None:
                # Signal the track processor that this is the end, and perform the track calculation
                logger.debug(f"End of position list after {number_of_positions} positions")
                if positions_to_save:
                    self.save_positions(positions_to_save)
                    positions_to_save = []
                self.notify_termination("End of position list")
                continue

            if self.track_terminated:
                break

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
            for position_to_process in positions_to_process:
                p = self.contestant.generate_position_block_for_contestant(
                    position_to_process, position_to_process["device_time"]
                )

                if self.previous_position and (
                    (p.latitude == self.previous_position.latitude and p.longitude == self.previous_position.longitude)
                    or self.previous_position.time >= p.time
                ):
                    # Old or duplicate position, ignoring
                    # We still need to update the previous position to avoid fetching unnecessary data from traccar
                    if self.previous_position.time < p.time:
                        self.previous_position = p
                    continue

                # If the tracker did not report a heading (``course`` defaulted to 0
                # in generate_position_block_for_contestant), derive it from the
                # track. This avoids every map icon pointing north when the source
                # omits the field.
                self.fill_in_missing_course(self.previous_position, p)

                # Pre-project non-interpolated position
                p_obj = self.projector.project_point(p.latitude, p.longitude)
                p.projected_x = p_obj.projected_x
                p.projected_y = p_obj.projected_y

                for position in self.interpolate_track(self.previous_position, p):
                    position.websocket_transmitted_time = datetime.datetime.now(datetime.timezone.utc)
                    all_positions.append(position)
                self.previous_position = p

            for position in all_positions:
                # Toggle silent mode based on position time
                was_suppressing = self.suppress_side_effects
                self.suppress_side_effects = position.time <= self.latest_recorded_time
                
                if was_suppressing and not self.suppress_side_effects:
                    logger.info(f"{self.contestant}: Silent catch-up completed at {position.time}, resuming active scoring")

                self.orchestrator.calculate_score(position)
                if position.time > self.latest_recorded_time:
                    positions_to_save.append(position)

                # Proactive termination check based on speed
                if self.live_processing and self.orchestrator.has_any_gate_passed and not self.track_terminated:
                    if position.speed < 6:  # knots
                        self.consecutive_low_speed_positions += 1
                    else:
                        self.consecutive_low_speed_positions = 0

                    if self.consecutive_low_speed_positions >= 60:  # 1 minute at 1Hz
                        logger.info(
                            f"{self.contestant}: Inferred landing due to {self.consecutive_low_speed_positions} consecutive low speed positions. Terminating."
                        )
                        self.notify_termination(
                            f"Inferred landing due to {self.consecutive_low_speed_positions} consecutive low speed positions"
                        )
                        break

            if positions_to_save and (
                len(positions_to_save) > 100 or now - last_position_flush > POSITION_SAVE_INTERVAL
            ):
                self.save_positions(positions_to_save)
                positions_to_save = []
                last_position_flush = now

            if self.track_terminated:
                break

            if not self.suppress_side_effects:
                self.websocket_facade.transmit_navigation_task_position_data(self.contestant, all_positions)

        if positions_to_save:
            self.save_positions(positions_to_save)

        if number_of_positions > 0:
            self.orchestrator.finished_processing()

        self.contestant_track.set_calculator_finished()
        # Refresh the "running" heartbeat before the (normally fast, but unbounded) drain/join
        # below. Without this, a slow queue drain or thread join can outlast the heartbeat's
        # normal <=5s-refresh/30s-TTL cadence (its last refresh was up to LOOP_TIME ago, from
        # inside the now-exited while loop), so the key expires and is_calculator_running()
        # reports False while this processor is still shutting down. blocking_request_calculator_termination()
        # (contestant.py) polls exactly that key, so a stale False lets a "Restart calculator"
        # click race a second ContestantProcessor against this one instead of waiting for it to
        # actually finish (see GH #29). calculator_is_terminated() below clears the key for real
        # as soon as shutdown completes, so this only matters for that stale-expiry window.
        calculator_is_alive(self.contestant.pk, 60)
        # Drain the position queue efficiently
        while True:
            try:
                self.position_queue.pop()
            except RedisEmpty:
                break
            except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError):
                # Redis is down, we can't drain. Just stop.
                break
        self.score_processing_queue.put(None)
        self.score_processing_queue.join()
        self.score_thread.join()
        self.queuer_thread.join()
        logger.info("Terminating calculator for {}".format(self.contestant))
        calculator_is_terminated(self.contestant.pk)

    def should_i_terminate(self):
        """
        Check if the time has passed the finished by time and terminate the  processor if this is the case.
        We only terminate if the timed_queue is empty to allow catch-up processing.
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        if self.live_processing and not self.track_terminated:
            if self.orchestrator.has_the_contestant_passed_a_gate_and_landed():
                if self.contestant.finished_by_time + self.delay > now:
                    self.contestant.finished_by_time = now
                    self.contestant.save(update_fields=["finished_by_time"])
                    logger.info(
                        f"Contestant {self.contestant} has passed a gate and apparently landed, triggering calculator termination"
                    )
            if now > self.contestant.finished_by_time + self.delay:
                if self.timed_queue.empty() and self.position_queue.empty():
                    self.notify_termination("Finished by time exceeded (should_i_terminate)")
                else:
                    logger.debug(f"{self.contestant}: Time exceeded, but waiting for {self.timed_queue.qsize()} queued positions and {self.position_queue.size} Redis positions to be processed")

    def notify_termination(self, reason: str = ""):
        """
        Trigger termination of the run function.
        """
        logger.info("%s: Setting termination flag. Reason: %s", self.contestant, reason or "unspecified")
        if logger.isEnabledFor(logging.DEBUG):
            stack_trace = "".join(traceback.format_stack(limit=12))
            logger.debug(
                "%s: Calculator termination stack:\n%s",
                self.contestant,
                stack_trace,
            )
        self.contestant_track.set_calculator_finished()
        self.track_terminated = True
        self.timed_queue.close()

    def check_termination_is_commanded(self, position: Optional[ContestantReceivedPosition]):
        """
        Checks if termination has been manually triggered. If it has been triggered, create a score log entry to
        reflect this and notify termination.
        """
        if not self.track_terminated:
            termination_time = self.is_termination_commanded()
            if termination_time:
                last_gate = self.orchestrator.get_last_gate()
                
                # Fallbacks for when no gates have been passed yet
                lat = 0.0
                lon = 0.0
                planned = self.contestant.takeoff_time
                
                if position:
                    lat, lon = position.latitude, position.longitude
                elif last_gate:
                    lat, lon = last_gate.latitude, last_gate.longitude
                    planned = last_gate.expected_time
                elif self.contestant.navigation_task.route.waypoints:
                    # ContestantProcessor is not a Calculator subclass - it never had a
                    # self.route (only Calculator.__init__ sets that) - hit whenever a manual
                    # termination is requested while position is None and
                    # orchestrator.get_last_gate() is None (normal pre-first-position state,
                    # and permanent for POKER/LANDING tasks, whose calculators never emit
                    # NextGateExpectedEvent). The AttributeError fired before
                    # notify_termination(), so track_terminated never got set.
                    lat, lon = (
                        self.contestant.navigation_task.route.waypoints[0].latitude,
                        self.contestant.navigation_task.route.waypoints[0].longitude,
                    )

                self.score_processing_queue.put_nowait(
                    UpdateScoreMessage(
                        termination_time,
                        last_gate,
                        0,
                        "manually terminated",
                        lat,
                        lon,
                        "information",
                        "",
                        planned=planned,
                    )
                )
                self.notify_termination("Manually terminated")

    def is_termination_commanded(self) -> Optional[datetime.datetime]:
        """
        Return the termination request time if manual termination has been requested, else None.
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        if now - self.last_termination_check > datetime.timedelta(seconds=5):
            self.termination_requested_cached = is_termination_requested(self.contestant.pk)
            self.last_termination_check = now
            if self.termination_requested_cached:
                logger.info(f"{self.contestant}: Termination request received at {self.termination_requested_cached}")

        return self.termination_requested_cached

    def enqueue_positions_thread(self):
        """
        Thread function which enqueues incoming positions in a timed queue. The time queue is used to delay the
        calculation by a user configurable duration. The time the queue is read by the main run function in the class.
        """
        logger.info(
            f"{self.contestant}: Starting delayed position queuer with {self.position_queue.size} waiting messages. Track terminated is {self.track_terminated}"
        )
        receiving = False
        if self.live_processing and self.contestant.tracking_service == TrackingService.TRACCAR:
            device_ids = self.traccar.get_device_ids_for_contestant(self.contestant)
            current_time = datetime.datetime.now(datetime.timezone.utc)
            device_positions = {}
            # Fetch any earlier positions for the contestant to ensure that we start from the beginning.
            for device_id in device_ids:
                positions = self.traccar.get_positions_for_device_id(
                    device_id, self.contestant.tracker_start_time, current_time
                )
                augment_positions_from_traccar(positions)
                device_positions[device_id] = positions
            try:
                # Select the longest track
                positions_to_use = sorted(device_positions.values(), key=lambda k: len(k), reverse=True)[0]
                logger.info(
                    f"{self.contestant}: Fetched {len(positions_to_use)} historic positions at start of calculator"
                )
                if len(positions_to_use) > 0:
                    receiving = True
                    self.finished_loading_initial_positions.set()

                now = datetime.datetime.now(datetime.timezone.utc)
                for position in positions_to_use:
                    self.timed_queue.put(position, position["device_time"] + self.delay)
            except IndexError:
                pass
        elif self.live_processing and self.contestant.tracking_service == TrackingService.FLY_MASTER:
            existing_data = self.contestant.get_flymaster_track()
            now = datetime.datetime.now(datetime.timezone.utc)
            if len(existing_data) > 0:
                receiving = True
                self.finished_loading_initial_positions.set()
            for position in existing_data:
                self.timed_queue.put(position, position["device_time"] + self.delay)

        while not self.track_terminated:
            # Hard limit for live processing: stop ingesting data if we are way past the finished_by_time.
            # This prevents a runaway device from keeping the calculator alive forever.
            now = datetime.datetime.now(datetime.timezone.utc)
            if self.live_processing and now > self.contestant.finished_by_time + self.delay + datetime.timedelta(minutes=5):
                # If we are catching up, don't stop yet if we still have data in the queue
                if self.position_queue.empty():
                    logger.info(f"{self.contestant}: Hard limit reached in enqueue_positions_thread, stopping ingestion")
                    self.timed_queue.close()
                    break
                else:
                    logger.debug(f"{self.contestant}: Hard limit reached, but still processing {self.position_queue.size} positions from queue")

            try:
                position_data = self.position_queue.pop(True, timeout=1)
                if position_data is not None:
                    release_time = position_data["device_time"] + self.delay
                    if not receiving:
                        logger.info(f"{self.contestant}: Started receiving data")
                        receiving = True
                        self.finished_loading_initial_positions.set()
                    self.timed_queue.put(position_data, release_time)
                else:
                    # RedisQueue.pop() returns None ONLY when it receives a pickle.dumps(None) sentinel.
                    # This happens when the ingestion source (like Traccar or Flymaster) is finished.
                    logger.info(f"{self.contestant}: Delayed position queuer received termination sentinel from {self.position_queue.queue_name}")
                    self.timed_queue.close()
                    if not receiving:
                        self.finished_loading_initial_positions.set()
                        receiving = True
                    break
            except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError) as e:
                # Transient infra error (e.g. Redis restart during redeploy). Do NOT terminate.
                logger.warning(f"{self.contestant}: Transient Redis error in enqueue_positions_thread: {e}. Retrying...")
                time.sleep(1)
                continue
            except RedisEmpty:
                if receiving:
                    self.check_termination_is_commanded(self.previous_position)
                else:
                    if self.is_termination_commanded():
                        logger.info(f"{self.contestant}: Termination request received while waiting for first position")
                        self.finished_loading_initial_positions.set()
                        break
                    time.sleep(0.5)

    def _get_cima_gate_qmax(self) -> Optional[float]:
        # Lazily computed and cached on first use rather than in __init__: some tests
        # (test_cima_descending_scoring.py) construct a bare ContestantProcessor via
        # object.__new__ specifically to exercise this scoring logic without __init__'s
        # Redis/Traccar/thread setup - see that module's docstring. Qmax only depends on the
        # task's route + scorecard, neither of which changes mid-flight, so computing it once
        # and reusing it is safe regardless of when in the processor's lifecycle this first runs.
        if not hasattr(self, "_cima_gate_qmax_cache"):
            self._cima_gate_qmax_cache = get_cima_gate_qmax(self.contestant.navigation_task)
            self._cima_gate_component = self.contestant.navigation_task.scorecard.initial_score
        return self._cima_gate_qmax_cache

    def _cima_normalized_gate_score_delta(self) -> Optional[float]:
        """
        The catalogue's P = 1000 * Q / Qmax normalization (see cima_score_normalization.py),
        converted into a delta to apply to self.score in place of the raw per-event penalty
        magnitude. self._cima_gate_component tracks the gate-crossing component's current
        contribution to self.score (starting at scorecard.initial_score) so that only the
        INCREMENTAL change from this one event is returned - self.score's other bookkeeping
        (backtracking, procedure turns, ...) is untouched and keeps accumulating linearly as
        before, only the GATE_SCORE_TYPE component is normalized.

        Returns None (meaning: use the raw magnitude, unchanged from before this method existed)
        when this task's subtype/route isn't eligible for gate-Qmax normalization.
        """
        qmax = self._get_cima_gate_qmax()
        if qmax is None:
            return None
        initial_score = self.contestant.navigation_task.scorecard.initial_score
        gate_deficit = self.accumulated_scores.related_score.get(GATE_SCORE_TYPE, 0)
        new_component = initial_score * (1 - gate_deficit / qmax)
        delta = new_component - self._cima_gate_component
        self._cima_gate_component = new_component
        return delta

    def update_score_from_thread(self, update_score_message: UpdateScoreMessage):
        """
        Constructs the score structures required to update the contestants score. Optionally cap the score if it has a
        maximum value.
        """
        score, capped = self.accumulated_scores.set_and_update_score(
            update_score_message.score, update_score_message.score_type, update_score_message.maximum_score
        )
        # Every UpdateScoreMessage.score value is authored as a penalty magnitude (positive =
        # worse) - true for every calculator, including CIMA ones (circle_calculator.py emits
        # the deficit from Pmax, not the achieved value directly). For an ascending scorecard
        # (legacy default) that magnitude is added as-is, same as always. For a descending CIMA
        # scorecard the contestant starts at scorecard.initial_score (a maximum) and each
        # penalty must subtract from it instead - per the original CIMA design intent ("applying
        # negative penalties", documentation/cima/CIMA_Task_catalogue_implementation_plan.md)
        # which was never wired up. Applied here, once, after set_and_update_score's per-type
        # capping (which itself must stay unsigned - maximum_score there is a positive ceiling
        # on a penalty magnitude, independent of the scorecard's sort direction).
        # Reads through self.contestant.navigation_task.scorecard, not self.scorecard - some
        # tests construct a bare ContestantProcessor (object.__new__) that only sets the
        # handful of attributes update_score_from_thread otherwise touches, without a cached
        # self.scorecard (see e.g. test_idempotent_restart.py's replay test); self.contestant
        # is always present, and __init__ reads the scorecard the same way (line ~134 above).
        if self.contestant.navigation_task.scorecard.score_sorting_direction == "desc":
            score = -score
        if update_score_message.score_type == GATE_SCORE_TYPE:
            normalized_delta = self._cima_normalized_gate_score_delta()
            if normalized_delta is not None:
                score = normalized_delta
        if update_score_message.planned is not None and update_score_message.actual is not None:
            offset = (update_score_message.actual - update_score_message.planned).total_seconds()
            # Must use round, this is the same as used in the score calculation
            offset_val = round(offset)
            offset_string = f"{offset_val:+} s" if offset_val != 0 else "0 s"
            if offset_string and offset_string not in update_score_message.message:
                update_score_message.message += f" ({offset_string})"
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
        # Format score as float for consistency (0.0, 15.0, etc.)
        display_score = float(score)
        string = "{}: {} points {}".format(update_score_message.gate.name, display_score, update_score_message.message)
        times_string = ""
        if update_score_message.planned and update_score_message.actual:
            times_string = "planned: {}\nactual: {}".format(planned_time, actual_time)
        elif update_score_message.planned:
            times_string = "planned: {}\nactual: --".format(planned_time)
        if len(times_string) > 0:
            string += f"\n{times_string}"
        logger.info("UPDATE_SCORE {} {}: {}{}".format(update_score_message.score_type, self.contestant, "", string))

        # Optimized record_score_by_gate logic with local caching
        gate_name = update_score_message.gate.name
        if gate_name not in self.gate_scores:
            from display.models import GateCumulativeScore

            try:
                gate_score, _ = GateCumulativeScore.objects.get_or_create(gate=gate_name, contestant=self.contestant)
                self.gate_scores[gate_name] = gate_score
            except (ObjectDoesNotExist, IntegrityError):
                # Contestant has been deleted since this position was computed (self.contestant is only
                # refreshed every CONTESTANT_REFRESH_INTERVAL, see GH #707). Terminate rather than retrying
                # this get_or_create - and hitting the same FK violation - on every subsequent gate crossing
                # until the next refresh notices the deletion.
                logger.info(f"{self.contestant}: Contestant deleted during score update, terminating")
                self.track_terminated = True
                return

        gate_score = self.gate_scores[gate_name]
        if self.suppress_side_effects:
            self.score += score
            return

        entry, created = ScoreLogEntry.get_or_create_and_push(
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

        if not created:
            return

        gate_score.points += score
        gate_score.save(update_fields=["points"])

        self.score += score

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
            self.contestant_track.increment_score(score)
