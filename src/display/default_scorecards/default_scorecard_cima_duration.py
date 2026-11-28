import datetime

from display.models import Scorecard
from display.utilities.gate_definitions import LANDING_GATE, TAKEOFF_GATE
from display.utilities.task_types import PRECISION


def get_default_scorecard():
    """
    2.B3 Duration: fly as long as possible on a limited amount of fuel. The longest flight earns the task value and the
    others in proportion (the task-level quality scoring, see display.services.task_scoring), so the scorecard has no
    time gates: a take-off or landing gate that the route authors only marks the flight and costs nothing. The one
    penalty it sets is the percentage lost for landing outside the specified area, which the catalogue leaves to the
    briefing.
    """
    unscored_gate = {
        "extended_gate_width": 0,
        "bad_crossing_extended_gate_penalty": 0,
        "graceperiod_before": 0,
        "graceperiod_after": 0,
        "maximum_penalty": 0,
        "penalty_per_second": 0,
        "missed_penalty": 0,
        "missed_procedure_turn_penalty": 0,
        "backtracking_after_steep_gate_grace_period_seconds": 0,
        "included_fields": [["Penalties", "maximum_penalty", "missed_penalty"]],
    }
    gates = {TAKEOFF_GATE: dict(unscored_gate), LANDING_GATE: dict(unscored_gate)}
    scorecard, created = Scorecard.objects.update_or_create(
        name="CIMA Duration 2026",
        defaults={
            "shortcut_name": "CIMA Duration",
            "valid_from": datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
            "score_sorting_direction": "desc",
            "initial_score": 1000,
            "use_procedure_turns": False,
            "task_type": [PRECISION],
            "calculator": PRECISION,
            "prohibited_zone_maximum": 0,
            "prohibited_zone_penalty": 0,
            "duration_landing_area_penalty_percent": 50,
            "included_fields": [
                [
                    "Prohibited zone",
                    "prohibited_zone_grace_time",
                    "prohibited_zone_penalty",
                ],
                ["Initial score", "initial_score"],
            ],
        },
    )
    scorecard.config["gates"] = gates
    scorecard.save(update_fields=["config"])
    return scorecard
