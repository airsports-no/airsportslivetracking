"""
Regression test: every scorecard's TAKEOFF_GATE grants a 60-second graceperiod_after
(tolerance for a late takeoff), but graceperiod_before was inconsistent - most cards
explicitly set it to 0 (an early takeoff should always be penalised), while
default_scorecard_airsports.py omitted it entirely (silently inheriting the model default of
3) and default_scorecard_airsport_challenge.py explicitly set it to 3. Both normalized to 0,
confirmed with the repo owner.
"""

from django.test import TestCase

from display.default_scorecards.default_scorecard_airsport_challenge import (
    get_default_scorecard as get_airsport_challenge_scorecard,
)
from display.default_scorecards.default_scorecard_airsports import get_default_scorecard as get_airsports_scorecard
from display.utilities.gate_definitions import TAKEOFF_GATE


class TestTakeoffGateGracePeriodNormalization(TestCase):
    def test_airsports_takeoff_gate_has_zero_graceperiod_before(self):
        scorecard = get_airsports_scorecard()
        gate_score = scorecard.gatescore_set.get(gate_type=TAKEOFF_GATE)
        self.assertEqual(0, gate_score.graceperiod_before)
        self.assertEqual(60, gate_score.graceperiod_after)

    def test_airsport_challenge_takeoff_gate_has_zero_graceperiod_before(self):
        scorecard = get_airsport_challenge_scorecard()
        gate_score = scorecard.gatescore_set.get(gate_type=TAKEOFF_GATE)
        self.assertEqual(0, gate_score.graceperiod_before)
        self.assertEqual(60, gate_score.graceperiod_after)
