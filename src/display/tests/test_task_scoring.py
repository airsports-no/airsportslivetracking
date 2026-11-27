"""
The task-level normalisation of the quality scoring model (display.services.task_scoring): P = task_value x Q / Qmax
from the raw quality scores of all contestants of a task, percentage penalties, floor at zero, whole numbers rounded
half up, and the triggers that keep the stored task scores consistent.

The expected numbers are worked out by hand in the tests, independently of the code under test.
"""

import datetime
import threading

from django.db import connection
from django.test import TestCase, TransactionTestCase

from display.calculators.tests.test_score_message_kinds import MessageTestCase
from display.calculators.update_score_message import ACHIEVEMENT, PENALTY, PERCENTAGE_PENALTY
from display.models import Contestant, ContestantTrack, ScoreLogEntry, TeamTestScore
from display.services.administrative_penalties import AdministrativePenaltyService
from display.services.task_scoring import (
    QualityEntry,
    ScoringParameters,
    compute_task_scores,
    recompute_task_scores,
    refresh_contestant_quality,
    round_half_up,
    task_scores_are_provisional,
    validate_task_value,
)
from display.utilities.task_types import (
    ANR_CATALOGUE,
    CIRCLE,
    CURVE_NAVIGATION_TIME_ESTIMATION,
    CONTRACT_NAVIGATION_TIME_CONTROLS,
    CONTRACT_POINTS_SCORE_TYPE,
    KNOWN_CIRCUIT,
    PRECISION_NAVIGATION,
    SPEED_TERM_SCORE_TYPE,
    QMAX_ABSOLUTE,
    QMAX_BEST_IN_TASK,
    QMAX_THEORETICAL,
    SCORING_QUALITY,
    TURNPOINT_HUNT,
)

BEST = ScoringParameters(SCORING_QUALITY, QMAX_BEST_IN_TASK, 1000.0)


def flown(raw_quality, percentage=0.0, theoretical=0.0) -> QualityEntry:
    return QualityEntry(True, raw_quality, theoretical, percentage)


