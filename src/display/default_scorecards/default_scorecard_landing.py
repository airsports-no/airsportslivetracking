#
import datetime

from display.utilities.clone_object import simple_clone, get_or_none
from display.models import GateScore, Scorecard
from display.utilities.gate_definitions import LANDING_GATE, DUMMY, UNKNOWN_LEG
from display.utilities.navigation_task_type_definitions import LANDING


def get_default_scorecard():
    scorecard, created = Scorecard.objects.update_or_create(
        name="Landing",
        defaults={
            "shortcut_name": "Landing",
            "valid_from": datetime.datetime(2022, 1, 1, tzinfo=datetime.timezone.utc),
            "backtracking_penalty": 0,
            "backtracking_grace_time_seconds": 5,
            "use_procedure_turns": False,
            "task_type": [LANDING],
            "calculator": LANDING,
            "prohibited_zone_penalty": 0,
        },
    )

    regular_gate_score, _ = GateScore.objects.update_or_create(
        scorecard=scorecard,
        gate_type=LANDING_GATE,
        defaults={
            "extended_gate_width": 6,
            "bad_crossing_extended_gate_penalty": 0,
            "graceperiod_before": 2,
            "graceperiod_after": 2,
            "maximum_penalty": 0,
            "penalty_per_second": 0,
            "missed_penalty": 0,
            "missed_procedure_turn_penalty": 0,
            "backtracking_after_steep_gate_grace_period_seconds": 0,
        },
    )
    simple_clone(
        regular_gate_score,
        {"gate_type": DUMMY},
        existing_clone=get_or_none(scorecard.gatescore_set.filter(gate_type=DUMMY)),
    )
    simple_clone(
        regular_gate_score,
        {"gate_type": UNKNOWN_LEG},
        existing_clone=get_or_none(scorecard.gatescore_set.filter(gate_type=UNKNOWN_LEG)),
    )

    return scorecard
