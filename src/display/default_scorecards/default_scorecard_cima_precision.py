#
import datetime

from display.models import Scorecard
from display.utilities.gate_definitions import (
    TURNPOINT,
    TAKEOFF_GATE,
    LANDING_GATE,
    STARTINGPOINT,
    UNKNOWN_LEG,
    DUMMY,
    SECRETPOINT,
    FINISHPOINT,
)
from display.utilities.navigation_task_type_definitions import PRECISION

# The CIMA task catalogue (documentation/cima/cima_task_catalog.md, 2.A1-2.A5): one point per second of error at a
# time gate, at most Emax ("typically 180"), and Emax for a gate not flown. No grace period, and no procedure turns:
# the catalogue has none.
CATALOGUE_TIMING = {
    "graceperiod_before": 0,
    "graceperiod_after": 0,
    "penalty_per_second": 1,
    "maximum_penalty": 180,
    "missed_penalty": 180,
}


def get_default_scorecard():
    regular_gate = {
        "extended_gate_width": 6,
        "bad_crossing_extended_gate_penalty": 0,
        **CATALOGUE_TIMING,
        "missed_procedure_turn_penalty": 0,
        "backtracking_after_steep_gate_grace_period_seconds": 0,
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
            "maximum_penalty": 200,
            "penalty_per_second": 200,
            "missed_penalty": 200,
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
            "graceperiod_before": 999999999,
            "graceperiod_after": 60,
            "maximum_penalty": 0,
            "penalty_per_second": 0,
            "missed_penalty": 0,
            "missed_procedure_turn_penalty": 0,
            "backtracking_after_steep_gate_grace_period_seconds": 0,
            "included_fields": [["Penalties", "maximum_penalty", "missed_penalty"]],
        },
        STARTINGPOINT: {
            **regular_gate,
            "extended_gate_width": 2,
        },
        DUMMY: dict(regular_gate),
        UNKNOWN_LEG: dict(regular_gate),
        SECRETPOINT: dict(regular_gate),
        FINISHPOINT: dict(regular_gate),
    }

    scorecard, created = Scorecard.objects.update_or_create(
        name="CIMA Precision 2026",
        defaults={
            "shortcut_name": "CIMA Precision",
            "valid_from": datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
            # CIMA scores are points out of 1000 (P = 1000 * Q / Qmax), so the highest wins
            "score_sorting_direction": "desc",
            "initial_score": 1000,
            "backtracking_penalty": 200,
            "backtracking_grace_time_seconds": 5,
            "use_procedure_turns": False,
            "task_type": [PRECISION],
            "calculator": PRECISION,
            "prohibited_zone_maximum": 0,
            "prohibited_zone_penalty": 0,
            "included_fields": [
                [
                    "Backtracking",
                    "backtracking_penalty",
                    "backtracking_grace_time_seconds",
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
