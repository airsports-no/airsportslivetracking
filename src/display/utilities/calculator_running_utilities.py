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


def count_all_running(redis_connection) -> int:
    """
    Counts every live CALCULATOR_RUNNING_* heartbeat key directly in Redis, independent of any
    schedule query - unlike count_running(contestant_pks) above, which can only ever report a
    subset of whatever pks it's handed.

    calculator_pool_scaler.desired_replicas() relies on running+queued being a genuinely
    independent floor derived from what's actually happening on the broker/heartbeat side, so a
    gap in the schedule query can never cause a shrink that evicts a live contestant. Passing it
    count_running(scheduled_pks) (the same pks the schedule query just produced) can't provide
    that: running <= len(scheduled_pks) always, collapsing the floor to just the schedule query's
    own opinion. A calculator can legitimately still be running with its contestant no longer in
    that query's result - e.g. draining its position queue past finished_by_time
    (contestant_processor.py's queue-drain wait), or should_i_terminate() advancing
    finished_by_time to an inferred landing time - and count_running would silently exclude it.

    Uses SCAN (cursor-based, non-blocking), not KEYS, and cache.make_key() to build the pattern
    so it's correct regardless of the cache's KEY_PREFIX/VERSION settings.
    """
    pattern = cache.make_key(f"{KEY_BASE}_") + "*"
    return sum(1 for _ in redis_connection.scan_iter(match=pattern, count=100))


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
