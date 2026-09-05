#
import datetime

from display.models import Scorecard
from display.utilities.gate_definitions import (
    TURNPOINT,
    TAKEOFF_GATE,
    LANDING_GATE,
    SECRETPOINT,
    FINISHPOINT,
    STARTINGPOINT,
    DUMMY,
    UNKNOWN_LEG,
)
from display.utilities.navigation_task_type_definitions import PRECISION


# No procedure turn
# Extended starting gate 2NM
# No penalty for backtracking within 45 seconds for more than 90° turns


def get_default_scorecard():
    regular_gate = {
        "extended_gate_width": 0.3,
        "bad_crossing_extended_gate_penalty": 0,
        "graceperiod_before": 2,
        "graceperiod_after": 2,
        "maximum_penalty": 100,
        "penalty_per_second": 3,
        "missed_penalty": 100,
        "missed_procedure_turn_penalty": 0,
        "backtracking_after_steep_gate_grace_period_seconds": 45,
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
            "graceperiod_before": 0,
            "graceperiod_after": 60,
            "maximum_penalty": 100,
            "penalty_per_second": 3,
            "missed_penalty": 0,
            "missed_procedure_turn_penalty": 0,
            "backtracking_after_steep_gate_grace_period_seconds": 0,
            "included_fields": [
                ["Penalties", "maximum_penalty", "missed_penalty"],
                ["Time limits", "graceperiod_before", "graceperiod_after"],
            ],
        },
        LANDING_GATE: {
            "extended_gate_width": 0,
            "bad_crossing_extended_gate_penalty": 0,
            "graceperiod_before": 0,
            "graceperiod_after": 60,
            "maximum_penalty": 0,
            "penalty_per_second": 0,
            "missed_penalty": 0,
            "missed_procedure_turn_penalty": 0,
            "backtracking_after_steep_gate_grace_period_seconds": 0,
            "included_fields": [["Penalties", "maximum_penalty", "missed_penalty"]],
        },
        SECRETPOINT: dict(regular_gate),
        FINISHPOINT: dict(regular_gate),
        STARTINGPOINT: {
            "extended_gate_width": 2,
            "bad_crossing_extended_gate_penalty": 200,
            "graceperiod_before": 2,
            "graceperiod_after": 2,
            "maximum_penalty": 100,
            "penalty_per_second": 3,
            "missed_penalty": 100,
            "missed_procedure_turn_penalty": 0,
            "backtracking_after_steep_gate_grace_period_seconds": 45,
            "included_fields": [
                [
                    "Penalties",
                    "penalty_per_second",
                    "maximum_penalty",
                    "missed_penalty",
                    "bad_crossing_extended_gate_penalty",
                ],
                ["Additional gate sizes", "extended_gate_width"],
                ["Time limits", "graceperiod_before", "graceperiod_after"],
            ],
        },
        DUMMY: dict(regular_gate),
        UNKNOWN_LEG: dict(regular_gate),
    }

    scorecard, created = Scorecard.objects.update_or_create(
        name="FAI Air Rally 2020",
        defaults={
            "shortcut_name": "FAI Air Rally",
            "valid_from": datetime.datetime(2022, 1, 1, tzinfo=datetime.timezone.utc),
            "score_sorting_direction": "asc",
            "backtracking_penalty": 100,
            "backtracking_grace_time_seconds": 5,
            "backtracking_maximum_penalty": 1000,
            "prohibited_zone_maximum": 0,
            "use_procedure_turns": False,
            "task_type": [PRECISION],
            "calculator": PRECISION,
            "prohibited_zone_penalty": 0,
            "included_fields": [
                [
                    "Backtracking",
                    "backtracking_penalty",
                    "backtracking_grace_time_seconds",
                    "backtracking_maximum_penalty",
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
    # Phase 2e of the scorecard-system review roadmap: gates are built as plain dicts and
    # written straight into config["gates"] - no more per-gate GateScore rows or the
    # signal-mirror round trip that used to require a refresh_from_db() at the end.
    scorecard.config["gates"] = gates
    scorecard.save(update_fields=["config"])
    return scorecard
