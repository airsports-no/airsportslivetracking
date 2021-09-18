import datetime
import json
import logging
import os
import threading
from multiprocessing import Process, Queue
from typing import List, TYPE_CHECKING, Dict, Optional
import sentry_sdk

import dateutil

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "live_tracking_map.settings")
    import django

    django.setup()

from live_tracking_map import settings
from traccar_facade import Traccar
from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist
from django.db import connections, close_old_connections, OperationalError, connection
from display.serialisers import PersonSerialiser, PersonLtdSerialiser

from websocket_channels import WebsocketFacade

import websocket
from influx_facade import InfluxFacade
from display.models import Contestant, TraccarCredentials, Person
from display.calculators.calculator_factory import calculator_factory

logger = logging.getLogger(__name__)

PURGE_GLOBAL_MAP_INTERVAL = 60

CONTESTANT_TYPE = 0
PERSON_TYPE = 1

configuration = TraccarCredentials.objects.get()

if __name__ == "__main__":
    traccar = Traccar.create_from_configuration(configuration)
    devices = traccar.get_device_map()
    websocket_facade = WebsocketFacade()

influx = InfluxFacade(
    settings.INFLUX_HOST, settings.INFLUX_PORT, settings.INFLUX_USER, settings.INFLUX_PASSWORD, settings.INFLUX_DB_NAME
)
processes = {}
calculator_lock = threading.Lock()

global_map_queue = Queue()


def calculator_process(contestant_pk: int, position_queue: Queue):
    """
    To be run in a separate process
    """
    django.db.connections.close_all()
    contestant = Contestant.objects.get(pk=contestant_pk)
    calculator = calculator_factory(contestant, position_queue, live_processing=True)
    calculator.run()


def add_positions_to_calculator(contestant: Contestant, positions: List):
    global processes
    key = contestant.pk
    if key not in processes:
        q = Queue()
        django.db.connections.close_all()
        p = Process(target=calculator_process, args=(key, q), daemon=True)
        processes[key] = (q, p)
        p.start()
    queue = processes[key][0]  # type: Queue
    for position in positions:
        queue.put(position)


def cleanup_calculators():
    for key, (queue, process) in dict(processes).items():
        if not process.is_alive():
            processes.pop(key)


def map_positions_to_contestants(
        traccar: Traccar, positions: List
) -> Dict[Contestant, List[Dict]]:
    if len(positions) == 0:
        return {}
    # logger.info("Received {} positions".format(len(positions)))
    received_tracks = {}
    for position_data in positions:
        global_tracking_name = ""
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
        now = datetime.datetime.now(datetime.timezone.utc)
        last_seen_key = f"last_seen_{position_data['deviceId']}"
        if (now - device_time).total_seconds() > 30:
            # Only check the cache if the position is old
            last_seen = cache.get(last_seen_key)
            if last_seen == device_time or device_time < now - datetime.timedelta(
                    hours=14
            ):
                # If we have seen it or it is really old, ignore it
                logger.info(f"Received repeated position, disregarding: {device_name} {device_time}")
                continue
        cache.set(last_seen_key, device_time)
        # print(device_time)
        contestant, is_simulator = Contestant.get_contestant_for_device_at_time(device_name, device_time)
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


def live_position_transmitter_process(queue):
    django.db.connections.close_all()
    while True:
        (
            data_type,
            person_or_contestant,
            position_data,
            device_time,
            is_simulator,
        ) = queue.get()

        navigation_task_id = None
        global_tracking_name = None
        person_data = None
        if data_type == PERSON_TYPE:
            try:
                person = Person.objects.get(app_tracking_id=person_or_contestant)
                person.last_seen = device_time
                person.save(update_fields=["last_seen"])
                global_tracking_name = person.app_aircraft_registration
                if person.is_public:
                    person_data = PersonLtdSerialiser(person).data
            except ObjectDoesNotExist:
                pass
            except OperationalError:
                logger.warning(
                    f"Error when fetching person for app_tracking_id '{person_or_contestant}'. Attempting to reconnect"
                )
                connection.connect()

        else:
            try:
                contestant = (
                    Contestant.objects.filter(pk=person_or_contestant)
                        .select_related("navigation_task", "team", "team__aeroplane")
                        .first()
                )
                if contestant is not None:
                    global_tracking_name = contestant.team.aeroplane.registration
                    try:
                        person = contestant.team.crew.member1
                        if person.is_public:
                            person_data = PersonLtdSerialiser(person).data
                    except:
                        logger.exception(f"Failed fetching person data for contestant {contestant}")
                    if contestant.navigation_task.everything_public:
                        navigation_task_id = contestant.navigation_task_id
            except OperationalError:
                logger.warning(
                    f"Error when fetching contestant for app_tracking_id '{person_or_contestant}'. Attempting to reconnect"
                )
                connection.connect()
        now = datetime.datetime.now(datetime.timezone.utc)
        if (
                global_tracking_name is not None
                and not is_simulator
                and now
                < device_time + datetime.timedelta(seconds=PURGE_GLOBAL_MAP_INTERVAL)
        ):
            websocket_facade.transmit_global_position_data(
                global_tracking_name,
                person_data,
                position_data,
                device_time,
                navigation_task_id,
            )


def build_and_push_position_data(data):
    # logger.info("Received data")
    with calculator_lock:
        received_positions = map_positions_to_contestants(traccar, data.get("positions", []))
        for contestant, positions in received_positions.items():
            # logger.info("Positions for {}".format(contestant))
            add_positions_to_calculator(contestant, positions)
            # logger.info("Positions to calculator for {}".format(contestant))
        cleanup_calculators()


def clean_db_positions():
    for c in connections.all():
        c.close_if_unusable_or_obsolete()


def on_message(ws, message):
    clean_db_positions()
    data = json.loads(message)
    build_and_push_position_data(data)


def on_error(ws, error):
    print(error)


def on_close(ws, *args, **kwargs):
    print("### closed ###")


def on_open(ws):
    pass


headers = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.103 Safari/537.36"
}

headers["Upgrade"] = "websocket"

if __name__ == "__main__":
    django.db.connections.close_all()
    p = Process(
        target=live_position_transmitter_process,
        args=(global_map_queue,),
        daemon=True,
        name="live_position_transmitter",
    )
    p.start()
    sentry_sdk.init(
        "https://56e7c26e749c45c585c7123ddd34df7a@o568590.ingest.sentry.io/5713804",
        # Set traces_sample_rate to 1.0 to capture 100%
        # of transactions for performance monitoring.
        # We recommend adjusting this value in production.
        traces_sample_rate=1.0,
    )
    cache.clear()
    while True:
        websocket.enableTrace(False)
        cookies = traccar.session.cookies.get_dict()
        ws = websocket.WebSocketApp(
            "ws://{}/api/socket".format(configuration.address),
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
            header=headers,
            cookie="; ".join(["%s=%s" % (i, j) for i, j in cookies.items()]),
        )
        ws.run_forever()
        logger.warning("Websocket terminated, restarting")
