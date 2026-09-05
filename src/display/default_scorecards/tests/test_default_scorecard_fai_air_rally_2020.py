"""
Regression test (local code review, scheduling/scorecards section, finding #7): the FAI Air
Rally 2020 scorecard's header comment documents "Extended starting gate 2NM", but STARTINGPOINT
was cloned from the regular turnpoint gate score, inheriting extended_gate_width=0.3 and
bad_crossing_extended_gate_penalty=0 instead of the 2NM/200-point rule every other precision
scorecard uses for the starting point - the rule that exists specifically to catch an
early/backwards start awarded 0 points and detected at the wrong width.
"""

from django.test import TestCase

from display.default_scorecards.default_scorecard_fai_air_rally_2020 import get_default_scorecard
from display.utilities.gate_definitions import STARTINGPOINT, TURNPOINT


class TestDefaultScorecardFaiAirRally2020(TestCase):
    def test_starting_point_has_its_own_extended_gate_rule(self):
        scorecard = get_default_scorecard()

        starting_point = scorecard.get_gate_scorecard(STARTINGPOINT)
        self.assertEqual(starting_point.extended_gate_width, 2)
        self.assertEqual(starting_point.bad_crossing_extended_gate_penalty, 200)

    def test_starting_point_is_no_longer_an_identical_clone_of_the_turnpoint_gate(self):
        scorecard = get_default_scorecard()

        starting_point = scorecard.get_gate_scorecard(STARTINGPOINT)
        turnpoint = scorecard.get_gate_scorecard(TURNPOINT)
        self.assertNotEqual(starting_point.extended_gate_width, turnpoint.extended_gate_width)
        self.assertNotEqual(
            starting_point.bad_crossing_extended_gate_penalty, turnpoint.bad_crossing_extended_gate_penalty
        )

    def test_starting_point_extended_gate_fields_are_visible_in_the_admin_form(self):
        # Regression test (CodeRabbit review of PR #738): GateScore.visible_fields derives the
        # organizer-facing edit form's fields from included_fields - extended_gate_width and
        # bad_crossing_extended_gate_penalty were configured but not listed, so administrators
        # could not view or edit the very rule this scorecard exists to configure.
        scorecard = get_default_scorecard()

        starting_point = scorecard.get_gate_scorecard(STARTINGPOINT)
        self.assertIn("extended_gate_width", starting_point.visible_fields)
        self.assertIn("bad_crossing_extended_gate_penalty", starting_point.visible_fields)
