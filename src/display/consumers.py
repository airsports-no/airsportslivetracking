import datetime
import json
import logging
import pickle

import dateutil.parser
from asgiref.sync import async_to_sync
from channels.generic.websocket import WebsocketConsumer
from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist
from redis import StrictRedis

from display.coordinate_utilities import calculate_distance_lat_lon, calculate_bounding_box
from display.models import NavigationTask, Contest
from display.views import cached_generate_data
from live_tracking_map.settings import REDIS_GLOBAL_POSITIONS_KEY
from websocket_channels import WebsocketFacade

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
        logger.info(f"Current user {self.scope.get('user')}")
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
            self.send(json.dumps(cached_generate_data(contestant.pk), cls=DateTimeEncoder))

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
        self.send(text_data=json.dumps(data, cls=DateTimeEncoder))


GLOBAL_TRAFFIC_MAXIMUM_AGE = datetime.timedelta(seconds=20)


class GlobalConsumer(WebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.location = None
        self.range = 0
        self.safe_sky_timer = None
        self.bounding_box = None
        self.redis = StrictRedis("redis")

    def connect(self):
        self.group_name = "tracking_global"
        logger.info(f"Current user {self.scope.get('user')}")
        async_to_sync(self.channel_layer.group_add)(
            self.group_name,
            self.channel_name
        )
        self.accept()
        existing = cache.get("GLOBAL_MAP_DATA") or {}
        for age, data in existing.values():
            try:
                self.send(json.dumps(data['data']))
            except KeyError:
                logger.exception("Did not find expected data block in {}".format(data))
        cached = self.redis.hgetall(REDIS_GLOBAL_POSITIONS_KEY)
        now = datetime.datetime.now(datetime.timezone.utc)
        for key, value in cached.items():
            data = pickle.loads(value)
            stamp = data["time"]
            if now - stamp > GLOBAL_TRAFFIC_MAXIMUM_AGE:
                self.redis.hdel(REDIS_GLOBAL_POSITIONS_KEY, key)
                continue
            if self.location and self.range:
                position = (data["latitude"], data["longitude"])
                if calculate_distance_lat_lon(position, self.location) > self.range:
                    continue
            self.send(text_data=json.dumps(data, cls=DateTimeEncoder))

    def disconnect(self, code):
        async_to_sync(self.channel_layer.group_discard)(
            self.group_name,
            self.channel_name
        )
        if self.safe_sky_timer:
            self.safe_sky_timer.cancel()

    def receive(self, text_data, **kwargs):
        logger.info(text_data)
        message = json.loads(text_data)
        message_type = message.get("type")
        if message_type == "location":
            if type(message.get("latitude")) in (float, int) and type(message.get("longitude")) in (
                    float, int) and type(
                message.get("range")) in (float, int):
                self.location = (message.get("latitude"), message.get("longitude"))
                self.range = message.get("range") * 1000
                logger.info(f"Setting position to {self.location} with range {self.range}")
                self.bounding_box = calculate_bounding_box(self.location, self.range)
            else:
                self.location = None
                self.range = None

    def tracking_data(self, event):
        data = json.loads(event["data"])
        if self.location and self.range:
            position = (data["latitude"], data["longitude"])
            if calculate_distance_lat_lon(position, self.location) > self.range:
                return
        # logger.info("Received data: {}".format(data))
        self.send(text_data=event["data"])


class ContestResultsConsumer(WebsocketConsumer):
    def connect(self):
        self.user = self.scope.get("user")
        self.contest_pk = self.scope["url_route"]["kwargs"]["contest_pk"]
        self.contest_results_group_name = "contestresults_{}".format(self.contest_pk)

        async_to_sync(self.channel_layer.group_add)(
            self.contest_results_group_name,
            self.channel_name
        )
        try:
            contest = Contest.objects.get(pk=self.contest_pk)
        except ObjectDoesNotExist:
            return
        self.accept()
        ws = WebsocketFacade()
        ws.transmit_teams(contest)
        ws.transmit_tasks(contest)
        ws.transmit_tests(contest)
        # Initial contest results must be retrieved through rest to get the correct user credentials
        # ws.transmit_contest_results(self.user, contest)

    def disconnect(self, code):
        async_to_sync(self.channel_layer.group_discard)(
            self.contest_results_group_name,
            self.channel_name
        )

    def receive(self, text_data, **kwargs):
        message = json.loads(text_data)
        logger.info(message)

    def contestresults(self, event):
        self.send(text_data=json.dumps(event["content"], cls=DateTimeEncoder))
