"""Scenario tests: synthetic flights through the real calculators for CIMA 2.A6 and 2.B2 (turnpoint hunts).

The catalogue: typically 100 points per photo (turn point identified), 200 per time gate, and for 2.A6 a bonus for the
full and correct sequence; a timing gate more than 10 s from its prediction costs 10 points per second beyond the
tolerance, time over the maximum task duration 10 points per second, a photo wrongly identified 50% of its value, a
quarantine breach 100%. P = 1000 x Q / Qmax, Qmax the best Q of the task. 2.B2 flies the same hunt on limited fuel and
has no sequence: every crossing scores in whatever order the pilot flies.

The route has no backbone: three standalone timed points CP1, CP2, CP3 on a line east, and two free targets worth 100
each. The pilot declares the times of the three timed points (174 s apart) and the sequence. The end of the task, for the
maximum duration, is the last gate crossed (the application has no other event for it).

Tests marked xfail(strict=True) are known disagreements of the application, with the finding and the slice of
docs/PLAN_task_scoring_reliability.md that will fix them.
"""

import datetime

import pytest

from display.calculators.tests import catalogue_oracle as oracle
from display.calculators.tests.cima_scenario_support import CimaScenarioCase, first_crossing_errors
from display.calculators.tests.flight_simulator import (
    SkipGate,
    TimeOffset,
    add_contestant,
    build_task,
    gate_crossings,
    generate_track,
    hunt_route_geojson,
)
from display.utilities.task_types import LIMITED_FUEL_TURNPOINT_HUNT, TURNPOINT_HUNT

START = datetime.datetime(2020, 8, 1, 8, 15, tzinfo=datetime.timezone.utc)
COMPULSORY = {"CP1": (0, 0), "CP2": (6000, 0), "CP3": (12000, 0)}
TARGETS = {"A": (3000, -1500, 100), "B": (9000, 1500, 100)}
TIMED = ["CP1", "CP2", "CP3"]
SEQUENCE = ["CP1", "A", "CP2", "B", "CP3"]
SEQUENCE_BONUS = 250
MAX_DURATION_MINUTES = 15  # from take-off at 08:05: the deadline is 08:20:00, CP3 is crossed at 08:20:48


def declaration(sequence=SEQUENCE, seconds=(0, 174, 348), **extra):
    times = {name: START + datetime.timedelta(seconds=offset) for name, offset in zip(TIMED, seconds)}
    payload = {"compulsory_point_times": {name: time.isoformat() for name, time in times.items()}, **extra}
    if sequence:
        payload["declared_sequence"] = sequence
    return payload


def configure(bonus=SEQUENCE_BONUS, maximum_duration=None):
    def configure_scorecard(scorecard):
        scorecard.turnpoint_hunt_sequence_bonus = bonus
        if maximum_duration:
            scorecard.maximum_task_duration_minutes = maximum_duration

    return configure_scorecard


def build(subtype, declared=None, bonus=SEQUENCE_BONUS, maximum_duration=None, targets=TARGETS, **options):
    task = build_task(
        hunt_route_geojson(compulsory=COMPULSORY, catalogue=targets),
        task_subtype=subtype,
        scorecard_shortcut="CIMA Precision",
        configure_scorecard=configure(bonus, maximum_duration),
        whole_second_gate_times=True,
        **options,
    )
    return task.declare(declared if declared is not None else declaration())


def flown_times(order):
    """Expected times of the points of a flight over `order`: the timed points as declared, the free targets half way
    between their timed neighbours."""
    times = {name: START + datetime.timedelta(seconds=offset) for name, offset in zip(TIMED, (0, 174, 348))}
    times.update({"A": START + datetime.timedelta(seconds=87), "B": START + datetime.timedelta(seconds=261)})
    return {name: times[name] for name in order}


def hunt_quality(task, track, declared_sequence, *, targets=TARGETS, maximum_duration_minutes=None, order=None):
    """Q of a flown hunt, from the geometry: the targets overflown, the timing errors of the three timed points, the
    full sequence, and the seconds the last gate was crossed after the deadline. With `order` the gate lines are those
    of a flight over the points in that order (whatever sequence was declared)."""
    if order:
        by_name = {w.name: w for w in task.effective_waypoints}
        crossings = gate_crossings([by_name[name] for name in order], flown_times(order), track, task.projector)
    else:
        crossings = task.crossings(track, [*TIMED, *targets])
    photo_values = [targets[name][2] for name in targets if crossings[name]]
    errors = first_crossing_errors(crossings, TIMED)
    flown_order = [
        name for _, name in sorted((crossings[name][0].time, name) for name in [*TIMED, *targets] if crossings[name])
    ]
    full_sequence = bool(declared_sequence) and flown_order == declared_sequence
    over = 0.0
    if maximum_duration_minutes:
        deadline = task.contestant.takeoff_time + datetime.timedelta(minutes=maximum_duration_minutes)
        last = max((crossings[name][-1].time for name in [*TIMED, *targets] if crossings[name]), default=deadline)
        over = max(0.0, (last - deadline).total_seconds())
    return photo_values, errors, full_sequence, over


