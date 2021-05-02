import datetime
import sys
import time
import logging
import os

import asyncio

import redis
import sentry_sdk
from opensky_api import OpenSkyApi
from requests import ReadTimeout

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

from ogn.client import AprsClient
from ogn.parser import parse_aprs, ParseError

ws = WebsocketFacade()


def process_beacon(raw_message):
    if raw_message[0] == '#':
        print('Server Status: {}'.format(raw_message))
        return

    try:
        beacon = parse_aprs(raw_message)
        # beacon.update(parse_ogn_beacon(beacon['comment']))
        # print(f"Received beacon {beacon}")
        if beacon.get("aprs_type") == "position":
            beacon["reference_timestamp"] = beacon["reference_timestamp"].replace(tzinfo=datetime.timezone.utc)
            # print(beacon["reference_timestamp"])
            asyncio.run(ws.transmit_external_global_position_data(beacon["name"], beacon["name"], beacon["reference_timestamp"],
                                                  beacon["latitude"], beacon["longitude"], beacon["altitude"],
                                                  beacon["altitude"], beacon["ground_speed"], beacon["track"], "ogn"))
        # print('Received {aprs_type}: {raw_message}'.format(**beacon))
        # print('Received {beacon_type} from {name}'.format(**beacon))
    except ParseError as e:
        print('Error, {}'.format(e.message))


if __name__ == "__main__":
    client = AprsClient(aprs_user='N0CALL')
    client.connect()

    try:
        client.run(callback=process_beacon, autoreconnect=True)
    except KeyboardInterrupt:
        print('\nStop ogn gateway')
        client.disconnect()
