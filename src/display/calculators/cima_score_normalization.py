"""
The CIMA task catalogue's actual scoring formula for 2.A1-2.A5 is NOT "start at a fixed 1000
and subtract raw penalty points" (that was the deliberately-simplified interim step landed in
"Implement CIMA 'start at max, subtract penalties' scoring foundation") - it is a normalization:

    Q = <achieved combination of hidden-gate hits and time-gate accuracy>
    Qmax = <the worst possible Q for THIS task's specific configuration>
    P = 1000 * Q / Qmax

(documentation/cima/cima_task_catalog.md - 2.A1 "CURVE NAVIGATION WITH TIME ESTIMATION", 2.A2
"PRECISION NAVIGATION", 2.A3 "CONTRACT NAVIGATION WITH TIME CONTROLS", 2.A4 "NAVIGATION OVER A
KNOWN CIRCUIT", 2.A5 "NAVIGATION WITH UNKNOWN LEGS" all share this Q/Qmax shape, just with
different named components inside Q). The catalogue is explicit that Qmax scales with however
many gates the organizer places and however harsh their briefed error tolerances are - it is NOT
a fixed constant across every task instance. The flat "1000 minus raw penalty" approximation
silently assumed every task's penalty units already lived on the same 0-1000 scale, which is
only true by coincidence: a route with more gates (larger Qmax) should let the same absolute
penalty cost proportionally less, exactly the comparability-across-configurations property Qmax
normalization exists to provide.

The catalogue's own fixed numbers (Emax=180s, 180 points/hidden gate, etc.) are themselves
described as briefed-per-competition examples ("the specific scoring for markers, turn points
etc to be used in the competition will be briefed prior to the task being flown" -
cima_task_catalog.md 1.3), which maps directly onto this platform's existing per-gate-type
scorecard configuration (GateScoreValue.missed_penalty/maximum_penalty, already organizer-
editable via the scorecard editor). So rather than hardcoding the catalogue's example constants,
Qmax is computed from whatever the organizer has actually configured: the worst-case deficit is
the sum, over every gate that can ACTUALLY be scored for this contestant, of that gate's worst
possible single-gate outcome.

"Actually be scored" is doing real work here, and is why this takes a Contestant, not a bare
NavigationTask:

- Per-CONTESTANT effective route, not the shared task route. 2.A3 (and any other
  requires_contestant_configuration subtype) lets each contestant declare their OWN subset/order
  of the organizer's full catalogue-turnpoint route - gate_calculator.py's own create_gates()
  builds its scored-gate list from get_effective_route_waypoints(navigation_task, contestant),
  not navigation_task.route.waypoints directly, for exactly this reason. Using the shared route
  here would inflate Qmax with catalogue points THIS contestant never declared (and which
  therefore can never generate a scoring event for them), making their displayed score
  understate real performance. For subtypes with no per-contestant declaration (2.A1/2.A2),
  get_effective_route_waypoints transparently falls back to the shared route, so this is a
  strict generalization, not a behavior change for them.
- gate_check / time_check gate real scoring, not gate TYPE. Every non-dummy/non-curved waypoint
  becomes a Gate object (create_gates() has no gate_check filter at all), but a missed gate only
  actually produces a penalty if gate.gate_check is True (on_gate_missed's `if event.gate.
  gate_check:` guard), and a crossed gate only gets a non-zero timing penalty if it has an
  expected_time at all, i.e. gate.time_check is True (on_gate_passed's `if event.gate.
  expected_time: ... else: ...score 0...`). A waypoint with BOTH flags off can never contribute
  any deficit under any circumstance, so counting its missed_penalty/maximum_penalty toward Qmax
  would inflate the ceiling for a scenario that can't happen - see _worst_case_penalty.
  Takeoff/landing gates are a further special case:
  takeoff_and_landing_gate_calculator.py has no "missed" scoring path at all (no
  on_takeoff_missed/on_landing_missed), so missed_penalty can never apply there regardless of
  gate_check - only the timing cap (maximum_penalty) is a reachable worst case.

Deliberately NOT included in Qmax (and therefore not part of the normalized ratio - handled by
the existing flat per-event subtraction instead, unchanged from before this module existed):
- Backtracking / procedure-turn penalties: the catalogue treats backtracking as a separate flat
  penalty layered on top of the Q/Qmax result ("A 50% penalty will be imposed for backtracking",
  cima_task_catalog.md's 2.A1 Comments - a flat deduction, not a term inside Q), and procedure
  turns aren't mentioned in any of 2.A1-2.A5's formulas. Both also use `..._maximum_penalty`
  scorecard fields that default to -1 ("unbounded" - see corridor_maximum_penalty's identical
  sentinel, fixed in task_information.py this same session), which cannot contribute a finite
  term to a maximum-possible-deficit sum.
- Speed-keeping (2.A4's Qv term): GateCalculator._score_speed_keeping scores under its own
  "speed_keeping" score_type (not GATE_SCORE_TYPE) with an uncapped per-kt penalty - excluded
  from Qmax for the same "not a finite reachable cap" reason as backtracking, and it keeps
  accumulating via the untouched flat-subtraction path in update_score_from_thread.
- Observation evidence (2.A4/2.A5's Qh photo/marker-placement component, and 2.A3/2.A6's
  "observation_evidence" scoring_module generally): cima_task_type_definitions.py declares this
  as a scoring_module name, but no calculator implementing it exists anywhere in the codebase -
  it is a documented future feature, not something Qmax needs to (or can) account for yet. What
  Qmax DOES cover for 2.A4/2.A5 is the hidden-gate-crossing component only (real secret-point
  gates authored on the route, scored the same GATE_SCORE_TYPE way as 2.A1/2.A2's hidden gates).
- Every other CIMA subtype (2.A6-2.A8, 2.B2, 2.B3): each has either a different formula shape
  (2.A6/2.B2's is additive and route-dependent, not a ratio - see
  cima_task_type_definitions.py's CIMA_SCORING_BASELINE docstring) or hasn't had its gate-vs-
  achievement semantics confirmed yet. Extending get_cima_gate_qmax to a new subtype requires
  confirming its calculator(s) only ever emit GATE_SCORE_TYPE deficits the same way
  gate_calculator.py does for 2.A1-2.A5 - do not just add a subtype to _QMAX_ELIGIBLE_SUBTYPES
  without checking that first.
"""

