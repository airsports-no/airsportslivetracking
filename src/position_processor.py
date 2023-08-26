import json
import logging
import os
import threading
import time
from multiprocessing import Process, Queue

import probes

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "live_tracking_map.settings")
    import django

    django.setup()

from traccar_facade import Traccar
from django.core.cache import cache
from django.db import connections

from position_processor_process import initial_processor, LAST_DEBUG_KEY
from live_position_transmitter import live_position_transmitter_process

import websocket

logger = logging.getLogger(__name__)

FAILED_TRACCAR_CONNECTION_COUNT_LIMIT = 10

global_map_queue = Queue()
processing_queue = Queue()

received_messages = 0
failed_traccar_connection_count = 0

disconnected_time = time.time()


def on_message(ws, message):
    global received_messages, failed_traccar_connection_count
    failed_traccar_connection_count = 0
    data = json.loads(message)
    received_messages += 1
    # for item in data.get("positions", []):
    #     logger.debug(f"Received position ID {item['id']} for device ID {item['deviceId']}")
    processing_queue.put(data)


def on_error(ws, error):
    logger.error(f"Websocket error: {error}")


def on_close(ws, *args, **kwargs):
    global disconnected_time
    disconnected_time = time.time()
    print("### closed ###")


def on_open(ws):
    global disconnected_time
    disconnected_time = None
    logger.info(f"Websocket connected")


CONNECTION_CHECK_INTERVAL = 30


def check_connection():
    """
    Used in the main process
    """
    global disconnected_time
    last_debug = cache.get(LAST_DEBUG_KEY)
    if (
        (disconnected_time and time.time() - disconnected_time > 300)
        or not last_debug
        or (time.time() - last_debug > 300)
    ):
        if disconnected_time:
            logger.error(
                f"Websocket has not been connected for 5 minutes, setting liveness probe to false to force a restart."
            )
        elif not last_debug:
            logger.error(f"Last debug time is not in the cache, setting liveness to false")
        else:
            logger.error(f"Loss debug time is {time.time()-last_debug} seconds old, setting liveness to false")
        probes.liveness(False)
    else:
        probes.liveness(True)
    threading.Timer(CONNECTION_CHECK_INTERVAL, check_connection).start()


headers = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.103 Safari/537.36"
}

headers["Upgrade"] = "websocket"

if __name__ == "__main__":
    """
    Incoming positions are first sent to the initial processor. The person or contestant is then forwarded  to the live
    position transmitter process  to appear on the global map and on the air sports data feed.
    """
    django.db.connections.close_all()
    cache.clear()

    Process(
        target=live_position_transmitter_process,
        args=(global_map_queue,),
        daemon=True,
        name="live_position_transmitter",
    ).start()

    logger.info(f"Creating initial processor")
    Process(
        target=initial_processor,
        args=(processing_queue, global_map_queue),
        daemon=False,
        name="initial_processor",
    ).start()

    probes.readiness(True)
    check_connection()
    while True:
        try:
            traccar = Traccar.create_from_configuration()
        except Exception:
            logger.exception("Connection error connecting to traccar")
            time.sleep(5)
            continue
        websocket.enableTrace(False)
        logger.info("Initiating session and getting cookie")
        cookies = traccar.session.cookies.get_dict()
        ws = websocket.WebSocketApp(
            "ws://{}/api/socket".format(traccar.address),
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
            header=headers,
            cookie="; ".join(["%s=%s" % (i, j) for i, j in cookies.items()]),
        )
        ws.run_forever(ping_interval=55)
        failed_traccar_connection_count += 1
        logger.warning(f"Websocket terminated for {failed_traccar_connection_count} consecutive time, restarting")
        time.sleep(5)
