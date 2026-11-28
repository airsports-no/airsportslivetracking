"""
How a task is scored, in plain language for the organiser (slice S20b).

One place writes the explanation, from the same things the engine reads: the task type registry
(display.utilities.task_types), the scorecard's values and, when a task is given, its route. There is no second table of
numbers here, so the text cannot disagree with the scoring. The API serves it (the navigation task and the
scorecard endpoints) and the screens only show it.

Why it exists: in a CIMA task a pilot's score is a share of the best pilot's raw points, so it can go down after
landing when a later pilot flies better, and it is only final when every flight is finished. An organiser who starts a
default task must not be surprised by that, even without opening the scorecard.

The text avoids the engine's own names: it says "task score", "best pilot in the task" and "raw points", and explains a
letter of the rules (V, S) where it first appears.
"""

import copy
import logging
from typing import Optional

from display.services.catalogue_gate_quality import CatalogueGateQuality, flat_hidden_gate_value
from display.services.task_scoring import (
    backtracking_penalty_percentage_for,
    relative_term_values,
    scores_depend_on_other_pilots,
    scoring_parameters_for,
)
from display.utilities.cima_scoring_config import CimaScoringConfig
from display.utilities.gate_definitions import (
    FINISHPOINT,
    SECRETPOINT,
    STARTINGPOINT,
    TAKEOFF_GATE,
    TURNPOINT,
)
from display.utilities.task_types import (
    CONTRACT_POINTS_SCORE_TYPE,
    POKER,
    QMAX_ABSOLUTE,
    QMAX_BEST_IN_TASK,
    QMAX_POLICIES,
    QMAX_THEORETICAL,
    QUALITY_START_ACHIEVEMENT,
    QUALITY_START_FIXED,
    QUALITY_START_GATE_DEFICIT,
    SCORING_MODELS,
    SCORING_PENALTIES,
    SCORING_QUALITY,
    SPEED_TERM_SCORE_TYPE,
    CatalogueGateModel,
    TaskTypeDefinition,
    find_task_type,
    find_task_type_for,
    stored_task_type,
)

logger = logging.getLogger(__name__)

# The scorecard values the explanation preview may take from the editor before they are saved.
PREVIEW_OVERRIDE_FIELDS = (
    "scoring_model",
    "qmax_policy",
    "task_value",
    "backtracking_penalty_percentage",
    "speed_term_value",
)

_POLICY_LABELS = {
    QMAX_BEST_IN_TASK: "Scaled against the best pilot",
    QMAX_THEORETICAL: "Scaled against a perfect flight",
    QMAX_ABSOLUTE: "Fixed scale",
}


# ---------------------------------------------------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------------------------------------------------


def _num(value, digits: int = 1) -> str:
    """A number as it reads in a sentence: 180 not 180.0, 142.857 as 142.9."""
    try:
        return format(round(float(value), digits), "g")
    except (TypeError, ValueError):
        return str(value)


def _seconds(value) -> str:
    return f"{_num(value)} second{'' if float(value) == 1 else 's'}"


def _points(value) -> str:
    return f"{_num(value)} point{'' if float(value) == 1 else 's'}"