PERFECT_2A6 = oracle.q_turnpoint_hunt([100, 100], [0, 0, 0], sequence_bonus=SEQUENCE_BONUS, full_sequence=True)
PERFECT_2B2 = oracle.q_limited_fuel_turnpoint_hunt([100, 100], [0, 0, 0])


class TurnpointHuntFlightsTest(CimaScenarioCase):
    def build(self, **options):
        self.task = build(TURNPOINT_HUNT, **options)
        self.assertTrue(self.task.contestant.contestanttaskconfiguration.is_valid)
        return self.task

    def fly(self, *deviations, maximum_duration=None, **options):
        track = self.task.generate_track(list(deviations), **options)
        result = self.task.run(track)
        photos, errors, full, over = hunt_quality(self.task, track, SEQUENCE, maximum_duration_minutes=maximum_duration)
        q = oracle.q_turnpoint_hunt(
            photos, errors, sequence_bonus=SEQUENCE_BONUS, full_sequence=full, seconds_over_maximum_duration=over
        )
        return result, self.final_against_reference(q, PERFECT_2A6)

    def test_the_time_gates_are_the_declared_times(self):
        task = self.build()
        self.assertEqual(task.gate_times["CP1"], START)
        self.assertEqual(task.gate_times["CP3"] - task.gate_times["CP1"], datetime.timedelta(seconds=348))
        self.assertEqual([w.name for w in task.effective_waypoints], SEQUENCE)

    def test_perfect_flight_scores_the_task_value(self):
        self.build()
        result, expected = self.fly()
        self.assertEqual(expected, 1000)
        self.assert_final_score(result, expected, "perfect flight")

    @pytest.mark.xfail(
        strict=True,
        reason="F8 / S16: the generic gate timing score (1 point per second) is charged "
        "on a compulsory gate inside its 10 s tolerance, which must cost nothing",
    )
    def test_a_timing_gate_eight_seconds_off_is_inside_the_tolerance_and_costs_nothing(self):
        self.build()
        result, expected = self.fly(TimeOffset("CP2", 8))
        self.assertEqual(expected, 1000)
        self.assert_final_score(result, expected, "CP2 8 s late")

    @pytest.mark.xfail(
        strict=True,
        reason="F8 / S16: a compulsory gate 25 s off is charged twice (the generic gate "
        "timing score and the compulsory timing score, 25 points each); the "
        "catalogue charges 10 points per second beyond the 10 s tolerance (150)",
    )
    def test_a_timing_gate_twenty_five_seconds_off_costs_ten_points_per_second_beyond_the_tolerance(self):
        self.build()
        result, expected = self.fly(TimeOffset("CP2", 25))
        self.assertEqual(expected, oracle.round_half_up(1000 * (1050 - 150) / 1050))
        self.assert_final_score(result, expected, "CP2 25 s late")

    @pytest.mark.xfail(
        strict=True,
        reason="F9 / S16: a time gate crossed earns nothing in the application (200 per time "
        "gate in the catalogue), so a missed target costs a fifth of what it "
        "should; the application's score also goes below zero (S9)",
    )
    def test_a_target_missed_loses_its_points_and_the_sequence_bonus(self):
        self.build()
        result, expected = self.fly(SkipGate("B"))
        self.assertEqual(expected, oracle.round_half_up(1000 * (100 + 600) / 1050))
        self.assert_final_score(result, expected, "B missed")

    @pytest.mark.xfail(
        strict=True,
        reason="F10 / S16: the time over the maximum task duration costs a flat 100 points "
        "per gate crossed after it in the application; the catalogue 10 points "
        "per second over (480 for 48 s)",
    )
    def test_time_over_the_maximum_duration_costs_ten_points_per_second(self):
        self.build(maximum_duration=MAX_DURATION_MINUTES)
        result, expected = self.fly(maximum_duration=MAX_DURATION_MINUTES)
        self.assertEqual(expected, oracle.round_half_up(1000 * (1050 - 480) / 1050))
        self.assert_final_score(result, expected, "CP3 48 s after the maximum duration")

    @pytest.mark.xfail(
        strict=True,
        reason="F9 / S16 and S9: the full sequence bonus is awarded but the time gates "
        "earn nothing, and Qmax is not the best pilot's Q; the second pilot "
        "scores negative",
    )
    def test_two_pilots_in_the_same_task_are_scored_against_the_best(self):
        self.build()
        second = add_contestant(self.task).declare(declaration())
        track_a = self.task.generate_track([TimeOffset("CP3", 12)])
        track_b = second.generate_track([SkipGate("A"), TimeOffset("CP2", 25)])
        a, b = self.task.run(track_a), second.run(track_b)
        qs = []
        for task, track in ((self.task, track_a), (second, track_b)):
            photos, errors, full, _ = hunt_quality(task, track, SEQUENCE)
            qs.append(oracle.q_turnpoint_hunt(photos, errors, sequence_bonus=SEQUENCE_BONUS, full_sequence=full))
        expected = oracle.final_scores(qs)
        self.assertEqual(expected[0], 1000)
        self.assertLess(expected[1], 1000)
        self.assertEqual((a.score, b.score), tuple(expected))


