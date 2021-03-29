import datetime
import json
import logging
import os
import threading
from multiprocessing import Process, Queue
from typing import List, TYPE_CHECKING, Dict, Optional

import dateutil

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "live_tracking_map.settings")
    import django

    django.setup()

if TYPE_CHECKING:
    from display.calculators.calculator import Calculator
from traccar_facade import Traccar
from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist
from django.db import connections

from websocket_channels import WebsocketFacade

import websocket
from influx_facade import InfluxFacade
from display.models import Contestant, TraccarCredentials, ContestantTrack, CONTESTANT_CACHE_KEY, Person
from display.calculators.calculator_factory import calculator_factory

logger = logging.getLogger(__name__)

GLOBAL_TRANSMISSION_INTERVAL = 5
PURGE_GLOBAL_MAP_INTERVAL = 180

configuration = TraccarCredentials.objects.get()

if __name__ == "__main__":
    traccar = Traccar.create_from_configuration(configuration)
    devices = traccar.get_device_map()
    websocket_facade = WebsocketFacade()
influx = InfluxFacade()
processes = {}
calculator_lock = threading.Lock()
global_map = {}
last_purge = datetime.datetime.now(datetime.timezone.utc)


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


def map_positions_to_contestants(traccar: Traccar, positions: List) -> Dict[Contestant, List[Dict]]:
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
        # logger.info(device_name)
        now = datetime.datetime.now(datetime.timezone.utc)
        last_seen_key = f"last_seen_{position_data['deviceId']}"
        if (now - device_time).total_seconds() > 30:
            # Only check the cache if the position is old
            last_seen = cache.get(last_seen_key)
            if last_seen == device_time or device_time < now - datetime.timedelta(hours=4):
                # If we have seen it or it is really old, ignore it
                logger.info(f"Received repeated position, disregarding: {device_name} {device_time}")
                continue
        cache.set(last_seen_key, device_time)
        # print(device_time)
        contestant, is_simulator = Contestant.get_contestant_for_device_at_time(device_name, device_time)
        navigation_task_id = None
        global_tracking_name = None
        person_name = None
        if not contestant:
            try:
                person = Person.objects.get(app_tracking_id=device_name)
                global_tracking_name = person.app_aircraft_registration
                if person.is_public:
                    person_name = person.first_name
            except ObjectDoesNotExist:
                # logger.info("Found no person for tracking ID {}".format(device_name))
                pass
        # print(contestant)
        if contestant:
            if contestant.navigation_task.everything_public:
                navigation_task_id = contestant.navigation_task_id
            global_tracking_name = contestant.team.aeroplane.registration
            data = influx.generate_position_block_for_contestant(contestant, position_data, device_time)
            try:
                received_tracks[contestant].append(data)
            except KeyError:
                received_tracks[contestant] = [data]
        if global_tracking_name is not None:
            transmit_live_position(position_data, global_tracking_name, person_name, device_time, navigation_task_id)
    return received_tracks


def transmit_live_position(position_data: Dict, global_tracking_name: str, person_name: Optional[str], device_time: datetime.datetime, navigation_task_id:Optional[int]):
    last_global, last_data = global_map.get(position_data["deviceId"],
                                            (datetime.datetime.min.replace(tzinfo=datetime.timezone.utc),
                                             {}))
    now = datetime.datetime.now(datetime.timezone.utc)
    if (now - last_global).total_seconds() > GLOBAL_TRANSMISSION_INTERVAL:
        global_map[position_data["deviceId"]] = (
        now, websocket_facade.transmit_global_position_data(global_tracking_name, person_name, position_data, device_time, navigation_task_id))
        cache.set("GLOBAL_MAP_DATA", global_map)


def purge_global_map():
    global last_purge
    logger.info("Purging global map cache")
    now = datetime.datetime.now(datetime.timezone.utc)
    last_purge = now
    for key in list(global_map.keys()):
        value = global_map[key]
        if (now - value[0]).total_seconds() > PURGE_GLOBAL_MAP_INTERVAL:
            del global_map[key]
    cache.set("GLOBAL_MAP_DATA", global_map)
    threading.Timer(PURGE_GLOBAL_MAP_INTERVAL, purge_global_map).start()
    logger.info("Purged global map cache")


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
    clean_db_positions()


def on_error(ws, error):
    print(error)


def on_close(ws):
    print("### closed ###")


def on_open(ws):
    pass


headers = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.103 Safari/537.36'}

headers['Upgrade'] = 'websocket'

if __name__ == "__main__":
    cache.clear()
    purge_global_map()
    while True:
        websocket.enableTrace(True)
        cookies = traccar.session.cookies.get_dict()
        ws = websocket.WebSocketApp("ws://{}/api/socket".format(configuration.address),
                                    on_message=on_message,
                                    on_error=on_error,
                                    on_close=on_close,
                                    header=headers,
                                    cookie="; ".join(["%s=%s" % (i, j) for i, j in cookies.items()]))
        ws.run_forever()
        logger.warning("Websocket terminated, restarting")
