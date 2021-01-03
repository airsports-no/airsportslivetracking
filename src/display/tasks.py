import base64
import logging
from typing import TYPE_CHECKING

from celery import shared_task
from django.core.exceptions import ObjectDoesNotExist

from influx_facade import InfluxFacade
from display.models import Contestant
from playback_tools import insert_gpx_file

influx = InfluxFacade()
logger=logging.getLogger(__name__)

@shared_task
def import_gpx_track(contestant_pk: int, gpx_file: str):
    try:
        contestant = Contestant.objects.get(pk=contestant_pk)
    except ObjectDoesNotExist:
        logger.exception("Could not find contestant for contestant key {}".format(contestant_pk))
        raise
    insert_gpx_file(contestant, base64.decodebytes(gpx_file.encode("utf-8")), influx)
