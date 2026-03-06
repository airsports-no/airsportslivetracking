from django.core.cache import cache

import datetime

KEY_BASE = "CALCULATOR_TERMINATION_REQUESTED"


def request_termination(contestant_pk: int):
    cache.set(f"{KEY_BASE}_{contestant_pk}", datetime.datetime.now(datetime.timezone.utc))


def cancel_termination_request(contestant_pk: int):
    cache.delete(f"{KEY_BASE}_{contestant_pk}")


def is_termination_requested(contestant_pk: int) -> datetime.datetime:
    return cache.get(f"{KEY_BASE}_{contestant_pk}")
