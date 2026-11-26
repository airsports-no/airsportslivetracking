"""Shared helpers for the CIMA scenario tests (test_simulated_cima_*.py).

The scenario tests build a CIMA task, fly a simulated track and compare the application's final score with the one the
catalogue oracle (catalogue_oracle.py) gives for what was flown. What was flown is read from the track's geometry here,
independently of the calculators: which gate lines were crossed, in which direction, and how many seconds after the
gate's expected time.
"""

from typing import Optional, Sequence

from django.test import TestCase

from display.calculators.tests import catalogue_oracle as oracle
from display.calculators.tests.flight_simulator import Crossing
from display.utilities.navigation_task_type_definitions import PRECISION

# Hidden gates on the standard route (SP 6000 m east, TP1 5000 m south-east, TP2 6000 m east, FP): two on each of the
# last two legs, none on the first, which is left clear for backtracking scenarios (backtracking is ignored close to a
# gate).
HIDDEN_GATES = {1: [0.35, 0.65], 2: [0.3, 0.7]}
BACKTRACKING_LEG = "SP"
HIDDEN_NAMES = ["HG1", "HG2", "HG3", "HG4"]
# A brief loop (about three seconds against the route) that crosses a hidden gate twice or against the route. It is
# shorter than the five seconds that make backtracking, so the scenarios that use it test the invalidation of the gate
# only; backtracking has scenarios of its own.
BRIEF_LOOP = {"distance_m": 60.0, "margin_m": 100.0}
BRIEF_LOOP_GAP_S = 19.0
LONG_BACKTRACKING_GRACE_S = 60


def allow_brief_backtracking(scorecard):
    """Raise the backtracking grace time so that the brief loops of the hidden-gate scenarios cannot be mistaken for
    backtracking, whatever the application's own bearing smoothing makes of them."""
    scorecard.backtracking_grace_time_seconds = LONG_BACKTRACKING_GRACE_S


def hidden_crossing_sequence(crossings: dict[str, list[Crossing]], names: Sequence[str]) -> list[tuple[int, int]]:
    """(gate number, direction) of every crossing of the hidden gates `names`, in the order they happened."""
    events = sorted((c.time, names.index(name), c.direction) for name in names for c in crossings.get(name, []))
    return [(number, direction) for _, number, direction in events]


def measured_error(crossing: Crossing) -> int:
    """The error in seconds as the system measures it: crossings are timed to the whole second (the resolution of
    the position reports and of the gate times), so a crossing 35.9 s late is 36 s late."""
    microseconds = crossing.time.microsecond
    to_whole_second = (1_000_000 - microseconds if microseconds >= 500_000 else -microseconds) / 1_000_000
    return round(crossing.error_s + to_whole_second)


def first_crossing_errors(crossings: dict[str, list[Crossing]], names: Sequence[str]) -> list[Optional[float]]:
    """The timing error of each gate from its first crossing (in any direction), None for a gate never crossed."""
    return [measured_error(crossings[name][0]) if crossings.get(name) else None for name in names]


def correct_gate_count(crossings: dict[str, list[Crossing]], names: Sequence[str]) -> int:
    """H of the catalogue: the hidden gates crossed once, in order and in the proper direction."""
    return len(oracle.correct_hidden_gates(hidden_crossing_sequence(crossings, names)))


class CimaScenarioCase(TestCase):
    """Base of the scenario test cases: builds nothing itself, but knows how to compare with the oracle."""

    task_type = PRECISION

    def assert_final_score(self, result, expected: float, what: str = ""):
        """The application's final score of the flight is the catalogue's."""
        penalties = [(m.gate.name, m.score_type, float(m.score)) for m in result.messages if m.score]
        self.assertEqual(
            result.score,
            expected,
            f"{what}: the application scored {result.score:.2f}, the catalogue gives {expected} "
            f"(application penalties: {penalties})",
        )

    @staticmethod
    def final_against_reference(q: float, reference_q: float, percentage_penalties: Sequence[float] = ()) -> int:
        """The catalogue's P of a pilot with quality `q` in a task whose best pilot scored `reference_q`."""
        qs = [reference_q, q]
        return oracle.final_scores(qs, [(), tuple(percentage_penalties)])[1]
