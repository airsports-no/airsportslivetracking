from logging.config import dictConfig
import os

import logging
import sys
from pathlib import Path

from celery import Celery

# set the default Django settings module for the 'celery' program.
from celery.signals import after_setup_logger, worker_ready, worker_shutdown

from live_tracking_map.celery_bootstrap import LivenessProbe
import log_configuration

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "live_tracking_map.settings")

# The scheduler (tracker-celery-beat) only sends task names from CELERY_BEAT_SCHEDULE and never runs a task. Without
# celery's Django integration it reads the settings but does not set Django up, so none of the application code
# (models, admin, matplotlib through the task modules) is loaded: about 120MB instead of 410MB. Skipping
# autodiscover_tasks alone is not enough, django.setup() imports display.tasks all the same.
BEAT_ONLY = bool(os.environ.get("CELERY_BEAT_ONLY"))

app = Celery("live_tracking_map", fixups=[]) if BEAT_ONLY else Celery("live_tracking_map")
if BEAT_ONLY:
    # The Django integration is also what keeps the source directory on the import path, which the logging
    # configuration needs (utilities.logging_filters)
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Load task modules from all registered Django app configs.
if not BEAT_ONLY:
    app.autodiscover_tasks()

# Add liveness probe for k8s
app.steps["worker"].add(LivenessProbe)


@after_setup_logger.connect()
def logger_setup_handler(logger, **kwargs):
    dictConfig(log_configuration.LOG_CONFIGURATION)
    logging.info("My log handler connected -> Global Logging")


@app.task(bind=True)
def debug_task(self):
    print(f"Request: {self.request!r}")


# File for validating worker readiness
READINESS_FILE = Path("/tmp/celery_ready")


@worker_ready.connect
def worker_ready(**_):
    READINESS_FILE.touch()


@worker_shutdown.connect
def worker_shutdown(**_):
    READINESS_FILE.unlink(missing_ok=True)
