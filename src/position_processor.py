import datetime
import json
import logging
import os
import threading
import time
from multiprocessing import Process, Queue

# import sentry_sdk

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "live_tracking_map.settings")
    import django

    django.setup()

from traccar_facade import Traccar
from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist
from django.db import connections, OperationalError, connection
from display.serialisers import PersonLtdSerialiser

from websocket_channels import WebsocketFacade

from position_processor_process import initial_processor, PERSON_TYPE

import websocket
from display.models import Contestant, TraccarCredentials, Person

logger = logging.getLogger(__name__)

PURGE_GLOBAL_MAP_INTERVAL = 60

if __name__ == "__main__":
    websocket_facade = WebsocketFacade()

global_map_queue = Queue()
processing_queue = Queue()
RESET_INTERVAL = 300

received_messages = 0


def live_position_transmitter_process(queue):
    django.db.connections.close_all()
    person_cache = {}
    contestant_cache = {}
    last_reset = datetime.datetime.now()

    def fetch_person(person_or_contestant):
        try:
            person = person_cache[person_or_contestant]
        except KeyError:
            person = Person.objects.get(app_tracking_id=person_or_contestant)
            person_cache[person_or_contestant] = person
            logger.info(f"Found person for live position {person}")
        return person

    def fetch_contestant(person_or_contestant):
        try:
            contestant = contestant_cache[person_or_contestant]
        except KeyError:
            contestant = (
                Contestant.objects.filter(pk=person_or_contestant)
                .select_related(
                    "navigation_task",
                    "team",
                    "team__crew",
                    "team__crew__member1",
                    "team__crew__member2",
                    "team__aeroplane",
                )
                .first()
            )
            logger.info(f"Found contestant for live position {contestant}")
            contestant_cache[person_or_contestant] = contestant
        return contestant

    while True:
        (
            data_type,
            person_or_contestant,
            position_data,
            device_time,
            is_simulator,
        ) = queue.get()
        if (datetime.datetime.now() - last_reset).total_seconds() > RESET_INTERVAL:
            person_cache = {}
            contestant_cache = {}
            last_reset=datetime.datetime.now()

        navigation_task_id = None
        global_tracking_name = None
        person_data = None
        if data_type == PERSON_TYPE:
            try:
                person = fetch_person(person_or_contestant)
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
            except Exception:
                logger.exception(
                    f"Something failed when trying to update person {person_or_contestant}"
                )

        else:
            try:
                contestant = fetch_contestant(person_or_contestant)
                if contestant is not None:
                    # Check for delayed tracking, do not push global positions if there is delay
                    if contestant.navigation_task.calculation_delay_minutes != 0:
                        continue
                    global_tracking_name = contestant.team.aeroplane.registration
                    try:
                        person = contestant.team.crew.member1
                        person.last_seen = device_time
                        person.save(update_fields=["last_seen"])
                        if person.is_public:
                            person_data = PersonLtdSerialiser(person).data
                    except:
                        logger.exception(
                            f"Failed fetching person data for contestant {contestant}"
                        )
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
            websocket_facade.transmit_airsports_position_data(
                global_tracking_name,
                position_data,
                device_time,
                navigation_task_id,
            )


def on_message(ws, message):
    global received_messages
    data = json.loads(message)
    received_messages += 1
    # for item in data.get("positions", []):
    #     logger.debug(f"Received position ID {item['id']} for device ID {item['deviceId']}")
    processing_queue.put(data)


def on_error(ws, error):
    logger.error(f"Websocket error: {error}")


def on_close(ws, *args, **kwargs):
    print("### closed ###")


def on_open(ws):
    logger.info(f"Websocket connected")


DEBUG_INTERVAL = 60


def print_debug():
    global received_messages
    logger.debug(
        f"Received {received_messages} messages last {DEBUG_INTERVAL} seconds ({(received_messages/DEBUG_INTERVAL):.2f} m/s)"
    )
    received_messages = 0
    threading.Timer(DEBUG_INTERVAL, print_debug).start()


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
    for index in range(1):
        logger.info(f"Creating initial processor number {index}")
        Process(
            target=initial_processor,
            args=(processing_queue, global_map_queue),
            daemon=False,
            name="initial_processor_{}".format(index),
        ).start()
    # sentry_sdk.init(
    #     "https://56e7c26e749c45c585c7123ddd34df7a@o568590.ingest.sentry.io/5713804",
    #     # Set traces_sample_rate to 1.0 to capture 100%
    #     # of transactions for performance monitoring.
    #     # We recommend adjusting this value in production.
    #     traces_sample_rate=1.0,
    # )
    cache.clear()

    configuration = TraccarCredentials.objects.get()
    print_debug()
    while True:
        try:
            traccar = Traccar.create_from_configuration(configuration)
        except Exception:
            logger.exception("Connection error connecting to traccar")
            time.sleep(5)
            continue
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
        ws.run_forever(ping_interval=55)
        logger.warning("Websocket terminated, restarting")
        time.sleep(5)
