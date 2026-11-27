import copy
import datetime

from display.default_scorecards import default_scorecard_fai_anr_2022
from display.models import Scorecard
from display.utilities.gate_definitions import FINISHPOINT, STARTINGPOINT, TAKEOFF_GATE

# 2.A8 (Annex 4): plus or minus one second at SP and FP is free, then 3 points per full second, at most 200, and 200 for
# a gate not crossed. (FAI ANR 2022 gives two seconds.)
CATALOGUE_TIME_GATE_GRACE_S = 1
# 2.A8: take-off at the given time and within 60 s after it is free, before it or later costs 100 points.
CATALOGUE_TAKEOFF_PENALTY = 100


def get_gates() -> dict:
    """The gates of FAI ANR 2022 with the differences of the catalogue (see get_default_scorecard)."""
    gates = copy.deepcopy(default_scorecard_fai_anr_2022.get_gates())
    for gate_type in (STARTINGPOINT, FINISHPOINT):
        gates[gate_type]["graceperiod_before"] = CATALOGUE_TIME_GATE_GRACE_S
        gates[gate_type]["graceperiod_after"] = CATALOGUE_TIME_GATE_GRACE_S
    takeoff = gates[TAKEOFF_GATE]
    takeoff["penalty_per_second"] = CATALOGUE_TAKEOFF_PENALTY
    takeoff["maximum_penalty"] = CATALOGUE_TAKEOFF_PENALTY
    takeoff["missed_penalty"] = CATALOGUE_TAKEOFF_PENALTY
    return gates


def get_default_scorecard():
    """
    2.A8 Precision navigation Air Nav Race: the FAI ANR 2022 rules, but scored like every CIMA task (Q = 2000 less
    penalties, P = 1000 x Q / 2000, the highest winning) and with the catalogue's own values where they differ:
    one second of grace at SP and FP, 100 points for taking off outside the given time, and no maximum on the points
    lost for backtracking or circling (200 each).
    """
    scorecard, created = Scorecard.objects.update_or_create(
        name="CIMA ANR 2026",
        defaults={
            **default_scorecard_fai_anr_2022.get_scorecard_defaults(),
            "shortcut_name": "CIMA ANR",
            "valid_from": datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
            "score_sorting_direction": "desc",
            "initial_score": 1000,
            # No maximum: -1 is the scorecard's "unlimited" (FAI ANR 2022 stops at 400).
            "backtracking_maximum_penalty": -1,
        },
    )
    scorecard.config["gates"] = get_gates()
    scorecard.save(update_fields=["config"])
    return scorecard
