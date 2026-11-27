"""
The starting quality and the theoretical maximum of a contestant of a quality task (display.services.task_scoring).

For the deficit-style tasks (2.A1-2.A5) Q starts at the worst possible gate deficit of the contestant's own effective
route, taken from what the scorecard configures: the sum, over every gate that can actually be scored, of that gate's
worst possible outcome. The fixed-scale tasks start at the catalogue's number (2000 for the ANR, 250 for the circle) and
the achievement-style tasks (2.A6, 2.B2, 2.B3) at zero, with the sum of everything that can be earned as their
theoretical maximum.

Uses a real Scorecard (from create_scorecards()) so get_gate_scorecard()'s config-backed lookups behave exactly as in
production, but a lightweight SimpleNamespace for the contestant/navigation task/route: theoretical_gate_quality only
reads the task type, scorecard, and route.waypoints/takeoff_gates/landing_gates (via get_effective_route_waypoints,
which falls back to the shared route when the contestant has no contestanttaskconfiguration).
"""

from types import SimpleNamespace

from django.test import TestCase

from display.calculators.tests.test_score_message_kinds import MessageTestCase
from display.models import Contestant, ContestantTaskConfiguration, Route, Scorecard
from display.services.task_scoring import quality_baseline, theoretical_gate_quality
from display.utilities.gate_definitions import DUMMY, LANDING_GATE, TAKEOFF_GATE, TURNPOINT
from display.utilities.task_types import (
    ANR_CATALOGUE,
    CIRCLE,
    CONTRACT_NAVIGATION_TIME_CONTROLS,
    CURVE_NAVIGATION_TIME_ESTIMATION,
    DURATION,
    KNOWN_CIRCUIT,
    LIMITED_FUEL_TURNPOINT_HUNT,
    PRECISION_NAVIGATION,
    TURNPOINT_HUNT,
    UNKNOWN_LEGS,
)
from display.waypoint import Waypoint


