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

        starting_point = scorecard.gatescore_set.get(gate_type=STARTINGPOINT)
        self.assertEqual(starting_point.extended_gate_width, 2)
        self.assertEqual(starting_point.bad_crossing_extended_gate_penalty, 200)

    def test_starting_point_is_no_longer_an_identical_clone_of_the_turnpoint_gate(self):
        scorecard = get_default_scorecard()

        starting_point = scorecard.gatescore_set.get(gate_type=STARTINGPOINT)
        turnpoint = scorecard.gatescore_set.get(gate_type=TURNPOINT)
        self.assertNotEqual(starting_point.extended_gate_width, turnpoint.extended_gate_width)
        self.assertNotEqual(
            starting_point.bad_crossing_extended_gate_penalty, turnpoint.bad_crossing_extended_gate_penalty
        )
