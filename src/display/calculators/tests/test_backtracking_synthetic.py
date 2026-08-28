"""Synthetic (no DB, no fixture files, no ContestantProcessor/Orchestrator)
state-machine tests for BacktrackingAndProcedureTurnsCalculator, focused on
the fragile timing/duplicate-scoring paths flagged during the calculator
state-machine review: the grace-time-then-backtrack sequence, the two
near-identical penalty-scoring blocks (calculate_track_score,
backtracking_and_procedure_turns.py:472-503 and 515-534), the structurally
unreachable `elif` at line 504, and the procedure-turn 180 second timeout
branches.

Methodology: calculate_track_score(track, last_visible_gate, in_range_of_gate,
next_gate) is called directly with hand-built Mock gates, bypassing route/
gate-time setup entirely - the method takes last_visible_gate/next_gate as
explicit parameters and never reads self.gates for this logic. Reference
bearing is derived once via the real calculate_bearing() function against
two fixed points and reused everywhere a "correct heading" is needed, so
"backtracking" is simply flying the same two points in reverse (a real,
independently-verified ~180 degree bearing difference), never a hand-guessed
compass value. See synthetic_helpers.py for the general approach and
test_anr_corridor_calculator_synthetic.py for the @skip-for-suspected-bug
convention used below.
"""

import datetime
from queue import Queue
from unittest import skip
from unittest.mock import MagicMock, patch

from display.calculators.backtracking_and_procedure_turns import BacktrackingAndProcedureTurnsCalculator
from display.calculators.calculator import GateMissedEvent, GatePassedEvent
from display.calculators.tests.synthetic_helpers import SyntheticCalculatorTestBase
from display.utilities.coordinate_utilities import calculate_bearing


