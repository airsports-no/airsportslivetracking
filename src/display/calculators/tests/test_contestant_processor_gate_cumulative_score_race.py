import datetime
from unittest.mock import MagicMock, patch

from django.test import TestCase

from display.calculators.contestant_processor import ContestantProcessor
from display.calculators.update_score_message import UpdateScoreMessage
from display.models import (
    Aeroplane,
    Contest,
    Contestant,
    Crew,
    GateCumulativeScore,
    NavigationTask,
    Person,
    Route,
    Scorecard,
    Team,
)
from display.models.contestant_track import ContestantTrack
from utilities.mock_utilities import TraccarMock


@patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
@patch("display.calculators.contestant_processor.get_traccar_instance", return_value=TraccarMock)
@patch("display.signals.get_traccar_instance", return_value=TraccarMock)
class TestContestantProcessorGateCumulativeScoreRace(TestCase):
    """
    Regression test for Sentry issue PYTHON-DJANGO-K: GateCumulativeScore.NotUpdated crashed
    update_score_from_thread's score_updater_thread with "Save with update_fields did not
    affect any rows".

    Root cause: self.gate_scores is a per-ContestantProcessor in-memory cache of
    GateCumulativeScore objects, populated once via get_or_create and then reused for every
    later score update to that gate for as long as the live calculator runs. If an organizer
    uses delete_score_item (views.py) to delete the only ScoreLogEntry for a gate - which also
    deletes that gate's GateCumulativeScore row - while the contestant's live calculator is
    still running, the cache is never invalidated: the next score update for that same gate
    reuses the stale cached object and calls save(update_fields=["points"]) against a row that
    no longer exists.
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

    def _make_message(self, gate_name, score):
        gate = MagicMock()
        gate.name = gate_name
        gate.type = "tp"
        return UpdateScoreMessage(
            time=datetime.datetime.now(datetime.timezone.utc),
            gate=gate,
            score=score,
            message="",
            latitude=60.0,
            longitude=11.0,
            annotation_type="anomaly",
            score_type="test",
        )

    @patch("websocket_channels.WebsocketFacade")
    @patch("display.calculators.contestant_processor.calculator_is_alive")
    @patch("display.calculators.contestant_processor.WebsocketFacade")
    @patch("display.calculators.contestant_processor.get_traccar_instance")
    @patch("display.calculators.contestant_processor.RedisQueue")
    @patch("display.calculators.contestant_processor.calculator_factory")
    @patch("display.calculators.contestant_processor.post_slack_competition_message")
    def test_score_update_recovers_when_gate_cumulative_score_deleted_out_from_under_the_cache(
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

            # First score update for TP1: creates the GateCumulativeScore row and caches it.
            processor.update_score_from_thread(self._make_message("TP1", 10.0))
            self.assertEqual(
                GateCumulativeScore.objects.get(contestant=self.contestant, gate="TP1").points, 10.0
            )
            cached = processor.gate_scores["TP1"]

            # Simulate delete_score_item deleting the only ScoreLogEntry for this gate, which
            # deletes the GateCumulativeScore row too - out from under the processor's cache.
            GateCumulativeScore.objects.filter(contestant=self.contestant, gate="TP1").delete()

            # Second score update for the SAME gate reuses the stale cached object. Should not
            # raise GateCumulativeScore.NotUpdated.
            processor.update_score_from_thread(self._make_message("TP1", 5.0))

            # Recovered with a fresh row seeded from just this second increment, not the stale
            # cached total (10.0) plus the new one.
            recreated = GateCumulativeScore.objects.get(contestant=self.contestant, gate="TP1")
            self.assertEqual(recreated.points, 5.0)
            self.assertNotEqual(recreated.pk, cached.pk)
            # The cache now points at the recreated row, not the stale deleted one.
            self.assertEqual(processor.gate_scores["TP1"].pk, recreated.pk)
