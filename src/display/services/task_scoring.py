"""
The quality scoring model: the task score P of every contestant of a navigation task, from raw quality scores.

FAI Section 10 and Annex 3 give a pilot a raw score Q in a task and publish P = task_value x Q / Qmax, where Qmax is the
best Q of the task (all contestants of a task are one class) and task_value is announced per task (1000 by default,
500 to 1500 allowed). Percentage penalties (50% for backtracking, 20% for the altitude band, 100% for a quarantine
breach, ...) are deducted from P after scoring is complete, several add up (at most 100%), a negative task score becomes
zero, and the task score is a whole number with 0.5 rounded up. A pilot who did not fly scores zero.

Where the numbers live
- The score log (ScoreLogEntry) holds every event of a contestant. For a quality task `points` is the signed raw
  contribution to Q (a penalty is negative, an achievement positive); a percentage penalty is stored as its percentage.
- ContestantTrack caches what follows from the log: `raw_quality` (Q = the starting quality plus the contributions),
  `percentage_penalty`, `quality_breakdown` (contributions by score type) and the contestant's starting quality and
  theoretical maximum. They are always rebuilt from the log and the task type (`refresh_contestant_quality`), never
  incremented, so a calculator restart, a replayed event or a deleted log entry cannot make them drift.
- Some terms of Q are a share of the best contestant of the task (2.A3 Qp = 1000 x V / Vmax, 2.A4 Qv = Vs x S /
  Smax; see RelativeQualityTerm). For those the log holds the contestant's measure (V, S), not points; the points are
  value x measure / best measure, derived for every contestant of the task each time (`_apply_relative_terms`), so
  they follow every other contestant's result and are stored in the breakdown as points of Q like everything else.
- ContestantTrack.score holds P. It is written by `recompute_task_scores` only (for a quality task).

The per-task policy (Scorecard.config scoring_model, qmax_policy, task_value; the task type's registry entry supplies
the defaults) says what Q is divided by: the best Q of the task, the contestant's own theoretical maximum, or an
absolute scale (2.A7: P = Q; 2.A8: P = task_value x Q / 2000). Tasks of the penalty model are not touched by any of
this: the processor keeps adding penalties to the track's score as it always did.

Concurrency: contestants are scored by separate worker processes, and a change of one Q changes the P of the others.
`recompute_task_scores` therefore locks the ContestantTrack rows of the task (in primary key order, so two recomputations
queue instead of deadlocking) in one short transaction, rebuilds the Q of the contestants it was asked to refresh from
the log, derives every P from the stored values and writes only the P that changed. It is idempotent: running it again
(or two of them one after the other) gives the same result, whoever ran last sees every committed log entry.
"""

import logging
import math
from dataclasses import dataclass
from typing import Iterable, Optional, Sequence

from django.db import transaction

from display.flight_order_and_maps.effective_route_rendering import get_effective_route_waypoints
from display.services.catalogue_gate_quality import CatalogueGateQuality
from display.utilities.db_retry import retry_on_lock_timeout
from display.utilities.gate_definitions import DUMMY, LANDING_GATE, TAKEOFF_GATE
from display.utilities.task_types import (
    DEFAULT_TASK_VALUE,
    MAX_TASK_VALUE,
    MIN_TASK_VALUE,
    QMAX_ABSOLUTE,
    QMAX_POLICIES,
    QMAX_THEORETICAL,
    QUALITY_START_FIXED,
    QUALITY_START_GATE_DEFICIT,
    SCORING_MODELS,
    SCORING_PENALTIES,
    SCORING_QUALITY,
    TaskTypeDefinition,
    stored_task_type,
)

logger = logging.getLogger(__name__)

# The score type under which a log entry without one is listed in the breakdown.
UNTYPED_SCORE_TYPE = "other"
# Rounding noise below this does not decide which way a half is rounded.
_ROUNDING_DIGITS = 9


# ---------------------------------------------------------------------------------------------------------------------
# The policy of a task
# ---------------------------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class ScoringParameters:
    """How the score of a task is made: the scorecard's values, with the task type's defaults where it stores none."""

    model: str
    qmax_policy: str
    task_value: float
    # Q divided by this is the absolute scale of QMAX_ABSOLUTE; None: P = Q.
    absolute_reference: Optional[float] = None

    @property
    def is_quality(self) -> bool:
        return self.model == SCORING_QUALITY


