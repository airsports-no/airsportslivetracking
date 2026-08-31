import datetime
import threading
import time
from unittest.mock import MagicMock, patch

from django.test import TransactionTestCase

from display.calculators.contestant_processor import ContestantProcessor
from display.models import Aeroplane, Contest, Contestant, Crew, NavigationTask, Person, Route, Scorecard, Team
from display.models.contestant_track import ContestantTrack
from redis_queue import RedisQueue
from utilities.mock_utilities import TraccarMock


class _DelayedSetEvent(threading.Event):
    """A threading.Event whose set() is delayed, to simulate a slow initial-position load
    (e.g. a large Traccar history fetch) without depending on real Traccar timing."""

    def __init__(self, delay_seconds):
        super().__init__()
        self._delay_seconds = delay_seconds

    def set(self):
        time.sleep(self._delay_seconds)
        super().set()


@patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
@patch("display.calculators.contestant_processor.get_traccar_instance", return_value=TraccarMock)
@patch("display.signals.get_traccar_instance", return_value=TraccarMock)
class TestContestantProcessorStartupHeartbeat(TransactionTestCase):
    """
    Regression test: ContestantProcessor.run() waits on finished_loading_initial_positions with
    no timeout while enqueue_positions_thread performs an unbounded initial Traccar history
    fetch. Without a heartbeat refresh covering that wait, a fetch exceeding the heartbeat's 30s
    TTL lets is_calculator_running() report False while the processor is still starting up,
    letting a broker redelivery spin up a second ContestantProcessor for the same contestant
    against the same Redis queue (same failure class as the shutdown-window race fixed for GH #29).
    """

    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    @patch("display.calculators.contestant_processor.get_traccar_instance", return_value=TraccarMock)
    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, *args):
        self.person = Person.objects.create(first_name="Test", last_name="Pilot")
        self.crew = Crew.objects.create(member1=self.person)
        self.aeroplane = Aeroplane.objects.create(registration="TEST-REG")
        self.team = Team.objects.create(crew=self.crew, aeroplane=self.aeroplane)
        self.route = Route.objects.create(name="Test Route")
        self.scorecard = Scorecard.objects.create(name="Test Scorecard")
        self.contest = Contest.objects.create(
            name="Test Contest",
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc),
        )
        self.navigation_task = NavigationTask.objects.create(
            name="Test Task",
            route=self.route,
            original_scorecard=self.scorecard,
            scorecard=self.scorecard,
            contest=self.contest,
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc),
        )
        self.contestant = Contestant.objects.create(
            team=self.team,
            navigation_task=self.navigation_task,
            takeoff_time=datetime.datetime.now(datetime.timezone.utc),
            finished_by_time=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1),
            tracker_start_time=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=30),
            tracker_device_id="test_device",
            contestant_number=1,
        )
        self.contestant_track = ContestantTrack.objects.get(contestant=self.contestant)

    @patch("display.calculators.contestant_processor.INITIAL_POSITION_LOAD_HEARTBEAT_POLL_SECONDS", 0.05)
    @patch("websocket_channels.WebsocketFacade")
    @patch("display.calculators.contestant_processor.WebsocketFacade")
    @patch("display.calculators.contestant_processor.calculator_factory")
    @patch("display.calculators.contestant_processor.post_slack_competition_message")
    def test_heartbeat_is_renewed_while_waiting_for_initial_positions_to_load(
        self,
        mock_slack,
        mock_calc_factory,
        mock_ws_proc,
        mock_ws_channels,
        *args,
    ):
        mock_calc_factory.return_value = MagicMock()

        q = RedisQueue(self.contestant.pk)
        q.append(None)  # Signal end of positions once the (simulated slow) load finishes.

        processor = ContestantProcessor(self.contestant, live_processing=False)
        # Simulate a slow initial-position load (e.g. a large Traccar history fetch) that takes
        # longer than a single poll interval, without depending on real Traccar timing.
        processor.finished_loading_initial_positions = _DelayedSetEvent(0.3)

        with patch(
            "display.calculators.contestant_processor.calculator_is_alive"
        ) as mock_calculator_is_alive:
            processor.run()
        processor.score_processing_queue.join()

        # run()'s opening line always calls calculator_is_alive(pk, 30) once, before the wait -
        # that alone doesn't cover a load that outlasts the poll interval. The fix is a refresh
        # call (same 30s TTL) on every poll that finds the load still in progress. (The run then
        # continues into the main loop and shutdown, which have their own, separately-tested,
        # heartbeat calls - not asserted on here.)
        ttl_30_calls = [c for c in mock_calculator_is_alive.call_args_list if c.args == (self.contestant.pk, 30)]
        self.assertGreater(
            len(ttl_30_calls),
            1,
            f"expected extra 30s-TTL heartbeat refresh(es) while waiting for initial load, got "
            f"{mock_calculator_is_alive.call_args_list}",
        )
