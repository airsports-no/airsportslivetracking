import base64
import datetime
import logging

from django.core.cache import cache
from django.db import connections
from celery.schedules import crontab
from django.core.exceptions import ObjectDoesNotExist

from display.generate_flight_orders import generate_flight_orders
from display.models import Contestant, EmailMapLink, MyUser
from live_tracking_map.celery import app
from playback_tools import insert_gpx_file, recalculate_traccar

logger = logging.getLogger(__name__)


@app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    # Executes every morning at 7:30 a.m.
    sender.add_periodic_task(
        crontab(hour=7, minute=30, day_of_week="*"),
        delete_old_flight_orders.s(),
    )
    sender.add_periodic_task(
        10, debug.s()
    )


@app.task
def debug():
    print(debug)


@app.task
def revert_gpx_track_to_traccar(contestant_pk: int):
    try:
        contestant = Contestant.objects.get(pk=contestant_pk)
    except ObjectDoesNotExist:
        logger.exception("Could not find contestant for contestant key {}".format(contestant_pk))
        return
    logger.debug(f"{contestant}: About recalculate traccar track")
    try:
        recalculate_traccar(contestant)
    except:
        logger.exception("Exception in revert_gpx_track_to_traccar")


@app.task
def import_gpx_track(contestant_pk: int, gpx_file: str):
    try:
        contestant = Contestant.objects.get(pk=contestant_pk)
    except ObjectDoesNotExist:
        logger.exception("Could not find contestant for contestant key {}".format(contestant_pk))
        return
    logger.debug(f"{contestant}: About to insert GPX file")
    try:
        insert_gpx_file(contestant, gpx_file.encode("utf-8"))
    except:
        logger.exception("Exception in import_gpx_track")


@app.task
def generate_and_notify_flight_order(contestant_pk: int, email: str, first_name: str):
    try:
        try:
            contestant = Contestant.objects.get(pk=contestant_pk)
        except ObjectDoesNotExist:
            logger.exception("Could not find contestant for contestant key {}".format(contestant_pk))
            return
        try:
            orders = generate_flight_orders(contestant)
            for c in connections.all():
                c.close_if_unusable_or_obsolete()
            mail_link = EmailMapLink.objects.create(contestant=contestant, orders=bytes(orders))
            mail_link.send_email(email, first_name)
        except Exception as e:
            existing_failures = cache.get(f"failed_flight_orders_details_{contestant.navigation_task.pk}") or []
            existing_failures.append(f"{contestant}: {e}")
            cache.set(f"failed_flight_orders_details_{contestant.navigation_task.pk}", existing_failures)
            cache.incr(f"failed_flight_orders_{contestant.navigation_task.pk}")
            raise
        for c in connections.all():
            c.close_if_unusable_or_obsolete()
        cache.incr(f"completed_flight_orders_{contestant.navigation_task.pk}")
    except:
        logger.exception("Exception in generate_and_notify_flight_order")


@app.task
def delete_old_flight_orders():
    EmailMapLink.objects.filter(
        contestant__finished_by_time__lt=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=5))
