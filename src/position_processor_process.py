from multiprocessing import Queue, Process

import os
from typing import List, Dict, Tuple

import logging

import multiprocessing

import datetime
import dateutil
from django.core.mail import send_mail

from display.kubernetes_calculator.job_creator import JobCreator, AlreadyExists
from redis_queue import RedisQueue

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "live_tracking_map.settings")
    import django

    django.setup()

from django.core.cache import cache
from django.db import connections, OperationalError, connection

from display.calculators.calculator_factory import calculator_factory
from display.models import TraccarCredentials, Contestant
from traccar_facade import Traccar

CACHE_TTL = 180
contestant_cache = {}

logger = logging.getLogger(__name__)
processes = {}
calculator_lock = multiprocessing.Lock()
CONTESTANT_TYPE = 0
PERSON_TYPE = 1


def cached_find_contestant(device_name: str, device_time: datetime.datetime) -> Tuple[Contestant, bool]:
    try:
        contestant, is_simulator, valid_to = contestant_cache[device_name]
        if valid_to < device_time:
            raise KeyError
    except KeyError:
        contestant, is_simulator = Contestant.get_contestant_for_device_at_time(device_name, device_time)
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
    return contestant, is_simulator


def clean_db_positions():
    for c in connections.all():
        c.close_if_unusable_or_obsolete()


def initial_processor(queue: Queue, global_map_queue: Queue):
    configuration = TraccarCredentials.objects.get()
    connections.close_all()
    traccar = Traccar.create_from_configuration(configuration)

    while True:
        clean_db_positions()
        data = queue.get()
        build_and_push_position_data(data, traccar, global_map_queue)


def build_and_push_position_data(data, traccar, global_map_queue):
    # logger.info("Received data")
    received_positions = map_positions_to_contestants(traccar, data.get("positions", []), global_map_queue)
    for contestant, positions in received_positions.items():
        # logger.info("Positions for {}".format(contestant))
        add_positions_to_calculator(contestant, positions)
        # logger.info("Positions to calculator for {}".format(contestant))
    cleanup_calculators()


def calculator_process(contestant_pk: int):
    """
    To be run in a separate process
    """
    connections.close_all()
    contestant = Contestant.objects.get(pk=contestant_pk)
    if not contestant.contestanttrack.calculator_finished:
        calculator = calculator_factory(contestant, live_processing=True)
        calculator.run()
    else:
        logger.warning(f"Attempting to start new calculator for terminated contestant {contestant}")


def add_positions_to_calculator(contestant: Contestant, positions: List):
    global processes
    key = contestant.pk
    with calculator_lock:
        if key not in processes:
            q = RedisQueue(str(contestant.pk))
            # Create kubernetes job for the calculator
            creator = JobCreator()
            processes[key] = (q, None)
            try:
                response = creator.spawn_calculator_job(contestant.pk)
                logger.info(f"Successfully created calculator job for {contestant}")
            except AlreadyExists:
                logger.warning(
                    f"Tried to start existing calculator job for contestant {contestant}. Ignoring the failure.")
            except:
                logger.exception(f"Failed starting kubernetes calculator job for {contestant}")
                try:
                    send_mail("Failed starting kubernetes calculator job",
                              f"Failed starting job for contestant {contestant}. Falling back to internal calculator.",
                              None, ["frankose@ifi.uio.no"])
                except:
                    logger.exception("Failed sending error email")
                # Create an internal process for the calculator
                connections.close_all()
                p = Process(target=calculator_process, args=(contestant.pk,), daemon=True)
                p.start()
                processes[key] = (q, p)
    redis_queue = processes[key][0]
    for position in positions:
        # logger.debug(f"Adding position ID {position['id']} for device ID {position['deviceId']} to calculator")
        redis_queue.append(position)


def cleanup_calculators():
    for key, (queue, process) in dict(processes).items():
        if process and not process.is_alive():
            processes.pop(key)


def map_positions_to_contestants(traccar: Traccar, positions: List, global_map_queue) -> Dict[Contestant, List[Dict]]:
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
            # logger.debug(
            #     f"Mapped position ID {position_data['id']} for device ID {position_data['deviceId']} to contestant {contestant}"
            # )

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
