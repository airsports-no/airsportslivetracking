import json
import logging
import os
import threading
from datetime import datetime
from typing import List, TYPE_CHECKING

from django.core.cache import cache

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "live_tracking_map.settings")
    import django

    django.setup()

if TYPE_CHECKING:
    from display.calculators.calculator import Calculator
from traccar_facade import Traccar

import websocket
from influx_facade import InfluxFacade
from display.models import Contestant, TraccarCredentials, ContestantTrack, CONTESTANT_CACHE_KEY
from display.calculators.calculator_factory import calculator_factory

logger = logging.getLogger(__name__)

configuration = TraccarCredentials.objects.get()

if __name__ == "__main__":
    traccar = Traccar.create_from_configuration(configuration)
    devices = traccar.get_device_map()
influx = InfluxFacade()
calculators = {}
position_buffer = {}
POSITION_BUFFER_SIZE = 5
calculator_lock = threading.Lock()


def add_positions_to_calculator(contestant: Contestant, positions: List):
    if contestant.pk not in calculators:
        contestant_track, _ = ContestantTrack.objects.get_or_create(contestant=contestant)
        if contestant_track.calculator_finished:
            return
        calculators[contestant.pk] = calculator_factory(contestant, influx, live_processing=False)
        calculators[contestant.pk].start()
    calculator = calculators[contestant.pk]  # type: Calculator
    new_positions = []
    for position in positions:
        data = position["fields"]
        data["time"] = position["time"]
        new_positions.append(data)
    calculator.add_positions(new_positions)


def cleanup_calculators():
    for key, calculator in dict(calculators).items():
        if not calculator.is_alive():
            calculators.pop(key)


def build_and_push_position_data(data):
    # logger.info("Received data")
    with calculator_lock:
        received_positions = influx.generate_position_data(traccar, data.get("positions", []))
        for contestant, positions in received_positions.items():
            # logger.info("Positions for {}".format(contestant))
            add_positions_to_calculator(contestant, positions)
            # logger.info("Positions to calculator for {}".format(contestant))
            if len(positions) > 0:
                latest_time = None
                for item in positions:
                    if latest_time is None:
                        latest_time = item.pop("time_object")
                    else:
                        current_time = item.pop("time_object")
                        if current_time > latest_time:
                            latest_time = current_time
                progress = contestant.calculate_progress(latest_time)
                influx.put_position_data_for_contestant(contestant, positions, progress)
                # logger.info("Positions to influx for {}".format(contestant))
                key = "{}.{}.*".format(CONTESTANT_CACHE_KEY, contestant.pk)
                # logger.info("Clearing cache for {}".format(contestant))
                cache.delete_pattern(key)
        cleanup_calculators()


def on_message(ws, message):
    data = json.loads(message)
    build_and_push_position_data(data)


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
