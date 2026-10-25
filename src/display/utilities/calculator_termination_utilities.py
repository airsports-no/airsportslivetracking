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


def stop_calculators(contestant_pks, timeout_seconds: float = 30.0, poll_seconds: float = 0.5) -> bool:
    """
    Asks the live calculators of these contestants to stop and waits until none of them is running (or the timeout).
    Used before a task or contest is deleted: a calculator that goes on writing scores meanwhile adds rows that the
    delete's collected list does not know about, and the database then refuses to remove the contestant.
    Returns whether all of them had stopped.
    """
    import time

    from display.utilities.calculator_running_utilities import is_calculator_running

    pks = list(contestant_pks)
    running = [pk for pk in pks if is_calculator_running(pk)]
    for pk in running:
        request_termination(pk)
    deadline = time.monotonic() + timeout_seconds
    while running and time.monotonic() < deadline:
        time.sleep(poll_seconds)
        running = [pk for pk in running if is_calculator_running(pk)]
    return not running


# MySQL: 1451 a parent row still has children, 1213 deadlock, 1205 lock wait timeout. All can be caused by a calculator
# or the position processor writing while a delete runs, and a second attempt (which collects the rows again) works.
RETRYABLE_DELETE_ERRORS = {1451, 1213, 1205}


def delete_retrying(delete, attempts: int = 3, delay_seconds: float = 2.0):
    """Runs delete(), again if the database refuses it because of a write that raced with it."""
    import time

    from django.db.utils import IntegrityError, OperationalError

    for attempt in range(1, attempts + 1):
        try:
            return delete()
        except (IntegrityError, OperationalError) as error:
            code = error.args[0] if error.args else None
            if code not in RETRYABLE_DELETE_ERRORS or attempt == attempts:
                raise
            time.sleep(delay_seconds)
