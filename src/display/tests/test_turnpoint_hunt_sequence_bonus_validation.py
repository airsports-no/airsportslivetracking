"""
Regression tests for the non-negative constraint on turnpoint_hunt_sequence_bonus (CodeRabbit
finding on #756): GateCalculator._score_turnpoint_hunt_sequence_bonus adds this value straight
through as an achievement score (see contestant_processor.ACHIEVEMENT_SCORE_TYPES) - a negative
configured value would silently subtract from a contestant's score for completing the full
declared sequence, the opposite of what a "bonus" should ever do. All three writable surfaces
(Django admin form, the legacy organizer-facing ScorecardForm, and the DRF serialiser the React
scorecard editor uses) must reject a negative value, matching the field's min: 0 in
react_vite/src/features/scorecard-editor/fieldMetadata.ts.
"""

import datetime

from django.contrib import admin
from django.forms.models import model_to_dict
from django.test import TestCase

from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
from display.forms import ScorecardForm
from display.models import Contest, NavigationTask, Route, Scorecard
from display.serialisers import ScorecardNestedSerialiser


class TestTurnpointHuntSequenceBonusValidation(TestCase):
    def setUp(self):
        self.scorecard = get_default_scorecard()
        # ScorecardForm's corridor_width field reads
        # scorecard.navigation_task_override.route.corridor_width - a bare original scorecard
        # (get_default_scorecard()'s return value) has no such override, so ScorecardForm needs
        # a scorecard that's actually attached to a task, unlike the admin form/serialiser
        # (neither reads corridor_width).
        contest = Contest.objects.create(
            name="Sequence bonus validation contest",
            start_time=datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 1, 2, tzinfo=datetime.timezone.utc),
        )
        self.task = NavigationTask.create(
            name="Sequence bonus validation task",
            contest=contest,
            route=Route.objects.create(name="sequence-bonus-validation-route"),
            original_scorecard=self.scorecard,
            start_time=datetime.datetime(2026, 1, 1, 6, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 1, 1, 16, tzinfo=datetime.timezone.utc),
        )
        self.task_scorecard = self.task.scorecard

    def test_admin_form_rejects_negative_sequence_bonus(self):
        form_class = admin.site._registry[Scorecard].get_form(None)
        data = model_to_dict(self.scorecard, exclude=["config"])
        data.update(form_class(instance=self.scorecard).initial)
        data["free_text"] = data.get("free_text") or "x"
        data["turnpoint_hunt_sequence_bonus"] = -50
        form = form_class(data=data, instance=self.scorecard)
        self.assertFalse(form.is_valid())
        self.assertIn("turnpoint_hunt_sequence_bonus", form.errors)

    def test_admin_form_accepts_zero_sequence_bonus(self):
        # 0 is the default/disabled value (GateCalculator._score_turnpoint_hunt_sequence_bonus's
        # `if not bonus: return`) - min_value=0 must not reject it.
        form_class = admin.site._registry[Scorecard].get_form(None)
        data = model_to_dict(self.scorecard, exclude=["config"])
        data.update(form_class(instance=self.scorecard).initial)
        data["free_text"] = data.get("free_text") or "x"
        data["turnpoint_hunt_sequence_bonus"] = 0
        form = form_class(data=data, instance=self.scorecard)
        self.assertTrue(form.is_valid(), form.errors)

    def test_legacy_scorecard_form_rejects_negative_sequence_bonus(self):
        data = model_to_dict(self.task_scorecard, exclude=["config"])
        data.update(ScorecardForm(instance=self.task_scorecard).initial)
        data["turnpoint_hunt_sequence_bonus"] = -50
        form = ScorecardForm(data=data, instance=self.task_scorecard)
        self.assertFalse(form.is_valid())
        self.assertIn("turnpoint_hunt_sequence_bonus", form.errors)

    def test_serialiser_rejects_negative_sequence_bonus(self):
        serialiser = ScorecardNestedSerialiser(
            self.scorecard, data={"turnpoint_hunt_sequence_bonus": -50}, partial=True
        )
        self.assertFalse(serialiser.is_valid())
        self.assertIn("turnpoint_hunt_sequence_bonus", serialiser.errors)

    def test_serialiser_accepts_zero_sequence_bonus(self):
        serialiser = ScorecardNestedSerialiser(self.scorecard, data={"turnpoint_hunt_sequence_bonus": 0}, partial=True)
        self.assertTrue(serialiser.is_valid(), serialiser.errors)
