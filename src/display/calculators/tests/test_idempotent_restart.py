import os
import datetime
import uuid
import dateutil.parser
from unittest.mock import patch, Mock

from django.test import TransactionTestCase

from display.calculators.contestant_processor import ContestantProcessor
from display.calculators.tests.test_precision_calculator import load_track_points, TEST_DATA_DIR
from display.calculators.update_score_message import UpdateScoreMessage
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
    TrackAnnotation,
    GateCumulativeScore,
    EditableRoute,
)
from display.models.scoring_models import ANOMALY
from display.models.contestant_utility_models import ContestantReceivedPosition
from utilities.mock_utilities import TraccarMock
from redis_queue import RedisQueue

# Ensure TraccarMock is properly configured for all expected calls
TraccarMock.get_or_create_device.return_value = ({}, False)
TraccarMock.get_device_ids_for_contestant.return_value = []
TraccarMock.get_positions_for_device_id.return_value = []


@patch("display.utilities.traccar_factory.get_traccar_instance", return_value=TraccarMock)
@patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
@patch("display.calculators.contestant_processor.get_traccar_instance", return_value=TraccarMock)
@patch("display.signals.get_traccar_instance", return_value=TraccarMock)
@patch("display.calculators.contestant_processor.WebsocketFacade")
@patch("display.calculators.orchestrator.WebsocketFacade")
@patch("display.calculators.gate_calculator.WebsocketFacade")
@patch("display.calculators.contestant_processor.post_slack_competition_message")
class TestIdempotentRestart(TransactionTestCase):
    @patch("display.utilities.traccar_factory.get_traccar_instance", return_value=TraccarMock)
    @patch("display.calculators.contestant_processor.get_traccar_instance", return_value=TraccarMock)
    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, *args):
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
            name=f"contest_restart_test_{uuid.uuid4().hex}",
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
                email=f"pilot_{uuid.uuid4().hex}@test.com",
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
        q = RedisQueue(self.contestant.pk)
        for p in first_half:
            q.append(p)
        q.append(None)  # Signal end for this run

        processor = ContestantProcessor(self.contestant, live_processing=False)
        with patch.object(processor.orchestrator, "finished_processing"):
            processor.run()
        processor.score_processing_queue.join()

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
        processor_restart.score_processing_queue.join()

        # 4. Verifications
        # Verify final state
        final_track = ContestantTrack.objects.get(contestant=self.contestant)
        self.assertEqual(222, final_track.score)  # Total score for this track should be 222

        # Actually, let's just check that we don't have multiple SP entries or similar.
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
        processor.score_processing_queue.join()

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
        processor_recalc.score_processing_queue.join()

        # Verify final state is correct (not double counted)
        final_track = ContestantTrack.objects.get(contestant=self.contestant)
        self.assertEqual(222, final_track.score)

    def test_update_score_from_thread_is_idempotent_for_replayed_event(
        self, mock_slack, mock_ws_gate, mock_ws_orch, mock_ws_proc, *args
    ):
        gate = self.contestant.navigation_task.route.waypoints[0]
        event_time = self.start_time + datetime.timedelta(minutes=5)
        initial_score = ContestantTrack.objects.get(contestant=self.contestant).score

        update = UpdateScoreMessage(
            time=event_time,
            gate=gate,
            score=57,
            message="passing gate",
            latitude=gate.latitude,
            longitude=gate.longitude,
            annotation_type=ANOMALY,
            score_type="gate_score",
            planned=event_time - datetime.timedelta(seconds=21),
            actual=event_time,
        )

        from display.calculators.contestant_processor import ScoreAccumulator

        processor = ContestantProcessor.__new__(ContestantProcessor)
        processor.accumulated_scores = ScoreAccumulator()
        processor.contestant = self.contestant
        processor.contestant_track = ContestantTrack.objects.get(contestant=self.contestant)
        processor.gate_scores = {}
        processor.suppress_side_effects = False
        processor.score = initial_score

        processor.update_score_from_thread(update)
        processor.update_score_from_thread(update)

        self.assertEqual(1, ScoreLogEntry.objects.filter(contestant=self.contestant).count())
        self.assertEqual(1, TrackAnnotation.objects.filter(contestant=self.contestant).count())
        self.assertEqual(57, GateCumulativeScore.objects.get(contestant=self.contestant, gate=gate.name).points)
        self.assertEqual(initial_score + 57, ContestantTrack.objects.get(contestant=self.contestant).score)

    def test_restart_after_crash_between_scoring_and_position_flush_does_not_double_count(
        self, mock_slack, mock_ws_gate, mock_ws_orch, mock_ws_proc, *args
    ):
        """Regression test for the exact window the idempotent-scoring fix
        (commit 94782a91/0122c7e0) targets: ContestantReceivedPosition rows
        are flushed in batches (every 100, or at track end - see run()'s
        positions_to_save handling), but score_processing_queue is drained
        continuously as positions are scored. A crash between "position N
        was scored" and "position N's batch was bulk_created" leaves
        ScoreLogEntry rows in the DB for positions that
        existing_positions.last().time (and therefore latest_recorded_time)
        does not yet cover - so those positions get replayed as *live*, not
        suppressed, on restart. Only ScoreLogEntry.get_or_create_and_push's
        idempotency key protects against double-scoring in this window;
        test_restart_idempotency above never exercises it, because it always
        crashes cleanly after a full flush.
        """
        positions = load_track_points(os.path.join(TEST_DATA_DIR, "test_contestant_correct_track.gpx"))
        for p in positions:
            p["id"] = 0
            p["deviceId"] = "Test contestant"
            p["attributes"] = {}
            p["device_time"] = dateutil.parser.parse(p["time"])

        mid_point = len(positions) // 2
        first_half = positions[:mid_point]
        # Wide enough to guarantee at least one further gate crossing beyond
        # whatever first_half already reached (route is SP, SC1/1, TP1,
        # SC2/1, TP2, SC3/1, SC3/2, TP3, TP4, SC5/1, TP5, SC6/1, TP6, SC7/1,
        # SC7/2, FP - first_half alone already reaches TP4).
        first_half_plus_gap = positions[: mid_point + 1500]

        # 1. Clean run of the first half - fully scored AND fully persisted.
        q = RedisQueue(self.contestant.pk)
        for p in first_half:
            q.append(p)
        q.append(None)
        processor = ContestantProcessor(self.contestant, live_processing=False)
        with patch.object(processor.orchestrator, "finished_processing"):
            processor.run()
        processor.score_processing_queue.join()

        checkpoint_position_count = ContestantReceivedPosition.objects.filter(contestant=self.contestant).count()
        checkpoint_log_pks = set(ScoreLogEntry.objects.filter(contestant=self.contestant).values_list("pk", flat=True))
        self.assertGreater(len(checkpoint_log_pks), 0)

        # 2. A restart that replays from the true beginning - exactly like a
        # real production restart does (enqueue_positions_thread always
        # re-fetches from tracker_start_time; the test feeds the same thing
        # into the queue by hand). first_half is silently suppressed
        # (already safely persisted, per latest_recorded_time), and the next
        # 1500 positions are processed *live*, scoring new gates - but this
        # run crashes before flushing their ContestantReceivedPosition batch,
        # by making bulk_create a no-op for this run only. A fresh
        # orchestrator that only ever saw a slice starting mid-track (not a
        # full replay) would spuriously fire missed/passed-gate detection
        # for every earlier gate on its very first position - replaying from
        # the beginning is what avoids that artifact, matching production.
        q = RedisQueue(self.contestant.pk)
        for p in first_half_plus_gap:
            q.append(p)
        q.append(None)
        processor_gap = ContestantProcessor(self.contestant, live_processing=False)
        with patch.object(processor_gap.orchestrator, "finished_processing"):
            with patch.object(ContestantReceivedPosition.objects, "bulk_create"):
                processor_gap.run()
        processor_gap.score_processing_queue.join()

        # Confirm the gap scenario is real: positions were NOT persisted...
        self.assertEqual(
            checkpoint_position_count,
            ContestantReceivedPosition.objects.filter(contestant=self.contestant).count(),
        )
        # ...but new scoring DID happen and IS in the DB, ahead of what
        # latest_recorded_time will see on the next restart.
        log_pks_after_gap = set(ScoreLogEntry.objects.filter(contestant=self.contestant).values_list("pk", flat=True))
        new_gap_logs = list(
            ScoreLogEntry.objects.filter(contestant=self.contestant, pk__in=log_pks_after_gap - checkpoint_log_pks)
        )
        self.assertGreater(len(new_gap_logs), 0)
        gap_gate_names = {entry.gate for entry in new_gap_logs}

        # 3. The real restart: full track replay. latest_recorded_time is
        # still pinned at the checkpoint (the gap-window positions were
        # never persisted), so the gap-window positions get reprocessed as
        # *live*, not suppressed - this is exactly where the fix matters.
        q = RedisQueue(self.contestant.pk)
        for p in positions:
            q.append(p)
        q.append(None)
        processor_restart = ContestantProcessor(self.contestant, live_processing=False)
        processor_restart.run()
        processor_restart.score_processing_queue.join()

        # 4. No duplicate ScoreLogEntry for anything scored during the gap window.
        for gate_name in gap_gate_names:
            with self.subTest(gate=gate_name):
                self.assertEqual(
                    1,
                    ScoreLogEntry.objects.filter(contestant=self.contestant, gate=gate_name).count(),
                    f"gate {gate_name} scored during the unflushed gap window was double-counted on restart",
                )
        sp_logs = ScoreLogEntry.objects.filter(contestant=self.contestant, gate="SP")
        self.assertEqual(1, sp_logs.count())
        final_track = ContestantTrack.objects.get(contestant=self.contestant)
        self.assertEqual(222, final_track.score)
