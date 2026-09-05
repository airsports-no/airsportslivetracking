"""
The CIMA task catalogue's actual scoring formula for 2.A1/2.A2 is NOT "start at a fixed 1000
and subtract raw penalty points" (that was the deliberately-simplified interim step landed in
"Implement CIMA 'start at max, subtract penalties' scoring foundation") - it is a normalization:

    Q = <achieved combination of hidden-gate hits and time-gate accuracy>
    Qmax = <the worst possible Q for THIS task's specific configuration>
    P = 1000 * Q / Qmax

(documentation/cima/cima_task_catalog.md, 2.A1 "CURVE NAVIGATION WITH TIME ESTIMATION" and 2.A2
"PRECISION NAVIGATION"). The catalogue is explicit that Qmax scales with however many gates the
organizer places (Qh = 1000 * H / Nh) and however harsh their briefed error tolerances are (Qt's
Emax) - it is NOT a fixed constant across every task instance. The flat "1000 minus raw penalty"
approximation silently assumed every task's penalty units already lived on the same 0-1000 scale,
which is only true by coincidence: a route with more gates (larger Qmax) should let the same
absolute penalty cost proportionally less, exactly the comparability-across-configurations
property Qmax normalization exists to provide.

The catalogue's own fixed numbers (Emax=180s, 180 points/hidden gate, etc.) are themselves
described as briefed-per-competition examples ("the specific scoring for markers, turn points
etc to be used in the competition will be briefed prior to the task being flown" -
cima_task_catalog.md 1.3), which maps directly onto this platform's existing per-gate-type
scorecard configuration (GateScoreValue.missed_penalty/maximum_penalty, already organizer-
editable via the scorecard editor). So rather than hardcoding the catalogue's example constants,
Qmax is computed from whatever the organizer has actually configured: the worst-case deficit is
the sum, over every gate actually on the route, of that gate type's worst possible single-gate
outcome - missed entirely (missed_penalty) or crossed so far outside tolerance it hits the
timing cap (maximum_penalty), whichever this scorecard configures as worse.

Deliberately NOT included in Qmax (and therefore not part of the normalized ratio - handled by
the existing flat per-event subtraction instead, unchanged from before this module existed):
- Backtracking / procedure-turn penalties: the catalogue treats backtracking as a separate flat
  penalty layered on top of the Q/Qmax result ("A 50% penalty will be imposed for backtracking",
  cima_task_catalog.md's 2.A1 Comments - a flat deduction, not a term inside Q), and procedure
  turns aren't mentioned in the 2.A1/2.A2 formula at all. Both also use `..._maximum_penalty`
  scorecard fields that default to -1 ("unbounded" - see corridor_maximum_penalty's identical
  sentinel, fixed in task_information.py this same session), which cannot contribute a finite
  term to a maximum-possible-deficit sum, unlike GATE_SCORE_TYPE gates - takeoff_and_landing_gate
  and every other gate crossing is scored per-gate-instance with its own always-finite cap.
- Every other CIMA subtype (2.A3-2.A8, 2.B2, 2.B3): each has either a different formula shape
  (2.A6/2.B2's is additive and route-dependent, not a ratio - see
  cima_task_type_definitions.py's CIMA_SCORING_BASELINE docstring) or hasn't had its gate-vs-
  achievement semantics confirmed yet. Extending get_cima_gate_qmax to a new subtype requires
  confirming its calculator(s) only ever emit GATE_SCORE_TYPE deficits in the same way
  gate_calculator.py does for 2.A1/2.A2 - do not just add a subtype to _QMAX_ELIGIBLE_SUBTYPES
  without checking that first.
"""

from __future__ import annotations

import typing

from display.utilities.cima_task_type_definitions import (
    CURVE_NAVIGATION_TIME_ESTIMATION,
    PRECISION_NAVIGATION,
)
from display.utilities.gate_definitions import DUMMY, LANDING_GATE, TAKEOFF_GATE

if typing.TYPE_CHECKING:
    from display.models import NavigationTask

# See this module's docstring for why only these two subtypes, and why not e.g. 2.A6/2.B2.
_QMAX_ELIGIBLE_SUBTYPES = frozenset({CURVE_NAVIGATION_TIME_ESTIMATION, PRECISION_NAVIGATION})


def _worst_case_single_gate_penalty(scorecard, gate_type: str) -> float:
    gate_score = scorecard.get_gate_scorecard(gate_type)
    return max(abs(gate_score.missed_penalty), abs(gate_score.maximum_penalty))


def get_cima_gate_qmax(navigation_task: "NavigationTask") -> float | None:
    """
    The worst-case total GATE_SCORE_TYPE deficit achievable on this task's specific route with
    its specific scorecard configuration - i.e. Qmax for the catalogue's P = 1000 * Q / Qmax
    formula, restricted to the gate-crossing component of Q (see module docstring for what's
    excluded and why). Returns None for any subtype this normalization doesn't apply to yet, or
    for a route with no scored gates at all (a task that can't be normalized this way, e.g. one
    with a mistakenly-empty route - callers should treat None as "leave the score as-is", the
    same convention used by cima_task_type_definitions.get_cima_scoring_baseline).
    """
    if navigation_task.effective_task_subtype not in _QMAX_ELIGIBLE_SUBTYPES:
        return None

    scorecard = navigation_task.scorecard
    route = navigation_task.route
    total = 0.0
    for waypoint in route.waypoints:
        if waypoint.type == DUMMY or getattr(waypoint, "on_curved_segment", False):
            continue
        total += _worst_case_single_gate_penalty(scorecard, waypoint.type)
    if route.takeoff_gates:
        total += _worst_case_single_gate_penalty(scorecard, TAKEOFF_GATE)
    if route.landing_gates:
        total += _worst_case_single_gate_penalty(scorecard, LANDING_GATE)

    return total if total > 0 else None
