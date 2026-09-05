"""
Which gate types - and which scalar scorecard field groups - actually matter for a given
navigation task.

`Scorecard.gate_scores()` (models/scorecard_and_gate_score.py) returns every gate type the
scorecard happens to have configured (8-16 of them), unfiltered by task - a precision
scorecard configures `dummy`/`ul` even though a precision task never uses them, and every
default scorecard configures all 16 types identically for the Poker Run calculator. There was
previously no way to ask "which of these does THIS task actually score against" - this module
answers that, for Scorecard Phase 3's organizer-facing scorecard editor (only show/edit gate
types relevant to the task at hand).

The source of truth is deliberately the same one scoring itself uses: a task's route
waypoints (`NavigationTask.route.waypoints`) plus its `takeoff_gates`/`landing_gates`, mirrored
against `GateCalculator`'s own scored-gate filter (calculators/gate_calculator.py:87-98) - not
a hand-authored task-type -> gate-type table, which would drift out of sync with the actual
calculators as task types evolve.

Four "no backbone" task subtypes (see NO_BACKBONE_TASK_SUBTYPES) get an empty placeholder
Route with no waypoints and no takeoff/landing gates at all - their real gate types only exist
per-contestant, synthesized at compile time (ContestantTaskCompiler). For those, a small static
table stands in.
"""

from __future__ import annotations

import typing

from display.utilities.cima_task_type_definitions import (
    ANR_CATALOGUE,
    CIRCLE,
    DURATION,
    KNOWN_CIRCUIT,
    LIMITED_FUEL_TURNPOINT_HUNT,
    NO_BACKBONE_TASK_SUBTYPES,
    TURNPOINT_HUNT,
)
from display.utilities.gate_definitions import (
    CIRCLE_ENTRY,
    CIRCLE_EXIT,
    CIRCLE_START,
    DUMMY,
    LANDING_GATE,
    TAKEOFF_GATE,
    TURNPOINT,
)
from display.utilities.navigation_task_type_definitions import (
    AIRSPORT_CHALLENGE,
    AIRSPORTS,
    ANR_CORRIDOR,
    POKER,
    PRECISION,
)

if typing.TYPE_CHECKING:
    from display.models import NavigationTask

# The four NO_BACKBONE_TASK_SUBTYPES (see cima_task_type_definitions.py) get an empty
# placeholder Route (editable_route.py:744-750) - their real waypoint types are only
# materialised per-contestant by ContestantTaskCompiler, never on the shared Route, so they
# can't be derived from route data at all. Best-available reading of each subtype's scoring
# path (contestant_task_compiler.py):
#   - CIRCLE: circle_start/entry/exit become scored gates; circle_center never does (no
#     scorecard entry is ever read for it, gate_calculator.py:42-47).
#   - TURNPOINT_HUNT / LIMITED_FUEL_TURNPOINT_HUNT: every runtime waypoint is synthesized as
#     "tp" (contestant_task_compiler.py:1111,1155,1180).
#   - DURATION: best-effort guess from the "speed-inferred fallback" comment in
#     task_type_registry.py:90-97 - flag to confirm once seen in the UI, low-risk either way
#     since this only affects which gate editor is offered, not scoring itself.
NO_BACKBONE_GATE_TYPES: dict[str, frozenset[str]] = {
    CIRCLE: frozenset({CIRCLE_START, CIRCLE_ENTRY, CIRCLE_EXIT}),
    TURNPOINT_HUNT: frozenset({TURNPOINT}),
    LIMITED_FUEL_TURNPOINT_HUNT: frozenset({TURNPOINT}),
    DURATION: frozenset({TAKEOFF_GATE, LANDING_GATE}),
}

assert set(NO_BACKBONE_GATE_TYPES) == set(NO_BACKBONE_TASK_SUBTYPES)


def get_applicable_gate_types(navigation_task: "NavigationTask") -> set[str]:
    """
    The set of gate-type codes (see utilities/gate_definitions.py) that actually matter for
    this navigation task - i.e. the ones a calculator will actually look up a GateScore for.
    """
    subtype = navigation_task.effective_task_subtype
    if subtype in NO_BACKBONE_GATE_TYPES:
        return set(NO_BACKBONE_GATE_TYPES[subtype])

    route = navigation_task.route
    gate_types = {
        waypoint.type
        for waypoint in route.waypoints
        if waypoint.type != DUMMY and not getattr(waypoint, "on_curved_segment", False)
    }
    if route.takeoff_gates:
        gate_types.add(TAKEOFF_GATE)
    if route.landing_gates:
        gate_types.add(LANDING_GATE)
    return gate_types


