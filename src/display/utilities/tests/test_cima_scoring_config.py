"""
Regression test (scorecard-system review roadmap, Phase 1): every CimaScoringConfig field was
previously read via getattr(scorecard, "field", default) or default at each call site - since
none of these Scorecard columns are actually nullable, the `or default` idiom silently replaced
a legitimately-configured falsy value (0, False, "") with the default. Concretely,
fuel_deadline_penalty=0 (an organizer disabling the penalty) silently became 100 at scoring time.
"""

from django.test import SimpleTestCase, TestCase

from display.default_scorecards.create_scorecards import create_scorecards
from display.models import Scorecard
from display.utilities.cima_scoring_config import CimaScoringConfig


class TestCimaScoringConfigDefaults(SimpleTestCase):
    def test_default_construction_matches_scorecard_model_defaults(self):
        config = CimaScoringConfig()
        self.assertEqual(config.compulsory_timing_tolerance_seconds, 10)
        self.assertIsNone(config.maximum_task_duration_minutes)
        self.assertEqual(config.maximum_task_duration_penalty, 100)
        self.assertEqual(config.fuel_deadline_penalty, 100)
        self.assertEqual(config.duration_normalization_policy, "")
        self.assertFalse(config.duration_residual_fuel_required)
        self.assertEqual(config.circle_radius_min_m, 200)
        self.assertEqual(config.circle_radius_max_m, 750)
        self.assertEqual(config.speed_keeping_tolerance_kt, 5)
        self.assertEqual(config.speed_keeping_penalty_per_kt, 1)
        self.assertEqual(config.anr_route_to_sp_penalty, 200)
        self.assertEqual(config.anr_route_from_fp_penalty, 200)


class TestCimaScoringConfigFromScorecard(TestCase):
    def setUp(self):
        create_scorecards()
        self.scorecard = Scorecard.get_originals().get(shortcut_name="FAI Precision")

    def test_a_legitimately_configured_zero_penalty_is_not_replaced_by_the_default(self):
        # This is the exact bug: float(getattr(scorecard, "fuel_deadline_penalty", 100) or 100)
        # collapsed 0.0 back to 100 because 0.0 is falsy, not just "unset".
        self.scorecard.fuel_deadline_penalty = 0
        self.scorecard.maximum_task_duration_penalty = 0
        self.scorecard.circle_radius_min_m = 0
        self.scorecard.duration_residual_fuel_required = False
        self.scorecard.save()

        config = CimaScoringConfig.from_scorecard(self.scorecard)

        self.assertEqual(config.fuel_deadline_penalty, 0)
        self.assertEqual(config.maximum_task_duration_penalty, 0)
        self.assertEqual(config.circle_radius_min_m, 0)
        self.assertFalse(config.duration_residual_fuel_required)

    def test_reads_the_actual_configured_values(self):
        self.scorecard.fuel_deadline_penalty = 42
        self.scorecard.maximum_task_duration_minutes = 90
        self.scorecard.duration_normalization_policy = "raw_minutes"
        self.scorecard.save()

        config = CimaScoringConfig.from_scorecard(self.scorecard)

        self.assertEqual(config.fuel_deadline_penalty, 42)
        self.assertEqual(config.maximum_task_duration_minutes, 90)
        self.assertEqual(config.duration_normalization_policy, "raw_minutes")

    def test_maximum_task_duration_minutes_stays_none_when_unset(self):
        self.assertIsNone(self.scorecard.maximum_task_duration_minutes)
        config = CimaScoringConfig.from_scorecard(self.scorecard)
        self.assertIsNone(config.maximum_task_duration_minutes)