from __future__ import annotations

import typing

from display.flight_order_and_maps.effective_route_rendering import get_effective_route_waypoints
from display.utilities.cima_task_type_definitions import (
    CONTRACT_NAVIGATION_TIME_CONTROLS,
    CURVE_NAVIGATION_TIME_ESTIMATION,
    KNOWN_CIRCUIT,
    PRECISION_NAVIGATION,
    UNKNOWN_LEGS,
)
from display.utilities.gate_definitions import DUMMY, LANDING_GATE, TAKEOFF_GATE

if typing.TYPE_CHECKING:
    from display.models import Contestant

# See this module's docstring for why only these five, and why not e.g. 2.A6/2.B2.
_QMAX_ELIGIBLE_SUBTYPES = frozenset(
    {
        CURVE_NAVIGATION_TIME_ESTIMATION,
        PRECISION_NAVIGATION,
        CONTRACT_NAVIGATION_TIME_CONTROLS,
        KNOWN_CIRCUIT,
        UNKNOWN_LEGS,
    }
)


def _worst_case_penalty(scorecard, gate_type: str, *, gate_check: bool, time_check: bool) -> float:
    """
    The worst single-gate deficit that can ACTUALLY be scored for a gate with these check flags
    - see module docstring's "gate_check / time_check gate real scoring" section. A gate with
    neither flag set contributes 0: it can be missed without penalty (gate_check False) and
    crossed without penalty (time_check False, so on_gate_passed's "no time check" branch scores
    0 regardless of when it's crossed).
    """
    gate_score = scorecard.get_gate_scorecard(gate_type)
    worst_if_missed = abs(gate_score.missed_penalty) if gate_check else 0
    worst_if_crossed_badly = abs(gate_score.maximum_penalty) if time_check else 0
    return max(worst_if_missed, worst_if_crossed_badly)


def get_cima_gate_qmax(contestant: "Contestant") -> float | None:
    """
    The worst-case total GATE_SCORE_TYPE deficit achievable for this contestant's specific
    EFFECTIVE route (see module docstring - this may be a per-contestant declared subset of the
    task's shared route) with this task's scorecard configuration - i.e. Qmax for the
    catalogue's P = 1000 * Q / Qmax formula, restricted to the gate-crossing component of Q (see
    module docstring for what's excluded and why). Returns None for any subtype this
    normalization doesn't apply to yet, or for an effective route with no scoreable gates at all
    (e.g. every waypoint has both check flags off, or a mistakenly-empty route) - callers should
    treat None as "leave the score as-is", the same convention used by
    cima_task_type_definitions.get_cima_scoring_baseline.
    """
    navigation_task = contestant.navigation_task
    if navigation_task.effective_task_subtype not in _QMAX_ELIGIBLE_SUBTYPES:
        return None

    scorecard = navigation_task.scorecard
    waypoints = get_effective_route_waypoints(navigation_task, contestant)
    total = 0.0
    for waypoint in waypoints:
        if waypoint.type == DUMMY or getattr(waypoint, "on_curved_segment", False):
            continue
        total += _worst_case_penalty(
            scorecard,
            waypoint.type,
            gate_check=bool(getattr(waypoint, "gate_check", False)),
            time_check=bool(getattr(waypoint, "time_check", False)),
        )

    route = navigation_task.route
    # No on_takeoff_missed/on_landing_missed exists (see module docstring) - only a reachable
    # timing cap, never the missed_penalty.
    if route.takeoff_gates:
        total += _worst_case_penalty(scorecard, TAKEOFF_GATE, gate_check=False, time_check=True)
    if route.landing_gates:
        total += _worst_case_penalty(scorecard, LANDING_GATE, gate_check=False, time_check=True)

    return total if total > 0 else None
