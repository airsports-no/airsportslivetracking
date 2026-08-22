"""Synthetic (no DB, no fixture files, no ContestantProcessor/Orchestrator)
state-machine tests for AnrCorridorCalculator, focused on the fragile
"gate crossed while outside the corridor" and excursion-finalization paths
that the existing real-track-replay tests (test_anr_corridor_calculator.py)
and the smaller synthetic suite in test_calculators_unit.py don't cover.

Methodology: every expected value below is derived by hand from
_calculate_current_leg_penalty's formula (corridor_outside_penalty *
round(max(0, cumulative_outside_seconds - grace_time)), capped per leg when
corridor_maximum_penalty_is_per_leg and corridor_maximum_penalty > 0) before
being asserted - see the comment above each assertion. Where a test exposes
behavior that looks wrong rather than merely different from what a real
track produced, it's written with the CORRECT expected value and marked
@skip("SUSPECTED BUG: ...") with an explanation, never silently asserting
a value believed to be incorrect. See synthetic_helpers.py for the general
approach these tests build on.
"""

import datetime
from queue import Queue
from unittest.mock import MagicMock, patch

from display.calculators.anr_corridor_calculator import AnrCorridorCalculator
from display.calculators.calculator import FinishLinePassedEvent, GateMissedEvent, GatePassedEvent
from display.calculators.tests.synthetic_helpers import SyntheticCalculatorTestBase


