import datetime
from unittest.mock import MagicMock, patch

from django.test import TestCase

from display.calculators.contestant_processor import ContestantProcessor
from display.calculators.update_score_message import UpdateScoreMessage
from display.models import Aeroplane, Contest, Contestant, Crew, NavigationTask, Person, Route, Scorecard, Team
from display.models.contestant_track import ContestantTrack
from utilities.mock_utilities import TraccarMock


@patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
@patch("display.calculators.contestant_processor.get_traccar_instance", return_value=TraccarMock)
@patch("display.signals.get_traccar_instance", return_value=TraccarMock)
class TestContestantProcessorDeletedContestantRace(TestCase):
    """
    Regression test for GH #707: a contestant that is deleted mid-flight while its live
    calculator is still running used to crash the calculator with an unhandled
    django.db.utils.IntegrityError (FK constraint violation) the next time it tried to save
    a position or update a gate score, instead of terminating cleanly. self.contestant is only
    refreshed from the DB every CONTESTANT_REFRESH_INTERVAL, so this race is easy to hit.
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

    def create_mock_position_data(self, time, speed):
        return {
            "device_time": time,
            "latitude": 60.0,
            "longitude": 11.0,
            "speed": speed,
            "course": 0.0,
            "altitude": 0.0,
            "attributes": {"batteryLevel": 100, "course": 0.0},
            "id": 1,
            "deviceId": "test_device",
        }

    @patch("websocket_channels.WebsocketFacade")
    @patch("display.calculators.contestant_processor.calculator_is_alive")
    @patch("display.calculators.contestant_processor.WebsocketFacade")
    @patch("display.calculators.contestant_processor.get_traccar_instance")
    @patch("display.calculators.contestant_processor.RedisQueue")
    @patch("display.calculators.contestant_processor.calculator_factory")
    @patch("display.calculators.contestant_processor.post_slack_competition_message")
    def test_save_positions_terminates_instead_of_raising_when_contestant_deleted(
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

            position_data = self.create_mock_position_data(datetime.datetime.now(datetime.timezone.utc), 20.0)
            position = self.contestant.generate_position_block_for_contestant(
                position_data, position_data["device_time"]
            )

            # Simulate the contestant being deleted mid-flight by another process, leaving
            # processor.contestant a stale in-memory reference with a pk that no longer
            # exists in the DB (unlike self.contestant.delete(), which would also clear the
            # pk on this exact Python instance and mask the race we're testing).
            Contestant.objects.filter(pk=self.contestant.pk).delete()

            self.assertFalse(processor.track_terminated)
            processor.save_positions([position])

            self.assertTrue(processor.track_terminated)

    @patch("websocket_channels.WebsocketFacade")
    @patch("display.calculators.contestant_processor.calculator_is_alive")
    @patch("display.calculators.contestant_processor.WebsocketFacade")
    @patch("display.calculators.contestant_processor.get_traccar_instance")
    @patch("display.calculators.contestant_processor.RedisQueue")
    @patch("display.calculators.contestant_processor.calculator_factory")
    @patch("display.calculators.contestant_processor.post_slack_competition_message")
    def test_update_score_from_thread_terminates_instead_of_raising_when_contestant_deleted(
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

            # See comment in the previous test for why we delete via a fresh queryset
            # rather than self.contestant.delete().
            Contestant.objects.filter(pk=self.contestant.pk).delete()

            gate = MagicMock()
            gate.name = "TP1"
            update_score_message = UpdateScoreMessage(
                time=datetime.datetime.now(datetime.timezone.utc),
                gate=gate,
                score=1.0,
                message="",
                latitude=60.0,
                longitude=11.0,
                annotation_type="anomaly",
                score_type="test",
            )

            self.assertFalse(processor.track_terminated)
            # Should not raise django.db.utils.IntegrityError.
            processor.update_score_from_thread(update_score_message)

            self.assertTrue(processor.track_terminated)
