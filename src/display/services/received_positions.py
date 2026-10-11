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


def note_position_received(device_name: str, device_time: datetime.datetime) -> None:
    cache.set(_key(device_name), device_time, RECEIVED_TTL_SECONDS)


def last_received_position_time(device_name: Optional[str]) -> Optional[datetime.datetime]:
    if not device_name:
        return None
    return cache.get(_key(device_name))
