from django.core.cache import cache

KEY_BASE = "CALCULATOR_RUNNING"
# Separate from KEY_BASE on purpose: KEY_BASE is set only by the live
# processor's own heartbeat (ContestantProcessor.run(), refreshed every <=5s
# with a 30s TTL) once it is actually processing positions. DISPATCH_PENDING_KEY_BASE
# is the short-lived "a task has been handed to Celery but may not have started
# yet" marker set by add_positions_to_calculator - conflating the two meant a
# redelivered/duplicate Celery task had no way to tell "already running" apart
# from "dispatch in flight", so it would start a second ContestantProcessor on
# the same contestant. See run_live_contestant_calculator (display/tasks.py).
DISPATCH_PENDING_KEY_BASE = "CALCULATOR_DISPATCH_PENDING"


def calculator_is_alive(contestant_pk: int, timeout: float):
    cache.set(f"{KEY_BASE}_{contestant_pk}", True, timeout=timeout)


def calculator_is_terminated(contestant_pk: int):
    cache.delete(f"{KEY_BASE}_{contestant_pk}")


def is_calculator_running(contestant_pk: int) -> bool:
    return cache.get(f"{KEY_BASE}_{contestant_pk}") is True


def count_running(contestant_pks) -> int:
    """
    Batched version of is_calculator_running for a collection of pks - used by
    src/calculator_pool_scaler.py, which needs a count, not a per-contestant
    check, and would otherwise be one cache round-trip per contestant.
    """
    contestant_pks = list(contestant_pks)
    if not contestant_pks:
        return 0
    keys = [f"{KEY_BASE}_{pk}" for pk in contestant_pks]
    values = cache.get_many(keys)
    return sum(1 for value in values.values() if value is True)


def calculator_dispatch_pending(contestant_pk: int, timeout: float):
    """
    Marks that a calculator task has just been dispatched to Celery for this
    contestant, before it has necessarily started (and therefore before its
    own heartbeat via calculator_is_alive has had a chance to land). Cleared
    implicitly by TTL once the real heartbeat should have taken over - see the
    module docstring above.
    """
    cache.set(f"{DISPATCH_PENDING_KEY_BASE}_{contestant_pk}", True, timeout=timeout)


def is_dispatch_pending(contestant_pk: int) -> bool:
    return cache.get(f"{DISPATCH_PENDING_KEY_BASE}_{contestant_pk}") is True