def scoring_parameters_for(scorecard, definition: TaskTypeDefinition) -> ScoringParameters:
    """
    The scoring parameters of a scorecard of a task of type `definition`. A scorecard that stores no scoring_model (a
    task created before the model existed) behaves as the task type does by default. Only a task type that has a
    quality score (a starting quality and its calculators' signed messages) can use the quality model.
    """
    stored_model = scorecard.config.get("scoring_model") if scorecard is not None else None
    model = stored_model or definition.scoring_model
    if model == SCORING_QUALITY and definition.scoring_model != SCORING_QUALITY:
        model = SCORING_PENALTIES
    stored_policy = scorecard.config.get("qmax_policy") if scorecard is not None else None
    policy = stored_policy if stored_policy in dict(QMAX_POLICIES) else definition.qmax_policy
    task_value = scorecard.config.get("task_value") if scorecard is not None else None
    return ScoringParameters(
        model=model if model in dict(SCORING_MODELS) else SCORING_PENALTIES,
        qmax_policy=policy,
        task_value=float(task_value) if task_value else DEFAULT_TASK_VALUE,
        absolute_reference=definition.absolute_reference,
    )


def backtracking_penalty_percentage_for(scorecard, definition: TaskTypeDefinition) -> float:
    """
    The percentage of the task score one backtrack costs, 0 where it costs the scorecard's flat points. Only a task type
    that has a percentage (2.A1-2.A5: 50) can use one. A scorecard that stores none (a task created before the setting
    existed) gets the task type's, like scoring_model; a stored 0 chooses the flat points.
    """
    if not definition.backtracking_penalty_percentage:
        return 0.0
    stored = scorecard.config.get("backtracking_penalty_percentage") if scorecard is not None else None
    percentage = definition.backtracking_penalty_percentage if stored is None else float(stored)
    return min(100.0, max(0.0, percentage))


def relative_term_values(scorecard, definition: TaskTypeDefinition) -> dict[str, float]:
    """
    What each relative term of the task type is worth for the best contestant of the task: the registry's value, or the
    scorecard's where the term names a scorecard field (Vs of the speed term, briefed per task). A term worth nothing
    is left out.
    """
    values = {}
    for term in definition.relative_quality_terms:
        value = term.value
        if term.scorecard_field and scorecard is not None:
            stored = scorecard.config.get(term.scorecard_field)
            value = float(stored) if stored is not None else term.value
        if value > 0:
            values[term.score_type] = value
    return values


def scoring_parameters(navigation_task) -> ScoringParameters:
    return scoring_parameters_for(navigation_task.scorecard, stored_task_type(navigation_task))


def is_quality_task(navigation_task) -> bool:
    return scoring_parameters(navigation_task).is_quality


def validate_task_value(task_value) -> Optional[str]:
    """The reason a task value of a quality task is not allowed (Annex 3, 2.3.4), or None."""
    try:
        value = float(task_value)
    except (TypeError, ValueError):
        return "The task value must be a number."
    if not MIN_TASK_VALUE <= value <= MAX_TASK_VALUE:
        return f"The task value must be between {MIN_TASK_VALUE:g} and {MAX_TASK_VALUE:g} points."
    return None


def initial_track_score(navigation_task) -> float:
    """What a contestant's track scores before anything has happened: zero (nobody flew) for a quality task."""
    if is_quality_task(navigation_task):
        return 0.0
    return navigation_task.scorecard.initial_score


def default_scorecard_values(definition: TaskTypeDefinition) -> dict:
    """The scoring values written into the scorecard copy of a new task of this type."""
    return {
        "scoring_model": definition.scoring_model,
        "qmax_policy": definition.qmax_policy,
        "task_value": DEFAULT_TASK_VALUE,
    }


# ---------------------------------------------------------------------------------------------------------------------
# Message kinds
# ---------------------------------------------------------------------------------------------------------------------


