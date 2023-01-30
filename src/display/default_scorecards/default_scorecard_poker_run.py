#
from display.clone_object import simple_clone
from display.models import (
    GateScore,
    Scorecard,
    NavigationTask,
    TURNPOINT,
    SECRETPOINT,
    STARTINGPOINT,
    FINISHPOINT,
    TAKEOFF_GATE,
    LANDING_GATE,
    GATE_TYPES, DUMMY, UNKNOWN_LEG,
)


def get_default_scorecard():
    Scorecard.objects.filter(name="Poker run").update(name="Pilot Poker Run")
    scorecard, created = Scorecard.objects.update_or_create(
        name="Pilot Poker Run",
        defaults={
            "shortcut_name": "Pilot Poker Run",
            "backtracking_penalty": 0,
            "backtracking_grace_time_seconds": 5,
            "use_procedure_turns": False,
            "task_type": [NavigationTask.POKER],
            "calculator": Scorecard.POKER,
            "prohibited_zone_penalty": 0,
            "free_text": """
<p>The crew must follow the order of the waypoints to receive the next card.  To make the waypoint more accessible, polygons (Gate Zone) can be used in the route editor. Overlap the Gate Zone with the Turning Point, it will then be automatically connected as a waypoint.</p>

<p>If the route contains one or several stops, it is recommended that the Tracking Stop Time should be expanded so that it ensures completion before the tracker time expires. For example, in the track "update" you can set "Minutes to landing" with the extra time needed to complete the competition. This must be done before crew registration, alternatively each one crew can be changed manually.</p>
            """,
        },
    )

    turning_point, _ = GateScore.objects.update_or_create(
        scorecard=scorecard,
        gate_type=TURNPOINT,
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
    for gate_type, friendly_name in GATE_TYPES:
        if gate_type != TURNPOINT:
            scorecard.gatescore_set.filter(gate_type=gate_type).delete()
            simple_clone(turning_point, {"gate_type": gate_type})
    scorecard.gatescore_set.filter(gate_type__in=(DUMMY, UNKNOWN_LEG)).delete()
    simple_clone(turning_point, {"gate_type": DUMMY})
    simple_clone(turning_point, {"gate_type": UNKNOWN_LEG})

    return scorecard
