import datetime
import json
import logging
import threading

from asgiref.sync import async_to_sync
from channels.generic.websocket import WebsocketConsumer
from django.core.exceptions import ObjectDoesNotExist

from display.models import NavigationTask, Contest
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
        except (ObjectDoesNotExist, ValueError):
            logger.warning(f"NavigationTask with key {self.navigation_task_pk} does not exist or is invalid")
            # Must close rather than just return: returning without either
            # accepting or closing leaves the handshake unanswered, so the
            # client waits on a socket the server has no intention of using,
            # and the group subscription added above is never discarded.
            self.close()
            return
        self.accept()

    def receive(self, text_data, **kwargs):
        try:
            message = json.loads(text_data)
            if message.get("type") == "ping":
                self.send(text_data=json.dumps({"type": "pong"}))
        except json.JSONDecodeError:
            logger.debug(f"Received non-JSON message: {text_data}")
        # pass
        # message = json.loads(text_data)

    def tracking_data(self, event):
        self.send(text_data=json.dumps(event["data"], cls=DateTimeEncoder))


class AirsportsPositionsConsumer(WebsocketConsumer):
    """
    ws/traffic/airsports/ - the outbound live-traffic feed ASLT provides for
    external partners (SafeSky) to consume, not something ASLT consumes.
    Fed by live_position_transmitter.py's transmit_airsports_position_data:
    only non-simulator positions (Person.simulator_tracking_id help_text:
    "Persons or contestants identified by this field should not be displayed
    on the global map") within EXTERNAL_TRAFFIC_MAX_AGE_SECONDS seconds of "now" are
    forwarded, so an app/simulator-tracked contestant never appears here even
    though it scores normally.
    """

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
        except (ObjectDoesNotExist, ValueError):
            logger.warning(f"Contest with key {self.contest_pk} does not exist or is invalid")
            # See TrackingConsumer.connect - an unanswered handshake leaves the
            # client hanging and leaks the group subscription.
            self.close()
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