def signed_contribution(kind: str, magnitude: float, parameters: ScoringParameters, descending: bool) -> float:
    """
    The signed change of the score of a message of this kind with this magnitude. In the quality model a penalty
    reduces Q and an achievement adds to it. In the penalty model the sign follows the scorecard: on an ascending
    scorecard (lowest total wins) a penalty is added to the total and an achievement is deducted; on a descending one
    it is the other way around.
    A percentage penalty never changes the running score: it is a percentage of the final task score.
    """
    from display.calculators.update_score_message import ACHIEVEMENT, PENALTY, PERCENTAGE_PENALTY

    if kind == PERCENTAGE_PENALTY:
        return 0.0
    if kind not in (PENALTY, ACHIEVEMENT):
        raise ValueError(f"Unknown score message kind '{kind}'")
    improves = kind == ACHIEVEMENT
    if parameters.is_quality or descending:
        return magnitude if improves else -magnitude
    return -magnitude if improves else magnitude


# ---------------------------------------------------------------------------------------------------------------------
# The starting quality of a contestant
# ---------------------------------------------------------------------------------------------------------------------


def _worst_case_penalty(scorecard, gate_type: str, *, gate_check: bool, time_check: bool) -> float:
    """
    The worst single-gate deficit that can actually be scored for a gate with these check flags. A gate with neither
    flag set contributes 0: it can be missed without penalty (gate_check False) and crossed without penalty (time_check
    False, so a crossing scores 0 whenever it happens).
    """
    gate_score = scorecard.get_gate_scorecard(gate_type)
    worst_if_missed = abs(gate_score.missed_penalty) if gate_check else 0
    worst_if_crossed_badly = abs(gate_score.maximum_penalty) if time_check else 0
    return max(worst_if_missed, worst_if_crossed_badly)


def theoretical_gate_quality(contestant) -> float:
    """
    The starting quality of a deficit-style task (2.A1-2.A5): the worst possible total gate deficit (2.A1, 2.A2: what
    the catalogue's formulas make a perfect flight worth, see CatalogueGateQuality) of the
    contestant's own EFFECTIVE route (a contestant of 2.A3 flies a declared subset of the catalogue points, so the
    shared route would inflate it) with the scorecard's configuration, observation photos included. A pilot flying
    perfectly keeps all of it, and a pilot who loses every gate loses all of it.

    Only what can actually be scored counts: a waypoint with neither gate_check nor time_check can never cost points,
    and take-off and landing gates have no "missed" scoring, only their timing cap. Backtracking, procedure turns and
    speed keeping are not part of it: they have no finite cap and are deducted from Q as they happen.
    """
    navigation_task = contestant.navigation_task
    scorecard = navigation_task.scorecard
    total = 0.0
    waypoints = get_effective_route_waypoints(navigation_task, contestant)
    # 2.A1 and 2.A2 weigh the gates as the catalogue's formulas say, by the same object that makes the live deductions.
    catalogue = CatalogueGateQuality.for_task_type(stored_task_type(navigation_task), scorecard, waypoints)
    for waypoint in waypoints:
        if waypoint.type == DUMMY or getattr(waypoint, "on_curved_segment", False):
            continue
        if catalogue:
            total += catalogue.starting_quality(waypoint)
            continue
        total += _worst_case_penalty(
            scorecard,
            waypoint.type,
            gate_check=bool(getattr(waypoint, "gate_check", False)),
            time_check=bool(getattr(waypoint, "time_check", False)),
        )
    route = navigation_task.route
    if route.takeoff_gates:
        total += _worst_case_penalty(scorecard, TAKEOFF_GATE, gate_check=False, time_check=True)
    if route.landing_gates:
        total += _worst_case_penalty(scorecard, LANDING_GATE, gate_check=False, time_check=True)

    from display.services.photo_observations import get_cima_observation_qmax

    total += get_cima_observation_qmax(contestant)
    return total


