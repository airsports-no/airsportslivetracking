import logging

class HealthCheckFilter(logging.Filter):
    def filter(self, record):
        # Filter out health check logs from various loggers (Django, Daphne, Uvicorn)
        # These typically contain the request path in the message.
        msg = record.getMessage()
        return "/healthz/" not in msg and "/readyz/" not in msg


class DowngradeExpectedFirebaseAuthNoiseFilter(logging.Filter):
    """
    drf_firebase_auth logs some routine, expected auth outcomes at ERROR level via plain
    log.error() calls (not logger.exception()), which is noisy for log-based alerting:
    - "_get_or_create_local_user - User.DoesNotExist" fires on every brand-new user's first
      Firebase sign-in, before FIREBASE_CREATE_LOCAL_USER auto-provisions their local User row.
    - "_decode_token - Exception: Token expired" fires whenever a client presents a token past
      its expiry, which the frontend is expected to refresh and retry.
    Neither indicates an application problem, so downgrade them to INFO (kept, for volume
    trends) rather than ERROR (which pages/alerts).
    """

    _BENIGN_SUBSTRINGS = (
        "_get_or_create_local_user - User.DoesNotExist",
        "_decode_token - Exception: Token expired",
    )

    def filter(self, record):
        if record.levelno >= logging.ERROR and any(s in record.getMessage() for s in self._BENIGN_SUBSTRINGS):
            record.levelno = logging.INFO
            record.levelname = logging.getLevelName(logging.INFO)
        return True
