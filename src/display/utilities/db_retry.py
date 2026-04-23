"""Retry helpers for transient MySQL errors (lock wait timeout, deadlock)."""

import logging
import random
import time
from functools import wraps
from typing import Callable, TypeVar

from django.db import OperationalError

logger = logging.getLogger(__name__)

# MySQL error codes that indicate a transient contention issue.
# The transaction is rolled back by the server, so retrying is safe.
#   1205 — Lock wait timeout exceeded; try restarting transaction
#   1213 — Deadlock found when trying to get lock; try restarting transaction
_RETRYABLE_MYSQL_CODES = (1205, 1213)

T = TypeVar("T")


def is_retryable_lock_error(exc: OperationalError) -> bool:
    code = exc.args[0] if exc.args else None
    return code in _RETRYABLE_MYSQL_CODES


def retry_on_lock_timeout(
    max_attempts: int = 4,
    base_delay: float = 0.1,
    max_delay: float = 2.0,
) -> Callable:
    """Retry a callable on MySQL lock-wait-timeout / deadlock errors.

    Uses exponential backoff with jitter. Non-retryable ``OperationalError``
    codes (and all other exceptions) propagate immediately. Only statements
    that are rolled back by the server should be wrapped — at that point the
    partial work is gone and retrying applies the operation exactly once.
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            attempt = 1
            while True:
                try:
                    return func(*args, **kwargs)
                except OperationalError as exc:
                    if not is_retryable_lock_error(exc) or attempt >= max_attempts:
                        raise
                    delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
                    delay += random.uniform(0, base_delay)
                    logger.warning(
                        "MySQL lock error %s in %s (attempt %d/%d); retrying in %.2fs",
                        exc.args[0] if exc.args else "?",
                        func.__qualname__,
                        attempt,
                        max_attempts,
                        delay,
                    )
                    time.sleep(delay)
                    attempt += 1

        return wrapper

    return decorator