def achievable_quality(contestant) -> float:
    """
    The theoretical maximum of an achievement-style task (2.A6, 2.B2): everything the contestant can earn, the target
    values of their own declared targets, the time gates and the scorecard's sequence bonus. 0 without a valid declaration.
    """
    config = getattr(contestant, "contestanttaskconfiguration", None)
    if config is None or not config.is_valid:
        return 0.0
    payload = config.compiled_effective_route_payload or {}
    scored_target_values = payload.get("scored_target_values") or {}
    total = sum(float(value) for value in scored_target_values.values())
    total += contestant.navigation_task.scorecard.turnpoint_hunt_sequence_bonus or 0
    # Every time gate crossed exactly on its declared time earns its value (200 each).
    total += len(payload.get("compulsory_timing_gate_names") or []) * (
        contestant.navigation_task.scorecard.turnpoint_hunt_time_gate_value or 0
    )
    return float(total)


def quality_baseline(contestant, definition: Optional[TaskTypeDefinition] = None) -> tuple[float, float]:
    """(the starting quality, the theoretical maximum quality) of a contestant of a quality task."""
    definition = definition or stored_task_type(contestant.navigation_task)
    if definition.quality_start == QUALITY_START_GATE_DEFICIT:
        quality = theoretical_gate_quality(contestant)
        # The best contestant of the task earns the whole of a relative term (2.A3: 1000 for V = Vmax).
        relative = sum(relative_term_values(contestant.navigation_task.scorecard, definition).values())
        return quality, quality + relative
    if definition.quality_start == QUALITY_START_FIXED:
        quality = float(definition.fixed_quality or 0)
        return quality, quality
    return 0.0, achievable_quality(contestant)


# ---------------------------------------------------------------------------------------------------------------------
# The task score from the raw values (pure)
# ---------------------------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class QualityEntry:
    """What the task score of one contestant is made from."""

    flown: bool
    raw_quality: float
    theoretical_maximum: float = 0.0
    percentage_penalty: float = 0.0


def round_half_up(value: float) -> int:
    """A whole number, 0.5 rounded up (not to even: 874.5 is 875, 875.5 is 876)."""
    return int(math.floor(round(value, _ROUNDING_DIGITS) + 0.5))


def best_quality(entries: Sequence[QualityEntry]) -> float:
    """Qmax of the best-in-task policy: the best Q of the contestants who flew (0 when nobody scored above it)."""
    return max((entry.raw_quality for entry in entries if entry.flown), default=0.0)


def compute_task_scores(parameters: ScoringParameters, entries: Sequence[QualityEntry]) -> list[int]:
    """
    P of every contestant: task_value x Q / Qmax (0 when Qmax is not positive), less the percentage penalties
    (together at most 100%), never below zero, as a whole number with 0.5 rounded up. A contestant who did not fly
    scores 0 and takes no part in Qmax.
    """
    best = best_quality(entries)
    scores = []
    for entry in entries:
        if not entry.flown:
            scores.append(0)
            continue
        if parameters.qmax_policy == QMAX_ABSOLUTE:
            reference = parameters.absolute_reference
            task_score = parameters.task_value * entry.raw_quality / reference if reference else entry.raw_quality
        else:
            qmax = entry.theoretical_maximum if parameters.qmax_policy == QMAX_THEORETICAL else best
            task_score = parameters.task_value * entry.raw_quality / qmax if qmax > 0 else 0.0
        penalty = min(100.0, max(0.0, entry.percentage_penalty)) / 100.0
        scores.append(max(0, round_half_up(task_score * (1.0 - penalty))))
    return scores


# ---------------------------------------------------------------------------------------------------------------------
# The stored raw values
# ---------------------------------------------------------------------------------------------------------------------


def summarise_score_log(rows: Iterable[tuple[str, str, float]]) -> tuple[float, float, dict[str, float]]:
    """(the sum of the contributions to Q, the percentage penalty, the contributions by score type) of
    (score_type, score_kind, points) log rows."""
    from display.calculators.update_score_message import PERCENTAGE_PENALTY

    contributions = 0.0
    percentage = 0.0
    breakdown: dict[str, float] = {}
    for score_type, score_kind, points in rows:
        if score_kind == PERCENTAGE_PENALTY:
            percentage += points
            continue
        contributions += points
        key = score_type or UNTYPED_SCORE_TYPE
        breakdown[key] = breakdown.get(key, 0.0) + points
    return contributions, percentage, breakdown


