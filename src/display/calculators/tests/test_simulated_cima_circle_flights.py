"""Scenario tests: synthetic flights through the real calculators for CIMA 2.A7 (Circle).

The catalogue: over SP and CM in a straight line, bank left; the first 180 degrees are not scored; from crossing the
entry line X the next 360 degrees are scored, ending on crossing X again; then leave to WP. P = (Rmin/Rmax - 0.5) x 500
with Rmin and Rmax from the scored circle, at most 250, an absolute score. A 20% penalty when the circle spans more than
200 ft in altitude; a 100% penalty when it is flown clockwise, CM is outside the flown circle, SP and CM are not
overflown, the aircraft leaves the radius limits (200-750 m) or Rmin/Rmax is 0.5 or smaller.

The flights are generated with `circle_flight`: straight from SP (1000 m west of CM) over CM to the edge of the circle,
a left turn of 540 degrees (180 not scored and 360 scored) and out to WP. Whether the unit of the altitude is feet or
metres is open (D5), so the altitude scenarios use spreads far from the band either way (30 against 300).

Tests marked xfail(strict=True) are known disagreements of the application, with the finding and the slice of
docs/PLAN_task_scoring_reliability.md that will fix them.
"""

import math

import pytest

from display.calculators.tests import catalogue_oracle as oracle
from display.calculators.tests.cima_scenario_support import CimaScenarioCase
from display.calculators.tests.flight_simulator import (
    add_contestant,
    build_task,
    circle_flight,
    circle_route_geojson,
    local_point,
)
from display.utilities.task_types import CIRCLE

CENTRE = (59.895825678413914, 10.624465942382812)
START_M = (-1000.0, 0.0)  # SP, west of CM, the flight goes east
ENTRY_M = (
    150.0,
    0.0,
)  # X: the entry line, crossed on the straight run from CM to the circle (inside the minimum radius)
EXIT_NORTH = (0.0, 600.0)
SCORED_ARC = (180.0, 540.0)  # degrees from the start of the left turn
FLAT = 1000.0
BAND_EXCEEDED_AMPLITUDE = 150.0  # a spread of 300
BAND_KEPT_AMPLITUDE = 15.0  # a spread of 30


def point(offset_m):
    """(lat, lon) of a point `offset_m` (east, north) of CM."""
    return local_point(CENTRE, offset_m[0], -offset_m[1])


def scored_radii(radius, arc=SCORED_ARC):
    """Rmin and Rmax of the flown circle between the angles of `arc`, from the radius function of the flight."""
    values = [radius(arc[0] + (arc[1] - arc[0]) * step / 360.0) for step in range(361)]
    return min(values), max(values)


def wavy_altitude(task, amplitude):
    """Altitude as a function of time: a 60 s wave of the given amplitude around 1000 (several waves in the circle)."""
    start = task.gate_times["SP"]
    return lambda time: FLAT + amplitude * math.sin(2 * math.pi * (time - start).total_seconds() / 60.0)


