#
import datetime

from display.utilities.clone_object import simple_clone, get_or_none
from display.models import (
    GateScore,
    Scorecard,
)
from display.utilities.gate_definitions import (
    ANR_TP,
    FINISHPOINT,
    TAKEOFF_GATE,
    LANDING_GATE,
    SECRETPOINT,
    STARTINGPOINT,
    DUMMY,
    UNKNOWN_LEG,
)
from display.utilities.navigation_task_type_definitions import ANR_CORRIDOR


def get_default_scorecard():
    scorecard, created = Scorecard.objects.update_or_create(
        name="FAI ANR 2017",
        defaults={
            "shortcut_name": "FAI ANR 2017",
            "valid_from": datetime.datetime(2017, 1, 1, tzinfo=datetime.timezone.utc),
            "score_sorting_direction": "asc",
            "backtracking_penalty": 200,  # verified
            "backtracking_grace_time_seconds": 5,  # verified?
            "backtracking_maximum_penalty": 400,  # verified
            "use_procedure_turns": False,
            "task_type": [ANR_CORRIDOR],
            "calculator": ANR_CORRIDOR,
            "corridor_maximum_penalty": 0,  # verified
            "corridor_outside_penalty": 3,  # verified
            "corridor_maximum_penalty_is_per_leg": True,
            "corridor_grace_time": 5,  # verified
            "prohibited_zone_penalty": 200,
            "prohibited_zone_maximum": 0,
            "included_fields": [
                [
                    "Corridor penalties",
                    "corridor_grace_time",
                    "backtracking_penalty",
                    "corridor_outside_penalty",
                    "corridor_maximum_penalty",
                    "corridor_maximum_penalty_is_per_leg",
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
    GateScore.objects.update_or_create(
        scorecard=scorecard,
        gate_type=FINISHPOINT,
        defaults={
            "extended_gate_width": 0.6,  # verified,
            "bad_crossing_extended_gate_penalty": 0,
            "graceperiod_before": 1,  # verified
            "graceperiod_after": 1,  # verified
            "maximum_penalty": 200,  # verified
            "penalty_per_second": 3,  # verified
            "missed_penalty": 200,  # verified
            "backtracking_after_steep_gate_grace_period_seconds": 0,
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
        },
    )

    GateScore.objects.update_or_create(
        scorecard=scorecard,
        gate_type=TAKEOFF_GATE,
        defaults={
            "extended_gate_width": 0,
            "bad_crossing_extended_gate_penalty": 0,
            "graceperiod_before": 0,  # verified
            "graceperiod_after": 60,  # verified
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
    )

    GateScore.objects.update_or_create(
        scorecard=scorecard,
        gate_type=LANDING_GATE,
        defaults={
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
    )
    # Uses secret gates for all turning points along the track
    regular_gate_score, _ = GateScore.objects.update_or_create(
        scorecard=scorecard,
        gate_type=SECRETPOINT,
        defaults={
            "backtracking_before_gate_grace_period_nm": 0.5,
        },
    )

    GateScore.objects.update_or_create(
        scorecard=scorecard,
        gate_type=ANR_TP,
        defaults={
            "backtracking_before_gate_grace_period_nm": 0.5,
        },
    )

    GateScore.objects.update_or_create(
        scorecard=scorecard,
        gate_type=STARTINGPOINT,
        defaults={
            "extended_gate_width": 0.6,  # verified
            "bad_crossing_extended_gate_penalty": 200,
            "graceperiod_before": 1,  # verified
            "graceperiod_after": 1,  # verified
            "backtracking_after_steep_gate_grace_period_seconds": 0,
            "backtracking_after_gate_grace_period_nm": 0.5,
            "maximum_penalty": 200,  # verified
            "penalty_per_second": 3,  # verified
            "missed_penalty": 200,  # verified
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

    # The gate scores above are created/updated after `scorecard` was fetched or
    # created; each one's post_save signal (sync_gate_score_to_scorecard_config,
    # display/signals.py) mirrors itself into the *database row's* config["gates"]
    # via a fresh, separate fetch of the owning Scorecard - it can't reach back into
    # this in-memory `scorecard` object. Refresh so the object this function returns
    # (used directly by every default_scorecards/*.py caller and test) reflects all of
    # those gates instead of whatever config it had at its own fetch/creation time -
    # empty, on the very first creation of this scorecard.
    scorecard.refresh_from_db()
    return scorecard
