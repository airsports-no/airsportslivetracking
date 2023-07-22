import datetime
import logging

import redis_lock
from django.core.cache import cache
from django.db import connections
from celery.schedules import crontab
from django.core.exceptions import ObjectDoesNotExist
from redis.client import Redis

from display.flight_order_and_maps.generate_flight_orders import generate_flight_orders_latex
from display.models import Contestant, EmailMapLink
from live_tracking_map.celery import app
from live_tracking_map.settings import REDIS_HOST, REDIS_PORT, REDIS_PASSWORD
from playback_tools.playback import recalculate_traccar, insert_gpx_file

logger = logging.getLogger(__name__)


@app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    # Executes every morning at 7:30 a.m.
    sender.add_periodic_task(
        crontab(hour=7, minute=30, day_of_week="*"),
        delete_old_flight_orders.s(),
    )
    sender.add_periodic_task(10, debug.s())


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


def append_cache_dict(cache_key, dict_key, value):
    conn = Redis(REDIS_HOST, REDIS_PORT, 2)#, REDIS_PASSWORD)
    base = cache_key
    with redis_lock.Lock(conn, f"{base}_lock"):
        dictionary = cache.get(cache_key) or {}
        dictionary[dict_key] = value
        cache.set(cache_key, dictionary)



@app.task
def generate_and_maybe_notify_flight_order(
    contestant_pk: int, email: str, first_name: str, transmit_immediately: bool = False
):
    try:
        try:
            contestant = Contestant.objects.get(pk=contestant_pk)
        except ObjectDoesNotExist:
            logger.exception("Could not find contestant for contestant key {}".format(contestant_pk))
            return
        append_cache_dict(f"completed_flight_orders_map_{contestant.navigation_task.pk}", contestant.pk, False)
        try:
            orders = generate_flight_orders_latex(contestant)
            for c in connections.all():
                c.close_if_unusable_or_obsolete()
            contestant.emailmaplink_set.all().delete()
            mail_link = EmailMapLink.objects.create(contestant=contestant, orders=bytes(orders))
            if transmit_immediately:
                mail_link.send_email(email, first_name)
        except Exception as e:
            append_cache_dict(
                f"generate_failed_flight_orders_map_{contestant.navigation_task.pk}", contestant.pk, str(e)
            )
            raise
        for c in connections.all():
            c.close_if_unusable_or_obsolete()
        append_cache_dict(f"completed_flight_orders_map_{contestant.navigation_task.pk}", contestant.pk, True)
    except:
        logger.exception("Exception in generate_flight_order")


@app.task
def notify_flight_order(contestant_pk: int, email: str, first_name: str):
    try:
        try:
            contestant = Contestant.objects.get(pk=contestant_pk)
        except ObjectDoesNotExist:
            logger.exception("Could not find contestant for contestant key {}".format(contestant_pk))
            return
        try:
            mail_link = EmailMapLink.objects.filter(contestant=contestant).first()
            mail_link.send_email(email, first_name)
        except Exception as e:
            append_cache_dict(
                f"transmit_failed_flight_orders_map_{contestant.navigation_task.pk}", contestant.pk, str(e)
            )
            raise
        for c in connections.all():
            c.close_if_unusable_or_obsolete()
        append_cache_dict(f"transmitted_flight_orders_map_{contestant.navigation_task.pk}", contestant.pk, True)
    except:
        logger.exception("Exception in notify_flight_order")


@app.task
def delete_old_flight_orders():
    EmailMapLink.objects.filter(
        contestant__finished_by_time__lt=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=5)
    ).delete()
