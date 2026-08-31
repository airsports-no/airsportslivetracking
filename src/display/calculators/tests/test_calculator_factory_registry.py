"""
Regression test for the calculator_factory.py -> task_type_registry.py refactor (Phase 0 of the
scorecard-system review roadmap). Asserts the registry-driven dispatch produces exactly the same
calculator lists the old if/elif chain did, for every task type and PRECISION's two
subtype-conditional branches, plus the unknown-calculator-value fallback.
"""

from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from display.calculators.anr_corridor_calculator import AnrCorridorCalculator
from display.calculators.backtracking_and_procedure_turns import BacktrackingAndProcedureTurnsCalculator
from display.calculators.calculator_factory import calculator_factory
from display.calculators.circle_calculator import CircleCalculator
from display.calculators.duration_calculator import DurationCalculator
from display.calculators.gate_calculator import GateCalculator
from display.calculators.landing_pattern_calculator import LandingPatternCalculator
from display.calculators.penalty_zone_calculator import PenaltyZoneCalculator
from display.calculators.poker_calculator import PokerCalculator
from display.calculators.prohibited_zone_calculator import ProhibitedZoneCalculator
from display.calculators.speed_inferred_takeoff_landing_calculator import SpeedInferredTakeoffLandingCalculator
from display.calculators.takeoff_and_landing_gate_calculator import TakeoffAndLandingGateCalculator
from display.utilities.cima_task_type_definitions import CIRCLE, DURATION
from display.utilities.navigation_task_type_definitions import (
    AIRSPORT_CHALLENGE,
    AIRSPORTS,
    ANR_CORRIDOR,
    LANDING,
    POKER,
    PRECISION,
)


def _mock_contestant(calculator, task_subtype=None):
    contestant = MagicMock()
    contestant.navigation_task.scorecard.calculator = calculator
    contestant.navigation_task.task_subtype = task_subtype
    return contestant


class TestCalculatorFactoryRegistry(SimpleTestCase):
    @patch("display.calculators.calculator_factory.Orchestrator")
    def test_precision_default_subtype(self, mock_orchestrator):
        calculator_factory(_mock_contestant(PRECISION), MagicMock())
        self.assertEqual(
            mock_orchestrator.call_args.args[2],
            [
                GateCalculator,
                TakeoffAndLandingGateCalculator,
                BacktrackingAndProcedureTurnsCalculator,
                ProhibitedZoneCalculator,
                PenaltyZoneCalculator,
            ],
        )

    @patch("display.calculators.calculator_factory.Orchestrator")
    def test_precision_circle_subtype_swaps_in_circle_calculator(self, mock_orchestrator):
        calculator_factory(_mock_contestant(PRECISION, task_subtype=CIRCLE), MagicMock())
        calculators = mock_orchestrator.call_args.args[2]
        self.assertNotIn(BacktrackingAndProcedureTurnsCalculator, calculators)
        self.assertEqual(calculators[1], CircleCalculator)

    @patch("display.calculators.calculator_factory.Orchestrator")
    def test_precision_duration_subtype_adds_duration_calculators(self, mock_orchestrator):
        calculator_factory(_mock_contestant(PRECISION, task_subtype=DURATION), MagicMock())
        calculators = mock_orchestrator.call_args.args[2]
        self.assertIn(SpeedInferredTakeoffLandingCalculator, calculators)
        self.assertIn(DurationCalculator, calculators)
        self.assertIn(BacktrackingAndProcedureTurnsCalculator, calculators)

    @patch("display.calculators.calculator_factory.Orchestrator")
    def test_anr_corridor_airsports_and_airsport_challenge_share_one_pipeline(self, mock_orchestrator):
        expected = [
            GateCalculator,
            TakeoffAndLandingGateCalculator,
            BacktrackingAndProcedureTurnsCalculator,
            AnrCorridorCalculator,
            ProhibitedZoneCalculator,
            PenaltyZoneCalculator,
        ]
        for calculator_type in (ANR_CORRIDOR, AIRSPORTS, AIRSPORT_CHALLENGE):
            mock_orchestrator.reset_mock()
            calculator_factory(_mock_contestant(calculator_type), MagicMock())
            self.assertEqual(mock_orchestrator.call_args.args[2], expected)

    @patch("display.calculators.calculator_factory.Orchestrator")
    def test_landing(self, mock_orchestrator):
        calculator_factory(_mock_contestant(LANDING), MagicMock())
        self.assertEqual(mock_orchestrator.call_args.args[2], [LandingPatternCalculator])

    @patch("display.calculators.calculator_factory.Orchestrator")
    def test_poker(self, mock_orchestrator):
        calculator_factory(_mock_contestant(POKER), MagicMock())
        self.assertEqual(
            mock_orchestrator.call_args.args[2],
            [PokerCalculator, ProhibitedZoneCalculator, PenaltyZoneCalculator],
        )

    @patch("display.calculators.calculator_factory.Orchestrator")
    def test_unrecognised_calculator_value_falls_back_to_bare_gate_calculator(self, mock_orchestrator):
        calculator_factory(_mock_contestant("some_legacy_calculator_value"), MagicMock())
        self.assertEqual(mock_orchestrator.call_args.args[2], [GateCalculator])
