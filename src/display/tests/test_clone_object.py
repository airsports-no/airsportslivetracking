from django.test import TestCase

from display.default_scorecards import default_scorecard_airsports
from display.models import Scorecard, GateScore


class TestCloneObject(TestCase):
    def test_clone_object_only_foreign_keys(self):
        scorecard = default_scorecard_airsports.get_default_scorecard()
        self.assertEqual(1, Scorecard.objects.all().count())
        self.assertEqual(8, GateScore.objects.all().count())
        new_scorecard = scorecard.copy(f"navigationtasks_{scorecard.name}")
        self.assertEqual(2, Scorecard.objects.all().count())
        self.assertEqual(16, GateScore.objects.all().count())
        self.assertNotEqual(scorecard.pk, new_scorecard.pk)
        self.assertNotEqual(scorecard.gatescore_set.get(gate_type="to"),
                            new_scorecard.gatescore_set.get(gate_type="to"))
