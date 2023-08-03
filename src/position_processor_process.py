import time
from http.client import RemoteDisconnected
from multiprocessing import Queue, Process

import os
from queue import Empty
from typing import List, Dict, Tuple, Optional

import logging

import multiprocessing

import datetime
import dateutil
import threading

from django.core.exceptions import ObjectDoesNotExist
from django.core.mail import send_mail
from urllib3.exceptions import ProtocolError

from display.utilities.calculator_running_utilities import is_calculator_running, calculator_is_alive
from display.utilities.calculator_termination_utilities import is_termination_requested
from display.kubernetes_calculator.job_creator import JobCreator, AlreadyExists
from live_tracking_map import settings
from probes import probes
from redis_queue import RedisQueue

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "live_tracking_map.settings")
    import django

    django.setup()

from django.core.cache import cache
from django.db import connections, OperationalError, connection

from display.calculators.calculator_factory import calculator_factory
from display.models import Contestant
from traccar_facade import Traccar

CACHE_TTL = 60
contestant_cache = {}

logger = logging.getLogger(__name__)
processes = {}
calculator_lock = multiprocessing.Lock()
CONTESTANT_TYPE = 0
PERSON_TYPE = 1

DEBUG_INTERVAL = 60
global_received_positions = 0


def print_debug():
    global global_received_positions
    logger.debug(
        f"Received {global_received_positions} positions last {DEBUG_INTERVAL} seconds ({(global_received_positions / DEBUG_INTERVAL):.2f} p/s)"
    )
    global_received_positions = 0
    threading.Timer(DEBUG_INTERVAL, print_debug).start()


def cached_find_contestant(device_name: str, device_time: datetime.datetime) -> Tuple[Optional[Contestant], bool]:
    try:
        contestant, is_simulator, valid_to = contestant_cache[device_name]
        if valid_to < device_time:
            raise KeyError
    except KeyError:
        contestant, is_simulator = Contestant.get_contestant_for_device_at_time(device_name, device_time)
        if contestant:
            logger.info(f"Found contestant for incoming position {contestant}{' (simulator)' if is_simulator else ''}")
            if is_simulator and not contestant.has_been_tracked_by_simulator:
                contestant.has_been_tracked_by_simulator = True
                contestant.save(update_fields=("has_been_tracked_by_simulator",))

        contestant_cache[device_name] = (
            contestant,
            is_simulator,
            device_time
            + min(
                datetime.timedelta(seconds=CACHE_TTL),
                contestant.finished_by_time - device_time
                if contestant is not None
                else datetime.timedelta(seconds=CACHE_TTL),
            ),
        )
    if contestant and contestant.is_currently_tracked_by_device(device_name):
        return contestant, is_simulator
    return None, is_simulator


def clean_db_positions():
    for c in connections.all():
        c.close_if_unusable_or_obsolete()


def initial_processor(queue: Queue, global_map_queue: Queue):
    connections.close_all()
    while True:
        try:
            traccar = Traccar.create_from_configuration()
            break
        except:
            logger.exception(f"Initial processor failed to connect to traccer")
            time.sleep(5)
    print_debug()
    while True:
        clean_db_positions()
        try:
            data = queue.get(timeout=10)
            build_and_push_position_data(data, traccar, global_map_queue)
        except Empty:
            pass
        probes.liveness(True)


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
        calculator = calculator_factory(contestant, live_processing=True)
        calculator.run()
    else:
        logger.warning(f"Attempting to start new calculator for terminated contestant {contestant}")


def retry(func, args, kwargs, ex_types=(Exception,), limit=0, wait_ms=100, wait_increase_ratio=2, logger=None):
    """
    Retry a function invocation until no exception occurs
    :param func: function to invoke
    :param ex_type: retry only if exception is subclass of this type
    :param limit: maximum number of invocation attempts
    :param wait_ms: initial wait time after each attempt in milliseconds.
    :param wait_increase_ratio: increase wait period by multiplying this value after each attempt.
    :param logger: if not None, retry attempts will be logged to this logging.logger
    :return: result of first successful invocation
    :raises: last invocation exception if attempts exhausted or exception is not an instance of ex_type
    """
    attempt = 1
    while True:
        try:
            return func(*args, **kwargs)
        except Exception as ex:
            if not any(isinstance(ex, ex_type) for ex_type in ex_types):
                raise ex
            if 0 < limit <= attempt:
                if logger:
                    logger.warning("no more attempts")
                raise ex

            if logger:
                logger.error("failed execution attempt #%d", attempt, exc_info=ex)

            attempt += 1
            if logger:
                logger.info("waiting %d ms before attempt #%d", wait_ms, attempt)
            time.sleep(wait_ms / 1000)
            wait_ms *= wait_increase_ratio


def add_positions_to_calculator(contestant: Contestant, positions: List):
    global processes
    key = contestant.pk

    with calculator_lock:
        if key not in processes or not is_calculator_running(key):

            def start_internal_calculator():
                p = Process(target=calculator_process, args=(contestant.pk,), daemon=True)
                calculator_is_alive(contestant.pk, 30)
                p.start()
                processes[key] = (q, p)

            def start_kubernetes_job():
                return retry(
                    creator.spawn_calculator_job,
                    (contestant.pk,),
                    {},
                    ex_types=(ProtocolError, RemoteDisconnected),
                    limit=5,
                    wait_ms=500,
                )

            def delete_kubernetes_job():
                return retry(
                    creator.delete_calculator,
                    (contestant.pk,),
                    {},
                    ex_types=(ProtocolError, RemoteDisconnected),
                    limit=5,
                    wait_ms=500,
                )

            q = RedisQueue(str(contestant.pk))
            if settings.PRODUCTION:
                # Create kubernetes job for the calculator
                creator = JobCreator()
                processes[key] = (q, None)
                try:
                    response = start_kubernetes_job()
                    calculator_is_alive(contestant.pk, 300)  # Give it five minutes to spin up the kubernetes job
                    logger.info(f"Successfully created calculator job for {contestant}")
                except AlreadyExists:
                    logger.warning(
                        f"Tried to start existing calculator job for contestant {contestant}. Attempting to restart."
                    )
                    try:
                        delete_kubernetes_job()
                    except:
                        logger.error(f"Failed the deleting calculator job for contestant {contestant}")
                    try:
                        response = start_kubernetes_job()
                        calculator_is_alive(contestant.pk, 300)
                        logger.info(f"Successfully created calculator job for {contestant}")
                    except AlreadyExists:
                        logger.warning(f"Tried to start existing calculator job for contestant {contestant}. Ignoring.")
                except Exception as ex:
                    logger.exception(f"Failed starting kubernetes calculator job for {contestant}")
                    try:
                        send_mail(
                            "Failed starting kubernetes calculator job",
                            f"Failed starting job for contestant {contestant}. Falling back to internal calculator.\n{ex}",
                            None,
                            ["frankose@ifi.uio.no"],
                        )
                    except:
                        logger.exception("Failed sending error email")
                    # Create an internal process for the calculator
                    connections.close_all()
                    start_internal_calculator()
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
            contestant, is_simulator = cached_find_contestant(device_name, device_time)
        except OperationalError:
            logger.warning(f"Error when fetching person for app_tracking_id '{device_name}'. Attempting to reconnect")
            connection.connect()
            contestant = None
            is_simulator = True
        if contestant:
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
            global_map_queue.put((PERSON_TYPE, device_name, position_data, device_time, is_simulator))
    return received_tracks