class TestTheoreticalGateQuality(TestCase):
    def setUp(self):
        # A freshly created, saved Scorecard (real pk) rather than a shared original: get_gate_scorecard() caches per
        # (pk, gate_type) keyed off a per-pk cache version, so an unsaved or shared scorecard risks stale reads.
        Scorecard.SCORECARD_CACHE.clear()
        self.scorecard = Scorecard.objects.create(
            name="quality-baseline-test-scorecard",
            shortcut_name="quality-baseline-test-scorecard",
            config={
                "gates": {
                    TURNPOINT: {"missed_penalty": 200, "maximum_penalty": 150},
                    "secret": {"missed_penalty": 50, "maximum_penalty": 50},
                    TAKEOFF_GATE: {"missed_penalty": 75, "maximum_penalty": 40},
                    LANDING_GATE: {"missed_penalty": 30, "maximum_penalty": 60},
                }
            },
        )

    def tearDown(self):
        Scorecard.SCORECARD_CACHE.clear()

    @staticmethod
    def _waypoint(gate_type, *, on_curved_segment=False, gate_check=True, time_check=True) -> Waypoint:
        waypoint = Waypoint(gate_type)
        waypoint.type = gate_type
        waypoint.on_curved_segment = on_curved_segment
        waypoint.gate_check = gate_check
        waypoint.time_check = time_check
        return waypoint

    def _contestant(self, subtype, waypoints, takeoff_gates=None, landing_gates=None):
        route = SimpleNamespace(
            waypoints=waypoints, takeoff_gates=takeoff_gates or [], landing_gates=landing_gates or []
        )
        navigation_task = SimpleNamespace(
            effective_task_subtype=subtype, task_subtype=subtype, scorecard=self.scorecard, route=route
        )
        return SimpleNamespace(navigation_task=navigation_task)

    def test_empty_route_has_no_deficit_to_lose(self):
        self.assertEqual(0, theoretical_gate_quality(self._contestant(KNOWN_CIRCUIT, [])))

    def test_sums_worst_case_per_gate_using_the_worse_of_missed_and_maximum_penalty(self):
        # tp: worse of 200/150 = 200. Two tp + one hidden gate of the secret type (see the next test).
        contestant = self._contestant(
            KNOWN_CIRCUIT, [self._waypoint(TURNPOINT), self._waypoint("secret"), self._waypoint(TURNPOINT)]
        )
        self.assertEqual(200 + 100 + 200, theoretical_gate_quality(contestant))

    def test_a_hidden_gate_of_2a4_and_2a5_is_worth_the_scorecards_hidden_gate_value_not_its_gate_score(self):
        for subtype in (KNOWN_CIRCUIT, UNKNOWN_LEGS):
            for value in (100, 60):
                self.scorecard.observation_hidden_gate_value = value
                contestant = self._contestant(subtype, [self._waypoint("secret", time_check=False)])
                self.assertEqual(value, theoretical_gate_quality(contestant), (subtype, value))
        contestant = self._contestant(KNOWN_CIRCUIT, [self._waypoint("secret", gate_check=False, time_check=False)])
        self.assertEqual(0, theoretical_gate_quality(contestant))

    def test_dummy_and_curved_segment_waypoints_are_excluded(self):
        contestant = self._contestant(
            KNOWN_CIRCUIT,
            [self._waypoint(TURNPOINT), self._waypoint(DUMMY), self._waypoint(TURNPOINT, on_curved_segment=True)],
        )
        self.assertEqual(200, theoretical_gate_quality(contestant))

    def test_takeoff_and_landing_gates_count_with_their_timing_cap_only(self):
        # Take-off and landing have no "missed" scoring at all: takeoff worse-of(0, 40) = 40, not its 75.
        contestant = self._contestant(
            CURVE_NAVIGATION_TIME_ESTIMATION,
            [self._waypoint(TURNPOINT)],
            takeoff_gates=[object()],
            landing_gates=[object()],
        )
        # (and the turn point of 2.A1 is a time gate worth its Emax, the 150 maximum error)
        self.assertEqual(150 + 40 + 60, theoretical_gate_quality(contestant))

    def test_waypoint_with_neither_check_flag_contributes_nothing(self):
        contestant = self._contestant(
            KNOWN_CIRCUIT,
            [self._waypoint(TURNPOINT), self._waypoint(TURNPOINT, gate_check=False, time_check=False)],
        )
        self.assertEqual(200, theoretical_gate_quality(contestant))

    def test_gate_check_only_waypoint_uses_missed_penalty_only(self):
        contestant = self._contestant(KNOWN_CIRCUIT, [self._waypoint(TURNPOINT, time_check=False)])
        self.assertEqual(200, theoretical_gate_quality(contestant))

    def test_time_check_only_waypoint_uses_maximum_penalty_only(self):
        contestant = self._contestant(KNOWN_CIRCUIT, [self._waypoint(TURNPOINT, gate_check=False)])
        self.assertEqual(150, theoretical_gate_quality(contestant))

    def test_curve_navigation_starts_at_qh_plus_emax_per_time_gate(self):
        # 2.A1: Qh = 1000 x H / Nh, Qt = Emax x Nt - Et. SP and FP are not time gates, hidden gates are not timed
        # (the turn point's Emax is its 150 maximum error here).
        waypoints = [
            self._waypoint("sp"),
            self._waypoint(TURNPOINT),
            self._waypoint("secret", time_check=False),
            self._waypoint("secret", time_check=False),
            self._waypoint(TURNPOINT),
            self._waypoint("fp"),
        ]
        contestant = self._contestant(CURVE_NAVIGATION_TIME_ESTIMATION, waypoints)
        self.assertEqual(1000 + 2 * 150, theoretical_gate_quality(contestant))
        self.assertEqual((1300, 1300), quality_baseline(contestant))

    def test_precision_navigation_starts_at_emax_per_hidden_gate(self):
        # 2.A2: Qp = Emax x Ng, Qt = -sum(Ei): the time errors only deduct, so a perfect flight is worth the hidden
        # gates alone (a hidden gate's Emax is its 50 maximum error here)
        waypoints = [
            self._waypoint("sp"),
            self._waypoint(TURNPOINT),
            self._waypoint("secret"),
            self._waypoint("secret"),
            self._waypoint("fp"),
        ]
        contestant = self._contestant(PRECISION_NAVIGATION, waypoints)
        self.assertEqual(2 * 50, theoretical_gate_quality(contestant))

    def test_the_deficit_style_task_types_start_at_it_and_it_is_also_their_theoretical_maximum(self):
        for subtype in (
            KNOWN_CIRCUIT,
            UNKNOWN_LEGS,
        ):
            with self.subTest(subtype=subtype):
                contestant = self._contestant(subtype, [self._waypoint(TURNPOINT)])
                self.assertEqual((200, 200), quality_baseline(contestant))

    def test_contract_navigation_starts_at_emax_per_time_gate_and_can_earn_qp_on_top_of_it(self):
        # 2.A3: Qt = Emax x (the time gates), here one turn point with a time check (its 150 maximum error); Qp = 1000 x
        # V / Vmax is added for the best contestant of the task only, so the theoretical maximum has the 1000 as well.
        contestant = self._contestant(CONTRACT_NAVIGATION_TIME_CONTROLS, [self._waypoint(TURNPOINT)])
        self.assertEqual((150, 1150), quality_baseline(contestant))

    def test_the_fixed_scale_tasks_start_at_the_catalogue_number(self):
        contestant = self._contestant(ANR_CATALOGUE, [self._waypoint(TURNPOINT)])
        self.assertEqual((2000, 2000), quality_baseline(contestant))
        contestant = self._contestant(CIRCLE, [])
        self.assertEqual((250, 250), quality_baseline(contestant))

    def test_the_duration_task_starts_at_zero_and_has_nothing_to_earn_in_theory(self):
        self.assertEqual((0, 0), quality_baseline(self._contestant(DURATION, [])))


