import datetime
import json
import sys
import time
import logging
import os

import asyncio

import redis
import sentry_sdk
from opensky_api import OpenSkyApi
from redis import StrictRedis
from requests import ReadTimeout

from live_tracking_map.settings import REDIS_GLOBAL_POSITIONS_KEY

sentry_sdk.init(
    "https://56e7c26e749c45c585c7123ddd34df7a@o568590.ingest.sentry.io/5713804",

    # Set traces_sample_rate to 1.0 to capture 100%
    # of transactions for performance monitoring.
    # We recommend adjusting this value in production.
    traces_sample_rate=1.0
)

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "live_tracking_map.settings")
    import django

    django.setup()

from websocket_channels import WebsocketFacade

logger = logging.getLogger(__name__)
FETCH_INTERVAL = datetime.timedelta(seconds=5)

from display.consumers import DateTimeEncoder
from ogn.client import AprsClient
from ogn.parser import parse, ParseError

ws = WebsocketFacade()

ADDRESS_TYPES = {
    0: "Unknown",
    1: "ICAO",
    2: "Flarm",
    3: "OGN Tracker"
}

FLARM_AIRCRAFT_TYPES = {
    0: "Reserved",
    1: "Glider",
    2: "Tow plane",
    3: "Helicopter",
    4: "Skydiver",
    5: "Drop plane",
    6: "Hang glider",
    7: "Paraglider",
    8: "Airplane combustion engine",
    9: "Airplane jet engine",
    10: "Unknown",
    11: "Balloon",
    12: "Airship",
    13: "UAV",
    14: "Reserved",
    15: "Static"
}


def process_beacon(raw_message):
    if raw_message[0] == '#':
        print('Server Status: {}'.format(raw_message))
        return

    try:
        try:
            beacon = parse(raw_message)
        except NotImplementedError:
            return
        # beacon.update(parse_ogn_beacon(beacon['comment']))
        # print(f"Received beacon {json.dumps(beacon, cls=DateTimeEncoder)}")
        if beacon.get("aprs_type") == "position" and beacon.get("altitude"):
            altitude_feet = beacon["altitude"] * 3.281
            if altitude_feet < 10000 and beacon.get("address"):
                beacon["timestamp"] = beacon["timestamp"].replace(tzinfo=datetime.timezone.utc)
                # print(beacon["reference_timestamp"])
                asyncio.run(
                    ws.transmit_external_global_position_data(beacon.get("address") or beacon["name"], beacon["name"],
                                                              beacon["timestamp"],
                                                              beacon["latitude"], beacon["longitude"],
                                                              beacon["altitude"],
                                                              beacon["altitude"], beacon["ground_speed"],
                                                              beacon["track"],
                                                              "ogn", raw_data=None,
                                                              aircraft_type=beacon["aircraft_type"]))
        # print('Received {aprs_type}: {raw_message}'.format(**beacon))
        # print('Received {beacon_type} from {name}'.format(**beacon))
    except ParseError as e:
        print('Error, {}'.format(e.message))


if __name__ == "__main__":
    redis = StrictRedis("redis")
    redis.delete(REDIS_GLOBAL_POSITIONS_KEY)
    client = AprsClient(aprs_user='N0CALL')
    client.connect()

    try:
        client.run(callback=process_beacon, autoreconnect=True)
    except KeyboardInterrupt:
        print('\nStop ogn gateway')
        client.disconnect()
