import base64
import datetime
import logging

from celery import shared_task, Celery
from celery.schedules import crontab
from django.core.exceptions import ObjectDoesNotExist

from display.map_plotter import generate_flight_orders
from influx_facade import InfluxFacade
from display.models import Contestant, EmailMapLink, MyUser
from playback_tools import insert_gpx_file

influx = InfluxFacade()
logger = logging.getLogger(__name__)

app = Celery()


@app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    # Executes every morning at 7:30 a.m.
    sender.add_periodic_task(
        crontab(hour=7, minute=30, day_of_week="*"),
        delete_old_flight_orders.s(),
    )


@shared_task
def import_gpx_track(contestant_pk: int, gpx_file: str):
    try:
        contestant = Contestant.objects.get(pk=contestant_pk)
    except ObjectDoesNotExist:
        logger.exception("Could not find contestant for contestant key {}".format(contestant_pk))
        return
    insert_gpx_file(contestant, base64.decodebytes(gpx_file.encode("utf-8")), influx)


@app.task
def generate_and_notify_flight_order(contestant_pk: int, email: str, first_name: str):
    try:
        contestant = Contestant.objects.get(pk=contestant_pk)
    except ObjectDoesNotExist:
        logger.exception("Could not find contestant for contestant key {}".format(contestant_pk))
        return
    orders = generate_flight_orders(contestant)
    mail_link = EmailMapLink.objects.create(contestant=contestant, orders=orders)
    mail_link.send_email(email, first_name)


@app.task
def delete_old_flight_orders():
    EmailMapLink.objects.filter(
        contestant__finished_by_time__lt=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=5))
