"""
Regression test for calculators finding #1 (2026-08-28 review):
check_termination_is_commanded referenced self.route, which ContestantProcessor never sets
(only Calculator.__init__ does, and ContestantProcessor is not a Calculator subclass). Hit
whenever a manual termination is requested while position is None and
orchestrator.get_last_gate() is None - a normal pre-first-position state, and permanent for
POKER/LANDING tasks (their calculators never emit NextGateExpectedEvent). The AttributeError
fired before notify_termination(), so track_terminated never got set - if raised on the main
thread, the Celery task dies while enqueue_positions_thread keeps looping forever (its own loop
condition is also `while not self.track_terminated`), stealing positions from any restarted
calculator.
"""

import datetime
from unittest.mock import MagicMock, patch

from django.test import TestCase

from display.calculators.contestant_processor import ContestantProcessor
from display.models import Aeroplane, Contest, Contestant, Crew, NavigationTask, Person, Route, Scorecard, Team
from utilities.mock_utilities import TraccarMock


@patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
@patch("display.calculators.contestant_processor.get_traccar_instance", return_value=TraccarMock)
@patch("display.signals.get_traccar_instance", return_value=TraccarMock)
class TestCheckTerminationIsCommandedNoRouteAttribute(TestCase):
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
    def test_manual_termination_before_any_gate_passed_does_not_crash(
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

        with patch("threading.Thread"):
            processor = ContestantProcessor(self.contestant, live_processing=True)
            # Normal pre-first-position state: no position received yet, and no gate passed
            # yet either (also the permanent state for POKER/LANDING task calculators, which
            # never emit NextGateExpectedEvent).
            processor.orchestrator.get_last_gate = MagicMock(return_value=None)
            processor.is_termination_commanded = MagicMock(
                return_value=datetime.datetime.now(datetime.timezone.utc)
            )

            self.assertFalse(processor.track_terminated)
            # Must not raise AttributeError: 'ContestantProcessor' object has no attribute 'route'
            processor.check_termination_is_commanded(None)

            self.assertTrue(processor.track_terminated)
