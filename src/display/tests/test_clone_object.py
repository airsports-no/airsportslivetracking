from django.test import TestCase

from display.clone_object import clone_object_only_foreign_keys
from display.default_scorecards import default_scorecard_airsports
from display.models import Scorecard, GateScore


class TestCloneObject(TestCase):
    def test_clone_object_only_foreign_keys(self):
        scorecard = default_scorecard_airsports.get_default_scorecard()
        self.assertEqual(1, Scorecard.objects.all().count())
        self.assertEqual(4, GateScore.objects.all().count())
        new_scorecard = clone_object_only_foreign_keys(scorecard, {"name": f"navigationtasks_{scorecard.name}"})
        self.assertEqual(2, Scorecard.objects.all().count())
        # Gate scorecards are reused in the original, but they are created as separate copies in the new which means
        # we get all six (in addition to the original 4)
        self.assertEqual(10, GateScore.objects.all().count())
        self.assertNotEqual(scorecard.pk, new_scorecard.pk)
        self.assertNotEqual(scorecard.takeoff_gate_score.pk, new_scorecard.takeoff_gate_score.pk)
