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

from display.utilities.gate_definitions import DUMMY, LANDING_GATE, TAKEOFF_GATE
from display.utilities.task_types import AIRSPORTS, AIRSPORT_CHALLENGE, ANR_CORRIDOR, POKER, PRECISION, find_task_type

if typing.TYPE_CHECKING:
    from display.models import NavigationTask

# The task types without a backbone (TaskTypeDefinition.has_backbone) get an empty placeholder Route - their real
# waypoint types are only materialised per-contestant by ContestantTaskCompiler, never on the shared Route, so they
# can't be derived from route data at all. TaskTypeDefinition.gate_types_without_backbone stands in for them. Best
# available reading of each task type's scoring path (contestant_task_compiler.py):
#   - circle: circle_start/entry/exit become scored gates; circle_center never does (no
#     scorecard entry is ever read for it, gate_calculator.py:42-47).
#   - turnpoint hunts: every runtime waypoint is synthesized as "tp" (contestant_task_compiler.py).
#   - duration: best-effort guess from the "speed-inferred fallback" in its pipeline - flag to confirm once seen in the
#     UI, low-risk either way since this only affects which gate editor is offered, not scoring itself.


def get_applicable_gate_types(navigation_task: "NavigationTask") -> set[str]:
    """
    The set of gate-type codes (see utilities/gate_definitions.py) that actually matter for
    this navigation task - i.e. the ones a calculator will actually look up a GateScore for.
    """
    task_type = find_task_type(navigation_task.effective_task_subtype)
    if task_type is not None and task_type.gate_types_without_backbone:
        return set(task_type.gate_types_without_backbone)

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
# the real pipeline (TaskTypeDefinition.calculator_pipeline) and each calculator's own task type gating,
# not guessed:
#
# - Backtracking -> BacktrackingAndProcedureTurnsCalculator: in the PRECISION pipeline for
#   every task type except circle (which has none), and always in
#   the ANR-style (ANR_CORRIDOR/AIRSPORTS/AIRSPORT_CHALLENGE) pipeline. Never for LANDING/POKER.
# - Zones (prohibited + penalty) -> ProhibitedZoneCalculator/PenaltyZoneCalculator: in both the
#   PRECISION and ANR-style pipelines unconditionally (every task type), and in the POKER pipeline. Never for LANDING
#   (its pipeline is LandingPatternCalculator alone).
# - Corridor -> AnrCorridorCalculator: only the ANR-style pipeline.
# - ANR route -> AnrCorridorCalculator._check_auxiliary_route_compliance, explicitly gated on
#   `has_auxiliary_route_checks` (calculators/anr_corridor_calculator.py) - not legacy ANR
#   corridor, not AIRSPORTS/AIRSPORT_CHALLENGE despite sharing the same calculator.
# - Duration -> DurationCalculator (task types with `scores_duration` only) plus GateCalculator's
#   turnpoint-hunt-specific scoring methods, each individually gated on
#   `scores_turnpoint_hunt_targets`
#   (calculators/gate_calculator.py: _score_turnpoint_hunt_maximum_duration,
#   _score_limited_fuel_deadline, _score_turnpoint_hunt_compulsory_timing).
# - Circle -> CircleCalculator: task types with `scores_circle` only.
# - Observation photos -> services/photo_observations.py (scored when the crew registers an observation, and for
#   unregistered ones when the flight ends): legacy precision uses the penalty, 2.A4/2.A5 the value.
# - Speed keeping -> GateCalculator._score_speed_keeping, gated on
#   `scores_speed_keeping` only (calculators/gate_calculator.py).
GENERAL = "General"
BACKTRACKING = "Backtracking"
ZONES = "Zones"
CORRIDOR = "Corridor"
ANR_ROUTE = "ANR route"
DURATION_GROUP = "Duration"
CIRCLE_GROUP = "Circle"
SPEED_KEEPING = "Speed keeping"
OBSERVATION_PHOTOS = "Observation photos"


def get_applicable_scalar_groups(navigation_task: "NavigationTask") -> set[str]:
    """
    The set of SCALAR_FIELD_GROUPS card titles that actually matter for this navigation task -
    i.e. the ones some calculator in its pipeline actually reads a value from.

    GENERAL (initial_score / score_sorting_direction) is unconditional: every task type has a
    Scorecard with a starting score and a sort direction, unlike the calculator-specific groups
    below which only matter for the subset of task types their calculator actually runs for.
    """
    family = navigation_task.coarse_task_family
    task_type = find_task_type(navigation_task.effective_task_subtype)

    if family == PRECISION:
        groups = {GENERAL, ZONES}
        if task_type is None or task_type.has_backtracking_detection:
            groups.add(BACKTRACKING)
        if task_type is not None:
            if task_type.scores_circle:
                groups.add(CIRCLE_GROUP)
            elif task_type.scores_duration or task_type.scores_turnpoint_hunt_targets:
                groups.add(DURATION_GROUP)
            elif task_type.scores_speed_keeping:
                groups.add(SPEED_KEEPING)
            # Observation photos are scored for legacy precision (penalty) and 2.A4/2.A5 (value) - see
            # services/photo_observations.py
            if task_type.is_legacy or task_type.observation_photos_award_points:
                groups.add(OBSERVATION_PHOTOS)
        return groups

    if family in (ANR_CORRIDOR, AIRSPORTS, AIRSPORT_CHALLENGE):
        groups = {GENERAL, BACKTRACKING, ZONES, CORRIDOR}
        if task_type is not None and task_type.has_auxiliary_route_checks:
            groups.add(ANR_ROUTE)
        return groups

    if family == POKER:
        return {GENERAL, ZONES}

    # LANDING (LandingPatternCalculator alone) and anything else unrecognised: no
    # calculator-specific scalar group applies, but General still does.
    return {GENERAL}
