"""
What a score message does to a contestant's score, by kind (penalty, achievement, percentage penalty), and the scoring
model a task gets from its task type.

update_score_from_thread is exercised against a bare (object.__new__) ContestantProcessor: __init__ pulls in
Redis/Traccar/thread setup that has nothing to do with the scoring logic under test (see
test_contestant_processor_auto_terminate.py for the fully constructed processor). A task of the penalty model is applied
without side effects (the total is kept in memory); a task of the quality model with them, since its scores are derived
from the score log by display.services.task_scoring.
"""

import datetime
import uuid
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase

from display.calculators.contestant_processor import ContestantProcessor, ScoreAccumulator
from display.calculators.update_score_message import ACHIEVEMENT, PENALTY, PERCENTAGE_PENALTY, UpdateScoreMessage
from display.default_scorecards.create_scorecards import create_scorecards
from display.models import (
    ANOMALY,
    Aeroplane,
    Contest,
    Contestant,
    ContestantTrack,
    Crew,
    NavigationTask,
    Person,
    Route,
    ScoreLogEntry,
    Scorecard,
    Team,
)
from display.services.task_scoring import ScoringParameters, scoring_parameters, signed_contribution
from display.utilities.task_types import (
    ANR_CATALOGUE,
    CIRCLE,
    CONTRACT_NAVIGATION_TIME_CONTROLS,
    CURVE_NAVIGATION_TIME_ESTIMATION,
    DURATION,
    KNOWN_CIRCUIT,
    LIMITED_FUEL_TURNPOINT_HUNT,
    PRECISION_NAVIGATION,
    QMAX_ABSOLUTE,
    QMAX_BEST_IN_TASK,
    SCORING_PENALTIES,
    SCORING_QUALITY,
    TURNPOINT_HUNT,
    UNKNOWN_LEGS,
)
from utilities.mock_utilities import TraccarMock

QUALITY_TYPES_BEST_IN_TASK = (
    CURVE_NAVIGATION_TIME_ESTIMATION,
    PRECISION_NAVIGATION,
    CONTRACT_NAVIGATION_TIME_CONTROLS,
    KNOWN_CIRCUIT,
    UNKNOWN_LEGS,
    TURNPOINT_HUNT,
    LIMITED_FUEL_TURNPOINT_HUNT,
    DURATION,
)


class MessageTestCase(TestCase):
    """Builds tasks, contestants and bare processors; the Traccar mocks are in place for every test."""

    def setUp(self):
        patchers = [
            patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock),
            patch("display.signals.get_traccar_instance", return_value=TraccarMock),
        ]
        for patcher in patchers:
            patcher.start()
            self.addCleanup(patcher.stop)
        create_scorecards()
        self.precision_original = Scorecard.get_originals().get(shortcut_name="FAI Precision")
        self.anr_original = Scorecard.get_originals().get(shortcut_name="FAI ANR")
        self.contest = Contest.objects.create(
            name="Score message kinds contest",
            start_time=datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 1, 2, tzinfo=datetime.timezone.utc),
        )

    def make_task(self, task_subtype=None, original_scorecard=None) -> NavigationTask:
        return NavigationTask.create(
            name=f"task-{task_subtype}",
            contest=self.contest,
            route=Route.objects.create(name=f"route-{task_subtype}"),
            original_scorecard=original_scorecard or self.precision_original,
            start_time=datetime.datetime(2026, 1, 1, 6, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 1, 1, 16, tzinfo=datetime.timezone.utc),
            task_subtype=task_subtype,
        )

    def make_contestant(self, navigation_task: NavigationTask, number: int = 1) -> Contestant:
        start_time = datetime.datetime(2026, 1, 1, 8, tzinfo=datetime.timezone.utc)
        unique = uuid.uuid4().hex[:8]
        person = Person.objects.create(
            first_name="Kind", last_name=f"Pilot {number}", email=f"kind-{unique}@example.com"
        )
        team = Team.objects.create(
            crew=Crew.objects.create(member1=person), aeroplane=Aeroplane.objects.create(registration=f"LN-{unique}")
        )
        return Contestant.objects.create(
            navigation_task=navigation_task,
            team=team,
            takeoff_time=start_time,
            tracker_start_time=start_time - datetime.timedelta(minutes=30),
            finished_by_time=start_time + datetime.timedelta(hours=2),
            tracker_device_id=f"kind-{navigation_task.pk}-{number}",
            contestant_number=number,
        )

    @staticmethod
    def bare_processor(contestant: Contestant, suppress_side_effects: bool) -> ContestantProcessor:
        from display.services.task_scoring import initial_track_score

        processor = object.__new__(ContestantProcessor)
        processor.contestant = contestant
        processor.scorecard = contestant.navigation_task.scorecard
        processor.accumulated_scores = ScoreAccumulator()
        processor.gate_scores = {}
        processor.suppress_side_effects = suppress_side_effects
        processor.score = initial_track_score(contestant.navigation_task)
        return processor

    @staticmethod
    def message(
        points: float,
        kind: str = PENALTY,
        score_type: str = "test_penalty",
        gate_name: str = "TP1",
        minute: int = 5,
    ) -> UpdateScoreMessage:
        return UpdateScoreMessage(
            time=datetime.datetime(2026, 1, 1, 8, minute, tzinfo=datetime.timezone.utc),
            gate=SimpleNamespace(name=gate_name, type="tp"),
            score=points,
            message="test",
            latitude=60.0,
            longitude=11.0,
            annotation_type=ANOMALY,
            score_type=score_type,
            kind=kind,
        )


