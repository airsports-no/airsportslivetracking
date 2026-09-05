#
import datetime

from display.models import Scorecard
from display.utilities.gate_definitions import (
    TURNPOINT,
    TAKEOFF_GATE,
    LANDING_GATE,
    STARTINGPOINT,
    SECRETPOINT,
    FINISHPOINT,
    DUMMY,
    UNKNOWN_LEG,
)
from display.utilities.navigation_task_type_definitions import AIRSPORTS


def get_default_scorecard():
    regular_gate = {
        "extended_gate_width": 0,
        "bad_crossing_extended_gate_penalty": 0,
        "graceperiod_before": 2,
        "graceperiod_after": 2,
        "maximum_penalty": 100,
        "penalty_per_second": 3,
        "missed_penalty": 100,
        "backtracking_after_steep_gate_grace_period_seconds": 0,
        "backtracking_before_gate_grace_period_nm": 0.5,
        "backtracking_after_gate_grace_period_nm": 0.5,
        "missed_procedure_turn_penalty": 0,
        "included_fields": [
            [
                "Penalties",
                "penalty_per_second",
                "maximum_penalty",
                "missed_penalty",
            ],
            ["Time limits", "graceperiod_before", "graceperiod_after"],
        ],
    }
    gates = {
        TURNPOINT: regular_gate,
        TAKEOFF_GATE: {
            "extended_gate_width": 0,
            "bad_crossing_extended_gate_penalty": 0,
            "graceperiod_after": 60,  # verified
            "graceperiod_before": 0,
            "maximum_penalty": 200,  # verified
            "backtracking_after_steep_gate_grace_period_seconds": 0,
            "backtracking_after_gate_grace_period_nm": 0.5,
            "penalty_per_second": 200,  # verified
            "missed_penalty": 0,
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
        STARTINGPOINT: {
            "extended_gate_width": 0.01,
            "bad_crossing_extended_gate_penalty": 0,
            "graceperiod_before": 1,  # verified
            "graceperiod_after": 1,  # verified
            "backtracking_after_steep_gate_grace_period_seconds": 0,
            "backtracking_after_gate_grace_period_nm": 0.5,
            "maximum_penalty": 100,  # verified
            "penalty_per_second": 2,  # verified
            "missed_penalty": 100,  # verified
            "missed_procedure_turn_penalty": 0,
            "included_fields": [
                [
                    "Penalties",
                    "penalty_per_second",
                    "maximum_penalty",
                    "missed_penalty",
                    "bad_crossing_extended_gate_penalty",
                ],
                ["Time limits", "graceperiod_before", "graceperiod_after"],
            ],
        },
        SECRETPOINT: dict(regular_gate),
        FINISHPOINT: dict(regular_gate),
        DUMMY: dict(regular_gate),
        UNKNOWN_LEG: dict(regular_gate),
    }

    scorecard, created = Scorecard.objects.update_or_create(
        name="Nordic Air Sports Race",
        defaults={
            "shortcut_name": "Nordic Air Sports Race",
            "valid_from": datetime.datetime(2025, 1, 1, tzinfo=datetime.timezone.utc),
            "score_sorting_direction": "asc",
            "backtracking_penalty": 200,
            "backtracking_grace_time_seconds": 5,
            "backtracking_maximum_penalty": 200,
            "use_procedure_turns": False,
            "task_type": [AIRSPORTS],
            "calculator": AIRSPORTS,
            "corridor_maximum_penalty": 100,  # verified
            "corridor_outside_penalty": 1,  # verified
            "corridor_grace_time": 5,  # verified
            "prohibited_zone_penalty": 50,
            "prohibited_zone_grace_time": 0,
            "prohibited_zone_maximum": 200,
            "penalty_zone_grace_time": 0,
            "penalty_zone_penalty_per_second": 3,
            "penalty_zone_maximum": 200,
            "included_fields": [
                [
                    "Corridor penalties",
                    "corridor_grace_time",
                    "backtracking_penalty",
                    "corridor_outside_penalty",
                ],
                ["Prohibited zone", "prohibited_zone_grace_time", "prohibited_zone_penalty", "prohibited_zone_maximum"],
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
    # Phase 2e of the scorecard-system review roadmap: gates are built as plain dicts and
    # written straight into config["gates"] - no more per-gate GateScore rows or the
    # signal-mirror round trip that used to require a refresh_from_db() at the end.
    scorecard.config["gates"] = gates
    scorecard.save(update_fields=["config"])
    return scorecard