class TestComputeTaskScores(TestCase):
    """The arithmetic, without a database."""

    def test_best_in_task_with_three_contestants(self):
        # Qmax = 1200: 1000 x 1200/1200, 1000 x 900/1200, 1000 x 600/1200
        self.assertEqual([1000, 750, 500], compute_task_scores(BEST, [flown(1200), flown(900), flown(600)]))

    def test_a_later_better_flight_lowers_the_scores_of_the_others(self):
        self.assertEqual([1000], compute_task_scores(BEST, [flown(900)]))
        self.assertEqual([750, 1000], compute_task_scores(BEST, [flown(900), flown(1200)]))

    def test_theoretical_maximum_divides_by_the_contestants_own_maximum(self):
        parameters = ScoringParameters(SCORING_QUALITY, QMAX_THEORETICAL, 1000.0)
        # 900 of 1200 and 600 of 600: nobody's score depends on the other
        self.assertEqual(
            [750, 1000],
            compute_task_scores(parameters, [flown(900, theoretical=1200), flown(600, theoretical=600)]),
        )
        self.assertEqual([0], compute_task_scores(parameters, [flown(900, theoretical=0)]))

    def test_absolute_score_of_the_circle_is_q_whatever_the_task_value_and_the_others(self):
        parameters = ScoringParameters(SCORING_QUALITY, QMAX_ABSOLUTE, 1500.0, absolute_reference=None)
        self.assertEqual([200, 120], compute_task_scores(parameters, [flown(200), flown(120)]))

    def test_absolute_score_of_the_anr_is_a_fixed_scale(self):
        parameters = ScoringParameters(SCORING_QUALITY, QMAX_ABSOLUTE, 1000.0, absolute_reference=2000.0)
        self.assertEqual([750, 1000, 0], compute_task_scores(parameters, [flown(1500), flown(2000), flown(-10)]))
        half_value = ScoringParameters(SCORING_QUALITY, QMAX_ABSOLUTE, 500.0, absolute_reference=2000.0)
        self.assertEqual([375], compute_task_scores(half_value, [flown(1500)]))

    def test_a_single_percentage_penalty_comes_off_the_task_score(self):
        # 1000 x 900/1200 = 750, less 50% = 375; the best is 1000 less 20% = 800
        self.assertEqual([800, 375], compute_task_scores(BEST, [flown(1200, 20), flown(900, 50)]))

    def test_percentage_penalties_add_up(self):
        # Entries carry the sum of the percentages of the score log: 50% and 20% make 70%
        self.assertEqual([300], compute_task_scores(BEST, [flown(1200, 50 + 20)]))

    def test_percentage_penalties_are_capped_at_one_hundred_percent(self):
        self.assertEqual([0], compute_task_scores(BEST, [flown(1200, 80 + 50)]))

    def test_the_best_q_is_taken_before_the_percentage_penalty(self):
        # The best pilot loses 100% (a quarantine breach) and still sets Qmax for the others
        self.assertEqual([0, 500], compute_task_scores(BEST, [flown(1000, 100), flown(500)]))

    def test_a_negative_task_score_becomes_zero(self):
        self.assertEqual([1000, 0], compute_task_scores(BEST, [flown(1000), flown(-200)]))
        # Nobody above zero: everybody scores zero (Qmax is not positive)
        self.assertEqual([0, 0], compute_task_scores(BEST, [flown(-50), flown(0)]))

    def test_the_task_score_is_a_whole_number_with_half_rounded_up(self):
        # 1000 x 1749/2000 = 874.5 -> 875 (not 874, which is what rounding to even gives); 875.5 -> 876
        self.assertEqual([875, 876], compute_task_scores(BEST, [flown(2000), flown(1749), flown(1751)])[1:])
        self.assertEqual(875, round_half_up(874.5))
        self.assertEqual(876, round_half_up(875.5))
        self.assertEqual(874, round_half_up(874.4999))
        self.assertEqual(0, round_half_up(-0.5))

    def test_rounding_is_after_the_percentage_penalty(self):
        # 1000 x 999/1000 = 999, less 50% = 499.5 -> 500
        self.assertEqual([1000, 500], compute_task_scores(BEST, [flown(1000), flown(999, 50)]))

    def test_a_task_value_of_500_and_of_1500(self):
        for task_value, expected in ((500.0, [500, 375]), (1500.0, [1500, 1125])):
            with self.subTest(task_value=task_value):
                parameters = ScoringParameters(SCORING_QUALITY, QMAX_BEST_IN_TASK, task_value)
                self.assertEqual(expected, compute_task_scores(parameters, [flown(1200), flown(900)]))

    def test_a_contestant_who_did_not_fly_scores_zero_and_does_not_set_qmax(self):
        entries = [flown(900), QualityEntry(False, 5000.0), flown(450)]
        self.assertEqual([1000, 0, 500], compute_task_scores(BEST, entries))

    def test_the_task_value_must_be_between_500_and_1500(self):
        for value in (500, 1000, 1500, "750"):
            self.assertIsNone(validate_task_value(value))
        for value in (499.9, 1500.1, 0, None, "x"):
            self.assertIsNotNone(validate_task_value(value))


class TaskScoringTestCase(MessageTestCase):
    """A quality task with several contestants whose raw values are written through the score log."""

    task_subtype = PRECISION_NAVIGATION

    def setUp(self):
        super().setUp()
        self.task = self.make_task(self.task_subtype)
        self.contestants = [self.make_contestant(self.task, number) for number in (1, 2, 3)]

    def log(self, contestant, points, kind=PENALTY, score_type="gate_score", gate="TP1", minute=5):
        """A score log entry of a contestant; `points` as the processor stores it (signed; the percentage itself)."""
        return ScoreLogEntry.objects.create(
            time=datetime.datetime(2026, 1, 1, 8, minute, tzinfo=datetime.timezone.utc),
            contestant=contestant,
            gate=gate,
            message=f"{score_type} {points}",
            points=points,
            score_type=score_type,
            score_kind=kind,
        )

    def fly(self, contestant, start, *entries, theoretical=None, started=True):
        """The contestant flew a flight with Q starting at `start` and the given log entries (kwargs of `log`), and
        the task is renormalised."""
        ContestantTrack.objects.filter(contestant=contestant).update(
            quality_start=start,
            quality_theoretical_maximum=start if theoretical is None else theoretical,
            calculator_started=started,
        )
        for index, entry in enumerate(entries):
            self.log(contestant, minute=10 + index, **entry)
        refresh_contestant_quality(contestant)

    def track(self, contestant) -> ContestantTrack:
        return ContestantTrack.objects.get(contestant=contestant)

    def scores(self):
        return [self.track(contestant).score for contestant in self.contestants]