class CircleFlightsTest(CimaScenarioCase):
    def build(self, exit_m=EXIT_NORTH):
        self.task = build_task(
            circle_route_geojson(CENTRE, START_M, ENTRY_M, exit_m),
            task_subtype=CIRCLE,
            scorecard_shortcut="CIMA Precision",
        )
        self.assertEqual([w.name for w in self.task.effective_waypoints], ["SP", "X", "CM", "WP"])
        return self.task

    def circle(self, task=None, exit_m=EXIT_NORTH, sweep=540.0, **options):
        task = task or self.task
        return circle_flight(
            point(START_M),
            CENTRE,
            point(exit_m),
            start_time=task.gate_times["SP"],
            sweep_deg=sweep,
            **options,
        )

    def fly(self, radius=500.0, **options):
        track = self.circle(radius_m=radius, **options)
        return self.task.run(track)

    def test_the_task_scores_out_of_a_maximum_of_250(self):
        scorecard = self.build().navigation_task.scorecard
        self.assertEqual((scorecard.score_sorting_direction, scorecard.initial_score), ("desc", 250))

    @pytest.mark.xfail(
        strict=True,
        reason="F12 / S17: the scored arc is measured as 540 degrees from the entry "
        "crossing around CM and includes the approach over CM, so the radius samples "
        "of a correct circle spread (239.7 points instead of 250)",
    )
    def test_a_catalogue_shaped_circle_of_constant_radius_scores_the_maximum(self):
        self.build()
        result = self.fly(radius=500.0)
        expected = oracle.circle_final_score(*scored_radii(lambda angle: 500.0))
        self.assertEqual(expected, 250)
        self.assert_final_score(result, expected, "constant radius 500 m, left, 540 degrees")

    @pytest.mark.xfail(
        strict=True,
        reason="S9: the application's score is not rounded to a whole number (159.1 "
        "against 159); the ratio itself agrees with the formula",
    )
    def test_a_radius_that_varies_ten_percent_scores_from_the_formula(self):
        self.build()

        def radius(angle):
            return 500.0 + 50.0 * math.cos(math.radians(angle))

        result = self.fly(radius=radius)
        rmin, rmax = scored_radii(radius)
        self.assertEqual((round(rmin), round(rmax)), (450, 550))
        expected = oracle.circle_final_score(rmin, rmax)
        self.assertEqual(expected, 159)
        self.assert_final_score(result, expected, "radius 450-550 m")

    @pytest.mark.xfail(
        strict=True,
        reason="F13 / S17: the direction is judged from the entry position and the position "
        "of the exit crossing only; a clockwise circle that leaves to the north "
        "looks counter-clockwise and scores the maximum (250)",
    )
    def test_a_circle_flown_clockwise_scores_zero(self):
        self.build()
        result = self.fly(radius=500.0, direction="right")
        expected = oracle.circle_final_score(500, 500, clockwise=True)
        self.assertEqual(expected, 0)
        self.assert_final_score(result, expected, "clockwise")

    @pytest.mark.xfail(
        strict=True,
        reason="F13 / S17: the direction is judged from the entry position and the position "
        "of the exit crossing only, so a left circle that leaves to the south is "
        "taken for a clockwise one and scores zero",
    )
    def test_a_left_circle_is_not_clockwise_whichever_way_it_leaves(self):
        self.build(exit_m=(0.0, -600.0))
        result = self.fly(radius=500.0, exit_m=(0.0, -600.0))
        expected = oracle.circle_final_score(500, 500)
        self.assertEqual(expected, 250)
        self.assert_final_score(result, expected, "left circle leaving to the south")

    @pytest.mark.xfail(
        strict=True,
        reason="F13 / S17: the radius limits are only checked at the exit crossing; a "
        "circle that bulges to 800 m on the south side and is back at 500 m when "
        "it leaves is not invalidated (59.8 points)",
    )
    def test_leaving_the_radius_limits_during_the_circle_scores_zero(self):
        self.build()

        def radius(angle):
            return 800.0 if 240.0 <= angle <= 300.0 else 500.0

        result = self.fly(radius=radius)
        rmin, rmax = scored_radii(radius)
        self.assertEqual((rmin, rmax), (500.0, 800.0))
        expected = oracle.circle_final_score(rmin, rmax)
        self.assertEqual(expected, 0)
        self.assert_final_score(result, expected, "radius up to 800 m")

    def test_a_ratio_of_rmin_to_rmax_below_one_half_scores_zero(self):
        self.build()

        def radius(angle):
            return 700.0 - 400.0 * (angle - 180.0) / 360.0 if 180.0 <= angle <= 540.0 else 700.0

        result = self.fly(radius=radius)
        rmin, rmax = scored_radii(radius)
        self.assertLess(rmin / rmax, 0.5)
        expected = oracle.circle_final_score(rmin, rmax)
        self.assertEqual(expected, 0)
        self.assert_final_score(result, expected, "radius 700 m to 300 m")

    @pytest.mark.xfail(
        strict=True,
        reason="S9: the 100% penalty is charged as 250 points per violation found (entry "
        "line, then a false clockwise at the exit), so the score is -250; the "
        "catalogue scores zero (no negative score)",
    )
    def test_start_and_centre_not_overflown_scores_zero(self):
        self.build()
        # The circle is flown around a point 400 m north of CM: the straight run from SP does not pass CM.
        offset_centre = local_point(CENTRE, 0.0, -400.0)
        track = circle_flight(
            local_point(offset_centre, -1000.0, 0.0),
            offset_centre,
            point(EXIT_NORTH),
            start_time=self.task.gate_times["SP"],
            sweep_deg=540.0,
            radius_m=500.0,
        )
        result = self.task.run(track)
        expected = oracle.circle_final_score(500, 500, start_and_centre_overflown=False)
        self.assertEqual(expected, 0)
        self.assert_final_score(result, expected, "run 400 m beside CM")

    def test_an_altitude_band_kept_costs_nothing_and_exceeded_costs_twenty_percent_of_the_score(self):
        task = self.build()
        flat = self.task.run(self.circle(radius_m=500.0, altitude=FLAT))
        within = self.task.run(self.circle(radius_m=500.0, altitude=wavy_altitude(task, BAND_KEPT_AMPLITUDE)))
        exceeded = self.task.run(self.circle(radius_m=500.0, altitude=wavy_altitude(task, BAND_EXCEEDED_AMPLITUDE)))
        self.assertEqual(within.score, flat.score)
        self.assertAlmostEqual(exceeded.score, 0.8 * flat.score, delta=0.2)

    @pytest.mark.xfail(
        strict=True,
        reason="F12 / S17: the circle of a correct flight scores 239.7 instead of 250 "
        "(see the constant-radius scenario), so with the altitude penalty the "
        "application gives 191.8 and the catalogue 200",
    )
    def test_an_altitude_band_exceeded_costs_twenty_percent(self):
        task = self.build()
        result = self.fly(radius=500.0, altitude=wavy_altitude(task, BAND_EXCEEDED_AMPLITUDE))
        expected = oracle.circle_final_score(500, 500, altitude_spread_ft=2 * BAND_EXCEEDED_AMPLITUDE)
        self.assertEqual(expected, 200)
        self.assert_final_score(result, expected, "300 ft spread")

    @pytest.mark.xfail(
        strict=True,
        reason="S9 and F12 / S17: the scores are not whole numbers (159.1 against 159) and "
        "the constant circle scores 239.7 instead of 250",
    )
    def test_the_score_is_absolute_and_not_divided_by_the_best_pilot(self):
        task = self.build()
        second = add_contestant(task)

        def radius(angle):
            return 500.0 + 50.0 * math.cos(math.radians(angle))

        first_result = task.run(self.circle(task, radius_m=radius))
        second_result = second.run(self.circle(second, radius_m=500.0))
        rmin, rmax = scored_radii(radius)
        expected = (oracle.circle_final_score(rmin, rmax), oracle.circle_final_score(500, 500))
        self.assertEqual(expected, (159, 250))
        self.assertEqual((first_result.score, second_result.score), expected)
