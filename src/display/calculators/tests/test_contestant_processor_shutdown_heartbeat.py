import datetime
from unittest.mock import MagicMock, patch

from django.test import TransactionTestCase

from display.calculators.contestant_processor import ContestantProcessor
from display.models import Aeroplane, Contest, Contestant, Crew, NavigationTask, Person, Route, Scorecard, Team
from display.models.contestant_track import ContestantTrack
from display.utilities.calculator_running_utilities import calculator_is_alive, is_calculator_running
from redis_queue import RedisQueue
from utilities.mock_utilities import TraccarMock


@patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
@patch("display.calculators.contestant_processor.get_traccar_instance", return_value=TraccarMock)
@patch("display.signals.get_traccar_instance", return_value=TraccarMock)
class TestContestantProcessorShutdownHeartbeat(TransactionTestCase):
    """
    Regression test for GH #29: between the main loop exiting and the final
    calculator_is_terminated() call, ContestantProcessor.run() drains the position queue and
    joins its two background threads - work that isn't bounded by the <=5s heartbeat refresh
    cadence used while the loop is running. Without a fresh calculator_is_alive() call covering
    that window, a slow drain/join can outlast the heartbeat's 30s TTL and let
    is_calculator_running() report False while the processor is still shutting down, letting a
    "Restart calculator" click race a second ContestantProcessor against this one instead of
    waiting for it to actually finish.
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

    @patch("websocket_channels.WebsocketFacade")
    @patch("display.calculators.contestant_processor.WebsocketFacade")
    @patch("display.calculators.contestant_processor.calculator_factory")
    @patch("display.calculators.contestant_processor.post_slack_competition_message")
    def test_heartbeat_is_renewed_before_the_drain_and_join_cleanup(
        self,
        mock_slack,
        mock_calc_factory,
        mock_ws_proc,
        mock_ws_channels,
        *args,
    ):
        mock_calc_factory.return_value = MagicMock()

        q = RedisQueue(self.contestant.pk)
        q.append(None)  # Immediately signal end of positions.

        processor = ContestantProcessor(self.contestant, live_processing=False)
        with patch(
            "display.calculators.contestant_processor.calculator_is_alive", wraps=calculator_is_alive
        ) as spy_calculator_is_alive:
            processor.run()
        processor.score_processing_queue.join()

        # run()'s opening line always calls calculator_is_alive(pk, 30) once, before the loop -
        # that alone doesn't cover the drain/join cleanup below it. The fix is a second,
        # cleanup-phase call (with a longer timeout) right before that cleanup starts.
        calls = spy_calculator_is_alive.call_args_list
        self.assertGreaterEqual(len(calls), 2, f"expected an extra heartbeat refresh in cleanup, got {calls}")
        self.assertEqual(calls[-1].args, (self.contestant.pk, 60))

        # calculator_is_terminated() still runs last and clears the key for real once cleanup
        # (which was instantaneous here) has actually completed.
        self.assertFalse(is_calculator_running(self.contestant.pk))
