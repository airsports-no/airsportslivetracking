"""The weights of the gates of 2.A1 and 2.A2 (display.services.catalogue_gate_quality), against the catalogue's formulas."""

import datetime
from types import SimpleNamespace

from django.test import SimpleTestCase

from display.default_scorecards.default_scorecard_cima_precision import CATALOGUE_TIMING
from display.models.scorecard_and_gate_score import GateScoreValue
from display.services.catalogue_gate_quality import CatalogueGateQuality
from display.utilities.gate_definitions import DUMMY, FINISHPOINT, SECRETPOINT, STARTINGPOINT, TAKEOFF_GATE, TURNPOINT
from display.utilities.task_types import (
    CONTRACT_NAVIGATION_TIME_CONTROLS,
    CURVE_NAVIGATION_TIME_ESTIMATION,
    KNOWN_CIRCUIT,
    PRECISION_NAVIGATION,
    get_task_type,
)

NOON = datetime.datetime(2026, 8, 1, 12, 0, tzinfo=datetime.timezone.utc)


class StubScorecard:
    """The gate scores of the CIMA Precision scorecard: one point per second, at most 180, 180 if not flown."""

    def get_gate_scorecard(self, gate_type):
        return GateScoreValue.from_dict(gate_type, CATALOGUE_TIMING)

    def get_gate_timing_score_for_gate_type(self, gate_type, planned, actual):
        return self.get_gate_scorecard(gate_type).calculate_score(planned, actual)


def gate(name, gate_type, time_check=True, gate_check=True):
    return SimpleNamespace(name=name, type=gate_type, time_check=time_check, gate_check=gate_check)


def route(hidden: int, hidden_timed=False):
    """SP, TP1, TP2, FP and `hidden` hidden gates."""
    return [
        gate("SP", STARTINGPOINT),
        gate("TP1", TURNPOINT),
        *[gate(f"HG{number}", SECRETPOINT, time_check=hidden_timed) for number in range(1, hidden + 1)],
        gate("TP2", TURNPOINT),
        gate("FP", FINISHPOINT),
    ]


def quality(subtype, items):
    return CatalogueGateQuality.for_task_type(get_task_type(subtype), StubScorecard(), items)