class TestRecomputeTaskScores(TaskScoringTestCase):
    def test_best_in_task_with_three_contestants(self):
        a, b, c = self.contestants
        self.fly(a, 1200)
        self.fly(b, 1200, {"points": -300})
        self.fly(c, 1200, {"points": -600})
        self.assertEqual([1200, 900, 600], [self.track(x).raw_quality for x in self.contestants])
        self.assertEqual([1000, 750, 500], self.scores())

    def test_a_later_better_flight_lowers_the_scores_of_the_others(self):
        a, b, c = self.contestants
        self.fly(a, 1200, {"points": -300})
        self.assertEqual([1000, 0, 0], self.scores())
        self.fly(b, 1200)
        self.assertEqual([750, 1000, 0], self.scores())

    def test_the_task_test_score_of_the_leaderboard_follows(self):
        a, b, _ = self.contestants
        self.fly(a, 1200)
        self.fly(b, 1200, {"points": -300})
        points = {
            score.team_id: score.points for score in TeamTestScore.objects.filter(task_test__navigation_task=self.task)
        }
        self.assertEqual({a.team_id: 1000, b.team_id: 750}, points)

    def test_theoretical_policy(self):
        self.task.scorecard.config["qmax_policy"] = QMAX_THEORETICAL
        self.task.scorecard.save(update_fields=["config"])
        a, b, _ = self.contestants
        self.fly(a, 1200, {"points": -300})  # 900 of 1200
        self.fly(b, 600)  # 600 of 600
        self.assertEqual([750, 1000, 0], self.scores())

    def test_percentage_penalties_are_summed_capped_and_taken_from_the_task_score(self):
        a, b, c = self.contestants
        self.fly(a, 1000, {"points": 50, "kind": PERCENTAGE_PENALTY, "score_type": "backtracking", "gate": "G1"})
        self.fly(
            b,
            1000,
            {"points": 50, "kind": PERCENTAGE_PENALTY, "score_type": "backtracking", "gate": "G1"},
            {"points": 20, "kind": PERCENTAGE_PENALTY, "score_type": "altitude", "gate": "G2"},
        )
        self.fly(
            c,
            1000,
            {"points": 80, "kind": PERCENTAGE_PENALTY, "score_type": "backtracking", "gate": "G1"},
            {"points": 50, "kind": PERCENTAGE_PENALTY, "score_type": "altitude", "gate": "G2"},
        )
        self.assertEqual([500, 300, 0], self.scores())
        self.assertEqual([1000, 1000, 1000], [self.track(x).raw_quality for x in self.contestants])
        self.assertEqual([50, 70, 130], [self.track(x).percentage_penalty for x in self.contestants])

    def test_a_negative_q_scores_zero_and_a_contestant_who_did_not_fly_scores_zero(self):
        a, b, c = self.contestants
        self.fly(a, 1000)
        self.fly(b, 100, {"points": -300})
        self.fly(c, 5000, started=False)
        self.assertEqual([1000, 0, 0], self.scores())
        self.assertEqual(-200, self.track(b).raw_quality)

    def test_the_breakdown_by_score_type_is_stored_for_display(self):
        a, *_ = self.contestants
        self.fly(
            a,
            1000,
            {"points": -30, "score_type": "gate_score", "gate": "G1"},
            {"points": -20, "score_type": "gate_score", "gate": "G2"},
            {"points": -200, "score_type": "backtracking", "gate": "G3"},
        )
        track = self.track(a)
        self.assertEqual({"gate_score": -50, "backtracking": -200}, track.quality_breakdown)
        self.assertEqual(750, track.raw_quality)

    def test_recomputing_is_idempotent_and_writes_nothing_the_second_time(self):
        a, b, _ = self.contestants
        self.fly(a, 1200)
        self.fly(b, 1200, {"points": -300})
        before = self.scores()
        self.assertEqual(0, recompute_task_scores(self.task))
        self.assertEqual(0, recompute_task_scores(self.task, refresh=self.contestants))
        self.assertEqual(before, self.scores())

    def test_a_stale_stored_score_is_overwritten_from_the_stored_raw_values(self):
        a, b, _ = self.contestants
        self.fly(a, 1200)
        self.fly(b, 1200, {"points": -300})
        ContestantTrack.objects.filter(contestant=a).update(score=17)
        ContestantTrack.objects.filter(contestant=b).update(score=999)
        self.assertEqual(2, recompute_task_scores(self.task))
        self.assertEqual([1000, 750, 0], self.scores())

    def test_the_raw_values_are_rebuilt_from_the_log_not_incremented(self):
        a, *_ = self.contestants
        self.fly(a, 1000, {"points": -100})
        ContestantTrack.objects.filter(contestant=a).update(raw_quality=5, quality_breakdown={"x": 1})
        refresh_contestant_quality(a)
        self.assertEqual(900, self.track(a).raw_quality)
        self.assertEqual({"gate_score": -100}, self.track(a).quality_breakdown)

    def test_a_log_from_before_the_quality_model_is_left_alone(self):
        a, b, _ = self.contestants
        self.fly(b, 1000)
        # An entry without a kind and with points: made when the processor normalised per contestant
        self.log(a, -83.3, kind="")
        ContestantTrack.objects.filter(contestant=a).update(calculator_started=True, score=916.7)
        refresh_contestant_quality(a)
        self.assertEqual(916.7, self.track(a).score)
        self.assertIsNone(self.track(a).quality_start)

    def test_a_reset_of_the_best_contestant_renormalises_the_rest(self):
        a, b, _ = self.contestants
        self.fly(a, 1200)
        self.fly(b, 1200, {"points": -300})
        self.assertEqual([1000, 750], self.scores()[:2])
        a.reset_track_and_score()
        self.assertEqual([0, 1000], self.scores()[:2])
        self.assertEqual(0, self.track(a).raw_quality)
        self.assertIsNone(self.track(a).quality_start)

    def test_deleting_the_best_contestant_renormalises_the_rest(self):
        a, b, _ = self.contestants
        self.fly(a, 1200)
        self.fly(b, 1200, {"points": -300})
        with self.captureOnCommitCallbacks(execute=True):
            Contestant.objects.get(pk=a.pk).delete()
        self.assertEqual(1000, self.track(b).score)

    def test_deleting_the_task_with_its_contestants_does_not_fail(self):
        self.fly(self.contestants[0], 1200)
        with self.captureOnCommitCallbacks(execute=True):
            self.task.delete()
        self.assertFalse(ContestantTrack.objects.filter(contestant__in=self.contestants).exists())

    def test_changing_the_task_value_of_the_scorecard_rescores_the_task(self):
        a, b, _ = self.contestants
        self.fly(a, 1200)
        self.fly(b, 1200, {"points": -300})
        self.task.scorecard.config["task_value"] = 1500
        with self.captureOnCommitCallbacks(execute=True):
            self.task.scorecard.save(update_fields=["config"])
        self.assertEqual([1500, 1125, 0], self.scores())

    def test_scores_are_provisional_until_every_flight_has_finished(self):
        a, b, _ = self.contestants
        self.fly(a, 1200)
        self.assertTrue(task_scores_are_provisional(self.task))
        ContestantTrack.objects.filter(contestant__navigation_task=self.task).update(calculator_finished=True)
        self.assertFalse(task_scores_are_provisional(self.task))

    def test_a_task_of_the_penalty_model_is_not_touched(self):
        legacy = self.make_task(None)
        contestant = self.make_contestant(legacy)
        ContestantTrack.objects.filter(contestant=contestant).update(score=42, calculator_started=True)
        self.assertEqual(0, recompute_task_scores(legacy, refresh=[contestant]))
        self.assertEqual(42, self.track(contestant).score)
        self.assertFalse(task_scores_are_provisional(legacy))


