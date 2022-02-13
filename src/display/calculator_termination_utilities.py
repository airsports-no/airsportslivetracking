from django.core.cache import cache

KEY_BASE = "CALCULATOR_TERMINATION_REQUESTED"


def request_termination(contestant_pk: int):
    cache.set(f"{KEY_BASE}_{contestant_pk}", True, timeout=60)


def cancel_termination_request(contestant_pk: int):
    cache.delete(f"{KEY_BASE}_{contestant_pk}")


def is_termination_requested(contestant_pk: int) -> bool:
    return cache.get(f"{KEY_BASE}_{contestant_pk}") is True
