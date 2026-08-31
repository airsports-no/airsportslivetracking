"""
Regression test (local code review, scheduling/scorecards section, finding #6):
get_default_scorecard() renamed "Airsports Challenge 2023" -> "AirSport Challenge 2023" but then
upserted a different name, "Air Sport Challenge 2023" (extra space) - once both names existed
(the normal state after this had run at least once), a stray leftover "Airsports Challenge 2023"
row would hit Scorecard.name's unique constraint on the very next rename attempt.
"""

from django.db import IntegrityError
from django.test import TestCase

from display.default_scorecards.default_scorecard_airsport_challenge import get_default_scorecard
from display.models import Scorecard


class TestDefaultScorecardAirsportChallenge(TestCase):
    def test_repeated_calls_do_not_raise_even_with_a_stray_legacy_named_row(self):
        get_default_scorecard()
        Scorecard.objects.create(name="Airsports Challenge 2023", shortcut_name="legacy-airsport-challenge-name")

        try:
            get_default_scorecard()
        except IntegrityError:
            self.fail(
                "get_default_scorecard() must not raise IntegrityError when a stray "
                "'Airsports Challenge 2023' row coexists with the canonical scorecard"
            )

        self.assertEqual(Scorecard.objects.filter(name="Air Sport Challenge 2023").count(), 1)