class TestScoringModelOfNewTasks(MessageTestCase):
    """The task type's registry entry supplies the scoring model written into the task's own scorecard copy."""

    def test_the_quality_task_types_get_a_descending_scorecard_starting_at_zero(self):
        for subtype in (*QUALITY_TYPES_BEST_IN_TASK, CIRCLE):
            with self.subTest(subtype=subtype):
                task = self.make_task(subtype)
                self.assertEqual("desc", task.scorecard.score_sorting_direction)
                self.assertEqual(0, task.scorecard.initial_score)
                self.assertEqual(SCORING_QUALITY, task.scorecard.config["scoring_model"])
                self.assertEqual(1000, task.scorecard.task_value)

    def test_the_catalogue_tasks_divide_by_the_best_in_the_task(self):
        for subtype in QUALITY_TYPES_BEST_IN_TASK:
            with self.subTest(subtype=subtype):
                task = self.make_task(subtype)
                self.assertEqual(QMAX_BEST_IN_TASK, task.scorecard.config["qmax_policy"])
                self.assertEqual(QMAX_BEST_IN_TASK, scoring_parameters(task).qmax_policy)

    def test_the_circle_and_the_anr_have_an_absolute_score(self):
        circle = self.make_task(CIRCLE)
        anr = self.make_task(ANR_CATALOGUE, self.anr_original)
        self.assertEqual(QMAX_ABSOLUTE, scoring_parameters(circle).qmax_policy)
        self.assertEqual(QMAX_ABSOLUTE, scoring_parameters(anr).qmax_policy)
        self.assertEqual(None, scoring_parameters(circle).absolute_reference)  # P = Q
        self.assertEqual(2000, scoring_parameters(anr).absolute_reference)  # P = task_value x Q / 2000
        self.assertEqual(("desc", 0), (anr.scorecard.score_sorting_direction, anr.scorecard.initial_score))

    def test_the_shared_original_is_untouched(self):
        self.make_task(PRECISION_NAVIGATION)
        self.precision_original.refresh_from_db()
        self.assertEqual(
            ("asc", 0), (self.precision_original.score_sorting_direction, self.precision_original.initial_score)
        )
        self.assertNotIn("scoring_model", self.precision_original.config)

    def test_legacy_tasks_keep_the_penalty_model(self):
        task = self.make_task(None)
        self.assertEqual(("asc", 0), (task.scorecard.score_sorting_direction, task.scorecard.initial_score))
        self.assertEqual(SCORING_PENALTIES, scoring_parameters(task).model)
        self.assertNotIn("scoring_model", task.scorecard.config)

    def test_a_task_without_a_stored_scoring_model_behaves_as_its_task_type_does(self):
        # A task created before the scoring model existed: nothing is stored, the registry decides.
        task = self.make_task(PRECISION_NAVIGATION)
        for name in ("scoring_model", "qmax_policy", "task_value"):
            task.scorecard.config.pop(name, None)
        task.scorecard.save(update_fields=["config"])
        parameters = scoring_parameters(task)
        self.assertEqual(
            (SCORING_QUALITY, QMAX_BEST_IN_TASK, 1000.0),
            (parameters.model, parameters.qmax_policy, parameters.task_value),
        )

    def test_a_stored_value_wins_over_the_task_type_default(self):
        task = self.make_task(PRECISION_NAVIGATION)
        task.scorecard.config.update({"qmax_policy": "theoretical", "task_value": 1500})
        task.scorecard.save(update_fields=["config"])
        parameters = scoring_parameters(task)
        self.assertEqual(("theoretical", 1500.0), (parameters.qmax_policy, parameters.task_value))
        task.scorecard.config["scoring_model"] = SCORING_PENALTIES
        self.assertFalse(scoring_parameters(task).is_quality)

    def test_a_task_type_without_a_quality_score_cannot_be_switched_to_it(self):
        task = self.make_task(None)
        task.scorecard.config["scoring_model"] = SCORING_QUALITY
        self.assertFalse(scoring_parameters(task).is_quality)


