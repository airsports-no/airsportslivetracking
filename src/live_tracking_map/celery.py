from logging.config import dictConfig
import os

import logging
import sys
from pathlib import Path

from celery import Celery

# set the default Django settings module for the 'celery' program.
from celery.signals import after_setup_logger, worker_ready, worker_shutdown, worker_init

from live_tracking_map.celery_bootstrap import LivenessProbe
import log_configuration

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "live_tracking_map.settings")

app = Celery("live_tracking_map")

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()

# Add liveness probe for k8s
app.steps["worker"].add(LivenessProbe)


# Not needed for RabbitMQ
def restore_all_unacknowledged_messages():
    conn = app.connection(transport_options={"visibility_timeout": 0})
    qos = conn.channel().qos
    qos.restore_visible()
    print("Unacknowledged messages restored")


# Not needed for RabbitMQ
@worker_init.connect
def configure(sender=None, conf=None, **kwargs):
    restore_all_unacknowledged_messages()


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