class TestContractPointsShareOfTheBest(TaskScoringTestCase):
    """2.A3: Qp = 1000 x V / Vmax. The log holds the count V; the points follow the best V of the task."""

    task_subtype = CONTRACT_NAVIGATION_TIME_CONTROLS

    def points(self, contestant, count, kind=ACHIEVEMENT):
        """`count` entries of one V each, as the calculator logs them, one per declared point."""
        return [
            {"points": 1 if kind == ACHIEVEMENT else -1, "kind": kind, "score_type": CONTRACT_POINTS_SCORE_TYPE,
             "gate": f"P{index}"}
            for index in range(count)
        ]

    def test_the_best_v_earns_a_thousand_and_the_others_their_share(self):
        a, b, c = self.contestants
        self.fly(a, 540, *self.points(a, 4))
        self.fly(b, 540, *self.points(b, 2))
        self.fly(c, 540)
        # Q = 540 + 1000 x V / 4: 1540, 1040 and 540; P = 1000 x Q / 1540
        self.assertEqual([1540, 1040, 540], [self.track(x).raw_quality for x in self.contestants])
        self.assertEqual([1000, 675, 351], self.scores())

    def test_the_breakdown_shows_the_share_as_points_of_q(self):
        a, b, _ = self.contestants
        self.fly(a, 540, *self.points(a, 4))
        self.fly(b, 540, *self.points(b, 1))
        self.assertEqual({CONTRACT_POINTS_SCORE_TYPE: 1000.0}, self.track(a).quality_breakdown)
        self.assertEqual({CONTRACT_POINTS_SCORE_TYPE: 250.0}, self.track(b).quality_breakdown)

    def test_vmax_follows_the_other_contestants_results(self):
        a, b, _ = self.contestants
        self.fly(a, 540, *self.points(a, 2))
        self.assertEqual(1540, self.track(a).raw_quality)
        self.fly(b, 540, *self.points(b, 4))
        # b now sets Vmax: a's share halves without a's own log changing
        self.assertEqual([1040, 1540], [self.track(x).raw_quality for x in (a, b)])
        self.assertEqual([675, 1000], self.scores()[:2])
        # a result that is taken away (the contestant is reset) gives the share back
        ScoreLogEntry.objects.filter(contestant=b).delete()
        refresh_contestant_quality(b)
        self.assertEqual(1540, self.track(a).raw_quality)
        self.assertEqual([1000, 351], self.scores()[:2])

    def test_declared_points_not_flown_take_the_count_down_below_zero(self):
        a, b, _ = self.contestants
        self.fly(a, 540, *self.points(a, 4))
        self.fly(b, 540, *self.points(b, 1), *self.points(b, 3, PENALTY))
        # V = 1 - 3 = -2 of Vmax 4: -500 points
        self.assertEqual(40, self.track(b).raw_quality)
        self.assertEqual(round(1000 * 40 / 1540), self.scores()[1])

    def test_without_a_positive_vmax_the_term_is_nothing(self):
        a, b, _ = self.contestants
        self.fly(a, 540)
        self.fly(b, 540, *self.points(b, 2, PENALTY))
        self.assertEqual([540, 540], [self.track(x).raw_quality for x in (a, b)])

    def test_a_contestant_who_did_not_fly_does_not_set_vmax(self):
        a, b, _ = self.contestants
        self.fly(a, 540, *self.points(a, 2))
        self.fly(b, 540, *self.points(b, 4), started=False)
        self.assertEqual(1540, self.track(a).raw_quality)

    def test_recomputing_is_idempotent_and_writes_nothing_the_second_time(self):
        a, b, _ = self.contestants
        self.fly(a, 540, *self.points(a, 4))
        self.fly(b, 540, *self.points(b, 2))
        before = ([self.track(x).raw_quality for x in (a, b)], self.scores())
        self.assertEqual(0, recompute_task_scores(self.task))
        self.assertEqual(0, recompute_task_scores(self.task, refresh=self.contestants))
        self.assertEqual(before, ([self.track(x).raw_quality for x in (a, b)], self.scores()))

    def test_the_term_is_worth_a_thousand_for_the_best_contestant(self):
        from display.services.task_scoring import relative_term_values
        from display.utilities.task_types import get_task_type

        values = relative_term_values(self.task.scorecard, get_task_type(CONTRACT_NAVIGATION_TIME_CONTROLS))
        self.assertEqual({CONTRACT_POINTS_SCORE_TYPE: 1000.0}, values)