def _predates_quality_log(rows: Sequence[tuple[str, str, float]]) -> bool:
    """Whether the log has scoring entries made before entries carried a kind: their points are in other units."""
    return any(not score_kind and points for _, score_kind, points in rows)


def _rebuild_track(track, contestant, relative_types: frozenset = frozenset()) -> bool:
    """Rebuilds the raw values of `track` from the score log and the task type (the caller holds the lock on the track
    row); returns whether anything changed. A track whose log predates the quality model is left as it is. The log
    entries of the relative terms hold measures, not points: they are left out here, see _apply_relative_terms."""
    from display.models import ScoreLogEntry

    rows = list(ScoreLogEntry.objects.filter(contestant=contestant).values_list("score_type", "score_kind", "points"))
    if _predates_quality_log(rows):
        return False
    if track.quality_start is None or track.quality_theoretical_maximum is None:
        track.quality_start, track.quality_theoretical_maximum = quality_baseline(contestant)
    contributions, percentage, breakdown = summarise_score_log(rows)
    for score_type in relative_types:
        contributions -= breakdown.pop(score_type, 0.0)
    raw_quality = track.quality_start + contributions
    changed = (
        track.raw_quality != raw_quality
        or track.percentage_penalty != percentage
        or track.quality_breakdown != breakdown
    )
    track.raw_quality = raw_quality
    track.percentage_penalty = percentage
    track.quality_breakdown = breakdown
    track.save(
        update_fields=[
            "raw_quality",
            "quality_start",
            "quality_theoretical_maximum",
            "percentage_penalty",
            "quality_breakdown",
        ]
    )
    return changed


def _apply_relative_terms(tracks: Sequence, definition: TaskTypeDefinition, values: dict[str, float]) -> None:
    """
    Turns the measures the calculators logged for the relative terms of the task type into points of Q, for every
    contestant of the task: value x measure / best measure, the best being that of the contestants who flew (0 when
    nobody measured above zero, as the catalogue gives no share then). Rebuilt from the log each time, so another
    contestant's new best changes everybody's share, and running it again changes nothing.
    """
    from django.db.models import Sum

    from display.models import ScoreLogEntry

    types = {term.score_type for term in definition.relative_quality_terms}
    built = [track for track in tracks if track.quality_start is not None]
    if not types or not built:
        return
    measures: dict[tuple[int, str], float] = {
        (row["contestant_id"], row["score_type"]): row["total"]
        for row in ScoreLogEntry.objects.filter(
            contestant_id__in=[t.contestant_id for t in built], score_type__in=types
        )
        .order_by()  # the model's default ordering would split the groups
        .values("contestant_id", "score_type")
        .annotate(total=Sum("points"))
    }
    best = {
        score_type: max(
            (measures.get((t.contestant_id, score_type), 0.0) for t in built if t.calculator_started), default=0.0
        )
        for score_type in types
    }
    for track in built:
        breakdown = {key: value for key, value in track.quality_breakdown.items() if key not in types}
        for score_type, value in values.items():
            measure = measures.get((track.contestant_id, score_type))
            if measure is not None:
                breakdown[score_type] = value * measure / best[score_type] if best[score_type] > 0 else 0.0
        raw_quality = track.quality_start + sum(breakdown.values())
        if track.raw_quality != raw_quality or track.quality_breakdown != breakdown:
            track.raw_quality = raw_quality
            track.quality_breakdown = breakdown
            track.save(update_fields=["raw_quality", "quality_breakdown"])


def _is_legacy_track(track) -> bool:
    """A flown track whose raw values were never built: its score is from before the quality model and stays."""
    return track.calculator_started and track.quality_start is None


def recompute_task_scores(navigation_task, refresh: Iterable = ()) -> int:
    """
    Rebuilds the raw values of the contestants in `refresh` (Contestant objects or primary keys) from their score
    logs, then derives the task score of every contestant of the task from the stored raw values and writes the ones
    that changed (through ContestantTrack.update_score, so the task test score, the leaderboard and the websocket stay
    consistent). Does nothing for a task of the penalty model. Returns the number of task scores written.
    """
    if not is_quality_task(navigation_task):
        return 0
    refresh_ids = {getattr(item, "pk", item) for item in refresh}
    to_push, written = _recompute(navigation_task.pk, refresh_ids)
    # Pushed after the transaction: a websocket round trip must not hold the row locks
    for track in to_push:
        track.push_change()
    return written


