"""When did the server last hear from a tracking device, regardless of the task's calculation delay.

ContestantReceivedPosition (and so a contestant's `last_position_time`) is written only after a position has passed
through the calculator's delay (navigation task `calculation_delay_minutes`), so it lags the real reception by that
delay. The position processor therefore also records the device time of every position the moment it arrives, and the
pilot app reads that to tell whether its own positions are getting through.
"""

import datetime
from typing import Optional

from django.core.cache import cache

RECEIVED_TTL_SECONDS = 6 * 3600


def _key(device_name: str) -> str:
    return f"last_received_position_{device_name}"


def _position_key(device_name: str) -> str:
    return f"last_received_coordinates_{device_name}"


# The coordinates are kept for the admin statistics only, so they are refreshed at most this often per device.
COORDINATES_REFRESH_SECONDS = 5


def note_position_received(
    device_name: str,
    device_time: datetime.datetime,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
) -> None:
    # A report that arrives late must not move the time back: keep the newest device time seen
    current = cache.get(_key(device_name))
    if current is None or device_time > current:
        cache.set(_key(device_name), device_time, RECEIVED_TTL_SECONDS)
    if latitude is not None and longitude is not None:
        stored = cache.get(_position_key(device_name))
        if stored is None or device_time >= stored["time"] + datetime.timedelta(seconds=COORDINATES_REFRESH_SECONDS):
            cache.set(_position_key(device_name), {"latitude": latitude, "longitude": longitude, "time": device_time}, RECEIVED_TTL_SECONDS)


def last_received_coordinates(device_name: Optional[str]) -> Optional[dict]:
    """The last position that arrived from the device ({latitude, longitude, time}), a few seconds old at most, if known."""
    if not device_name:
        return None
    return cache.get(_position_key(device_name))


def last_received_position_time(device_name: Optional[str]) -> Optional[datetime.datetime]:
    if not device_name:
        return None
    return cache.get(_key(device_name))
