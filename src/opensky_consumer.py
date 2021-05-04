import datetime
import sys
import time
import logging
import os
import pandas as pd
import asyncio

import redis
import sentry_sdk
from opensky_api import OpenSkyApi
from requests import ReadTimeout
from typing import Optional

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


class AircraftDatabase:
    DEFAULT_TYPE = 9
    OGN_TYPE_MAP = {
        "piston": 8
    }

    def __init__(self):
        self.aircraft_database = pd.read_csv("/aircraft_database/aircraft_database.csv")
        self.aircraft_types = pd.read_csv("/aircraft_database/aircraft_types.csv")

    def _get_type_for_id(self, icao) -> Optional[str]:
        try:
            matches = self.aircraft_database[self.aircraft_database["icao24"].str.contains(icao, na=False)]
            type_code = matches["typecode"].iloc[0]
            if pd.notna(type_code):
                return type_code
            return None
        except IndexError:
            return None

    def _get_ogn_aircraft_type_code_for_aircraft_type(self, aircraft_type_code: str) -> int:
        try:
            aircraft_type = self.aircraft_types[
                self.aircraft_types["Designator"].str.contains(aircraft_type_code, na=False)].iloc[0]
            engine_type = aircraft_type["EngineType"].lower()
            return self.OGN_TYPE_MAP.get(engine_type, self.DEFAULT_TYPE)
        except IndexError:
            return self.DEFAULT_TYPE

    def get_ogn_aircraft_type_code_for_id(self, icao):
        aircraft_type = self._get_type_for_id(icao)
        print(aircraft_type)
        if aircraft_type is not None:
            return self._get_ogn_aircraft_type_code_for_aircraft_type(aircraft_type)
        return self.DEFAULT_TYPE


aircraft_database = AircraftDatabase()
print(f"Type: {aircraft_database.get_ogn_aircraft_type_code_for_id('a808bb')}")


async def transmit_states(states):
    for state in states:
        if state.time_position and state.latitude and state.longitude and state.velocity and state.geo_altitude:
            altitude_feet = state.geo_altitude * 3.281
            if altitude_feet < 10000:
                timestamp = datetime.datetime.fromtimestamp(state.time_position, datetime.timezone.utc)
                await websocket_facade.transmit_external_global_position_data(state.icao24.lower(),
                                                                              state.callsign or "", timestamp,
                                                                              state.latitude, state.longitude,
                                                                              state.geo_altitude,
                                                                              state.baro_altitude,
                                                                              state.velocity * 1.944,
                                                                              state.heading, "opensky",
                                                                              aircraft_type=aircraft_database.get_ogn_aircraft_type_code_for_id(
                                                                                  state.icao24.lower()))


if __name__ == "__main__":
    username, password = sys.argv[1:]
    websocket_facade = WebsocketFacade()
    api = OpenSkyApi(username, password)
    while True:
        logger.info("Fetching states")
        try:
            response = api.get_states()
        except ReadTimeout:
            logger.warning("Timeout")
            time.sleep(1)
            continue
        last_fetch = datetime.datetime.now()
        if response:
            logger.info(f"Received {len(response.states)} states")
            asyncio.run(transmit_states(response.states))
            logger.info("Done")
            elapsed = datetime.datetime.now() - last_fetch
            sleep_interval = (FETCH_INTERVAL - elapsed).total_seconds()
            logger.info(f"Elapsed {elapsed.total_seconds()}, sleeping {sleep_interval}")
            if sleep_interval > 0:
                time.sleep(sleep_interval)
        else:
            logger.warning("Failed fetching")
            time.sleep(1)
