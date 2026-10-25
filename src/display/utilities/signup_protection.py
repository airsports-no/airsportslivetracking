"""
What keeps bots from using the signup form: a hidden field a person never fills in, a signed time stamp from when the
form was shown (a bot submits at once, or without having fetched the form), and a limit on how many accounts one
address can start. Each signup creates a Firebase account and sends a verification email to the address given, so an
unprotected form can be used to send mail to anybody.
"""

import logging
import time
from typing import Optional

from django.core import signing
from django.core.cache import cache

logger = logging.getLogger(__name__)

SALT = "signup-form"
# A person takes longer than this to fill in six fields; a bot does not wait.
MINIMUM_SECONDS = 3
# A form left open longer than this is shown again with a fresh time stamp.
MAXIMUM_SECONDS = 2 * 3600
# Signups started from one address: per hour and per day.
LIMITS = ((3600, 5), (86400, 20))


def new_form_token() -> str:
    return signing.dumps(int(time.time()), salt=SALT)


def token_problem(token: Optional[str], now: Optional[float] = None) -> Optional[str]:
    """None when the token shows the form was fetched and filled in at a human pace, otherwise why not."""
    if not token:
        return "missing"
    try:
        shown_at = signing.loads(token, salt=SALT, max_age=MAXIMUM_SECONDS)
    except signing.SignatureExpired:
        return "expired"
    except signing.BadSignature:
        return "invalid"
    if (now if now is not None else time.time()) - shown_at < MINIMUM_SECONDS:
        return "too_fast"
    return None


def client_ip(request) -> str:
    """
    The address the request came from. Behind Google's load balancer X-Forwarded-For ends with the address the
    balancer saw and its own, so the one before the last: whatever a client puts first in the header does not count.
    """
    forwarded = [part.strip() for part in request.META.get("HTTP_X_FORWARDED_FOR", "").split(",") if part.strip()]
    if len(forwarded) >= 2:
        return forwarded[-2]
    if forwarded:
        return forwarded[0]
    return request.META.get("REMOTE_ADDR", "")


def over_limit(ip: str) -> bool:
    """Counts a signup started from this address, and says whether it is one too many."""
    exceeded = False
    for window, limit in LIMITS:
        key = f"signup-attempts:{window}:{ip}"
        cache.add(key, 0, window)
        try:
            count = cache.incr(key)
        except ValueError:  # expired between add and incr
            cache.set(key, 1, window)
            count = 1
        if count > limit:
            exceeded = True
    return exceeded
