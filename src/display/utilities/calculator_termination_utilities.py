from django.core.cache import cache
import datetime
from typing import Optional

KEY_BASE = "CALCULATOR_TERMINATION_REQUESTED"


def request_termination(contestant_pk: int):
    cache.set(f"{KEY_BASE}_{contestant_pk}", datetime.datetime.now(datetime.timezone.utc))


def cancel_termination_request(contestant_pk: int):
    cache.delete(f"{KEY_BASE}_{contestant_pk}")


def is_termination_requested(contestant_pk: int) -> Optional[datetime.datetime]:
    val = cache.get(f"{KEY_BASE}_{contestant_pk}")
    if val is True:
        # Fallback for old boolean values in cache
        return datetime.datetime.now(datetime.timezone.utc)
    if isinstance(val, datetime.datetime) and val.tzinfo is None:
        val = val.replace(tzinfo=datetime.timezone.utc)
    return val