class TestBacktrackingSynthetic(SyntheticCalculatorTestBase):
    def setUp(self):
        super().setUp()
        self.contestant = MagicMock()
        self.contestant.gate_times = {}
        self.route = MagicMock()
        # Empty waypoints -> create_gates()/_get_effective_waypoints() safely
        # returns [] (no DB, no real route needed - see module docstring),
        # and _get_relevant_waypoints() also returns [] so
        # _get_local_reference_bearing() falls back directly to
        # last_visible_gate.bearing, which is exactly the direct control
        # these tests need.
        self.route.waypoints = []
        self.route.use_procedure_turns = False
        self.contestant.navigation_task.route = self.route

        self.scorecard = MagicMock()
        self.scorecard.backtracking_bearing_difference = 90  # limit: >90 degrees off triggers the backtracking flag
        self.scorecard.backtracking_grace_time_seconds = 30
        self.scorecard.backtracking_penalty = 200
        self.scorecard.backtracking_maximum_penalty = 200
        # Disable all the distance/time grace suppressions by default so
        # tests exercise the core timing logic in isolation; individual
        # tests override where the suppression itself is under test.
        self.scorecard.get_backtracking_after_steep_gate_grace_period_seconds_for_gate_type.return_value = 0
        self.scorecard.get_backtracking_before_gate_grace_period_nm_for_gate_type.return_value = 0
        self.scorecard.get_backtracking_after_gate_grace_period_nm_for_gate_type.return_value = 0
        self.scorecard.get_procedure_turn_penalty_for_gate_type.return_value = 150.0

        self.calculator = BacktrackingAndProcedureTurnsCalculator(
            self.contestant,
            self.scorecard,
            self.route,
            Queue(),
            live_processing=False,
            projector=self.projector,
        )
        self.calculator.update_score = MagicMock()

        # A due-east-ish reference leg; both the "correct" and "backtracking"
        # tracks below are built from these same two points (forward for
        # correct, reversed for backtracking), so the ~180 degree difference
        # between them is derived by the real bearing function, not guessed.
        self.point_a = (60.0, 11.00)
        self.point_b = (60.0, 11.05)
        self.reference_bearing = calculate_bearing(self.point_a, self.point_b)
        # Progressively further west of point_a, for sequences that need
        # several consecutive "still reversing" ticks. Each successive pair
        # (point_a, point_west_1), (point_west_1, point_west_2), ... has the
        # same ~180 degree-from-reference bearing as (point_b, point_a) -
        # using the SAME point twice in a row would give a degenerate
        # zero-length segment instead of a continued reversal.
        self.point_west_1 = (60.0, 10.95)
        self.point_west_2 = (60.0, 10.90)

    def _gate(self, name, **overrides):
        gate = MagicMock()
        gate.name = name
        gate.type = "tp"
        gate.bearing = self.reference_bearing
        gate.bearing_from_previous = self.reference_bearing
        gate.center_x = -1_000_000.0  # far from all test positions -> never inside the 0.5 NM near-gate grace zone
        gate.center_y = -1_000_000.0
        gate.latitude = 0.0
        gate.longitude = 0.0
        gate.is_procedure_turn = False
        gate.is_steep_turn = False
        gate.infinite_passing_time = None  # disables the steep-turn-grace check regardless of is_steep_turn
        gate.missed = False
        gate.has_extended_been_passed.return_value = False
        gate.get_distance_to_gate_line.return_value = 999_999.0  # disables the before/after-gate distance grace checks
        for key, value in overrides.items():
            setattr(gate, key, value)
        return gate

    def _pos(self, lat, lon, time):
        return self.make_position(lat, lon, time)

    def test_happy_path_no_false_positive_penalty(self):
        """Flying the correct heading the whole time never triggers a
        backtracking penalty, regardless of tracking_state."""
        gate = self._gate("TP1")
        t0 = datetime.datetime(2026, 1, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)
        track = [self._pos(*self.point_a, t0)]
        for i in range(1, 5):
            lat = self.point_a[0]
            lon = self.point_a[1] + (self.point_b[1] - self.point_a[1]) * i / 4
            track.append(self._pos(lat, lon, t0 + datetime.timedelta(seconds=10 * i)))
            self.calculator.calculate_track_score(track, gate, gate, gate)

        self.calculator.update_score.assert_not_called()

    def test_backtracking_exceeds_grace_time_single_penalty_then_clean_recovery(self):
        """Sustained backtracking past the grace period scores exactly once;
        continuing to backtrack does not score again; recovering afterwards
        does not score again either."""
        gate = self._gate("TP1")
        self.calculator.tracking_state = self.calculator.TRACKING
        self.calculator.last_gate_previous_round = gate
        t0 = datetime.datetime(2026, 1, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)

        # Establish a correct-heading baseline (no backtracking flagged).
        track = [self._pos(*self.point_a, t0), self._pos(*self.point_b, t0 + datetime.timedelta(seconds=10))]
        self.calculator.calculate_track_score(track, gate, gate, gate)
        self.calculator.update_score.assert_not_called()

        # Reverse direction (back toward point_a) at t0+20s: bearing
        # difference ~180 > 90 -> enters BACKTRACKING_TEMPORARY,
        # backtracking_start_time = t0+20s. Elapsed so far = 0 -> no score yet.
        t_reverse_start = t0 + datetime.timedelta(seconds=20)
        track.append(self._pos(*self.point_a, t_reverse_start))
        self.calculator.calculate_track_score(track, gate, gate, gate)
        self.assertEqual(self.calculator.tracking_state, self.calculator.BACKTRACKING_TEMPORARY)
        self.assertEqual(self.calculator.backtracking_start_time, t_reverse_start)
        self.calculator.update_score.assert_not_called()

        # Still reversing 35s after backtracking_start_time (>= 30s grace) ->
        # exactly one penalty. point_a -> point_west_1 continues the same
        # westward (reversed) bearing as point_b -> point_a above; reusing
        # point_a again would give a degenerate zero-length segment instead.
        t_grace_exceeded = t_reverse_start + datetime.timedelta(seconds=35)
        track.append(self._pos(*self.point_west_1, t_grace_exceeded))
        self.calculator.calculate_track_score(track, gate, gate, gate)
        self.assertEqual(self.calculator.tracking_state, self.calculator.BACKTRACKING)
        self.assertEqual(self.calculator.update_score.call_count, 1)
        penalty_msg = self.calculator.update_score.call_args_list[0][0][0]
        self.assertEqual(penalty_msg.score, 200)
        self.assertEqual(penalty_msg.message, "backtracking")
        self.assertEqual(penalty_msg.score_type, "backtracking")

        # Continuing to backtrack afterwards must not score again (dedup via
        # backtracked_on_current_leg, and BACKTRACKING is no longer
        # BACKTRACKING_TEMPORARY so the timing block doesn't even run).
        t_continue = t_grace_exceeded + datetime.timedelta(seconds=5)
        track.append(self._pos(*self.point_west_2, t_continue))
        self.calculator.calculate_track_score(track, gate, gate, gate)
        self.assertEqual(self.calculator.update_score.call_count, 1)

        # Recovering afterwards (correct heading again) must not score again
        # either, and cleanly returns to TRACKING.
        t_recover = t_continue + datetime.timedelta(seconds=10)
        track.append(self._pos(*self.point_b, t_recover))
        self.calculator.calculate_track_score(track, gate, gate, gate)
        self.assertEqual(self.calculator.update_score.call_count, 1)
        self.assertEqual(self.calculator.tracking_state, self.calculator.TRACKING)

    def test_backtracking_recovers_within_grace_time_no_penalty(self):
        """Reversing briefly and recovering before the grace period elapses
        never scores a penalty."""
        gate = self._gate("TP1")
        self.calculator.tracking_state = self.calculator.TRACKING
        self.calculator.last_gate_previous_round = gate
        t0 = datetime.datetime(2026, 1, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)

        track = [self._pos(*self.point_a, t0), self._pos(*self.point_b, t0 + datetime.timedelta(seconds=10))]
        self.calculator.calculate_track_score(track, gate, gate, gate)

        t_reverse_start = t0 + datetime.timedelta(seconds=20)
        track.append(self._pos(*self.point_a, t_reverse_start))
        self.calculator.calculate_track_score(track, gate, gate, gate)
        self.assertEqual(self.calculator.tracking_state, self.calculator.BACKTRACKING_TEMPORARY)

        # Still reversing, but only 10s later (< 30s grace) -> no score, still
        # TEMPORARY. point_a -> point_west_1 continues the westward bearing;
        # reusing point_a would give a degenerate zero-length segment instead.
        t_still_reversing = t_reverse_start + datetime.timedelta(seconds=10)
        track.append(self._pos(*self.point_west_1, t_still_reversing))
        self.calculator.calculate_track_score(track, gate, gate, gate)
        self.assertEqual(self.calculator.tracking_state, self.calculator.BACKTRACKING_TEMPORARY)
        self.calculator.update_score.assert_not_called()

        # Recovers 15s after backtracking_start_time (< 30s grace) -> no
        # score, exercising the recovery branch's OWN duplicate-looking
        # elapsed check (backtracking_and_procedure_turns.py:515) with a
        # real elapsed value under the grace threshold.
        t_recover = t_reverse_start + datetime.timedelta(seconds=15)
        track.append(self._pos(*self.point_b, t_recover))
        self.calculator.calculate_track_score(track, gate, gate, gate)
        self.calculator.update_score.assert_not_called()
        self.assertEqual(self.calculator.tracking_state, self.calculator.TRACKING)

    def test_recovery_exactly_after_grace_elapsed_scores_via_recovery_block_only(self):
        """If the contestant recovers on the very first tick where elapsed
        time already exceeds the grace period (skipping any intervening
        "still backtracking, not yet at grace" tick), the recovery block
        (backtracking_and_procedure_turns.py:515-534) is the ONLY path that
        can score this excursion - the "still backtracking" block
        (472-503) never runs for this sequence. This demonstrates the
        recovery block is NOT simply redundant/removable duplicate code as
        it might look at a glance: it's the only handler for this specific
        interleaving. Exactly one penalty must be scored either way."""
        gate = self._gate("TP1")
        self.calculator.tracking_state = self.calculator.TRACKING
        self.calculator.last_gate_previous_round = gate
        t0 = datetime.datetime(2026, 1, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)

        track = [self._pos(*self.point_a, t0), self._pos(*self.point_b, t0 + datetime.timedelta(seconds=10))]
        self.calculator.calculate_track_score(track, gate, gate, gate)

        t_reverse_start = t0 + datetime.timedelta(seconds=20)
        track.append(self._pos(*self.point_a, t_reverse_start))
        self.calculator.calculate_track_score(track, gate, gate, gate)
        self.assertEqual(self.calculator.tracking_state, self.calculator.BACKTRACKING_TEMPORARY)

        # Jump straight to a recovery tick 35s later (>= 30s grace),
        # skipping any "still backtracking" tick in between.
        t_recover_after_grace = t_reverse_start + datetime.timedelta(seconds=35)
        track.append(self._pos(*self.point_b, t_recover_after_grace))
        self.calculator.calculate_track_score(track, gate, gate, gate)

        self.assertEqual(self.calculator.update_score.call_count, 1)
        penalty_msg = self.calculator.update_score.call_args_list[0][0][0]
        self.assertEqual(penalty_msg.score, 200)
        self.assertEqual(self.calculator.tracking_state, self.calculator.TRACKING)

    def test_elif_at_line_504_is_structurally_unreachable(self):
        """The `elif` guarding the "resumed... so no penalty" log message
        (backtracking_and_procedure_turns.py:504) has the exact same
        condition as the `if` immediately above it (line 472). Since both
        are evaluated against the same unchanged state within one call,
        whenever the `if`'s condition is true the code enters that branch
        and the `elif` can never run - regardless of whether the elapsed
        time is under or over the grace threshold. This locks that in as a
        regression: the branch's own distinguishing log message must never
        be emitted, in either the under-grace or over-grace case. Likely a
        latent authoring bug (the log text describes a "resumed" i.e.
        already-recovered scenario, but this code path is nested under
        `if backtracking:`, meaning the bearing is still off this tick -
        the two are contradictory), flagged for the user's consideration,
        not asserted as intentional."""
        gate = self._gate("TP1")
        self.calculator.tracking_state = self.calculator.TRACKING
        self.calculator.last_gate_previous_round = gate
        t0 = datetime.datetime(2026, 1, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)
        track = [self._pos(*self.point_a, t0), self._pos(*self.point_b, t0 + datetime.timedelta(seconds=10))]
        self.calculator.calculate_track_score(track, gate, gate, gate)

        t_reverse_start = t0 + datetime.timedelta(seconds=20)
        track.append(self._pos(*self.point_a, t_reverse_start))

        with patch(
            "display.calculators.backtracking_and_procedure_turns.logger"
        ) as mock_logger:
            self.calculator.calculate_track_score(track, gate, gate, gate)
            # Under-grace tick (elapsed 0 < 30s): the dead branch's message must not appear.
            self._assert_dead_branch_message_absent(mock_logger)

            # Still reversing, now over-grace (elapsed 35s >= 30s): still
            # must not appear, even though this tick DOES hit the `if` at
            # 472 whose elapsed check passes.
            mock_logger.reset_mock()
            t_over_grace = t_reverse_start + datetime.timedelta(seconds=35)
            track.append(self._pos(*self.point_a, t_over_grace))
            self.calculator.calculate_track_score(track, gate, gate, gate)
            self._assert_dead_branch_message_absent(mock_logger)

    def _assert_dead_branch_message_absent(self, mock_logger):
        for call in mock_logger.info.call_args_list:
            message = call.args[0] if call.args else ""
            self.assertNotIn("Resumed tracking within time limits", message)

    def test_procedure_turn_soft_success_within_180_second_timeout(self):
        """A procedure turn that ends up close to (but not exactly at) the
        expected turn amount, discovered only once 180s have elapsed since
        the turn started, is accepted without penalty (the "soft success"
        branch, backtracking_and_procedure_turns.py:304-310)."""
        gate = self._gate("TP1")
        t0 = datetime.datetime(2026, 1, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)
        self._seed_procedure_turn_in_progress(gate, t0, slices_total=150.0, expected_turn=180.0)

        # One more real tick contributing exactly 0 additional turn (same
        # two reference points as everywhere else, so bearing == last_bearing
        # exactly), 190s after the turn started -> total stays 150 (30 off
        # from the expected 180, within the 60 degree tolerance), elapsed > 180s.
        track = [self._pos(*self.point_a, t0), self._pos(*self.point_b, t0 + datetime.timedelta(seconds=190))]
        self.calculator.calculate_track_score(track, gate, gate, gate)

        self.assertEqual(self.calculator.tracking_state, self.calculator.TRACKING)
        self.calculator.update_score.assert_not_called()

    def test_procedure_turn_failure_after_180_second_timeout(self):
        """A procedure turn that stays more than 60 degrees off the
        expected amount past the 180s timeout fails and scores the
        procedure-turn penalty (backtracking_and_procedure_turns.py:312-339)."""
        gate = self._gate("TP1")
        t0 = datetime.datetime(2026, 1, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)
        self._seed_procedure_turn_in_progress(gate, t0, slices_total=250.0, expected_turn=180.0)

        track = [self._pos(*self.point_a, t0), self._pos(*self.point_b, t0 + datetime.timedelta(seconds=190))]
        self.calculator.calculate_track_score(track, gate, gate, gate)

        self.assertEqual(self.calculator.tracking_state, self.calculator.FAILED_PROCEDURE_TURN)
        self.calculator.update_score.assert_called_once()
        penalty_msg = self.calculator.update_score.call_args_list[0][0][0]
        self.assertEqual(penalty_msg.score, 150.0)
        self.assertEqual(penalty_msg.message, "incorrect procedure turn")
        self.assertEqual(penalty_msg.score_type, "procedure_turn")
        self.assertEqual(penalty_msg.gate, gate)

    def test_procedure_turn_failure_suppressed_after_prior_leg_backtracking(self):
        """A failed procedure turn's penalty is suppressed - though the
        state still transitions to FAILED_PROCEDURE_TURN - if the leg
        leading into this gate was already penalized for backtracking
        (avoids double-penalizing what's really the same deviation)."""
        gate = self._gate("TP1")
        t0 = datetime.datetime(2026, 1, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)
        self._seed_procedure_turn_in_progress(gate, t0, slices_total=250.0, expected_turn=180.0)
        self.calculator.was_backtracked_on_leg_leading_to_last_gate = True

        track = [self._pos(*self.point_a, t0), self._pos(*self.point_b, t0 + datetime.timedelta(seconds=190))]
        self.calculator.calculate_track_score(track, gate, gate, gate)

        self.assertEqual(self.calculator.tracking_state, self.calculator.FAILED_PROCEDURE_TURN)
        self.calculator.update_score.assert_not_called()

    def _seed_procedure_turn_in_progress(self, gate, start_time, slices_total, expected_turn):
        """Directly seed an in-progress procedure turn rather than driving
        the entry-detection branch (which requires a specific
        just_passed_gate/is_procedure_turn/has_extended_been_passed
        combination irrelevant to what these timeout tests exercise) - a
        legitimate, targeted way to reach the timeout logic in isolation."""
        self.calculator.tracking_state = self.calculator.PROCEDURE_TURN
        self.calculator.current_procedure_turn_gate = gate
        self.calculator.current_procedure_turn_bearing_difference = expected_turn
        self.calculator.current_procedure_turn_start_time = start_time
        self.calculator.current_procedure_turn_slices = [slices_total]
        self.calculator.last_bearing = self.reference_bearing
        self.calculator.last_gate_previous_round = gate
        self.calculator.was_backtracked_on_leg_leading_to_last_gate = False

    def test_on_gate_missed_reset_is_consistent_with_leg_transition_reset(self):
        """on_gate_missed's own backtracking-state reset
        (backtracking_and_procedure_turns.py:181-183) and
        calculate_track_score's leg-transition reset (258-264) reset the
        same fields; calling on_gate_missed and then immediately
        transitioning to a new leg must not leave a contradictory state."""
        gate1 = self._gate("TP1")
        gate2 = self._gate("TP2")
        t0 = datetime.datetime(2026, 1, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)

        self.calculator.backtracking_start_time = t0
        self.calculator.backtracked_on_current_leg = True

        self.calculator.on_gate_missed(GateMissedEvent(None, gate1, self._pos(*self.point_a, t0)))
        self.assertIsNone(self.calculator.backtracking_start_time)
        self.assertFalse(self.calculator.backtracked_on_current_leg)
        self.assertTrue(self.calculator.was_backtracked_on_leg_leading_to_last_gate)

        # A leg transition to a different gate right afterwards must agree,
        # not re-derive a contradictory was_backtracked_on_leg_leading_to_last_gate.
        track = [self._pos(*self.point_a, t0), self._pos(*self.point_b, t0 + datetime.timedelta(seconds=10))]
        self.calculator.calculate_track_score(track, gate2, gate2, gate2)
        self.assertIsNone(self.calculator.backtracking_start_time)
        self.assertFalse(self.calculator.backtracked_on_current_leg)
        # backtracked_on_current_leg was already False going in, so the
        # leg-transition reset should carry that same False forward, not flip it.
        self.assertFalse(self.calculator.was_backtracked_on_leg_leading_to_last_gate)


# Note on DEVIATING (backtracking_and_procedure_turns.py:50): this state is
# defined and included in TRACKING_MAP, but grep confirms it is never
# assigned via update_tracking_state anywhere in the class - it is dead
# code. No test exercises it (there is nothing to exercise); flagged here
# for the user's consideration as a removal candidate rather than left
# silently undocumented.
