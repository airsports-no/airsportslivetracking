import datetime

from display.models import Scorecard
from display.utilities.gate_definitions import (
    DUMMY,
    FINISHPOINT,
    LANDING_GATE,
    SECRETPOINT,
    STARTINGPOINT,
    TAKEOFF_GATE,
    TURNPOINT,
    UNKNOWN_LEG,
)
from display.utilities.task_types import AIR_SPORT_CHALLENGE_2025_SCORECARD, AIRSPORT_CHALLENGE, AIRSPORTS

NAME = "Air Sports Race 2025 (Annex 9)"
SHORTCUT_NAME = "Air Sports Race 2025"
CHALLENGE_NAME = "Air Sport Challenge 2025 (Annex 9)"
CHALLENGE_SHORTCUT_NAME = AIR_SPORT_CHALLENGE_2025_SCORECARD

GATE_FIELDS = [
    ["Penalties", "penalty_per_second", "maximum_penalty", "missed_penalty"],
    ["Time limits", "graceperiod_before", "graceperiod_after"],
]


def _timed_gate(penalty_per_second: int, maximum_penalty: int, missed_penalty: int, **overrides) -> dict:
    """A gate crossed within two seconds of its time is free, 6.7.5."""
    return {
        "extended_gate_width": 0,
        "bad_crossing_extended_gate_penalty": 0,
        "graceperiod_before": 2,
        "graceperiod_after": 2,
        "penalty_per_second": penalty_per_second,
        "maximum_penalty": maximum_penalty,
        "missed_penalty": missed_penalty,
        "backtracking_after_steep_gate_grace_period_seconds": 0,
        "backtracking_before_gate_grace_period_nm": 0.5,
        "backtracking_after_gate_grace_period_nm": 0.5,
        "missed_procedure_turn_penalty": 0,
        "included_fields": GATE_FIELDS,
        **overrides,
    }


def get_default_scorecard():
    """
    The navigation penalties of the FAI Sporting Code Section 10, Annex 9 (Air Sport Race), 2025 edition, table 6.7.5.
    The older "Air Sports Race" scorecard is kept for the tasks made from it; this one is the family's default
    (DEFAULT_SCORECARD_SHORTCUT_NAMES).
    """
    return _build_scorecard(AIRSPORTS, NAME, SHORTCUT_NAME)


def get_airsport_challenge_scorecard():
    """
    The same Annex 9 rules for the Air Sport Challenge family. A scorecard's calculator is the family of the tasks made
    from it, so the family needs a row of its own; the rules are built by the same code and cannot drift apart. The
    older "Air Sport Challenge 2023" scorecard is kept for the tasks made from it.
    """
    return _build_scorecard(AIRSPORT_CHALLENGE, CHALLENGE_NAME, CHALLENGE_SHORTCUT_NAME)


def _build_scorecard(family: str, name: str, shortcut_name: str):
    """

    Not scored here, because nothing detects them: leaving the quarantine late (100) and not following the departure and
    arrival instructions at the airfield (200). The contest director gives those as manual penalties.
    """
    # Start point, finish point and known timed gates: 2 points per second, at most 200, 200 when missed
    known_gate = _timed_gate(2, 200, 200)
    gates = {
        TURNPOINT: known_gate,
        FINISHPOINT: dict(known_gate),
        STARTINGPOINT: _timed_gate(2, 200, 200, extended_gate_width=0.01),
        # Hidden timed gates: 1 point per second, at most 100, 100 when missed
        SECRETPOINT: _timed_gate(1, 100, 100),
        DUMMY: dict(known_gate),
        UNKNOWN_LEG: dict(known_gate),
        # Take-off from 3 seconds before to 60 seconds after the given time is free, otherwise 200
        TAKEOFF_GATE: {
            "extended_gate_width": 0,
            "bad_crossing_extended_gate_penalty": 0,
            "graceperiod_before": 3,
            "graceperiod_after": 60,
            "maximum_penalty": 200,
            "penalty_per_second": 200,
            "missed_penalty": 0,
            "backtracking_after_steep_gate_grace_period_seconds": 0,
            "backtracking_after_gate_grace_period_nm": 0.5,
            "missed_procedure_turn_penalty": 0,
            "included_fields": [
                ["Penalties", "maximum_penalty", "missed_penalty"],
                ["Time limits", "graceperiod_before", "graceperiod_after"],
            ],
        },
        LANDING_GATE: {
            "extended_gate_width": 0,
            "bad_crossing_extended_gate_penalty": 0,
            "graceperiod_before": 9999999999,
            "graceperiod_after": 0,
            "backtracking_after_steep_gate_grace_period_seconds": 0,
            "backtracking_after_gate_grace_period_nm": 0.5,
            "maximum_penalty": 0,
            "penalty_per_second": 0,
            "missed_penalty": 0,
            "missed_procedure_turn_penalty": 0,
            "included_fields": [["Penalties", "maximum_penalty", "missed_penalty"]],
        },
    }

    scorecard, created = Scorecard.objects.update_or_create(
        name=name,
        defaults={
            "shortcut_name": shortcut_name,
            "valid_from": datetime.datetime(2025, 1, 1, tzinfo=datetime.timezone.utc),
            # 6.7.4: cumulative penalties, the fewest win
            "score_sorting_direction": "asc",
            # One backtrack costs 100, and 100 is the most a task can cost
            "backtracking_penalty": 100,
            "backtracking_grace_time_seconds": 5,
            "backtracking_maximum_penalty": 100,
            "use_procedure_turns": False,
            "task_type": [family],
            "calculator": family,
            # Outside the corridor or inside a penalty zone: 1 point per second after 5 seconds, no maximum (0)
            "corridor_maximum_penalty": 0,
            "corridor_outside_penalty": 1,
            "corridor_grace_time": 5,
            "penalty_zone_grace_time": 5,
            "penalty_zone_penalty_per_second": 1,
            "penalty_zone_maximum": 0,
            # A prohibited zone: 100 for each entrance that lasts more than 5 seconds
            "prohibited_zone_penalty": 100,
            "prohibited_zone_grace_time": 5,
            "prohibited_zone_maximum": 0,
            "included_fields": [
                [
                    "Corridor penalties",
                    "corridor_grace_time",
                    "backtracking_penalty",
                    "corridor_outside_penalty",
                ],
                [
                    "Prohibited zone",
                    "prohibited_zone_grace_time",
                    "prohibited_zone_penalty",
                ],
                [
                    "Penalty zone",
                    "penalty_zone_grace_time",
                    "penalty_zone_penalty_per_second",
                    "penalty_zone_maximum",
                ],
                ["Initial score", "initial_score"],
            ],
        },
    )
    scorecard.config["gates"] = gates
    scorecard.save(update_fields=["config"])
    return scorecard
