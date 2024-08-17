import os


if os.environ.get("MODE") != "dev" and os.environ.get("LOG_HANDLER") == "stackdriver":
    handlers = ["json"]
else:
    handlers = ["console"]


LOG_CONFIGURATION = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s %(name)-15s: %(funcName)-15s %(levelname)-8s %(message)s",
            "datefmt": "%d/%m/%Y %H:%M:%S",
        },
    },
    "handlers": {
        "console": {"level": "DEBUG", "class": "logging.StreamHandler", "formatter": "standard"},
        "json": {"level": "DEBUG", "class": "google.cloud.logging_v2.handlers.structured_log.StructuredLogHandler"},
    },
    "loggers": {
        "root": {
            "handlers": handlers,
            "level": "DEBUG",
        },
        "": {"handlers": handlers, "level": "DEBUG"},
        "celery": {
            "handlers": handlers,
            "level": "INFO",
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
