import os


if os.environ.get("MODE") != "dev" and os.environ.get("LOG_HANDLER") == "stackdriver":
    handlers = ["json"]
else:
    handlers = ["console"]


LOG_CONFIGURATION = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "skip_healthz": {
            "()": "utilities.logging_filters.HealthCheckFilter",
        },
    },
    "formatters": {
        "standard": {
            "format": "%(asctime)s %(name)-15s: %(funcName)-15s %(levelname)-8s %(message)s",
            "datefmt": "%d/%m/%Y %H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "standard",
            "filters": ["skip_healthz"],
        },
        "json": {
            "level": "DEBUG",
            "class": "google.cloud.logging_v2.handlers.structured_log.StructuredLogHandler",
            "filters": ["skip_healthz"],
        },
    },
    "loggers": {
        "root": {
            "handlers": handlers,
            "level": "INFO",
        },
        "": {"handlers": handlers, "level": "INFO"},
        "celery": {
            "handlers": handlers,
            "level": "INFO",
            "propagate": False,
        },
        "django": {
            "handlers": handlers,
            "level": "INFO",
            "propagate": False,
        },
        "gunicorn": {
            "handlers": handlers,
            "level": "INFO",
            "propagate": False,
        },
        # Request-per-line access logging is the biggest Cloud Logging volume
        # driver in production. Keep warnings/errors from the server stack, but
        # drop routine successful request logs and websocket open/accepted chat.
        "uvicorn.access": {
            "handlers": handlers,
            "level": "WARNING",
            "propagate": False,
        },
        "uvicorn.error": {
            "handlers": handlers,
            "level": "WARNING",
            "propagate": False,
        },
        "websocket": {
            "handlers": handlers,
            "level": "INFO",
            "propagate": False,
        },
        "asyncio": {
            "handlers": handlers,
            "level": "WARNING",
            "propagate": False,
        },
        "aioredis": {
            "handlers": handlers,
            "level": "WARNING",
            "propagate": False,
        },
        "channels_redis": {
            "handlers": handlers,
            "level": "WARNING",
            "propagate": False,
        },
        "daphne": {
            "handlers": handlers,
            "level": "INFO",
            "propagate": False,
        },
        "uvicorn": {
            "handlers": handlers,
            "level": "WARNING",
            "propagate": False,
        },
        "urllib3": {
            "handlers": handlers,
            "level": "INFO",
            "propagate": False,
        },
        "matplotlib": {
            "handlers": handlers,
            "level": "INFO",
            "propagate": False,
        },
        "shapely": {
            "handlers": handlers,
            "level": "INFO",
            "propagate": False,
        },
        "PIL": {
            "handlers": handlers,
            "level": "INFO",
            "propagate": False,
        },
    },
}
