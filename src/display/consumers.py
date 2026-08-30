import datetime
import json
import logging
import threading

from asgiref.sync import async_to_sync, sync_to_async
from channels.consumer import SyncConsumer
from channels.generic.websocket import WebsocketConsumer
from django.core.exceptions import ObjectDoesNotExist

from display.models import NavigationTask, Contest
from websocket_channels import WebsocketFacade

logger = logging.getLogger(__name__)


class ParallelDispatchMixin(SyncConsumer):
    """
    Channels' SyncConsumer.dispatch is wrapped with @database_sync_to_async, which defaults to
    thread_sensitive=True - asgiref then pins ALL sync-consumer dispatch (every event: connect,
    receive, disconnect, every group-handler call) for the WHOLE ASGI process onto one single
    shared thread (asgiref.sync.SyncToAsync.single_thread_executor, a class-level
    ThreadPoolExecutor(max_workers=1); verified against asgiref 3.12.1 sources - Channels never
    establishes a per-connection ThreadSensitiveContext to opt out of this). A slow handler on
    one connection (e.g. ContestResultsConsumer.connect's DB query + full serialization) blocks
    every other connection's message processing on the same pod, including simple ping/pong
    keepalives, which can cascade into a mass-reconnect storm right when a pod rollout already
    closed every socket at once.

    thread_sensitive=False lets asgiref dispatch to its normal (much larger, per asgiref's own
    default sizing) thread pool instead. This is Django/Channels' own documented escape hatch for
    exactly this situation, not a workaround: each dispatch() call is a self-contained unit of
    work that still gets a normal per-thread Django DB connection, the same way a plain
    synchronous view running under gunicorn already works - there's no shared mutable state
    between separate dispatch calls for thread_sensitive=True to protect here (confirmed: all
    three consumers below only touch per-instance `self.` attributes).
    """

    # SyncConsumer.dispatch (attribute access) triggers SyncToAsync's descriptor protocol and
    # returns a bound partial, not the raw function - __dict__ access bypasses that and gets the
    # actual DatabaseSyncToAsync wrapper instance, whose .func is the original undecorated
    # dispatch() Channels defines.
    dispatch = sync_to_async(SyncConsumer.__dict__["dispatch"].func, thread_sensitive=False)


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


class TrackingConsumer(ParallelDispatchMixin, WebsocketConsumer):
    def connect(self):
        self.navigation_task_pk = self.scope["url_route"]["kwargs"]["navigation_task"]
        self.navigation_task_group_name = "tracking_{}".format(self.navigation_task_pk)
        user = self.scope.get("user")
        logger.debug(f"Current user {user}")
        try:
            self.navigation_task = NavigationTask.objects.get(pk=self.navigation_task_pk)
        except (ObjectDoesNotExist, ValueError):
            logger.warning(f"NavigationTask with key {self.navigation_task_pk} does not exist or is invalid")
            # Must close rather than just return: returning without either
            # accepting or closing leaves the handshake unanswered, so the
            # client waits on a socket the server has no intention of using.
            self.close()
            return
        # Mirrors the REST equivalent (NavigationTaskPublicPutDeletePermissions /
        # NavigationTaskContestPermissions): a private/unlisted task is only visible to someone
        # with view_contest on the contest. Previously this consumer only checked the row
        # existed, so any anonymous client could subscribe to live positions, score-log entries,
        # gate scores and full contestant records for a private task by guessing its pk.
        is_publicly_visible = self.navigation_task.is_public and self.navigation_task.contest.is_public
        has_view_permission = bool(user) and user.is_authenticated and user.has_perm(
            "display.view_contest", self.navigation_task.contest
        )
        if not is_publicly_visible and not has_view_permission:
            logger.warning(
                f"Rejected websocket connection to navigation task {self.navigation_task_pk}: "
                f"not authorized for user {user}"
            )
            self.close()
            return
        async_to_sync(self.channel_layer.group_add)(self.navigation_task_group_name, self.channel_name)
        self.groups.append(self.navigation_task_group_name)
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


class AirsportsPositionsConsumer(ParallelDispatchMixin, WebsocketConsumer):
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


class ContestResultsConsumer(ParallelDispatchMixin, WebsocketConsumer):
    def connect(self):
        self.user = self.scope.get("user")
        self.contest_pk = self.scope["url_route"]["kwargs"]["contest_pk"]
        self.contest_results_group_name = "contestresults_{}".format(self.contest_pk)
        try:
            contest = Contest.objects.get(pk=self.contest_pk)
        except (ObjectDoesNotExist, ValueError):
            logger.warning(f"Contest with key {self.contest_pk} does not exist or is invalid")
            # See TrackingConsumer.connect - an unanswered handshake leaves the client hanging.
            self.close()
            return
        # Mirrors the REST equivalent's visibility rule - see TrackingConsumer.connect. Previously
        # this consumer only checked the contest row existed, so any anonymous client could
        # subscribe to a private contest's results and receive a full team/task/test dump on
        # connect.
        has_view_permission = bool(self.user) and self.user.is_authenticated and self.user.has_perm(
            "display.view_contest", contest
        )
        if not contest.is_public and not has_view_permission:
            logger.warning(
                f"Rejected websocket connection to contest results {self.contest_pk}: "
                f"not authorized for user {self.user}"
            )
            self.close()
            return
        self.groups.append(self.contest_results_group_name)
        async_to_sync(self.channel_layer.group_add)(self.contest_results_group_name, self.channel_name)
        self.accept()
        ws = WebsocketFacade()
        # channel_name=self.channel_name: unicast the initial dump to just this connection,
        # not group_send to the whole contestresults_<pk> group - every already-connected
        # viewer used to get a redundant full teams/tasks/tests dump whenever *anyone*
        # connected, O(N^2) messages for N viewers, which self-amplifies into a reconnect
        # storm exactly when a pod rollout closes every socket at once during a live contest.
        ws.transmit_teams(contest, channel_name=self.channel_name)
        ws.transmit_tasks(contest, channel_name=self.channel_name)
        ws.transmit_tests(contest, channel_name=self.channel_name)
        # Initial contest results must be retrieved through rest to get the correct user credentials
        # ws.transmit_contest_results(self.user, contest)

    def receive(self, text_data, **kwargs):
        message = json.loads(text_data)
        logger.debug(message)

    def contestresults(self, event):
        self.send(text_data=json.dumps(event["content"], cls=DateTimeEncoder))
