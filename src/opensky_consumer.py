import datetime
import time
import logging
import os
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
FETCH_INTERVAL = datetime.timedelta(seconds=11)
if __name__ == "__main__":
    websocket_facade = WebsocketFacade()
    api = OpenSkyApi()
    while True:
        try:
            states = api.get_states()
        except ReadTimeout:
            time.sleep(3)
            continue
        last_fetch = datetime.datetime.now()
        if states:
            logger.info(f"Received {len(states.states)} states")
            for state in states.states:
                if state.time_position and state.latitude and state.longitude and state.velocity and state.geo_altitude:
                    altitude_feet = state.geo_altitude * 3.281
                    if altitude_feet < 10000:
                        timestamp = datetime.datetime.fromtimestamp(state.time_position, datetime.timezone.utc)
                        websocket_facade.transmit_external_global_position_data(state.icao24, state.callsign, timestamp,
                                                                                state.latitude, state.longitude,
                                                                                state.geo_altitude, state.velocity * 1.944,
                                                                                state.heading)
            logger.info("Done")
            elapsed = datetime.datetime.now() - last_fetch
            sleep_interval = max(2, (FETCH_INTERVAL - elapsed).total_seconds())
            logger.info(f"Elapsed {elapsed.total_seconds()}, sleeping {sleep_interval}")
            time.sleep(sleep_interval)
        else:
            logger.warning("Failed fetching")
            time.sleep(1)