class TestSignedContribution(TestCase):
    PENALTY_MODEL = ScoringParameters(SCORING_PENALTIES, QMAX_BEST_IN_TASK, 1000.0)
    QUALITY_MODEL = ScoringParameters(SCORING_QUALITY, QMAX_BEST_IN_TASK, 1000.0)

    def test_quality_model_penalties_reduce_and_achievements_add_whatever_the_sort_direction(self):
        for descending in (True, False):
            self.assertEqual(-30, signed_contribution(PENALTY, 30, self.QUALITY_MODEL, descending))
            self.assertEqual(30, signed_contribution(ACHIEVEMENT, 30, self.QUALITY_MODEL, descending))

    def test_ascending_penalty_model_adds_penalties_to_the_total(self):
        self.assertEqual(30, signed_contribution(PENALTY, 30, self.PENALTY_MODEL, descending=False))
        self.assertEqual(-30, signed_contribution(ACHIEVEMENT, 30, self.PENALTY_MODEL, descending=False))

    def test_descending_penalty_model_subtracts_penalties_from_the_total(self):
        self.assertEqual(-30, signed_contribution(PENALTY, 30, self.PENALTY_MODEL, descending=True))
        self.assertEqual(30, signed_contribution(ACHIEVEMENT, 30, self.PENALTY_MODEL, descending=True))

    def test_a_percentage_penalty_never_moves_the_running_score(self):
        for parameters in (self.PENALTY_MODEL, self.QUALITY_MODEL):
            self.assertEqual(0, signed_contribution(PERCENTAGE_PENALTY, 50, parameters, descending=True))

    def test_an_unknown_kind_is_refused(self):
        with self.assertRaises(ValueError):
            signed_contribution("bonus", 1, self.QUALITY_MODEL, True)

    def test_a_message_has_a_penalty_kind_unless_it_says_otherwise(self):
        message = UpdateScoreMessage(None, None, 1, "m", 0, 0, ANOMALY, "t")
        self.assertEqual(PENALTY, message.kind)
        with self.assertRaises(ValueError):
            UpdateScoreMessage(None, None, 1, "m", 0, 0, ANOMALY, "t", kind="bonus")