class TestQualityBaselineOfRealContestants(MessageTestCase):
    def setUp(self):
        super().setUp()
        Scorecard.SCORECARD_CACHE.clear()
        self.addCleanup(Scorecard.SCORECARD_CACHE.clear)

    @staticmethod
    def _turnpoint(name: str) -> Waypoint:
        waypoint = Waypoint(name)
        waypoint.type = TURNPOINT
        waypoint.gate_check = True
        waypoint.time_check = True
        return waypoint

    def test_the_deficit_comes_from_the_contestants_declared_subset_not_the_shared_route(self):
        # 2.A3: the shared route carries more catalogue turnpoints than any one contestant declares to fly, and the
        # starting quality must not count the points that can never score for this contestant.
        route = Route.objects.create(
            name="contract-route",
            waypoints=[self._turnpoint("TP1"), self._turnpoint("TP2"), self._turnpoint("TP3")],
        )
        task = self.make_task(CONTRACT_NAVIGATION_TIME_CONTROLS)
        task.route = route
        task.save(update_fields=["route"])
        task.scorecard.config.setdefault("gates", {})[TURNPOINT] = {"missed_penalty": 200, "maximum_penalty": 150}
        task.scorecard.save(update_fields=["config"])
        contestant = self.make_contestant(task)
        ContestantTaskConfiguration.objects.create(
            contestant=contestant,
            task_subtype=CONTRACT_NAVIGATION_TIME_CONTROLS,
            is_valid=True,
            compiled_effective_route_payload={
                "effective_waypoints": [
                    {
                        "name": "TP1",
                        "latitude": 0.0,
                        "longitude": 0.0,
                        "type": TURNPOINT,
                        "width": 0.1,
                        "time_check": True,
                        "gate_check": True,
                    }
                ]
            },
        )
        contestant = Contestant.objects.get(pk=contestant.pk)
        # TP1 is the only point of the declared route (a time gate worth its 150 Emax); TP2 and TP3 do not count
        self.assertEqual((150, 1150), quality_baseline(contestant))

    def _hunt_contestant(self, target_values: dict, sequence_bonus: float = 0, subtype=TURNPOINT_HUNT):
        task = self.make_task(subtype)
        if sequence_bonus:
            task.scorecard.config["turnpoint_hunt_sequence_bonus"] = sequence_bonus
            task.scorecard.save(update_fields=["config"])
        contestant = self.make_contestant(task)
        ContestantTaskConfiguration.objects.create(
            contestant=contestant,
            task_subtype=subtype,
            is_valid=True,
            compiled_effective_route_payload={"scored_target_values": target_values},
        )
        return Contestant.objects.get(pk=contestant.pk)

    def test_a_hunt_starts_at_zero_and_can_earn_the_targets_and_the_sequence_bonus(self):
        contestant = self._hunt_contestant({"A": 60, "B": 40}, sequence_bonus=25)
        self.assertEqual((0, 125), quality_baseline(contestant))

    def test_a_limited_fuel_hunt_is_the_same(self):
        contestant = self._hunt_contestant({"A": 60}, subtype=LIMITED_FUEL_TURNPOINT_HUNT)
        self.assertEqual((0, 60), quality_baseline(contestant))

    def test_a_hunt_without_a_valid_declaration_can_earn_nothing_in_theory(self):
        contestant = self.make_contestant(self.make_task(TURNPOINT_HUNT))
        self.assertEqual((0, 0), quality_baseline(contestant))
