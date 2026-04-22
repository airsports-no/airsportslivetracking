import os
import datetime
import dateutil.parser
from unittest.mock import patch

from django.test import TransactionTestCase

from display.calculators.contestant_processor import ContestantProcessor
from display.calculators.tests.test_precision_calculator import load_track_points, TEST_DATA_DIR
from display.models import (
    Aeroplane,
    NavigationTask,
    Team,
    Contestant,
    ContestantTrack,
    Crew,
    Contest,
    Person,
    ScoreLogEntry,
    EditableRoute,
)
from utilities.mock_utilities import TraccarMock
from redis_queue import RedisQueue


@patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
@patch("display.calculators.contestant_processor.get_traccar_instance", return_value=TraccarMock)
@patch("display.signals.get_traccar_instance", return_value=TraccarMock)
@patch("display.calculators.contestant_processor.WebsocketFacade")
@patch("display.calculators.orchestrator.WebsocketFacade")
@patch("display.calculators.gate_calculator.WebsocketFacade")
@patch("display.calculators.contestant_processor.post_slack_competition_message")
class TestIdempotentRestart(TransactionTestCase):
    def setUp(self):
        from display.default_scorecards import default_scorecard_fai_precision_2020

        self.scorecard = default_scorecard_fai_precision_2020.get_default_scorecard()
        with open(os.path.join(TEST_DATA_DIR, "NM.csv"), "r") as file:
            with patch(
                "display.models.EditableRoute._create_route_and_thumbnail",
                lambda name, r: EditableRoute.objects.create(name=name, route=r),
            ):
                editable_route, _ = EditableRoute.create_from_csv("Test", file.readlines()[1:])
                route = editable_route.create_precision_route(True, self.scorecard)

        navigation_task_start_time = datetime.datetime(2020, 8, 1, 6, 0, 0, tzinfo=datetime.timezone.utc)
        navigation_task_finish_time = datetime.datetime(2020, 8, 1, 16, 0, 0, tzinfo=datetime.timezone.utc)
        aeroplane = Aeroplane.objects.create(registration="LN-YDB")

        self.contest = Contest.objects.create(
            name="contest_restart_test",
            start_time=navigation_task_start_time,
            finish_time=navigation_task_finish_time,
            time_zone="Europe/Oslo",
        )

        self.navigation_task = NavigationTask.create(
            name="NM navigation_task",
            route=route,
            original_scorecard=self.scorecard,
            contest=self.contest,
            start_time=navigation_task_start_time,
            finish_time=navigation_task_finish_time,
        )
        crew = Crew.objects.create(
            member1=Person.objects.create(
                first_name="Mister",
                last_name="Pilot",
                email="pilot@test.com",
            )
        )
        self.team = Team.objects.create(crew=crew, aeroplane=aeroplane)
        self.start_time = datetime.datetime(2020, 8, 1, 9, 15, tzinfo=datetime.timezone.utc)

        # Required to make the time zone save correctly
        self.navigation_task.refresh_from_db()
        self.contestant = Contestant.objects.create(
            navigation_task=self.navigation_task,
            team=self.team,
            takeoff_time=self.start_time,
            tracker_start_time=self.start_time - datetime.timedelta(minutes=30),
            finished_by_time=self.start_time + datetime.timedelta(hours=2),
            tracker_device_id="Test contestant",
            contestant_number=1,
            minutes_to_starting_point=6,
            air_speed=70,
            wind_direction=165,
            wind_speed=8,
        )

    def test_restart_idempotency(self, mock_slack, mock_ws_gate, mock_ws_orch, mock_ws_proc, *args):
        # 1. Load full track points
        positions = load_track_points(os.path.join(TEST_DATA_DIR, "test_contestant_correct_track.gpx"))
        for p in positions:
            p["id"] = 0
            p["deviceId"] = "Test contestant"
            p["attributes"] = {}
            p["device_time"] = dateutil.parser.parse(p["time"])

        # Split track in two
        mid_point = len(positions) // 2
        first_half = positions[:mid_point]

        # 2. Run first half - Simulate a crash by mocking finished_processing
        # (Alternatively, we could just not send the None sentinel, but that would require a timeout)
        q = RedisQueue(self.contestant.pk)
        for p in first_half:
            q.append(p)
        q.append(None)  # Signal end for this run

        processor = ContestantProcessor(self.contestant, live_processing=False)
        with patch.object(processor.orchestrator, "finished_processing"):
            processor.run()

        # Capture state after first run
        score_after_first = ContestantTrack.objects.get(contestant=self.contestant).score
        logs_after_first = list(ScoreLogEntry.objects.filter(contestant=self.contestant).values_list("pk", flat=True))

        self.assertGreater(len(logs_after_first), 0)
        # Score should be > 0 but definitely not the full score yet
        self.assertLess(score_after_first, 222)

        # Reset mocks to clear calls from first run
        mock_ws_proc.return_value.transmit_basic_information.reset_mock()
        mock_ws_proc.return_value.transmit_score_log_entry.reset_mock()
        mock_ws_proc.return_value.transmit_annotations.reset_mock()
        mock_slack.reset_mock()

        # 3. Simulate Restart - Run full track (including first half)
        # We instantiate a NEW processor. It should detect existing positions and skip reset.
        q = RedisQueue(self.contestant.pk)
        for p in positions:  # FULL track
            q.append(p)
        q.append(None)

        processor_restart = ContestantProcessor(self.contestant, live_processing=False)

        # Verify that reset_track_and_score was NOT called (indirectly by checking logs still exist)
        self.assertEqual(ScoreLogEntry.objects.filter(contestant=self.contestant).count(), len(logs_after_first))

        # Verify Slack was NOT called on restart (it's only called on clean start)
        mock_slack.assert_not_called()

        processor_restart.run()

        # 4. Verifications
        # Verify final state
        final_track = ContestantTrack.objects.get(contestant=self.contestant)
        self.assertEqual(222, final_track.score)  # Total score for this track should be 222

        # Re-run a full fresh run in another contestant to compare counts
        # (Actually, let's just check that we don't have multiple SP entries or similar.)
        sp_logs = ScoreLogEntry.objects.filter(contestant=self.contestant, gate="SP")
        self.assertEqual(sp_logs.count(), 1)

        # Verify WebSocket transmit_basic_information was called (it is called for new positions)
        self.assertGreater(mock_ws_proc.return_value.transmit_navigation_task_position_data.call_count, 0)

    def test_recalculate_flag(self, mock_slack, mock_ws_gate, mock_ws_orch, mock_ws_proc, *args):
        # 1. Run first half
        positions = load_track_points(os.path.join(TEST_DATA_DIR, "test_contestant_correct_track.gpx"))
        for p in positions:
            p["id"] = 0
            p["deviceId"] = "Test contestant"
            p["attributes"] = {}
            p["device_time"] = dateutil.parser.parse(p["time"])

        mid_point = len(positions) // 2
        first_half = positions[:mid_point]

        q = RedisQueue(self.contestant.pk)
        for p in first_half:
            q.append(p)
        q.append(None)

        processor = ContestantProcessor(self.contestant, live_processing=False)
        processor.run()

        # 2. Perform recalculate
        # This should wipe existing data and start over
        q = RedisQueue(self.contestant.pk)
        for p in positions:
            q.append(p)
        q.append(None)

        processor_recalc = ContestantProcessor(self.contestant, live_processing=False, recalculate=True)

        # Verify that reset_track_and_score WAS called (indirectly by checking logs are gone or reset)
        self.assertEqual(ScoreLogEntry.objects.filter(contestant=self.contestant).count(), 0)

        processor_recalc.run()

        # Verify final state is correct (not double counted)
        final_track = ContestantTrack.objects.get(contestant=self.contestant)
        self.assertEqual(222, final_track.score)