class TestSpeedTermShareOfTheBest(TaskScoringTestCase):
    """2.A4: Qv = Vs x S / Smax. The log holds the speed S in knots; Vs is the scorecard's."""

    task_subtype = KNOWN_CIRCUIT

    def speed(self, kt):
        return {"points": kt, "kind": ACHIEVEMENT, "score_type": SPEED_TERM_SCORE_TYPE, "gate": "FP"}

    def set_vs(self, value):
        self.task.scorecard.config["speed_term_value"] = value
        self.task.scorecard.save(update_fields=["config"])

    def test_the_fastest_pilot_earns_vs_and_the_others_their_share(self):
        self.set_vs(100)
        a, b, c = self.contestants
        self.fly(a, 1000, self.speed(80))
        self.fly(b, 1000, self.speed(100))
        self.fly(c, 1000)
        self.assertEqual([1080, 1100, 1000], [self.track(x).raw_quality for x in self.contestants])
        self.assertEqual({SPEED_TERM_SCORE_TYPE: 80.0}, self.track(a).quality_breakdown)

    def test_smax_follows_the_other_contestants_results(self):
        self.set_vs(100)
        a, b, _ = self.contestants
        self.fly(a, 1000, self.speed(80))
        self.assertEqual(1100, self.track(a).raw_quality)
        self.fly(b, 1000, self.speed(160))
        self.assertEqual([1050, 1100], [self.track(x).raw_quality for x in (a, b)])

    def test_without_a_briefed_value_the_task_has_no_speed_term(self):
        a, b, _ = self.contestants
        self.fly(a, 1000, self.speed(80))
        self.fly(b, 1000, self.speed(160))
        self.assertEqual([1000, 1000], [self.track(x).raw_quality for x in (a, b)])
        self.assertEqual({}, self.track(a).quality_breakdown)

    def test_changing_vs_rescores_the_task(self):
        a, b, _ = self.contestants
        self.fly(a, 1000, self.speed(80))
        self.fly(b, 1000, self.speed(160))
        self.set_vs(200)
        recompute_task_scores(self.task, refresh=self.contestants)
        self.assertEqual([1100, 1200], [self.track(x).raw_quality for x in (a, b)])