class TestMessageKindsInTheProcessor(MessageTestCase):
    def test_legacy_ascending_scorecard_adds_penalties_as_before(self):
        contestant = self.make_contestant(self.make_task(None))
        processor = self.bare_processor(contestant, suppress_side_effects=True)
        self.assertEqual(0, processor.score)
        processor.update_score_from_thread(self.message(30))
        self.assertEqual(30, processor.score)
        processor.update_score_from_thread(self.message(15.5))
        self.assertEqual(45.5, processor.score)

    def test_legacy_ascending_scorecard_deducts_an_achievement(self):
        contestant = self.make_contestant(self.make_task(None))
        processor = self.bare_processor(contestant, suppress_side_effects=True)
        processor.update_score_from_thread(self.message(30))
        processor.update_score_from_thread(self.message(10, ACHIEVEMENT, "test_achievement"))
        self.assertEqual(20, processor.score)

    def test_legacy_descending_scorecard_subtracts_penalties_and_adds_achievements(self):
        task = self.make_task(None)
        task.scorecard.score_sorting_direction = "desc"
        task.scorecard.initial_score = 100
        task.scorecard.save(update_fields=["score_sorting_direction", "initial_score"])
        processor = self.bare_processor(self.make_contestant(task), suppress_side_effects=True)
        processor.update_score_from_thread(self.message(30))
        self.assertEqual(70, processor.score)
        processor.update_score_from_thread(self.message(5, ACHIEVEMENT, "test_achievement"))
        self.assertEqual(75, processor.score)

    def test_quality_task_penalty_reduces_and_achievement_adds_to_the_running_contribution(self):
        processor = self.bare_processor(
            self.make_contestant(self.make_task(TURNPOINT_HUNT)), suppress_side_effects=True
        )
        self.assertEqual(0, processor.score)
        processor.update_score_from_thread(self.message(30))
        self.assertEqual(-30, processor.score)
        processor.update_score_from_thread(self.message(100, ACHIEVEMENT, "turnpoint_hunt_target_value"))
        self.assertEqual(70, processor.score)

    def test_a_percentage_penalty_does_not_move_the_running_contribution(self):
        processor = self.bare_processor(self.make_contestant(self.make_task(PRECISION_NAVIGATION)), True)
        processor.update_score_from_thread(self.message(50, PERCENTAGE_PENALTY, "backtracking"))
        self.assertEqual(0, processor.score)

    def test_score_log_of_a_quality_task_holds_the_signed_contribution_and_the_kind(self):
        contestant = self.make_contestant(self.make_task(TURNPOINT_HUNT))
        processor = self.bare_processor(contestant, suppress_side_effects=False)
        processor.update_score_from_thread(self.message(30, PENALTY, "gate_score", "TP1", 5))
        processor.update_score_from_thread(self.message(100, ACHIEVEMENT, "turnpoint_hunt_target_value", "TP2", 6))
        processor.update_score_from_thread(self.message(50, PERCENTAGE_PENALTY, "backtracking", "TP3", 7))
        entries = {
            entry.gate: (entry.points, entry.score_type, entry.score_kind)
            for entry in ScoreLogEntry.objects.filter(contestant=contestant)
        }
        self.assertEqual(
            {
                "TP1": (-30, "gate_score", PENALTY),
                "TP2": (100, "turnpoint_hunt_target_value", ACHIEVEMENT),
                "TP3": (50, "backtracking", PERCENTAGE_PENALTY),
            },
            entries,
        )
        # The old "[Qmax-normalized ...]" and "[x0.5 scale ...]" suffixes are gone; a percentage says what it is
        messages = {entry.gate: entry.message for entry in ScoreLogEntry.objects.filter(contestant=contestant)}
        self.assertNotIn("Qmax", messages["TP1"])
        self.assertIn("50% of the task score", messages["TP3"])

    def test_the_anr_is_not_scaled_any_more(self):
        contestant = self.make_contestant(self.make_task(ANR_CATALOGUE, self.anr_original))
        processor = self.bare_processor(contestant, suppress_side_effects=True)
        processor.update_score_from_thread(self.message(30))
        self.assertEqual(-30, processor.score)  # the raw magnitude, not -15

    def test_a_capped_penalty_is_capped_before_the_sign_is_applied(self):
        processor = self.bare_processor(self.make_contestant(self.make_task(PRECISION_NAVIGATION)), True)
        for _ in range(3):
            message = self.message(40)
            message.maximum_score = 100
            processor.update_score_from_thread(message)
        self.assertEqual(-100, processor.score)

    def test_contestant_track_starts_at_zero_in_a_quality_task_and_at_the_initial_score_in_a_legacy_task(self):
        legacy = self.make_task(None)
        legacy.scorecard.initial_score = 40
        legacy.scorecard.save(update_fields=["initial_score"])
        self.assertEqual(40, ContestantTrack.objects.get(contestant=self.make_contestant(legacy)).score)
        quality = self.make_contestant(self.make_task(PRECISION_NAVIGATION))
        self.assertEqual(0, ContestantTrack.objects.get(contestant=quality).score)
