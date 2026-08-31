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
