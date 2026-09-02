#
import datetime

from display.models import Scorecard
from display.utilities.gate_definitions import LANDING_GATE, DUMMY, UNKNOWN_LEG
from display.utilities.navigation_task_type_definitions import LANDING


def get_default_scorecard():
    regular_gate = {
        "extended_gate_width": 6,
        "bad_crossing_extended_gate_penalty": 0,
        "graceperiod_before": 2,
        "graceperiod_after": 2,
        "maximum_penalty": 0,
        "penalty_per_second": 0,
        "missed_penalty": 0,
        "missed_procedure_turn_penalty": 0,
        "backtracking_after_steep_gate_grace_period_seconds": 0,
    }
    gates = {
        LANDING_GATE: regular_gate,
        DUMMY: dict(regular_gate),
        UNKNOWN_LEG: dict(regular_gate),
    }

    scorecard, created = Scorecard.objects.update_or_create(
        name="Landing",
        defaults={
            "shortcut_name": "Landing",
            "valid_from": datetime.datetime(2022, 1, 1, tzinfo=datetime.timezone.utc),
            "score_sorting_direction": "asc",
            "backtracking_penalty": 0,
            "backtracking_grace_time_seconds": 5,
            "use_procedure_turns": False,
            "task_type": [LANDING],
            "calculator": LANDING,
            "prohibited_zone_penalty": 0,
            "prohibited_zone_maximum": 0,
        },
    )
    # Phase 2e of the scorecard-system review roadmap: gates are built as plain dicts and
    # written straight into config["gates"] - no more per-gate GateScore rows or the
    # signal-mirror round trip that used to require a refresh_from_db() at the end.
    scorecard.config["gates"] = gates
    scorecard.save(update_fields=["config"])
    return scorecard