class CurveNavigationWeightsTest(SimpleTestCase):
    """2.A1: Qh = 1000 x H / Nh, Qt = Emax x Nt - Et; SP and FP are not time gates."""

    def test_a_hidden_gate_is_worth_its_share_of_one_thousand(self):
        items = route(hidden=4)
        weights = quality(CURVE_NAVIGATION_TIME_ESTIMATION, items)
        self.assertEqual(weights.hidden_gate_count, 4)
        self.assertEqual(weights.hidden_gate_value(items[2]), 250)
        self.assertEqual(weights.missed_loss(items[2]), 250)

    def test_the_value_follows_the_number_of_hidden_gates(self):
        items = route(hidden=7)
        weights = quality(CURVE_NAVIGATION_TIME_ESTIMATION, items)
        self.assertAlmostEqual(weights.missed_loss(items[2]), 1000 / 7)

    def test_a_perfect_flight_is_worth_qh_plus_emax_per_time_gate(self):
        items = route(hidden=4)
        weights = quality(CURVE_NAVIGATION_TIME_ESTIMATION, items)
        # 1000 + Emax x Nt with the two turn points as time gates
        self.assertAlmostEqual(sum(weights.starting_quality(item) for item in items), 1000 + 2 * 180)

    def test_the_starting_quality_is_what_every_gate_can_lose(self):
        items = route(hidden=7)
        weights = quality(CURVE_NAVIGATION_TIME_ESTIMATION, items)
        self.assertAlmostEqual(
            sum(weights.starting_quality(item) for item in items), sum(weights.missed_loss(item) for item in items)
        )

    def test_a_time_gate_loses_its_error_at_most_emax_and_emax_when_not_flown(self):
        items = route(hidden=4)
        weights = quality(CURVE_NAVIGATION_TIME_ESTIMATION, items)
        turn_point = items[1]
        self.assertEqual(weights.timing_loss(turn_point, NOON, NOON + datetime.timedelta(seconds=35)), 35)
        self.assertEqual(weights.timing_loss(turn_point, NOON, NOON - datetime.timedelta(seconds=500)), 180)
        self.assertEqual(weights.missed_loss(turn_point), 180)

    def test_start_point_finish_point_and_untimed_hidden_gates_are_not_scored(self):
        items = route(hidden=4, hidden_timed=True)
        weights = quality(CURVE_NAVIGATION_TIME_ESTIMATION, items)
        start, finish, hidden = items[0], items[-1], items[2]
        for item in (start, finish):
            self.assertFalse(weights.is_timed(item))
            self.assertEqual(weights.missed_loss(item), 0)
            self.assertEqual(weights.starting_quality(item), 0)
        self.assertFalse(weights.is_timed(hidden))

    def test_a_task_without_hidden_gates_drops_the_spatial_part(self):
        items = route(hidden=0)
        weights = quality(CURVE_NAVIGATION_TIME_ESTIMATION, items)
        self.assertEqual(sum(weights.starting_quality(item) for item in items), 2 * 180)

    def test_a_task_without_time_gates_drops_the_time_part(self):
        items = [gate("SP", STARTINGPOINT), gate("HG1", SECRETPOINT, time_check=False), gate("FP", FINISHPOINT)]
        weights = quality(CURVE_NAVIGATION_TIME_ESTIMATION, items)
        self.assertEqual(sum(weights.starting_quality(item) for item in items), 1000)

    def test_an_invalidated_hidden_gate_loses_its_value_only(self):
        items = route(hidden=4)
        weights = quality(CURVE_NAVIGATION_TIME_ESTIMATION, items)
        self.assertEqual(weights.invalidated_loss(items[2]), 250)

    def test_gates_without_a_gate_check_cannot_be_missed_and_do_not_count_in_nh(self):
        items = route(hidden=4)
        items[2].gate_check = False
        weights = quality(CURVE_NAVIGATION_TIME_ESTIMATION, items)
        self.assertEqual(weights.hidden_gate_count, 3)
        self.assertEqual(weights.missed_loss(items[2]), 0)
        self.assertAlmostEqual(weights.hidden_gate_value(items[3]), 1000 / 3)


class PrecisionNavigationWeightsTest(SimpleTestCase):
    """2.A2: Qp = Emax x Ng, Qt = -sum(Ei); SP is time zero, the hidden gates and FP are time gates."""

    def setUp(self):
        self.items = route(hidden=4, hidden_timed=True)
        self.weights = quality(PRECISION_NAVIGATION, self.items)
        self.hidden = self.items[2]

    def test_a_hidden_gate_is_worth_emax(self):
        self.assertEqual(self.weights.hidden_gate_value(self.hidden), 180)

    def test_a_perfect_flight_is_worth_emax_per_hidden_gate_and_time_errors_only_deduct(self):
        self.assertEqual(sum(self.weights.starting_quality(item) for item in self.items), 4 * 180)

    def test_a_hidden_gate_not_crossed_loses_its_value_and_emax_of_time_error(self):
        self.assertEqual(self.weights.missed_loss(self.hidden), 360)

    def test_the_time_error_of_a_hidden_gate_is_charged_as_for_every_time_gate(self):
        self.assertEqual(self.weights.timing_loss(self.hidden, NOON, NOON + datetime.timedelta(seconds=30)), 30)

    def test_an_invalidated_hidden_gate_loses_its_value_and_its_time_comes_from_the_first_crossing(self):
        self.assertEqual(self.weights.invalidated_loss(self.hidden), 180)
        crossed_late = NOON + datetime.timedelta(seconds=12)
        self.assertEqual(self.weights.invalidated_loss(self.hidden, NOON, crossed_late), 192)

    def test_the_finish_point_is_a_time_gate_and_the_start_point_is_not(self):
        start, finish = self.items[0], self.items[-1]
        self.assertEqual(self.weights.missed_loss(finish), 180)
        self.assertEqual(self.weights.missed_loss(start), 0)

    def test_a_hidden_gate_without_a_time_check_is_not_timed(self):
        untimed = route(hidden=1)[2]
        weights = quality(PRECISION_NAVIGATION, [untimed])
        self.assertEqual(weights.missed_loss(untimed), 180)


