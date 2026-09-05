"""
Regression tests for the CIMA "start at a maximum, subtract penalties" scoring model
(descending scorecards), covering the two pieces added to make it actually work:

1. NavigationTask.assign_scorecard_from_original applies a per-subtype scoring baseline
   (score_sorting_direction/initial_score) to a freshly-copied task scorecard, without ever
   touching the shared "original" scorecard templates legacy tasks also use.
2. ContestantProcessor.update_score_from_thread negates the penalty magnitude for a descending
   scorecard, so it is subtracted from initial_score instead of added to it - the design intent
   documented in documentation/cima/CIMA_Task_catalogue_implementation_plan.md ("applying
   negative penalties") which was never wired up before this.

update_score_from_thread is exercised directly against a bare (object.__new__) ContestantProcessor
rather than a fully constructed one, deliberately - __init__ pulls in Redis/Traccar/thread setup
that has nothing to do with the scoring-sign logic under test here; see
test_contestant_processor_auto_terminate.py for a test exercising the fully constructed processor.
"""

import datetime
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase

from display.calculators.contestant_processor import ContestantProcessor, ScoreAccumulator
from display.calculators.update_score_message import UpdateScoreMessage
from display.default_scorecards.create_scorecards import create_scorecards
from display.models import (
    ANOMALY,
    Aeroplane,
    Contest,
    Contestant,
    Crew,
    NavigationTask,
    Person,
    Route,
    Scorecard,
    Team,
)
from display.utilities.cima_task_type_definitions import ANR_CATALOGUE, PRECISION_NAVIGATION
from utilities.mock_utilities import TraccarMock


@patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
@patch("display.signals.get_traccar_instance", return_value=TraccarMock)
class TestCimaDescendingScoring(TestCase):
    def setUp(self, *args):
        create_scorecards()
        self.precision_original = Scorecard.get_originals().get(shortcut_name="FAI Precision")
        self.anr_original = Scorecard.get_originals().get(shortcut_name="FAI ANR")
        self.contest = Contest.objects.create(
            name="CIMA descending scoring test contest",
            start_time=datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 1, 2, tzinfo=datetime.timezone.utc),
        )
        crew = Crew.objects.create(member1=Person.objects.create(first_name="Cima", last_name="Pilot"))
        self.team = Team.objects.create(crew=crew, aeroplane=Aeroplane.objects.create(registration="LN-CIMA"))

    def _make_task(self, original_scorecard, task_subtype=None) -> NavigationTask:
        return NavigationTask.create(
            name=f"task-{task_subtype}",
            contest=self.contest,
            route=Route.objects.create(name=f"route-{task_subtype}"),
            original_scorecard=original_scorecard,
            start_time=datetime.datetime(2026, 1, 1, 6, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 1, 1, 16, tzinfo=datetime.timezone.utc),
            task_subtype=task_subtype,
        )

    def _make_contestant(self, navigation_task: NavigationTask) -> Contestant:
        start_time = datetime.datetime(2026, 1, 1, 8, tzinfo=datetime.timezone.utc)
        return Contestant.objects.create(
            navigation_task=navigation_task,
            team=self.team,
            takeoff_time=start_time,
            tracker_start_time=start_time - datetime.timedelta(minutes=30),
            finished_by_time=start_time + datetime.timedelta(hours=2),
            tracker_device_id=f"cima-{navigation_task.pk}",
            contestant_number=1,
        )

    def _bare_processor(self, contestant: Contestant) -> ContestantProcessor:
        # Bypasses __init__ deliberately - see module docstring.
        processor = object.__new__(ContestantProcessor)
        processor.contestant = contestant
        processor.scorecard = contestant.navigation_task.scorecard
        processor.accumulated_scores = ScoreAccumulator()
        processor.gate_scores = {}
        processor.suppress_side_effects = True
        processor.score = processor.scorecard.initial_score
        return processor

    @staticmethod
    def _penalty_message(points: float) -> UpdateScoreMessage:
        return UpdateScoreMessage(
            time=datetime.datetime(2026, 1, 1, 8, 5, tzinfo=datetime.timezone.utc),
            gate=SimpleNamespace(name="TP1"),
            score=points,
            message="test penalty",
            latitude=60.0,
            longitude=11.0,
            annotation_type=ANOMALY,
            score_type="test_penalty",
        )

    def test_cima_precision_subtype_gets_descending_scorecard_with_max_of_1000(self, *args):
        task = self._make_task(self.precision_original, task_subtype=PRECISION_NAVIGATION)
        self.assertEqual(task.scorecard.score_sorting_direction, "desc")
        self.assertEqual(task.scorecard.initial_score, 1000)
        # The shared original template must be untouched - legacy tasks copy the same original.
        self.precision_original.refresh_from_db()
        self.assertEqual(self.precision_original.score_sorting_direction, "asc")
        self.assertEqual(self.precision_original.initial_score, 0)

    def test_cima_anr_catalogue_subtype_gets_descending_scorecard_with_max_of_2000(self, *args):
        task = self._make_task(self.anr_original, task_subtype=ANR_CATALOGUE)
        self.assertEqual(task.scorecard.score_sorting_direction, "desc")
        self.assertEqual(task.scorecard.initial_score, 2000)

    def test_legacy_task_scorecard_is_unaffected(self, *args):
        task = self._make_task(self.precision_original, task_subtype=None)
        self.assertEqual(task.scorecard.score_sorting_direction, "asc")
        self.assertEqual(task.scorecard.initial_score, 0)

    def test_descending_scorecard_subtracts_penalty_from_initial_score(self, *args):
        task = self._make_task(self.precision_original, task_subtype=PRECISION_NAVIGATION)
        contestant = self._make_contestant(task)
        processor = self._bare_processor(contestant)
        self.assertEqual(processor.score, 1000)

        processor.update_score_from_thread(self._penalty_message(30))
        self.assertEqual(processor.score, 970)

        processor.update_score_from_thread(self._penalty_message(15.5))
        self.assertEqual(processor.score, 954.5)

    def test_ascending_scorecard_still_adds_penalty_as_before(self, *args):
        # Same penalty magnitudes as the descending test above, against an unmodified legacy
        # scorecard - confirms the sign change is genuinely conditional, not a global flip.
        task = self._make_task(self.precision_original, task_subtype=None)
        contestant = self._make_contestant(task)
        processor = self._bare_processor(contestant)
        self.assertEqual(processor.score, 0)

        processor.update_score_from_thread(self._penalty_message(30))
        self.assertEqual(processor.score, 30)

        processor.update_score_from_thread(self._penalty_message(15.5))
        self.assertEqual(processor.score, 45.5)
