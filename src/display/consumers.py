import datetime
import json
import logging
import threading

from asgiref.sync import async_to_sync
from channels.generic.websocket import WebsocketConsumer
from django.core.exceptions import ObjectDoesNotExist
from redis import StrictRedis

from display.utilities.coordinate_utilities import (
    calculate_bounding_box,
    equirectangular_distance,
)
from display.models import NavigationTask, Contest
from live_tracking_map.settings import (
    REDIS_HOST,
    REDIS_PORT,
    REDIS_PASSWORD,
)
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
        logger.debug(f"Current user {self.scope.get('user')}")
        async_to_sync(self.channel_layer.group_add)(self.navigation_task_group_name, self.channel_name)
        self.groups.append(self.navigation_task_group_name)
        try:
            self.navigation_task = NavigationTask.objects.get(pk=self.navigation_task_pk)
        except ObjectDoesNotExist:
            return
        self.accept()
        # ws = WebsocketFacade()
        # for contestant in self.navigation_task.contestant_set.all():
            # ws.transmit_contestant(contestant)
            # ws.transmit_initial_load(contestant)
        self.transmit_current_time()

    def transmit_current_time(self):
        self.send(
            json.dumps(
                {
                    "type": "current_time",
                    "data": {
                        "current_time": (
                            datetime.datetime.now(datetime.timezone.utc)
                            - datetime.timedelta(
                                seconds=2,
                                minutes=self.navigation_task.calculation_delay_minutes,
                            )
                        )
                        .astimezone(self.navigation_task.contest.time_zone)
                        .strftime("%H:%M:%S"),
                        "current_date_time": (
                            datetime.datetime.now(datetime.timezone.utc)
                            - datetime.timedelta(
                                seconds=2,
                                minutes=self.navigation_task.calculation_delay_minutes,
                            )
                        ).isoformat(),
                    },
                }
            )
        )
        timer = threading.Timer(1, self.transmit_current_time)
        timer.daemon = True
        timer.start()

    def receive(self, text_data, **kwargs):
        pass
        # message = json.loads(text_data)

    def tracking_data(self, event):
        self.send(text_data=json.dumps(event["data"], cls=DateTimeEncoder))


GLOBAL_TRAFFIC_MAXIMUM_AGE = datetime.timedelta(seconds=20)


class GlobalConsumer(WebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.location = None
        self.range = 0
        self.safe_sky_timer = None
        self.bounding_box = None
        # if settings.PRODUCTION:
        #     self.redis = StrictRedis(unix_socket_path="/tmp/docker/redis.sock")
        # else:
        self.redis = StrictRedis(REDIS_HOST, REDIS_PORT, password=REDIS_PASSWORD)
        self.groups.append("tracking_global")

    def connect(self):
        self.accept()
        logger.info(f"Current user {self.scope.get('user')}")
        # Location has not been set at this point
        # if self.location and self.range:
        #     position = (data["latitude"], data["longitude"])
        #     if calculate_distance_lat_lon(position, self.location) > self.range:
        #         continue
        # self.send(text_data=json.dumps(data, cls=DateTimeEncoder))

    def disconnect(self, code):
        super().disconnect(code)
        if self.safe_sky_timer:
            self.safe_sky_timer.cancel()

    def receive(self, text_data, **kwargs):
        message = json.loads(text_data)
        message_type = message.get("type")
        if message_type == "location":
            if (
                type(message.get("latitude")) in (float, int)
                and type(message.get("longitude")) in (float, int)
                and type(message.get("range")) in (float, int)
            ):
                self.location = (message.get("latitude"), message.get("longitude"))
                self.range = message.get("range") * 1000
                logger.debug(f"Setting position to {self.location} with range {self.range}")
                self.bounding_box = calculate_bounding_box(self.location, self.range)
            else:
                self.location = None
                self.range = None

    def tracking_data(self, event):
        if self.location and self.range:
            position = (event["latitude"], event["longitude"])
            if equirectangular_distance(position, self.location) > self.range:
                return
        self.send(text_data=event["data"])


class AirsportsPositionsConsumer(WebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.groups.append("tracking_airsports")

    def tracking_data(self, event):
        """
        Example:
        {
          "name": "LN-YDB",  // Aircraft registration
          "time": "2021-12-12T18:13:08.091000+00:00",  // Time the position was recorded (device time)
          "latitude": 60.3857576,  // Degrees
          "longitude": 11.2679698,  // Degrees
          "altitude": 771.9816119506836,  // Feet (GPS)
          "speed": 0.024247659386761485,  // Knots
          "course": 285.223388671875,  // Degrees
          "navigation_task_id": null,  // id of navigation negative task where the user is competing
          "traffic_source": "airsports"  // 'airsports' is our app
        }


        :param event:
        :return:
        """
        data = event["data"]
        self.send(text_data=data)


class ContestResultsConsumer(WebsocketConsumer):
    def connect(self):
        self.user = self.scope.get("user")
        self.contest_pk = self.scope["url_route"]["kwargs"]["contest_pk"]
        self.contest_results_group_name = "contestresults_{}".format(self.contest_pk)
        self.groups.append(self.contest_results_group_name)
        async_to_sync(self.channel_layer.group_add)(self.contest_results_group_name, self.channel_name)
        try:
            contest = Contest.objects.get(pk=self.contest_pk)
        except ObjectDoesNotExist:
            logger.warning(f"Contest with key {self.contest_pk} does not exist")
            return
        self.accept()
        ws = WebsocketFacade()
        ws.transmit_teams(contest)
        ws.transmit_tasks(contest)
        ws.transmit_tests(contest)
        # Initial contest results must be retrieved through rest to get the correct user credentials
        # ws.transmit_contest_results(self.user, contest)

    def receive(self, text_data, **kwargs):
        message = json.loads(text_data)
        logger.debug(message)

    def contestresults(self, event):
        self.send(text_data=json.dumps(event["content"], cls=DateTimeEncoder))
