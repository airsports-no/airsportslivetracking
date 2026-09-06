"""
Regression test for GH #760 (a follow-up flagged during code review of #660): ContestantProcessor's
termination handling had an unsynchronized check-and-set race on self.track_terminated between the
threads that can all reach a termination check concurrently (run()'s main loop, the
enqueue_positions_thread() daemon, and score_updater_thread()/update_score_from_thread()). A plain
check-then-act on a bool is not atomic across threads, so more than one thread could pass
check_termination_is_commanded()'s "not yet terminated" guard, each build and enqueue its own
"manually terminated" score-log entry, and each call notify_termination() - which used to call
ContestantTrack.set_calculator_finished() and close the timed queue unconditionally.

_finalize_track_termination() now owns the whole check-and-set, guarded by a re-entrant lock shared
with check_termination_is_commanded()'s own lock use, so exactly one caller ever performs those
side effects and enqueues the score-log entry, no matter how many threads race to request
termination at the same instant.
"""

import datetime
import queue
import threading
import time
from unittest.mock import MagicMock, patch

from django.test import TestCase

from display.calculators.contestant_processor import ContestantProcessor
from display.models import Aeroplane, Contest, Contestant, Crew, NavigationTask, Person, Route, Scorecard, Team
from utilities.mock_utilities import TraccarMock


@patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
@patch("display.calculators.contestant_processor.get_traccar_instance", return_value=TraccarMock)
@patch("display.signals.get_traccar_instance", return_value=TraccarMock)
class TestContestantProcessorTerminationRace(TestCase):
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

    @patch("websocket_channels.WebsocketFacade")
    @patch("display.calculators.contestant_processor.calculator_is_alive")
    @patch("display.calculators.contestant_processor.WebsocketFacade")
    @patch("display.calculators.contestant_processor.get_traccar_instance")
    @patch("display.calculators.contestant_processor.RedisQueue")
    @patch("display.calculators.contestant_processor.calculator_factory")
    @patch("display.calculators.contestant_processor.post_slack_competition_message")
    def test_concurrent_termination_requests_finalize_exactly_once(
        self,
        mock_slack,
        mock_calc_factory,
        mock_redis_queue,
        mock_traccar_factory,
        mock_ws,
        mock_alive,
        mock_ws_channels,
        *args,
    ):
        mock_calc_factory.return_value = MagicMock()
        mock_redis_queue.return_value.pop.return_value = None
        mock_redis_queue.return_value.size = 0

        # threading.Thread is only patched for construction, so ContestantProcessor.__init__
        # doesn't spawn its own real enqueue_positions_thread/score_updater_thread background
        # threads - the test's own threads (created below, after this context exits) must be
        # real ones, or race_to_terminate() below would never actually run.
        with patch("threading.Thread"):
            processor = ContestantProcessor(self.contestant, live_processing=True)
        processor.orchestrator.get_last_gate = MagicMock(return_value=None)

        # A real sleep here (releases the GIL) turns the narrow, timing-dependent
        # check-then-act window into a wide, deterministic one: under the pre-#760 code (no
        # lock around this call), every one of the 12 racing threads gets a real chance to
        # also observe "not yet terminated" and act on it during these 10ms, instead of the
        # race only sometimes landing within a sub-microsecond window. Under the fix, this
        # call happens *inside* _termination_lock, so a sleep here just makes the other 11
        # threads block on the lock a little longer - still resolves to exactly one caller.
        def slow_is_termination_commanded():
            time.sleep(0.01)
            return datetime.datetime.now(datetime.timezone.utc)

        processor.is_termination_commanded = MagicMock(side_effect=slow_is_termination_commanded)
        processor.contestant_track.set_calculator_finished = MagicMock()
        processor.timed_queue.close = MagicMock()

        thread_count = 12
        barrier = threading.Barrier(thread_count)

        def race_to_terminate():
            barrier.wait(timeout=5)
            processor.check_termination_is_commanded(None)

        threads = [threading.Thread(target=race_to_terminate) for _ in range(thread_count)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5)

        self.assertTrue(processor.track_terminated)
        # The whole point of _finalize_track_termination()'s lock: no matter how many
        # threads raced to request termination at once, these idempotent-but-not-free side
        # effects must have run exactly once, not once per racing thread.
        processor.contestant_track.set_calculator_finished.assert_called_once()
        processor.timed_queue.close.assert_called_once()

        # Likewise for check_termination_is_commanded()'s own duplicate-prone side effect: only
        # one "manually terminated" score-log entry should have been enqueued, not one per
        # thread that observed "not yet terminated" before the lock closed the window.
        enqueued_messages = []
        while True:
            try:
                enqueued_messages.append(processor.score_processing_queue.get_nowait())
            except queue.Empty:
                break
        manually_terminated_messages = [
            m for m in enqueued_messages if m is not None and m.message == "manually terminated"
        ]
        self.assertEqual(len(manually_terminated_messages), 1)