class TestAbsoluteScores(MessageTestCase):
    def fly(self, contestant, start, points):
        ContestantTrack.objects.filter(contestant=contestant).update(
            quality_start=start, quality_theoretical_maximum=start, calculator_started=True
        )
        ScoreLogEntry.objects.create(
            time=datetime.datetime(2026, 1, 1, 8, 5, tzinfo=datetime.timezone.utc),
            contestant=contestant,
            gate="G",
            message="penalty",
            points=points,
            score_type="x",
            score_kind=PENALTY,
        )
        refresh_contestant_quality(contestant)

    def test_the_circle_scores_its_formula_value_not_a_share_of_the_best(self):
        task = self.make_task(CIRCLE)
        task.scorecard.config["task_value"] = 1500
        task.scorecard.save(update_fields=["config"])
        a, b = self.make_contestant(task, 1), self.make_contestant(task, 2)
        self.fly(a, 250, -50)  # P = 200 even though b is worse and the task value is 1500
        self.fly(b, 250, -130)
        self.assertEqual([200, 120], [ContestantTrack.objects.get(contestant=c).score for c in (a, b)])

    def test_the_anr_scores_q_over_2000_of_the_task_value(self):
        task = self.make_task(ANR_CATALOGUE, self.anr_original)
        a, b = self.make_contestant(task, 1), self.make_contestant(task, 2)
        self.fly(a, 2000, -500)
        self.fly(b, 2000, -2000)
        self.assertEqual([750, 0], [ContestantTrack.objects.get(contestant=c).score for c in (a, b)])
        task.scorecard.config["task_value"] = 500
        task.scorecard.save(update_fields=["config"])
        recompute_task_scores(task)
        self.assertEqual(375, ContestantTrack.objects.get(contestant=a).score)


class TestProvisionalMeansDependingOnOtherPilots(MessageTestCase):
    """A score is provisional while a flight of another pilot can still change it, not merely while a flight is going."""

    def provisional(self, subtype, policy=None, original=None) -> bool:
        task = self.make_task(subtype, original) if original else self.make_task(subtype)
        if policy:
            task.scorecard.config["qmax_policy"] = policy
            task.scorecard.save(update_fields=["config"])
        self.make_contestant(task, 1)  # a flight that is not finished
        return task_scores_are_provisional(task)

    def test_the_circle_and_the_anr_task_are_fixed_scales_and_never_provisional(self):
        self.assertFalse(self.provisional(CIRCLE))
        self.assertFalse(self.provisional(ANR_CATALOGUE, original=self.anr_original))

    def test_a_theoretical_policy_without_relative_terms_is_final_at_landing(self):
        self.assertFalse(self.provisional(CURVE_NAVIGATION_TIME_ESTIMATION, QMAX_THEORETICAL))
        self.assertFalse(self.provisional(PRECISION_NAVIGATION, QMAX_THEORETICAL))

    def test_the_best_in_task_policy_is_provisional_until_the_flights_are_finished(self):
        self.assertTrue(self.provisional(CURVE_NAVIGATION_TIME_ESTIMATION, QMAX_BEST_IN_TASK))

    def test_a_theoretical_policy_is_provisional_where_a_term_follows_the_best_pilot(self):
        # 2.A3's V is shared against the best pilot whatever the policy
        self.assertTrue(self.provisional(CONTRACT_NAVIGATION_TIME_CONTROLS, QMAX_THEORETICAL))

    def test_it_ends_with_the_last_flight(self):
        task = self.make_task(CURVE_NAVIGATION_TIME_ESTIMATION)
        self.make_contestant(task, 1)
        self.assertTrue(task_scores_are_provisional(task))
        ContestantTrack.objects.filter(contestant__navigation_task=task).update(calculator_finished=True)
        self.assertFalse(task_scores_are_provisional(task))

    def test_the_explanation_agrees(self):
        from display.services.scoring_explanation import explain_navigation_task

        circle = self.make_task(CIRCLE)
        self.assertFalse(explain_navigation_task(circle)["provisional"]["depends_on_other_pilots"])
        theoretical = self.make_task(PRECISION_NAVIGATION)
        theoretical.scorecard.config["qmax_policy"] = QMAX_THEORETICAL
        theoretical.scorecard.save(update_fields=["config"])
        self.assertFalse(explain_navigation_task(theoretical)["provisional"]["depends_on_other_pilots"])