def contract_route():
    """SP, MP and FP (time gates) and two declared catalogue points without a time check."""
    return [
        gate("SP", STARTINGPOINT),
        gate("A", TURNPOINT, time_check=False),
        gate("MP", TURNPOINT),
        gate("B", TURNPOINT, time_check=False),
        gate("FP", FINISHPOINT),
    ]


class ContractNavigationWeightsTest(SimpleTestCase):
    """2.A3: Qt = Emax x 3 - Et over SP, MP and FP; the declared points only count in V = N - Ep."""

    def setUp(self):
        self.items = contract_route()
        self.weights = quality(CONTRACT_NAVIGATION_TIME_CONTROLS, self.items)
        self.sp, self.a, self.mp, self.b, self.fp = self.items

    def test_sp_mp_and_fp_are_the_time_gates_worth_emax_each(self):
        self.assertEqual([self.weights.is_timed(item) for item in self.items], [True, False, True, False, True])
        self.assertEqual(sum(self.weights.starting_quality(item) for item in self.items), 3 * 180)

    def test_a_declared_point_is_worth_nothing_in_points_of_q(self):
        self.assertEqual(self.weights.starting_quality(self.a), 0)
        self.assertEqual(self.weights.missed_loss(self.a), 0)

    def test_a_time_gate_not_flown_loses_emax(self):
        for item in (self.sp, self.mp, self.fp):
            self.assertEqual(self.weights.missed_loss(item), 180)

    def test_a_declared_turn_point_adds_one_to_v_and_the_mandatory_points_nothing(self):
        self.assertEqual([self.weights.v_gain(item) for item in self.items], [0, 1, 0, 1, 0])

    def test_every_declared_point_not_flown_takes_one_off_v_sp_mp_and_fp_included(self):
        self.assertEqual([self.weights.v_loss(item) for item in self.items], [1, 1, 1, 1, 1])

    def test_a_point_nobody_checks_is_not_declared(self):
        unchecked = gate("X", TURNPOINT, time_check=False, gate_check=False)
        self.assertEqual((self.weights.v_gain(unchecked), self.weights.v_loss(unchecked)), (0, 0))

    def test_the_other_task_types_do_not_count_in_v(self):
        weights = quality(CURVE_NAVIGATION_TIME_ESTIMATION, route(hidden=2))
        turn_point, start = gate("TP", TURNPOINT, time_check=False), gate("SP", STARTINGPOINT)
        self.assertEqual((weights.v_gain(turn_point), weights.v_loss(start)), (0, 0))


class OtherGatesAndTaskTypesTest(SimpleTestCase):
    def test_only_the_catalogue_task_types_have_weights(self):
        # 2.A4 scores the gates by the scorecard's flat scores; 2.A3 has weights since its formulas are followed
        self.assertIsNone(quality(KNOWN_CIRCUIT, route(hidden=2)))

    def test_gate_types_the_model_does_not_cover_keep_the_scorecards_flat_scores(self):
        takeoff = gate("TO", TAKEOFF_GATE, gate_check=False)
        weights = quality(PRECISION_NAVIGATION, [takeoff])
        self.assertEqual(weights.starting_quality(takeoff), 180)

    def test_dummy_gates_do_not_count(self):
        items = [*route(hidden=2), gate("D", DUMMY, gate_check=True)]
        weights = quality(CURVE_NAVIGATION_TIME_ESTIMATION, items)
        self.assertEqual(weights.hidden_gate_count, 2)
