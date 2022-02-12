#
from display.clone_object import simple_clone
from display.models import GateScore, Scorecard, NavigationTask, TURNPOINT, SECRETPOINT, STARTINGPOINT, FINISHPOINT, \
    TAKEOFF_GATE, LANDING_GATE, GATE_TYPES


def get_default_scorecard():
    scorecard, created = Scorecard.objects.update_or_create(
        name="Poker run",
        defaults={
            "shortcut_name": "Poker run",
            "backtracking_penalty": 0,
            "backtracking_grace_time_seconds": 5,
            "use_procedure_turns": False,
            "task_type": [NavigationTask.POKER],
            "calculator": Scorecard.POKER,
            "prohibited_zone_penalty": 0,
        })

    turning_point, _ = GateScore.objects.update_or_create(scorecard=scorecard, gate_type=TURNPOINT, defaults={
        "extended_gate_width": 6,
        "bad_crossing_extended_gate_penalty": 0,
        "graceperiod_before": 2,
        "graceperiod_after": 2,
        "maximum_penalty": 0,
        "penalty_per_second": 0,
        "missed_penalty": 0,
        "missed_procedure_turn_penalty": 0,
        "backtracking_after_steep_gate_grace_period_seconds": 0,
    })
    for gate_type, friendly_name in GATE_TYPES:
        if gate_type != TURNPOINT:
            simple_clone(turning_point, {"gate_type": gate_type})

    return scorecard