class TestAnrCorridorCalculatorSynthetic(SyntheticCalculatorTestBase):
    def setUp(self):
        super().setUp()
        self.contestant = MagicMock()
        self.contestant.navigation_task.task_subtype = None  # not ANR_CATALOGUE: skip auxiliary route-compliance checks
        self.contestant.contestanttaskconfiguration = MagicMock()
        self.contestant.contestanttaskconfiguration.is_valid = False

        self.route = MagicMock()
        self.route.corridor_width = 0.5
        self.route.waypoints = []

        self.scorecard = MagicMock()
        self.scorecard.corridor_grace_time = 5
        self.scorecard.corridor_outside_penalty = 10  # points per second beyond grace
        self.scorecard.corridor_maximum_penalty = -1  # no cap unless a test overrides it
        self.scorecard.corridor_maximum_penalty_is_per_leg = True

        # build_polygon() needs real corridor_polygon geometry; the state
        # machine under test doesn't depend on the real polygon shape, only
        # on what _check_inside_polygon returns, which every test below
        # patches directly - so a bare MagicMock is enough here.
        self.build_polygon_patcher = patch.object(AnrCorridorCalculator, "build_polygon", return_value=MagicMock())
        self.build_polygon_patcher.start()
        self.addCleanup(self.build_polygon_patcher.stop)

        self.calculator = AnrCorridorCalculator(
            self.contestant,
            self.scorecard,
            self.route,
            Queue(),
            live_processing=False,
            projector=self.projector,
        )
        self.calculator.polygon_helper = MagicMock()
        self.calculator.update_score = MagicMock()

    def _gate(self, name, gate_type="tp", is_visible=True):
        gate = self.make_waypoint(name=name, type=gate_type, is_visible=is_visible)
        return gate

    def test_gate_crossed_while_outside_corridor_visible_gate_rolls_over_leg(self):
        """Headline scenario: a visible gate crossed mid-excursion emits an
        informational "passed while outside" message, rolls the leg
        boundary over to the new gate, and the eventual return-inside
        finalization reports the correctly accumulated total."""
        gate_sp = self._gate("SP", "sp")
        gate_tp1 = self._gate("TP1", "tp")
        t0 = datetime.datetime(2026, 1, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)

        # 1. Go outside the corridor at t0, attributed to SP.
        with patch.object(self.calculator, "_check_inside_polygon", return_value=False):
            self.calculator.check_outside_corridor([self.make_position(60.5, 11.5, t0)], gate_sp)
        exiting_msg = self.calculator.update_score.call_args_list[-1][0][0]
        self.assertEqual(exiting_msg.message, "exiting corridor")
        self.assertEqual(self.calculator.crossed_outside_gate, gate_sp)
        self.assertEqual(self.calculator.current_leg_outside_start_time, t0)

        # 2. Cross TP1 (visible) 15s later, still outside.
        # leg_incremental = penalty*(round(15-5)) = 10*10 = 100
        t1 = t0 + datetime.timedelta(seconds=15)
        pos1 = self.make_position(60.5, 11.5, t1)
        self.calculator.on_gate_passed(GatePassedEvent(gate_tp1, pos1, t1, previous_gate=None))

        info_msg = self.calculator.update_score.call_args_list[-1][0][0]
        self.assertEqual(info_msg.annotation_type, "information")
        self.assertEqual(info_msg.message, "passed TP1 while outside corridor. Excursion penalty so far: 100.0")
        # Leg boundary must have rolled over to the new gate (this is the
        # mechanic that a non-visible/secret gate fails to perform - see
        # test_secret_gate_crossed_mid_excursion_does_not_roll_leg_boundary below).
        self.assertEqual(self.calculator.crossed_outside_gate, gate_tp1)
        self.assertEqual(self.calculator.current_leg_outside_start_time, t1)
        self.assertEqual(self.calculator.excursion_accumulated_score, 100.0)
        self.assertEqual(self.calculator.excursion_total_outside_seconds, 15.0)

        # 3. Orchestrator keeps calling calculate_enroute (-> check_outside_corridor)
        # every tick while still outside, which is what keeps
        # crossed_outside_position - the anchor check_and_apply_outside_penalty
        # finalizes against - fresh. Simulate one more "still outside" tick 10s
        # later before actually returning inside.
        t2 = t1 + datetime.timedelta(seconds=10)
        pos2 = self.make_position(60.5, 11.5, t2)
        with patch.object(self.calculator, "_check_inside_polygon", return_value=False):
            self.calculator.check_outside_corridor([pos2], gate_tp1)

        # 4. Now actually return inside. Grace was already fully consumed by
        # leg 1, so leg 2's 10s (t1->t2) is penalized in full:
        # total_outside_time = 15 (leg 1, already accumulated) + 10 = 25
        # penalty_time = round(25-5) = 20, total_penalty = 200,
        # leg2_incremental = 200 - 100 (already accumulated) = 100.
        # Total = 100 + 100 = 200, total_seconds = 25.
        t3 = t2 + datetime.timedelta(seconds=1)
        with patch.object(self.calculator, "_check_inside_polygon", return_value=True):
            self.calculator.check_outside_corridor([self.make_position(60.0, 11.0, t3)], gate_tp1)

        final_msg = self.calculator.update_score.call_args_list[-1][0][0]
        self.assertEqual(final_msg.score, 200.0)
        self.assertIn("Leg scores: [SP: 100.0, TP1: 100.0]", final_msg.message)
        self.assertEqual(final_msg.message, "outside corridor (25 s). Leg scores: [SP: 100.0, TP1: 100.0]. Total: 200.0")
        # Excursion state must be fully reset.
        self.assertEqual(self.calculator.excursion_accumulated_score, 0)
        self.assertIsNone(self.calculator.crossed_outside_time)
        self.assertIsNone(self.calculator.current_leg_outside_start_time)

    def test_secret_gate_crossed_mid_excursion_does_not_roll_leg_boundary(self):
        """Confirmed intentional (not a bug): legs are only rolled when
        passing a regular (non-secret) gate, regardless of whether the
        secret gate is crossed or missed. A secret gate crossed/missed
        while outside the corridor must not advance the leg boundary -
        current_leg_outside_start_time/crossed_outside_gate stay anchored
        at the last regular gate."""
        gate_sp = self._gate("SP", "sp")
        gate_secret = self._gate("SECRET1", "secret", is_visible=False)
        t0 = datetime.datetime(2026, 1, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)

        with patch.object(self.calculator, "_check_inside_polygon", return_value=False):
            self.calculator.check_outside_corridor([self.make_position(60.5, 11.5, t0)], gate_sp)

        t1 = t0 + datetime.timedelta(seconds=15)
        pos1 = self.make_position(60.5, 11.5, t1)
        self.calculator.on_gate_passed(GatePassedEvent(gate_secret, pos1, t1, previous_gate=None))

        # No informational message should leak for a secret gate.
        for call in self.calculator.update_score.call_args_list:
            self.assertNotIn("SECRET1", call.args[0].message)

        # The leg boundary must NOT roll over to the secret gate.
        self.assertEqual(self.calculator.crossed_outside_gate, gate_sp)
        self.assertEqual(self.calculator.current_leg_outside_start_time, t0)

    def test_secret_gate_missed_mid_excursion_does_not_roll_leg_boundary(self):
        """Same as above, but for a missed (rather than crossed) secret gate."""
        gate_sp = self._gate("SP", "sp")
        gate_secret = self._gate("SECRET1", "secret", is_visible=False)
        t0 = datetime.datetime(2026, 1, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)

        with patch.object(self.calculator, "_check_inside_polygon", return_value=False):
            self.calculator.check_outside_corridor([self.make_position(60.5, 11.5, t0)], gate_sp)

        t1 = t0 + datetime.timedelta(seconds=15)
        pos1 = self.make_position(60.5, 11.5, t1)
        self.calculator.on_gate_missed(GateMissedEvent(gate_sp, gate_secret, pos1, event_time=t1))

        for call in self.calculator.update_score.call_args_list:
            self.assertNotIn("SECRET1", call.args[0].message)

        self.assertEqual(self.calculator.crossed_outside_gate, gate_sp)
        self.assertEqual(self.calculator.current_leg_outside_start_time, t0)

    def test_finish_reached_while_outside_corridor_single_tick_ordering(self):
        """Regression test for a fixed double-count bug: crossing the finish
        gate while outside the corridor in per-leg mode used to score the
        final excursion segment twice (on_gate_passed's fp-skip accumulated
        the leg without rolling current_leg_outside_start_time forward, then
        passed_finishpoint's check_and_apply_outside_penalty recomputed and
        re-added the same segment). on_gate_passed now skips accumulation
        entirely for fp gates, leaving check_and_apply_outside_penalty as
        the single place that finalizes the last leg."""
        gate_sp = self._gate("SP", "sp")
        gate_fp = self._gate("FP", "fp")
        t0 = datetime.datetime(2026, 1, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)

        with patch.object(self.calculator, "_check_inside_polygon", return_value=False):
            self.calculator.check_outside_corridor([self.make_position(60.5, 11.5, t0)], gate_sp)

        # Orchestrator fires on_gate_passed(fp) first, then forces
        # passed_finishpoint - replicate that exact ordering in one tick.
        t1 = t0 + datetime.timedelta(seconds=20)
        pos1 = self.make_position(60.5, 11.5, t1)
        self.calculator.on_gate_passed(GatePassedEvent(gate_fp, pos1, t1, previous_gate=None))
        self.calculator.passed_finishpoint(FinishLinePassedEvent(gate_fp, [pos1], event_time=t1))

        final_msg = self.calculator.update_score.call_args_list[-1][0][0]
        # CORRECT: a single continuous 20s excursion, 10s beyond the 10s
        # grace, scored once: 10 (per-second penalty) * 10 = 100... using
        # this suite's grace_time=5: penalty_time = round(20-5) = 15,
        # total_penalty = 10*15 = 150.
        self.assertEqual(final_msg.score, 150.0)
        self.assertIn("(20 s)", final_msg.message)

    def test_multi_leg_excursion_across_three_visible_gates_per_leg_cap(self):
        """Three legs (SP->TP1->TP2->inside), grace consumed once for the
        whole excursion (not re-granted per leg), and the per-leg cap
        applied independently to each of the three legs."""
        self.scorecard.corridor_maximum_penalty = 30
        self.calculator.corridor_maximum_penalty = 30
        gate_sp = self._gate("SP", "sp")
        gate_tp1 = self._gate("TP1", "tp")
        gate_tp2 = self._gate("TP2", "tp")
        t0 = datetime.datetime(2026, 1, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)

        with patch.object(self.calculator, "_check_inside_polygon", return_value=False):
            self.calculator.check_outside_corridor([self.make_position(60.5, 11.5, t0)], gate_sp)

        # Leg SP: 12s outside. penalty_time=round(12-5)=7, penalty=70 -> capped to 30.
        t1 = t0 + datetime.timedelta(seconds=12)
        pos1 = self.make_position(60.5, 11.5, t1)
        self.calculator.on_gate_passed(GatePassedEvent(gate_tp1, pos1, t1, previous_gate=None))
        self.assertEqual(self.calculator.excursion_accumulated_score, 30.0)

        # Leg TP1: 9 more seconds (cumulative 21s). penalty_time=round(21-5)=16,
        # total_penalty=160, incremental=160-30=130 -> capped to 30. Cumulative=60.
        t2 = t1 + datetime.timedelta(seconds=9)
        pos2 = self.make_position(60.5, 11.5, t2)
        self.calculator.on_gate_passed(GatePassedEvent(gate_tp2, pos2, t2, previous_gate=None))
        self.assertEqual(self.calculator.excursion_accumulated_score, 60.0)

        # Leg TP2: 8 more seconds (cumulative 29s). penalty_time=round(29-5)=24,
        # total_penalty=240, incremental=240-60=180 -> capped to 30. Cumulative=90.
        t3 = t2 + datetime.timedelta(seconds=8)
        with patch.object(self.calculator, "_check_inside_polygon", return_value=True):
            self.calculator.check_outside_corridor([self.make_position(60.0, 11.0, t3)], gate_tp2)

        final_msg = self.calculator.update_score.call_args_list[-1][0][0]
        self.assertEqual(final_msg.score, 90.0)
        self.assertEqual(
            final_msg.message,
            "outside corridor (21 s). Leg scores: [SP: 30.0 (capped), TP1: 30.0 (capped), TP2: 30.0 (capped)]. Total: 90.0 (capped)",
        )

    def test_finalise_with_no_captured_gate_reference(self):
        """Regression test for a fixed bug: finalise() used to fall back to
        self.previous_existing_reference, an attribute set to None once in
        __init__ and never reassigned anywhere - so a track ending outside
        the corridor with no gate reference captured always scored against
        gate=None. finalise() now falls back to the route's first waypoint,
        matching the pattern already used by the auxiliary route-compliance
        checks in this same class."""
        t0 = datetime.datetime(2026, 1, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)
        self.calculator.corridor_state = self.calculator.OUTSIDE_CORRIDOR
        self.calculator.crossed_outside_time = t0
        self.calculator.current_leg_outside_start_time = t0
        self.calculator.crossed_outside_gate = None  # e.g. outside from the very start, before any gate context

        first_waypoint = self._gate("SP", "sp")
        self.route.waypoints = [first_waypoint]

        t1 = t0 + datetime.timedelta(seconds=30)
        self.calculator.finalise([self.make_position(60.5, 11.5, t1)])

        final_msg = self.calculator.update_score.call_args_list[-1][0][0]
        self.assertEqual(final_msg.gate, first_waypoint)
