import datetime
from unittest.mock import MagicMock, patch

from django.test import TestCase

from display.calculators.calculator import OrchestratorState
from display.calculators.gate_calculator import GateCalculator
from display.models.contestant_utility_models import ContestantReceivedPosition
from display.utilities.coordinate_utilities import Projector


class TestGateCalculatorEmptyRoute(TestCase):
    """2.B3 Duration tasks are authored with no route waypoints (just
    takeoff/landing gates and a landing area polygon). GateCalculator is
    unconditionally included in the precision calculator pipeline, so it must
    not assume there's always at least one waypoint to fall back on.
    """

    def setUp(self):
        self.contestant = MagicMock()
        self.contestant.gate_times = {}
        self.scorecard = MagicMock()
        self.route = MagicMock()
        self.queue = MagicMock()
        self.projector = Projector(60, 11)

    def _build_calculator(self) -> GateCalculator:
        with patch.object(GateCalculator, "_get_effective_waypoints", return_value=[]):
            return GateCalculator(
                self.contestant,
                self.scorecard,
                self.route,
                self.queue,
                live_processing=False,
                projector=self.projector,
            )

    def test_does_not_crash_constructing_with_no_route_waypoints(self):
        calculator = self._build_calculator()
        self.assertEqual(calculator.gates, [])
        self.assertIsNone(calculator.starting_line)

    def test_calculate_enroute_does_not_crash_with_no_gates(self):
        calculator = self._build_calculator()
        position = MagicMock(spec=ContestantReceivedPosition)
        position.latitude = 60.0
        position.longitude = 11.0
        position.time = datetime.datetime(2026, 1, 1, 10, 0, tzinfo=datetime.timezone.utc)
        state = OrchestratorState(
            last_gate=None,
            last_visible_gate=None,
            next_gate=None,
            in_range_of_gate=None,
            projector=self.projector,
            has_passed_finishpoint=False,
            recalculation_completed=True,
        )

        events = calculator.calculate_enroute([position], state)
        self.assertEqual(events, [])
