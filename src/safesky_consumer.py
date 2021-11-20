import datetime
import sys
import time
import logging
import os

import asyncio

import requests
# import sentry_sdk
from requests import ReadTimeout

if __name__ == "__main__":
    # sentry_sdk.init(
    #     "https://56e7c26e749c45c585c7123ddd34df7a@o568590.ingest.sentry.io/5713804",
    #
    #     # Set traces_sample_rate to 1.0 to capture 100%
    #     # of transactions for performance monitoring.
    #     # We recommend adjusting this value in production.
    #     traces_sample_rate=1.0
    # )
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "live_tracking_map.settings")
    import django

    django.setup()
from websocket_channels import WebsocketFacade

logger = logging.getLogger(__name__)
FETCH_INTERVAL = datetime.timedelta(seconds=5)
API_URL = 'https://public-api.safesky.app/v1/'


class SafeSky:
    def __init__(self, api_key):
        self.api_key = api_key
        self.headers = {
            "x-api-key": self.api_key
        }
    def fetch_positions(self, bounding_box):
        parameters = {
            "viewport": ','.join([str(item) for item in bounding_box])
        }
        # 43.1035, -2.0821, 47.9943, 15.3216
        response = requests.get(API_URL + f"beacons/", params=parameters,headers=self.headers)
        print([item["source"] for item in response.json()])


async def transmit_states(states):
    for state in states:
        if state.time_position and state.latitude and state.longitude and state.velocity and state.geo_altitude:
            altitude_feet = state.geo_altitude * 3.281
            if altitude_feet < 10000:
                timestamp = datetime.datetime.fromtimestamp(state.time_position, datetime.timezone.utc)
                await websocket_facade.transmit_external_global_position_data(state.icao24, state.callsign, timestamp,
                                                                              state.latitude, state.longitude,
                                                                              state.geo_altitude,
                                                                              state.velocity * 1.944,
                                                                              state.heading)


if __name__ == "__main__":
    api_key = sys.argv[1]
    safe_sky = SafeSky(api_key)
    bounding_box = [0, 0, 80, 20]
    safe_sky.fetch_positions(bounding_box)


