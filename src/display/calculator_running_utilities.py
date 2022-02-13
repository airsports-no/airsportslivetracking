from django.core.cache import cache

KEY_BASE = "CALCULATOR_RUNNING"


def calculator_is_alive(contestant_pk: int, timeout: float):
    cache.set(f"{KEY_BASE}_{contestant_pk}", True, timeout=timeout)


def calculator_is_terminated(contestant_pk: int):
    cache.delete(f"{KEY_BASE}_{contestant_pk}")


def is_calculator_running(contestant_pk: int) -> bool:
    return cache.get(f"{KEY_BASE}_{contestant_pk}") is True