class LimitedFuelTurnpointHuntFlightsTest(CimaScenarioCase):
    """2.B2: every crossing scores, in any order; no sequence bonus."""

    def build(self, sequence=SEQUENCE, **options):
        self.task = build(
            LIMITED_FUEL_TURNPOINT_HUNT,
            declared=declaration(sequence, fuel_metadata={"declared_endurance_minutes": 90}),
            bonus=0,
            **options,
        )
        self.assertTrue(self.task.contestant.contestanttaskconfiguration.is_valid)
        return self.task

    def expected(self, track, order=None):
        photos, errors, _, _ = hunt_quality(self.task, track, [], order=order)
        return self.final_against_reference(oracle.q_limited_fuel_turnpoint_hunt(photos, errors), PERFECT_2B2)

    def fly(self, *deviations, **options):
        track = self.task.generate_track(list(deviations), **options)
        return self.task.run(track), self.expected(track)

    def flown_in_order(self, names):
        """A track over the points in `names` in that order, timed as the declaration times the timed points (the free
        targets half way between their neighbours), whatever the declared sequence is."""
        by_name = {w.name: w for w in self.task.effective_waypoints}
        return generate_track([by_name[name] for name in names], flown_times(names), projector=self.task.projector)

    def test_perfect_flight_scores_the_task_value(self):
        self.build()
        result, expected = self.fly()
        self.assertEqual(expected, 1000)
        self.assert_final_score(result, expected, "perfect flight")

    @pytest.mark.xfail(
        strict=True,
        reason="F8 / S16: a compulsory gate 25 s off is charged twice (generic gate score "
        "and compulsory timing, 25 each) and the time gates earn nothing (F9); the "
        "catalogue charges 150 points",
    )
    def test_a_timing_gate_twenty_five_seconds_off(self):
        self.build()
        result, expected = self.fly(TimeOffset("CP2", 25))
        self.assertEqual(expected, oracle.round_half_up(1000 * (800 - 150) / 800))
        self.assert_final_score(result, expected, "CP2 25 s late")

    @pytest.mark.xfail(
        strict=True,
        reason="F11 / S16: the application matches the targets in the declared order: "
        "flying A where B was declared marks the gates in between as missed; in "
        "2.B2 the order is free and every target scores",
    )
    def test_targets_flown_in_an_order_different_from_the_declaration_all_score(self):
        self.build(sequence=["CP1", "B", "CP2", "A", "CP3"])
        order = ["CP1", "A", "CP2", "B", "CP3"]
        track = self.flown_in_order(order)
        result = self.task.run(track)
        expected = self.expected(track, order)
        self.assertEqual(expected, 1000)
        self.assert_final_score(result, expected, "A and B flown the other way round")

    @pytest.mark.xfail(
        strict=True,
        reason="NEW: without a declared sequence the free targets get no gate time and "
        "GateCalculator.create_gates raises KeyError, so nothing is scored "
        "(gate_calculator.py: expected_times[item.name]); the catalogue scores "
        "every target flown",
    )
    def test_no_declared_sequence_at_all(self):
        self.build(sequence=None)
        order = ["CP1", "A", "CP2", "B", "CP3"]
        track = self.flown_in_order(order)
        result = self.task.run(track)
        expected = self.expected(track, order)
        self.assertEqual(expected, 1000)
        self.assert_final_score(result, expected, "no declared sequence")
