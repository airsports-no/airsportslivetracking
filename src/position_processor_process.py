import time
from multiprocessing import Queue, Process

import os
from queue import Empty
from typing import List, Dict, Tuple, Optional

import logging

import datetime
import dateutil
import redis_lock
from redis.client import Redis

from django.core.exceptions import ObjectDoesNotExist
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError as DRFValidationError

from display.utilities.calculator_running_utilities import is_calculator_running, calculator_is_alive
from display.utilities.calculator_termination_utilities import is_termination_requested
from display.utilities.tracking_definitions import TrackingService
from live_tracking_map import settings
from redis_queue import RedisQueue

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "live_tracking_map.settings")
    import django

    django.setup()

from django.core.cache import cache
from django.db import connections, OperationalError, connection
from display.calculators.contestant_processor import ContestantProcessor

from display.models import Contestant
from traccar_facade import Traccar

CACHE_TTL = 60
contestant_cache = {}

logger = logging.getLogger(__name__)
processes = {}
CONTESTANT_TYPE = 0
PERSON_TYPE = 1

DEBUG_INTERVAL = 60
global_received_positions = 0
last_debug = time.time()

LAST_DEBUG_KEY = "last_debug"


def print_contestant_positions_debug():
    global global_received_positions, last_debug
    this_interval = time.time() - last_debug
    if this_interval > DEBUG_INTERVAL:
        logger.debug(
            f"Received {global_received_positions} positions last {this_interval:.1f} seconds ({(global_received_positions / this_interval):.2f} p/s)"
        )
        global_received_positions = 0
        last_debug = time.time()
        try:
            cache.set(LAST_DEBUG_KEY, last_debug, 10 * DEBUG_INTERVAL)
        except Exception:
            logger.warning("Unable to persist position processor heartbeat to Redis cache", exc_info=True)


def cached_find_contestant(device_name: str, device_time: datetime.datetime) -> List[Tuple[Contestant, bool]]:
    try:
        contestant_tuples, valid_to = contestant_cache[device_name]
        if valid_to < device_time:
            raise KeyError
    except KeyError:
        contestant_tuples = Contestant.get_contestant_for_device_at_time(
            TrackingService.TRACCAR, device_name, device_time
        )
        if contestant_tuples:
            logger.info(f"Found contestants for incoming position {contestant_tuples}")
            for contestant, is_simulator in contestant_tuples:
                if is_simulator and not contestant.has_been_tracked_by_simulator:
                    contestant.has_been_tracked_by_simulator = True
                    contestant.save(update_fields=("has_been_tracked_by_simulator",))

        min_finish = (
            min(c.finished_by_time for c, _ in contestant_tuples)
            if contestant_tuples
            else device_time + datetime.timedelta(seconds=CACHE_TTL)
        )

        contestant_cache[device_name] = (
            contestant_tuples,
            device_time
            + min(
                datetime.timedelta(seconds=CACHE_TTL),
                min_finish - device_time,
            ),
        )
    active_tuples = []
    if contestant_tuples:
        for c, is_sim in contestant_tuples:
            if c.is_currently_tracked_by_device(device_name):
                active_tuples.append((c, is_sim))
    return active_tuples


def clean_db_positions():
    for c in connections.all():
        c.close_if_unusable_or_obsolete()


def initial_processor(queue: Queue, global_map_queue: Queue):
    try:
        cache.set(LAST_DEBUG_KEY, last_debug, 10 * DEBUG_INTERVAL)
    except Exception:
        logger.warning("Unable to initialize position processor heartbeat in Redis cache", exc_info=True)

    connections.close_all()
    while True:
        try:
            traccar = Traccar.create_from_configuration()
            break
        except:
            logger.exception("Initial processor failed to connect to traccer")
            time.sleep(5)
    while True:
        clean_db_positions()
        try:
            data = queue.get(timeout=DEBUG_INTERVAL)
            build_and_push_position_data(data, traccar, global_map_queue)
        except Empty:
            pass
        print_contestant_positions_debug()


def build_and_push_position_data(data, traccar, global_map_queue):
    global global_received_positions
    received_positions = map_positions_to_contestants(traccar, data.get("positions", []), global_map_queue)
    for contestant, positions in received_positions.items():
        global_received_positions += len(positions)
        add_positions_to_calculator(contestant, positions)
    cleanup_calculators()


