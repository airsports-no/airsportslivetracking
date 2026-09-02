from django.test import TestCase

from display.default_scorecards import default_scorecard_airsports
from display.models import Scorecard


class TestCloneObject(TestCase):
    def test_clone_object_only_foreign_keys(self):
        scorecard = default_scorecard_airsports.get_default_scorecard()
        self.assertEqual(1, Scorecard.objects.all().count())
        new_scorecard = scorecard.copy(f"navigationtasks_{scorecard.name}")
        self.assertEqual(2, Scorecard.objects.all().count())
        self.assertNotEqual(scorecard.pk, new_scorecard.pk)
        self.assertEqual(
            scorecard.get_gate_scorecard("to").to_dict(),
            new_scorecard.get_gate_scorecard("to").to_dict(),
        )
        # Independent copies: mutating one's config must not affect the other's.
        self.assertIsNot(scorecard.config["gates"], new_scorecard.config["gates"])
        new_scorecard.config["gates"]["to"]["maximum_penalty"] = 999999
        new_scorecard.save(update_fields=["config"])
        self.assertNotEqual(999999, scorecard.get_gate_scorecard("to").maximum_penalty)