@retry_on_lock_timeout()
def _recompute(navigation_task_id: int, refresh_ids: set) -> tuple[list, int]:
    from display.models import Contestant, ContestantTrack, NavigationTask

    with transaction.atomic():
        # Lock first, in primary key order; every later read in this transaction sees what was committed before it.
        # (Without a join: a locking read over a join would lock the contestant rows as well.)
        contestant_ids = list(
            Contestant.objects.filter(navigation_task_id=navigation_task_id).values_list("pk", flat=True)
        )
        locked_ids = list(
            ContestantTrack.objects.select_for_update()
            .filter(contestant_id__in=contestant_ids)
            .order_by("pk")
            .values_list("pk", flat=True)
        )
        if not locked_ids:
            return [], 0  # no contestants (or the task is gone)
        navigation_task = NavigationTask.objects.select_related("scorecard").get(pk=navigation_task_id)
        tracks = list(
            ContestantTrack.objects.filter(pk__in=locked_ids).select_related("contestant__team__crew").order_by("pk")
        )
        parameters = scoring_parameters(navigation_task)
        definition = stored_task_type(navigation_task)
        relative_types = frozenset(term.score_type for term in definition.relative_quality_terms)
        before = {
            track.pk: (track.raw_quality, track.percentage_penalty, dict(track.quality_breakdown)) for track in tracks
        }
        for track in tracks:
            track.contestant.navigation_task = navigation_task
            if track.contestant_id in refresh_ids:
                _rebuild_track(track, track.contestant, relative_types)
        if relative_types:
            _apply_relative_terms(
                [track for track in tracks if not _is_legacy_track(track)],
                definition,
                relative_term_values(navigation_task.scorecard, definition),
            )
        rebuilt = {
            track.pk
            for track in tracks
            if track.contestant_id in refresh_ids
            and before[track.pk] != (track.raw_quality, track.percentage_penalty, track.quality_breakdown)
        }
        scorable = [track for track in tracks if not _is_legacy_track(track)]
        scores = compute_task_scores(
            parameters,
            [
                QualityEntry(
                    flown=track.calculator_started,
                    raw_quality=track.raw_quality,
                    theoretical_maximum=track.quality_theoretical_maximum or 0.0,
                    percentage_penalty=track.percentage_penalty,
                )
                for track in scorable
            ],
        )
        to_push = []
        written = 0
        for track, score in zip(scorable, scores):
            score_changed = track.update_score(float(score), push=False)
            written += score_changed
            if score_changed or track.pk in rebuilt:
                to_push.append(track)
    return to_push, written


def refresh_contestant_quality(contestant) -> int:
    """The raw values of `contestant` changed (a score log entry was added or removed, the calculator started):
    rebuild them and renormalise the task."""
    return recompute_task_scores(contestant.navigation_task, refresh=[contestant])


def quality_track_fields(track) -> dict:
    """The raw values of a track the front ends need to show how its task score came about (additive keys of the
    track's payloads; the same for every payload that carries a track)."""
    return {
        "raw_quality": track.raw_quality,
        "quality_start": track.quality_start,
        "quality_theoretical_maximum": track.quality_theoretical_maximum,
        "percentage_penalty": track.percentage_penalty,
        "quality_breakdown": track.quality_breakdown,
    }


def contestant_deleted(navigation_task_id: int) -> None:
    """A contestant is gone: the best Q of the task may have been theirs. Safe when the task is gone as well."""
    from display.models import NavigationTask

    navigation_task = NavigationTask.objects.filter(pk=navigation_task_id).select_related("scorecard").first()
    if navigation_task is not None:
        recompute_task_scores(navigation_task)


def task_scores_are_provisional(navigation_task) -> bool:
    """The scores of a quality task are provisional until every contestant's flight is finished: a later, better
    flight lowers the others' scores."""
    from display.models import ContestantTrack

    if not is_quality_task(navigation_task):
        return False
    return ContestantTrack.objects.filter(
        contestant__navigation_task=navigation_task, calculator_finished=False
    ).exists()
