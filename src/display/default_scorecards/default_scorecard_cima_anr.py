#
import datetime

from display.default_scorecards import default_scorecard_fai_anr_2022
from display.models import Scorecard


def get_default_scorecard():
    """
    2.A8 Precision navigation Air Nav Race: the FAI ANR 2022 rules, but scored like every CIMA task, out of 1000 with
    the highest winning.
    """
    scorecard, created = Scorecard.objects.update_or_create(
        name="CIMA ANR 2026",
        defaults={
            **default_scorecard_fai_anr_2022.get_scorecard_defaults(),
            "shortcut_name": "CIMA ANR",
            "valid_from": datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
            "score_sorting_direction": "desc",
            "initial_score": 1000,
        },
    )
    scorecard.config["gates"] = default_scorecard_fai_anr_2022.get_gates()
    scorecard.save(update_fields=["config"])
    return scorecard
