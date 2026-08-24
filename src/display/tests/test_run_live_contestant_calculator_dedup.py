from unittest.mock import MagicMock, patch

from django.test import TestCase

from display.tasks import run_live_contestant_calculator
from display.utilities.calculator_running_utilities import calculator_is_alive, calculator_is_terminated


class TestRunLiveContestantCalculatorDedup(TestCase):
    """
    The Redis broker's visibility timeout can redeliver a task for a
    contestant whose calculator is, in fact, still running (see
    CELERY_BROKER_TRANSPORT_OPTIONS in settings.py and the docstring on
    run_live_contestant_calculator). Without an explicit running check, that
    redelivery - or the worker-boot message-restore hook this task's
    docstring also references - would start a second ContestantProcessor
    racing the first one on the same contestant. Uses the real Redis-backed
    cache (calculator_is_alive/is_calculator_running), not a mock, since the
    guard's correctness depends on the same cache key both sides read/write.
    """

    def setUp(self):
        self.contestant_pk = 123456789
        calculator_is_terminated(self.contestant_pk)  # ensure a clean cache key

    def tearDown(self):
        calculator_is_terminated(self.contestant_pk)

    @patch("display.tasks.ContestantProcessor")
    @patch("display.tasks.Contestant")
    def test_redelivered_task_is_ignored_while_already_running(self, mock_contestant_model, mock_processor_cls):
        mock_contestant = MagicMock()
        mock_contestant.contestanttrack.calculator_finished = False
        mock_contestant_model.objects.get.return_value = mock_contestant

        calculator_is_alive(self.contestant_pk, 30)  # simulate a heartbeat from the already-running calculator

        run_live_contestant_calculator(self.contestant_pk)

        mock_processor_cls.assert_not_called()

    @patch("display.tasks.ContestantProcessor")
    @patch("display.tasks.Contestant")
    def test_first_dispatch_starts_the_processor(self, mock_contestant_model, mock_processor_cls):
        mock_contestant = MagicMock()
        mock_contestant.contestanttrack.calculator_finished = False
        mock_contestant_model.objects.get.return_value = mock_contestant
        mock_processor_instance = MagicMock()
        mock_processor_cls.return_value = mock_processor_instance

        # No calculator_is_alive call for this pk - nothing running yet.
        run_live_contestant_calculator(self.contestant_pk)

        mock_processor_cls.assert_called_once_with(mock_contestant, live_processing=True)
        mock_processor_instance.run.assert_called_once()