# Scorecard.config's 26 scalar scoring fields are grouped into 7 UI cards (see
# react_vite/src/features/scorecard-editor/fieldMetadata.ts's SCALAR_FIELD_GROUPS, whose
# titles this set matches exactly - "Zones" merges the old separate "Prohibited zone"/"Penalty
# zone" cards, which were always applicable together anyway, see below). Which cards are worth
# showing for a given task depends on which calculators actually run for it - verified against
# the real pipeline (utilities/task_type_registry.py) and each calculator's own subtype gating,
# not guessed:
#
# - Backtracking -> BacktrackingAndProcedureTurnsCalculator: in the PRECISION pipeline for
#   every subtype except CIRCLE (removed, calculators/task_type_registry.py:88), and always in
#   the ANR-style (ANR_CORRIDOR/AIRSPORTS/AIRSPORT_CHALLENGE) pipeline. Never for LANDING/POKER.
# - Zones (prohibited + penalty) -> ProhibitedZoneCalculator/PenaltyZoneCalculator: in both the
#   PRECISION and ANR-style pipelines unconditionally (every subtype, since neither branch
#   removes them), and in the POKER pipeline. Never for LANDING (calculators/
#   task_type_registry.py:112-113, its pipeline is LandingPatternCalculator alone).
# - Corridor -> AnrCorridorCalculator: only the ANR-style pipeline.
# - ANR route -> AnrCorridorCalculator._check_auxiliary_route_compliance, explicitly gated on
#   `task_subtype == ANR_CATALOGUE` (calculators/anr_corridor_calculator.py) - not legacy ANR
#   corridor, not AIRSPORTS/AIRSPORT_CHALLENGE despite sharing the same calculator.
# - Duration -> DurationCalculator (subtype == DURATION only) plus GateCalculator's
#   turnpoint-hunt-specific scoring methods, each individually gated on
#   `subtype in ("turnpoint_hunt", "limited_fuel_turnpoint_hunt")`
#   (calculators/gate_calculator.py: _score_turnpoint_hunt_maximum_duration,
#   _score_limited_fuel_deadline, _score_turnpoint_hunt_compulsory_timing).
# - Circle -> CircleCalculator: subtype == CIRCLE only.
# - Speed keeping -> GateCalculator._score_speed_keeping, gated on
#   `subtype == "known_circuit"` only (calculators/gate_calculator.py:744-751).
GENERAL = "General"
BACKTRACKING = "Backtracking"
ZONES = "Zones"
CORRIDOR = "Corridor"
ANR_ROUTE = "ANR route"
DURATION_GROUP = "Duration"
CIRCLE_GROUP = "Circle"
SPEED_KEEPING = "Speed keeping"

_TURNPOINT_HUNT_SUBTYPES = (TURNPOINT_HUNT, LIMITED_FUEL_TURNPOINT_HUNT)


def get_applicable_scalar_groups(navigation_task: "NavigationTask") -> set[str]:
    """
    The set of SCALAR_FIELD_GROUPS card titles that actually matter for this navigation task -
    i.e. the ones some calculator in its pipeline actually reads a value from.

    GENERAL (initial_score / score_sorting_direction) is unconditional: every task type has a
    Scorecard with a starting score and a sort direction, unlike the calculator-specific groups
    below which only matter for the subset of task types their calculator actually runs for.
    """
    family = navigation_task.coarse_task_family
    subtype = navigation_task.effective_task_subtype

    if family == PRECISION:
        groups = {GENERAL, ZONES}
        if subtype != CIRCLE:
            groups.add(BACKTRACKING)
        if subtype == CIRCLE:
            groups.add(CIRCLE_GROUP)
        elif subtype == DURATION:
            groups.add(DURATION_GROUP)
        elif subtype in _TURNPOINT_HUNT_SUBTYPES:
            groups.add(DURATION_GROUP)
        elif subtype == KNOWN_CIRCUIT:
            groups.add(SPEED_KEEPING)
        return groups

    if family in (ANR_CORRIDOR, AIRSPORTS, AIRSPORT_CHALLENGE):
        groups = {GENERAL, BACKTRACKING, ZONES, CORRIDOR}
        if subtype == ANR_CATALOGUE:
            groups.add(ANR_ROUTE)
        return groups

    if family == POKER:
        return {GENERAL, ZONES}

    # LANDING (LandingPatternCalculator alone) and anything else unrecognised: no
    # calculator-specific scalar group applies, but General still does.
    return {GENERAL}