class TestScoreScale(MessageTestCase):
    """What the task score is out of: the circle's score is Q itself (250), not a share of the task value."""

    def test_the_circle_is_out_of_its_perfect_score_not_the_task_value(self):
        from display.services.task_scoring import scoring_parameters

        task = self.make_task(CIRCLE)
        self.assertEqual(1000, scoring_parameters(task).task_value)
        self.assertEqual(250, scoring_parameters(task).score_scale)

    def test_the_anr_task_is_out_of_the_task_value(self):
        from display.services.task_scoring import scoring_parameters

        self.assertEqual(1000, scoring_parameters(self.make_task(ANR_CATALOGUE, self.anr_original)).score_scale)

    def test_the_other_quality_tasks_are_out_of_the_task_value(self):
        from display.services.task_scoring import scoring_parameters

        self.assertEqual(1000, scoring_parameters(self.make_task(PRECISION_NAVIGATION)).score_scale)

    def test_the_task_payload_sends_it(self):
        from display.serialisers import NavigationTaskNestedTeamRouteSerialiser

        task = self.make_task(CIRCLE)
        self.assertEqual(250, NavigationTaskNestedTeamRouteSerialiser().get_score_scale(task))


class TestOutsideContributors(TaskScoringTestCase):
    """Administrative penalties go through the same raw values and the same recomputation."""

    def test_an_administrative_penalty_reduces_q_and_renormalises(self):
        a, b, _ = self.contestants
        self.fly(a, 1000)
        self.fly(b, 1000)
        self.assertEqual([1000, 1000], self.scores()[:2])
        entry = AdministrativePenaltyService.apply_contestant_penalty(contestant=b, points=250, reason="fuel")
        self.assertEqual(-250, entry.points)
        self.assertEqual(PENALTY, entry.score_kind)
        self.assertEqual([1000, 750], self.scores()[:2])
        self.assertEqual(750, self.track(b).raw_quality)

    def test_a_penalty_of_the_best_contestant_raises_the_others(self):
        a, b, _ = self.contestants
        self.fly(a, 1000)
        self.fly(b, 1000, {"points": -500})
        self.assertEqual([1000, 500], self.scores()[:2])
        AdministrativePenaltyService.apply_contestant_penalty(contestant=a, points=700, reason="x")
        # Q = 300 and 500: b is the best now
        self.assertEqual([600, 1000], self.scores()[:2])

    def test_a_percentage_penalty_is_taken_from_the_task_score(self):
        a, b, _ = self.contestants
        self.fly(a, 1000)
        self.fly(b, 1000)
        AdministrativePenaltyService.apply_contestant_penalty(contestant=b, points=0, reason="q", percentage=100)
        self.assertEqual([1000, 0], self.scores()[:2])
        self.assertEqual(1000, self.track(b).raw_quality)
        self.assertEqual(100, self.track(b).percentage_penalty)

    def test_a_percentage_penalty_needs_a_quality_task(self):
        contestant = self.make_contestant(self.make_task(None))
        with self.assertRaises(ValueError):
            AdministrativePenaltyService.apply_contestant_penalty(
                contestant=contestant, points=0, reason="x", percentage=50
            )

    def test_removing_the_entry_gives_the_points_back(self):
        a, b, _ = self.contestants
        self.fly(a, 1000)
        self.fly(b, 1000)
        entry = AdministrativePenaltyService.apply_contestant_penalty(contestant=b, points=250, reason="fuel")
        AdministrativePenaltyService.remove_score_log_entry(ScoreLogEntry.objects.get(pk=entry.pk))
        self.assertEqual([1000, 1000], self.scores()[:2])
        self.assertEqual(1000, self.track(b).raw_quality)

    def test_a_penalty_of_the_penalty_model_still_adds_to_the_total(self):
        legacy = self.make_task(None)
        contestant = self.make_contestant(legacy)
        AdministrativePenaltyService.apply_contestant_penalty(contestant=contestant, points=75, reason="x")
        self.assertEqual(75, self.track(contestant).score)
        entry = ScoreLogEntry.objects.get(contestant=contestant)
        self.assertEqual(75, entry.points)
        AdministrativePenaltyService.remove_score_log_entry(entry)
        self.assertEqual(0, self.track(contestant).score)