def _join(items: list[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def _gate(scorecard, gate_type: str):
    """The scoring of a gate type, None where the scorecard has none."""
    try:
        return scorecard.get_gate_scorecard(gate_type)
    except (ValueError, KeyError):
        return None


def _with_overrides(scorecard, overrides: Optional[dict]):
    """A scorecard that reads as if the unsaved editor values were stored; the stored one is not touched."""
    if scorecard is None or not overrides:
        return scorecard
    preview = copy.copy(scorecard)
    preview.config = {**scorecard.config, **{k: v for k, v in overrides.items() if k in PREVIEW_OVERRIDE_FIELDS}}
    return preview


def parse_preview_overrides(params) -> dict:
    """
    The unsaved scorecard values of the editor, from query parameters (a blank value is "the task type's default").
    Raises ValueError, with a message for the user, for a value that is not allowed.
    """
    overrides: dict = {}
    for name in PREVIEW_OVERRIDE_FIELDS:
        if name not in params:
            continue
        raw = params.get(name)
        if raw in (None, ""):
            overrides[name] = None
        elif name == "scoring_model":
            if raw not in dict(SCORING_MODELS):
                raise ValueError(f"Unknown scoring model '{raw}'.")
            overrides[name] = raw
        elif name == "qmax_policy":
            if raw not in dict(QMAX_POLICIES):
                raise ValueError(f"Unknown way to scale the score '{raw}'.")
            overrides[name] = raw
        else:
            try:
                overrides[name] = float(raw)
            except ValueError:
                raise ValueError(f"{name} must be a number.")
    return overrides


def _config_value(scorecard, name: str, default):
    value = getattr(scorecard, name, default) if scorecard is not None else default
    return default if value is None else value


# ---------------------------------------------------------------------------------------------------------------------
# What the task is worth to the route: counts from the route, where a task is given
# ---------------------------------------------------------------------------------------------------------------------


def _route_counts(definition: TaskTypeDefinition, scorecard, navigation_task) -> dict:
    """The number of hidden gates of the task's route (what each is worth depends on it), empty with no route to count."""
    if navigation_task is None or definition.catalogue_gate_model is None:
        return {}
    try:
        waypoints = list(navigation_task.route.waypoints)
    except Exception:  # a task without a readable route is explained in general terms
        return {}
    if not waypoints:
        return {}
    quality = CatalogueGateQuality.for_task_type(definition, scorecard, waypoints)
    if quality is None:
        return {}
    return {"hidden": quality.hidden_gate_count}


# ---------------------------------------------------------------------------------------------------------------------
# Raw points: what a pilot's result is made of
# ---------------------------------------------------------------------------------------------------------------------


def _timing_sentence(subject: str, worth: Optional[float], rate: float, emax: float, grace: float, missed_note: str):
    cost = f"{_num(rate)} point{'' if rate == 1 else 's'} for every second it is crossed too early or too late"
    if worth is not None:
        text = f"{subject} is worth {_points(worth)}, less {cost} (at most {_points(emax)} can be lost)."
    else:
        text = f"{subject} loses {cost}, at most {_points(emax)} per gate."
    if grace > 0:
        text += f" Errors of up to {_num(grace)} seconds cost nothing."
    return f"{text} {missed_note}"


def _gate_model_lines(definition: TaskTypeDefinition, scorecard, counts: dict) -> list[str]:
    """2.A1, 2.A2 and 2.A3: the gates as the catalogue's formulas weigh them (see CatalogueGateQuality)."""
    model: CatalogueGateModel = definition.catalogue_gate_model
    lines = []
    secret = _gate(scorecard, SECRETPOINT)
    if model.hidden_gate_value_is_share_of_total:
        hidden = counts.get("hidden")
        if hidden:
            lines.append(
                f"The route's {hidden} hidden gates share {_num(model.hidden_gates_total)} points: "
                f"{_points(model.hidden_gates_total / hidden)} for each hidden gate crossed once, in the right direction."
            )
        else:
            lines.append(
                f"The hidden gates share {_num(model.hidden_gates_total)} points equally, so the more hidden gates "
                "the route has, the less each is worth. A hidden gate is earned by crossing it once, in the right "
                "direction."
            )
    elif secret is not None and not model.declared_points_count_in_v:
        value = abs(secret.maximum_penalty)
        hidden = counts.get("hidden")
        which = f"Each of the route's {hidden} hidden gates" if hidden else "Each hidden gate"
        lines.append(f"{which} crossed once, in the right direction, is worth {_points(value)}.")
    if definition.repeated_hidden_gate_crossing_invalidates:
        lines.append(
            "A hidden gate that is crossed more than once, or first crossed the wrong way, counts as not crossed."
        )

    # The time gates of the task, grouped by what a second of error costs
    kinds: list[tuple[str, str]] = []
    middle = "middle point" if model.declared_points_count_in_v else "timed turn point"
    if model.start_point_timed:
        kinds.append((STARTINGPOINT, "starting point"))
    kinds.append((TURNPOINT, middle))
    if model.hidden_gates_timed:
        kinds.append((SECRETPOINT, "hidden gate"))
    if model.finish_point_timed:
        kinds.append((FINISHPOINT, "finish point"))
    groups: dict[tuple, list[str]] = {}
    for gate_type, noun in kinds:
        gate = _gate(scorecard, gate_type)
        if gate is None:
            continue
        key = (abs(gate.maximum_penalty), gate.penalty_per_second, max(gate.graceperiod_before, gate.graceperiod_after))
        groups.setdefault(key, []).append(noun)
    for (emax, rate, grace), nouns in groups.items():
        subject = f"Each {nouns[0]}" if len(nouns) == 1 else f"Each time gate ({_join(nouns)})"
        if model.time_gate_is_worth_emax:
            lines.append(
                _timing_sentence(
                    subject, emax, rate, emax, grace, f"A time gate that is not flown loses all of its {_points(emax)}."
                )
            )
        else:
            lines.append(
                _timing_sentence(
                    subject,
                    None,
                    rate,
                    emax,
                    grace,
                    f"A gate that is not flown loses {_points(emax)}; a hidden gate that is not crossed also loses its "
                    "value.",
                )
            )
    if not model.start_point_timed and not model.finish_point_timed:
        lines.append("The starting and finish points are not time gates.")
    elif not model.start_point_timed:
        lines.append("The starting point only starts the clock; it is not a time gate.")
    if model.declared_points_count_in_v:
        lines.append(
            "The pilot declares turn points before take-off. The middle point must be flown at the declared time T "
            "after the start and the finish point at 2T; points declared after the middle point are invalid if they "
            "are flown before the middle point's time, and every turn point may be visited once."
        )
    return lines


def _flat_gate_lines(definition: TaskTypeDefinition, scorecard) -> list[str]:
    """The tasks without catalogue formulas of their own (2.A4, 2.A5): the scorecard's gate scores."""
    gate = _gate(scorecard, TURNPOINT)
    if gate is None:
        return []
    value = max(abs(gate.maximum_penalty), abs(gate.missed_penalty))
    text = (
        f"Each gate that is checked or timed is worth up to {_points(value)}. A timing error costs "
        f"{_num(gate.penalty_per_second)} point{'' if gate.penalty_per_second == 1 else 's'} per second, at most "
        f"{_points(abs(gate.maximum_penalty))} per gate, and a gate that is not flown loses {_points(abs(gate.missed_penalty))}."
    )
    grace = max(gate.graceperiod_before, gate.graceperiod_after)
    if grace > 0:
        text += f" Errors of up to {_num(grace)} seconds cost nothing."
    lines = [text]
    hidden_value = flat_hidden_gate_value(definition, scorecard)
    if hidden_value is not None:
        lines.append(
            f"A hidden gate crossed once, in the right direction, is worth {_points(hidden_value)}; one that is not "
            "crossed loses that."
        )
    return lines


def _hunt_lines(definition: TaskTypeDefinition, scorecard) -> list[str]:
    config = CimaScoringConfig.from_scorecard(scorecard)
    lines = []
    if definition.free_order_gate_matching:
        lines.append(
            "Every target collected earns its published value, in whatever order and direction the targets are flown."
        )
    else:
        lines.append("Every target collected, in the pilot's declared sequence, earns its published value.")
    lines.append(
        f"Each compulsory timing gate crossed is worth {_points(config.turnpoint_hunt_time_gate_value)}; errors of up "
        f"to {_num(config.compulsory_timing_tolerance_seconds)} seconds cost nothing, and every second beyond that "
        f"costs {_points(config.compulsory_timing_penalty_per_second)}."
    )
    if not definition.free_order_gate_matching and config.turnpoint_hunt_sequence_bonus > 0:
        lines.append(
            f"A bonus of {_points(config.turnpoint_hunt_sequence_bonus)} is added for flying the whole declared "
            "sequence correctly."
        )
    if config.maximum_task_duration_minutes is not None:
        lines.append(
            f"Every second after the maximum task duration of {_num(config.maximum_task_duration_minutes)} minutes "
            f"costs {_points(config.maximum_task_duration_penalty)}."
        )
    if definition.has_fuel_deadline:
        lines.append(
            f"Each gate passed after the declared fuel endurance costs {_points(config.fuel_deadline_penalty)}."
        )
    return lines


def _circle_lines(definition: TaskTypeDefinition, scorecard) -> list[str]:
    config = CimaScoringConfig.from_scorecard(scorecard)
    return [
        f"A perfect circle scores {_num(definition.fixed_quality)} points. The score is the smallest radius divided by "
        "the largest radius, less 0.5, times 500, measured over the 360 degrees scored from the entry line.",
        f"The circle is flown to the left, around the centre marker, with a radius between {_num(config.circle_radius_min_m)} "
        f"and {_num(config.circle_radius_max_m)} metres; a circle flown to the right, or outside those limits, scores nothing.",
    ]


def _anr_lines(definition: TaskTypeDefinition, scorecard) -> list[str]:
    config = CimaScoringConfig.from_scorecard(scorecard)
    lines = [f"Every pilot starts with {_num(definition.fixed_quality)} points and loses points for mistakes."]
    lines.append(
        f"Leaving the corridor costs {_points(scorecard.corridor_outside_penalty)} per second after "
        f"{_seconds(scorecard.corridor_grace_time)}."
    )
    start = _gate(scorecard, STARTINGPOINT)
    if start is not None:
        lines.append(
            f"Timing errors at the starting point and the finish point cost {_points(start.penalty_per_second)} per "
            f"second after {_seconds(start.graceperiod_after)}, at most {_points(abs(start.maximum_penalty))} per "
            f"gate; a gate that is missed costs {_points(abs(start.missed_penalty))}."
        )
    takeoff = _gate(scorecard, TAKEOFF_GATE)
    if takeoff is not None and takeoff.maximum_penalty:
        lines.append(f"Taking off outside the allowed window costs {_points(abs(takeoff.maximum_penalty))}.")
    lines.append(
        f"Not following the route to the starting point costs {_points(config.anr_route_to_sp_penalty)}, and not "
        f"following the route from the finish point costs {_points(config.anr_route_from_fp_penalty)}."
    )
    lines.append(f"Backtracking or circling costs {_points(scorecard.backtracking_penalty)} each time.")
    return lines


def _raw_points(definition: TaskTypeDefinition, scorecard, parameters, counts: dict) -> list[str]:
    config = CimaScoringConfig.from_scorecard(scorecard)
    lines: list[str] = []
    if definition.catalogue_gate_model is not None:
        lines.extend(_gate_model_lines(definition, scorecard, counts))
    elif definition.scores_circle:
        lines.extend(_circle_lines(definition, scorecard))
    elif definition.has_auxiliary_route_checks:
        lines.extend(_anr_lines(definition, scorecard))
    elif definition.scores_turnpoint_hunt_targets:
        lines.extend(_hunt_lines(definition, scorecard))
    elif definition.scores_duration:
        lines.append(
            "The pilot's raw result is the time spent in the air, from take-off to landing. The longest flight earns the "
            "full task value."
        )
    elif definition.quality_start == QUALITY_START_GATE_DEFICIT:
        lines.extend(_flat_gate_lines(definition, scorecard))
    if definition.observation_photos_award_points:
        lines.append(
            f"Each observation photo marked at the right place earns {_points(scorecard.observation_photo_value)} "
            "(half if it is marked a little off)."
        )
    if definition.scores_speed_keeping and config.speed_keeping_enabled:
        lines.append(
            f"A leg flown more than {_num(config.speed_keeping_tolerance_kt)} knots away from the declared speed costs "
            f"{_points(config.speed_keeping_penalty_per_kt)} per knot."
        )
    if (
        definition.has_backtracking_detection
        and not definition.has_auxiliary_route_checks
        and not definition.scores_duration
    ):
        if not backtracking_penalty_percentage_for(scorecard, definition):
            lines.append(f"Backtracking costs {_points(scorecard.backtracking_penalty)} each time.")
    values = relative_term_values(scorecard, definition)
    for term in definition.relative_quality_terms:
        if term.score_type in values:
            lines.append(
                f"Up to {_points(values[term.score_type])} come from {_term_name(term.score_type)}, shared against the "
                "best pilot (see the next section)."
            )
    return lines


def _term_name(score_type: str) -> str:
    return {
        CONTRACT_POINTS_SCORE_TYPE: "the declared turn points",
        SPEED_TERM_SCORE_TYPE: "the speed term",
    }.get(score_type, "a term")


# ---------------------------------------------------------------------------------------------------------------------
# What is always relative to the best pilot
# ---------------------------------------------------------------------------------------------------------------------


def _relative_terms(definition: TaskTypeDefinition, scorecard) -> list[str]:
    values = relative_term_values(scorecard, definition)
    lines = []
    for term in definition.relative_quality_terms:
        value = values.get(term.score_type)
        if term.score_type == CONTRACT_POINTS_SCORE_TYPE and value:
            lines.append(
                "Declared turn points: each declared turn point flown in the declared order counts +1, and each declared "
                "point (the starting, middle and finish points included) that is not flown, or flown out of order, "
                f"counts -1. The total is called V. The pilot with the highest V gets {_points(value)}; the others get "
                f"{_num(value)} times their V divided by the best V in the task."
            )
        elif term.score_type == SPEED_TERM_SCORE_TYPE:
            if value:
                lines.append(
                    f"Speed term: the ground speed S (in knots) flown between the first and the last time gate. The "
                    f"fastest pilot in the task gets {_points(value)}; the others get {_num(value)} times their S "
                    "divided by the best S."
                )
            else:
                lines.append("Speed term: not used in this task (it is worth 0 points on the scorecard).")
    return lines


# ---------------------------------------------------------------------------------------------------------------------
# Percentage penalties
# ---------------------------------------------------------------------------------------------------------------------


def _percentage_penalties(definition: TaskTypeDefinition, scorecard) -> list[str]:
    config = CimaScoringConfig.from_scorecard(scorecard)
    lines = []
    backtracking = backtracking_penalty_percentage_for(scorecard, definition)
    if backtracking:
        lines.append(f"Backtracking: each backtrack costs {_num(backtracking)}% of the task score.")
    if definition.scores_circle and config.circle_centre_outside_penalty_percent > 0:
        lines.append(
            f"Circle centre: {_num(config.circle_centre_outside_penalty_percent)}% of the task score is lost if the "
            "centre marker (CM) is outside the circle the pilot flew."
        )
    if definition.scores_circle and config.circle_altitude_penalty_percent > 0:
        lines.append(
            f"Circle altitude: {_num(config.circle_altitude_penalty_percent)}% of the task score is lost if the "
            f"circle's highest and lowest point are more than {_num(config.circle_altitude_band_ft)} feet apart."
        )
    if definition.scores_duration and config.duration_landing_area_penalty_percent > 0:
        lines.append(
            f"Landing: landing outside the specified area costs {_num(config.duration_landing_area_penalty_percent)}% "
            "of the task score."
        )
    lines.append(
        "The organiser can also apply percentage penalties by hand, for example 100% for a breach of quarantine. "
        "Percentage penalties add up (at most 100%) and are taken off after the task score has been worked out."
    )
    return lines


# ---------------------------------------------------------------------------------------------------------------------
# The task score, the choice of Qmax and the provisional state
# ---------------------------------------------------------------------------------------------------------------------


def _perfect_flight(definition: TaskTypeDefinition) -> str:
    if definition.quality_start == QUALITY_START_GATE_DEFICIT:
        return "the raw points of a perfect flight over that pilot's own route and declarations"
    if definition.quality_start == QUALITY_START_ACHIEVEMENT and definition.scores_turnpoint_hunt_targets:
        return "the most that pilot could have earned from their own declared targets and timing gates"
    return "the most that pilot could have scored"


def _policy_supported(definition: TaskTypeDefinition, policy: str) -> bool:
    """Whether a policy makes sense for the task type: a flight's duration has no perfect flight to compare with."""
    if policy == QMAX_THEORETICAL:
        return definition.quality_start == QUALITY_START_GATE_DEFICIT or (
            definition.quality_start == QUALITY_START_ACHIEVEMENT and definition.scores_turnpoint_hunt_targets
        )
    # The fixed-score tasks (the circle, the ANR task) are defined on a fixed scale
    fixed = definition.quality_start == QUALITY_START_FIXED
    return fixed if policy == QMAX_ABSOLUTE else not fixed


def offered_qmax_policies(definition: TaskTypeDefinition) -> list[str]:
    """The ways to scale the task score that the organiser may choose between for a task type: its default first."""
    if definition.scoring_model != SCORING_QUALITY:
        return []
    policies = [definition.qmax_policy]
    for policy in (QMAX_BEST_IN_TASK, QMAX_THEORETICAL):
        if policy not in policies and _policy_supported(definition, policy):
            policies.append(policy)
    return policies


def _relative_names(definition: TaskTypeDefinition, scorecard) -> list[str]:
    values = relative_term_values(scorecard, definition)
    return [_term_name(term.score_type) for term in definition.relative_quality_terms if term.score_type in values]


def _task_score_text(definition: TaskTypeDefinition, parameters) -> str:
    value = _num(parameters.task_value)
    if parameters.qmax_policy == QMAX_BEST_IN_TASK:
        return (
            f"The task score is {value} times the pilot's raw points divided by the raw points of the best pilot in the "
            f"task. The best pilot gets the full {value} points and everybody else gets the same share of {value} as "
            "their raw points are of the best pilot's. Percentage penalties are then taken off, the result is rounded "
            "to a whole number and cannot be below zero. A pilot who did not fly (DNF) scores 0."
        )
    if parameters.qmax_policy == QMAX_THEORETICAL:
        return (
            f"The task score is {value} times the pilot's raw points divided by {_perfect_flight(definition)}. So the "
            f"full {value} points need a perfect flight, and the score does not depend on how the other pilots flew. "
            "Percentage penalties are then taken off, the result is rounded to a whole number and cannot be below "
            "zero. A pilot who did not fly (DNF) scores 0."
        )
    if definition.absolute_reference:
        return (
            f"The task score is {value} times the pilot's raw points divided by {_num(definition.absolute_reference)}: a "
            "fixed scale that is the same for every pilot and does not depend on the other pilots. Percentage "
            "penalties are then taken off and the result cannot be below zero. A pilot who did not fly (DNF) scores 0."
        )
    return (
        "The raw points are the task score (a perfect flight is "
        f"{_num(definition.fixed_quality) if definition.fixed_quality else 'the most possible'} points); the task value is "
        "not used for this task, and the score does not depend on the other pilots. Percentage penalties are then "
        "taken off and the result cannot be below zero. A pilot who did not fly (DNF) scores 0."
    )


def _provisional(definition: TaskTypeDefinition, scorecard, parameters) -> dict:
    relative = _relative_names(definition, scorecard)
    if parameters.qmax_policy == QMAX_BEST_IN_TASK:
        return {
            "depends_on_other_pilots": True,
            "text": (
                "Scores are provisional until every flight in the task is finished. The task score is scaled against "
                "the best pilot in the task, so when a later pilot flies better, the bar goes up and the scores of the "
                "pilots who have already landed go down. A pilot's score can therefore fall after landing. A pilot who never "
                "flew does not hold the scores open once the end of their flight window has passed, and a pilot who is "
                "still flying does not raise the bar until they have landed: until then their own score is a preview "
                "that is never above the task value."
            ),
            "short": (
                "Provisional: scores are scaled against the best pilot in the task, so a better flight later in the "
                "task can lower yours. Scores are final when all flights are finished."
            ),
        }
    if relative and scores_depend_on_other_pilots(scorecard, definition, parameters):
        names = _join(relative)
        return {
            "depends_on_other_pilots": True,
            "text": (
                f"Most of a pilot's score is fixed when they land. The points that come from {names} are still "
                "shared against the best pilot in the task, so those points, and with them the score, can change until "
                "every flight is finished."
            ),
            "short": (
                f"Provisional: most of your score is fixed when you land, but the points from {names} are shared "
                "against the best pilot in the task and can still change. Scores are final when all flights are "
                "finished."
            ),
        }
    return {
        "depends_on_other_pilots": False,
        "text": (
            "A pilot's score does not depend on how the other pilots fly, so it is fixed when they land. It can still "
            "change if the organiser applies a penalty or corrects the result, and the results are final when every "
            "flight is finished."
        ),
        "short": (
            "Your score does not depend on the other pilots and is fixed when you land. The organiser can still apply "
            "penalties, and results are final when all flights are finished."
        ),
    }


def _policy_description(definition: TaskTypeDefinition, scorecard, policy: str, task_value: float) -> str:
    value = _num(task_value)
    relative = _relative_names(definition, scorecard)
    stays = (
        f" The points that come from {_join(relative)} are still shared against the best pilot, so they can "
        "change until everyone has flown."
        if relative
        else ""
    )
    if policy == QMAX_BEST_IN_TASK:
        return (
            f"The rules' default. The best pilot in the task always gets the full {value} points and the others a share "
            "of that. A pilot's score can go down after landing when someone later flies better."
        )
    if policy == QMAX_THEORETICAL:
        return (
            f"Each pilot is compared with {_perfect_flight(definition)}. Their score is fixed when they land and does "
            f"not depend on the other pilots, but nobody reaches {value} points without a perfect flight.{stays}"
        )
    return (
        "A fixed scale: the score is worked out from the pilot's own raw points only, so it never depends on the other "
        "pilots."
    )


def _qmax_choice(definition: TaskTypeDefinition, scorecard, parameters) -> dict:
    """The ways the organiser can decide what the raw points are divided by, with the task type's default marked."""
    policies = [QMAX_BEST_IN_TASK, QMAX_THEORETICAL, QMAX_ABSOLUTE]
    options = []
    for policy in policies:
        selected = policy == parameters.qmax_policy
        default = policy == definition.qmax_policy
        if not (selected or default or _policy_supported(definition, policy)):
            continue
        if policy == QMAX_ABSOLUTE and not (selected or default):
            continue
        options.append(
            {
                "value": policy,
                "label": _POLICY_LABELS[policy],
                "description": _policy_description(definition, scorecard, policy, parameters.task_value),
                "is_default": default,
                "is_selected": selected,
                "fixed_at_landing": policy != QMAX_BEST_IN_TASK,
            }
        )
    return {
        "offered": len(options) > 1,
        "selected": parameters.qmax_policy,
        "default": definition.qmax_policy,
        "options": options,
    }


# ---------------------------------------------------------------------------------------------------------------------
# The explanation
# ---------------------------------------------------------------------------------------------------------------------


def _penalty_explanation(definition: TaskTypeDefinition, scorecard, family: str) -> dict:
    if family == POKER:
        raw = ["Pilots collect playing cards at the waypoints of the route and the score comes from their own cards."]
        headline = "The score comes from the pilot's own flight and does not depend on the other pilots."
    elif scorecard is not None and scorecard.score_sorting_direction == "desc":
        raw = [
            f"Every pilot starts with {_num(scorecard.initial_score)} points and loses points for mistakes such as "
            "timing errors, missed gates, leaving the corridor and backtracking."
        ]
        headline = "Penalty points are taken off a starting score; the highest score wins. Scores do not depend on the other pilots."
    else:
        raw = [
            "Mistakes such as timing errors, missed gates, leaving the corridor and backtracking add penalty points; "
            "the score is the total."
        ]
        headline = "Penalty points are added up; the lowest total wins. Scores do not depend on the other pilots."
    return {
        "scoring_model": SCORING_PENALTIES,
        "task_value": None,
        "qmax_policy": None,
        "task_type": definition.key,
        "task_type_name": definition.display_name,
        "headline": headline,
        "raw_points": raw,
        "task_score": (
            "The score is worked out from the pilot's own flight only. It is the same whoever else flies, and it is "
            "final when the pilot has landed, apart from penalties the organiser applies afterwards."
        ),
        "relative_terms": [],
        "percentage_penalties": [],
        "provisional": {
            "depends_on_other_pilots": False,
            "text": "Scores do not depend on the other pilots, so they do not change because someone else flies later.",
            "short": "Scores do not depend on the other pilots.",
        },
        "qmax": {"offered": False, "selected": None, "default": None, "options": []},
        "depends_on_other_pilots": False,
        "creation_note": None,
        "route_used": False,
    }


def explain_scoring(
    definition: TaskTypeDefinition, scorecard, navigation_task=None, family: Optional[str] = None
) -> dict:
    """
    The explanation of how a task of this type is scored with this scorecard (see the module docstring). With a
    navigation_task, numbers that depend on the route (the number of hidden gates) are filled in; without one the
    explanation is in general terms.
    """
    family = family or definition.coarse_family or getattr(scorecard, "calculator", "")
    parameters = scoring_parameters_for(scorecard, definition)
    if not parameters.is_quality:
        return _penalty_explanation(definition, scorecard, family)

    counts = _route_counts(definition, scorecard, navigation_task)
    provisional = _provisional(definition, scorecard, parameters)
    value = _num(parameters.task_value)
    name = definition.display_name
    if parameters.qmax_policy == QMAX_BEST_IN_TASK:
        headline = (
            f"{name}: the best pilot in the task gets {value} points and every other pilot a share of that, so scores "
            "are scaled against the best pilot and can change until everyone has flown."
        )
    elif parameters.qmax_policy == QMAX_THEORETICAL:
        headline = (
            f"{name}: each pilot is scored against a perfect flight, out of {value} points, so a pilot's score is fixed "
            "when they land."
            + (" Only the shared terms below follow the best pilot." if _relative_names(definition, scorecard) else "")
        )
    else:
        headline = (
            f"{name}: each pilot's score is worked out from their own flight on a fixed scale, so it does not depend on "
            "the other pilots."
        )
    creation_note = (
        "Scores are scaled against the best pilot in the task and can change until everyone has flown."
        if provisional["depends_on_other_pilots"]
        else provisional["short"]
    )
    return {
        "scoring_model": SCORING_QUALITY,
        "task_value": parameters.task_value,
        "qmax_policy": parameters.qmax_policy,
        "task_type": definition.key,
        "task_type_name": name,
        "headline": headline,
        "raw_points": _raw_points(definition, scorecard, parameters, counts),
        "task_score": _task_score_text(definition, parameters),
        "relative_terms": _relative_terms(definition, scorecard),
        "percentage_penalties": _percentage_penalties(definition, scorecard),
        "provisional": {key: provisional[key] for key in ("depends_on_other_pilots", "text", "short")},
        "qmax": _qmax_choice(definition, scorecard, parameters),
        "depends_on_other_pilots": provisional["depends_on_other_pilots"],
        "creation_note": creation_note,
        "route_used": bool(counts),
    }


def explain_navigation_task(navigation_task, overrides: Optional[dict] = None) -> dict:
    """
    The explanation of a navigation task, from its own scorecard copy and route. `overrides` are scorecard values not
    yet saved (PREVIEW_OVERRIDE_FIELDS), for the scorecard editor's preview.
    """
    definition = stored_task_type(navigation_task)
    scorecard = _with_overrides(navigation_task.scorecard, overrides)
    explanation = explain_scoring(definition, scorecard, navigation_task, family=getattr(scorecard, "calculator", None))
    # A legacy task has no stored task type of its own to name; the family's default is what it is called
    effective = find_task_type_for(navigation_task)
    if effective is not None and not definition.key:
        explanation["task_type"] = effective.key
        explanation["task_type_name"] = effective.display_name
    return explanation


def explain_task_type(task_type_key: str, scorecard, overrides: Optional[dict] = None) -> Optional[dict]:
    """
    The explanation for a task type and a scorecard before a task exists (task creation, the scorecard editor). `overrides`
    are scorecard values not yet saved (PREVIEW_OVERRIDE_FIELDS). None for a task type that is not defined.
    """
    definition = find_task_type(task_type_key)
    if definition is None:
        return None
    return explain_scoring(definition, _with_overrides(scorecard, overrides), None, family=scorecard.calculator)
