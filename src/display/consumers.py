import datetime
import json
import logging

from asgiref.sync import async_to_sync
from channels.generic.websocket import WebsocketConsumer
from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist

from display.models import NavigationTask
from display.views import cached_generate_data

logger = logging.getLogger(__name__)


class DateTimeEncoder(json.JSONEncoder):
    """
    Helper class to correctly encode datetime objects to json.
    """

    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            encoded_object = obj.isoformat()
        else:
            encoded_object = json.JSONEncoder.default(self, obj)
        return encoded_object


class TrackingConsumer(WebsocketConsumer):
    def connect(self):
        self.navigation_task_pk = self.scope["url_route"]["kwargs"]["navigation_task"]
        self.navigation_task_group_name = "tracking_{}".format(self.navigation_task_pk)

        async_to_sync(self.channel_layer.group_add)(
            self.navigation_task_group_name,
            self.channel_name
        )
        try:
            navigation_task = NavigationTask.objects.get(pk=self.navigation_task_pk)
        except ObjectDoesNotExist:
            return
        self.accept()
        for contestant in navigation_task.contestant_set.all():
            self.send(json.dumps(cached_generate_data(contestant.pk, None), cls=DateTimeEncoder))

    def disconnect(self, code):
        async_to_sync(self.channel_layer.group_discard)(
            self.navigation_task_group_name,
            self.channel_name
        )

    def receive(self, text_data, **kwargs):
        message = json.loads(text_data)
        logger.info(message)

    def tracking_data(self, event):
        data = event["data"]
        # logger.info("Received data: {}".format(data))
        try:
            self.send(text_data=json.dumps(data["data"], cls=DateTimeEncoder))
        except KeyError:
            logger.exception("Did not find expected data block in {}".format(data))


class GlobalConsumer(WebsocketConsumer):
    def connect(self):
        self.group_name = "tracking_global"

        async_to_sync(self.channel_layer.group_add)(
            self.group_name,
            self.channel_name
        )
        self.accept()
        existing = cache.get("GLOBAL_MAP_DATA") or {}
        for age, data in existing.values():
            self.send(json.dumps(data))

    def disconnect(self, code):
        async_to_sync(self.channel_layer.group_discard)(
            self.group_name,
            self.channel_name
        )

    def receive(self, text_data, **kwargs):
        message = json.loads(text_data)
        logger.info(message)

    def tracking_data(self, event):
        data = event["data"]
        # logger.info("Received data: {}".format(data))
        self.send(text_data=json.dumps(data, cls=DateTimeEncoder))