class TestAchievementTasks(MessageTestCase):
    def test_a_hunt_earns_points_from_zero(self):
        task = self.make_task(TURNPOINT_HUNT)
        a, b = self.make_contestant(task, 1), self.make_contestant(task, 2)
        for contestant, points in ((a, 300), (b, 150)):
            ContestantTrack.objects.filter(contestant=contestant).update(
                quality_start=0, quality_theoretical_maximum=400, calculator_started=True
            )
            ScoreLogEntry.objects.create(
                time=datetime.datetime(2026, 1, 1, 8, 5, tzinfo=datetime.timezone.utc),
                contestant=contestant,
                gate="TP1",
                message="target",
                points=points,
                score_type="turnpoint_hunt_target_value",
                score_kind=ACHIEVEMENT,
            )
            refresh_contestant_quality(contestant)
        self.assertEqual([1000, 500], [ContestantTrack.objects.get(contestant=c).score for c in (a, b)])


class TestConcurrentRecomputation(TransactionTestCase):
    """Several worker processes change the raw values of their contestants and recompute at the same moment."""

    def test_concurrent_recomputation_ends_in_the_state_a_serial_run_gives(self):
        from unittest.mock import patch

        from display.default_scorecards.create_scorecards import create_scorecards
        from display.models import Aeroplane, Contest, Crew, NavigationTask, Person, Route, Scorecard, Team
        from utilities.mock_utilities import TraccarMock

        with (
            patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock),
            patch("display.signals.get_traccar_instance", return_value=TraccarMock),
        ):
            create_scorecards()
            contest = Contest.objects.create(
                name="Concurrent scoring contest",
                start_time=datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
                finish_time=datetime.datetime(2026, 1, 2, tzinfo=datetime.timezone.utc),
            )
            task = NavigationTask.create(
                name="concurrent",
                contest=contest,
                route=Route.objects.create(name="concurrent route"),
                original_scorecard=Scorecard.get_originals().get(shortcut_name="FAI Precision"),
                start_time=datetime.datetime(2026, 1, 1, 6, tzinfo=datetime.timezone.utc),
                finish_time=datetime.datetime(2026, 1, 1, 16, tzinfo=datetime.timezone.utc),
                task_subtype=PRECISION_NAVIGATION,
            )
            contestants = []
            for number in range(1, 5):
                person = Person.objects.create(first_name="C", last_name=str(number), email=f"c{number}@example.com")
                team = Team.objects.create(
                    crew=Crew.objects.create(member1=person),
                    aeroplane=Aeroplane.objects.create(registration=f"LN-C{number}"),
                )
                start = datetime.datetime(2026, 1, 1, 8, tzinfo=datetime.timezone.utc)
                contestants.append(
                    Contestant.objects.create(
                        navigation_task=task,
                        team=team,
                        takeoff_time=start,
                        tracker_start_time=start - datetime.timedelta(minutes=30),
                        finished_by_time=start + datetime.timedelta(hours=2),
                        tracker_device_id=f"c{number}",
                        contestant_number=number,
                    )
                )
        penalties = {contestant.pk: 100 * index for index, contestant in enumerate(contestants)}
        for contestant in contestants:
            ContestantTrack.objects.filter(contestant=contestant).update(
                quality_start=1000, quality_theoretical_maximum=1000, calculator_started=True
            )
        errors = []
        barrier = threading.Barrier(len(contestants))

        def worker(contestant):
            try:
                barrier.wait(timeout=30)
                ScoreLogEntry.objects.create(
                    time=datetime.datetime(2026, 1, 1, 8, 5, tzinfo=datetime.timezone.utc),
                    contestant=contestant,
                    gate="G",
                    message="penalty",
                    points=-penalties[contestant.pk],
                    score_type="gate_score",
                    score_kind=PENALTY,
                )
                refresh_contestant_quality(contestant)
            except Exception as exc:  # pragma: no cover - reported below
                errors.append(exc)
            finally:
                connection.close()

        threads = [threading.Thread(target=worker, args=(contestant,)) for contestant in contestants]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=120)
        self.assertEqual([], errors)
        # Q = 1000, 900, 800, 700 against the best 1000
        self.assertEqual([1000, 900, 800, 700], [ContestantTrack.objects.get(contestant=c).score for c in contestants])
        self.assertEqual(0, recompute_task_scores(NavigationTask.objects.get(pk=task.pk)))