def calculator_process(contestant_pk: int):
    """
    To be run in a separate process
    """
    connections.close_all()
    try:
        contestant = Contestant.objects.get(pk=contestant_pk)
    except ObjectDoesNotExist:
        logger.warning(f"Attempting to start new calculator for non-existent contestant {contestant_pk}")
        return
    if not contestant.contestanttrack.calculator_finished and not is_termination_requested(contestant_pk):
        try:
            contestant_processor = ContestantProcessor(contestant, live_processing=True)
        except (DjangoValidationError, DRFValidationError) as exc:
            logger.warning(f"Refusing to start calculator for contestant {contestant_pk}: {exc}")
            return
        contestant_processor.run()
    else:
        logger.warning(f"Attempting to start new calculator for terminated contestant {contestant}")


def add_positions_to_calculator(contestant: Contestant, positions: List):
    global processes
    key = contestant.pk

    conn = Redis(settings.REDIS_HOST, settings.REDIS_PORT, 2, password=settings.REDIS_PASSWORD)
    with redis_lock.Lock(conn, f"calculator_dispatch_{contestant.pk}"):
        if key not in processes or not is_calculator_running(key):

            def start_internal_calculator():
                p = Process(target=calculator_process, args=(contestant.pk,), daemon=True)
                calculator_is_alive(contestant.pk, 30)
                p.start()
                processes[key] = (q, p)

            q = RedisQueue(str(contestant.pk))
            if settings.PRODUCTION:
                # Dispatch the calculator as a Celery task on the dedicated live_calculator queue
                from display.tasks import run_live_contestant_calculator

                processes[key] = (q, None)
                calculator_is_alive(contestant.pk, 300)  # Give it five minutes to spin up
                run_live_contestant_calculator.apply_async(args=(contestant.pk,), queue="live_calculator")
                logger.info(f"Dispatched live calculator task for {contestant}")
            else:
                start_internal_calculator()
    redis_queue = processes[key][0]
    for position in positions:
        # logger.debug(f"Adding position ID {position['id']} for device ID {position['deviceId']} to calculator")
        redis_queue.append(position)


def cleanup_calculators():
    for key, (queue, process) in dict(processes).items():
        if process and not process.is_alive():
            processes.pop(key)


def map_positions_to_contestants(traccar: Traccar, positions: List, global_map_queue) -> Dict[Contestant, List[Dict]]:
    """
    Determine which contestant the position data belongs to. Forward the position with the associated person or
    contestant to the global queue.
    """
    if len(positions) == 0:
        return {}
    # logger.info("Received {} positions".format(len(positions)))
    received_tracks = {}
    for position_data in positions:
        # logger.info("Incoming position: {}".format(position_data))
        try:
            device_name = traccar.device_map[position_data["deviceId"]]
        except KeyError:
            traccar.get_device_map()
            try:
                device_name = traccar.device_map[position_data["deviceId"]]
            except KeyError:
                logger.error("Could not find device {}.".format(position_data["deviceId"]))
                continue
        device_time = dateutil.parser.parse(position_data["deviceTime"])
        # Store this so that we do not have to parse the datetime string again
        position_data["device_time"] = device_time
        position_data["server_time"] = dateutil.parser.parse(position_data["serverTime"])
        position_data["processor_received_time"] = datetime.datetime.now(datetime.timezone.utc)
        now = datetime.datetime.now(datetime.timezone.utc)
        last_seen_key = f"last_seen_{position_data['deviceId']}"
        if (now - device_time).total_seconds() > 30:
            # Only check the cache if the position is old
            last_seen = cache.get(last_seen_key)
            if last_seen == device_time or device_time < now - datetime.timedelta(hours=14):
                # If we have seen it or it is really old, ignore it
                logger.debug(f"Received repeated position, disregarding: {device_name} {device_time}")
                continue
        cache.set(last_seen_key, device_time)
        # print(device_time)
        try:
            contestant_tuples = cached_find_contestant(device_name, device_time)
        except OperationalError as e:
            if e.args[0] == 1040:  # Too many connections
                logger.error("MySQL: Too many connections. Waiting 2 seconds...")
                time.sleep(2)
            else:
                logger.warning(
                    f"Error when fetching person for app_tracking_id '{device_name}'. Attempting to reconnect: {e}"
                )
                try:
                    connection.connect()
                except:
                    pass
            contestant_tuples = []
        if contestant_tuples:
            for contestant, is_simulator in contestant_tuples:
                try:
                    received_tracks[contestant].append(position_data)
                except KeyError:
                    received_tracks[contestant] = [position_data]
                global_map_queue.put(
                    (
                        CONTESTANT_TYPE,
                        contestant.pk,
                        position_data,
                        device_time,
                        is_simulator,
                    )
                )
        else:
            global_map_queue.put((PERSON_TYPE, device_name, position_data, device_time, False))
    return received_tracks
