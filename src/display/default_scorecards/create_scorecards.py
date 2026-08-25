from display.default_scorecards import (
    default_scorecard_airsport_challenge,
    default_scorecard_airsports,
    default_scorecard_fai_air_rally_2020,
    default_scorecard_fai_anr_2017,
    default_scorecard_fai_anr_2022,
    default_scorecard_fai_precision_2020,
    default_scorecard_fai_precision_2020_without_procedure_turn,
    default_scorecard_landing,
    default_scorecard_nlf_precision_2020,
    default_scorecard_nordic_asr,
    default_scorecard_poker_run,
)
from display.models import Scorecard


def _seed_cima_runtime_defaults():
    precision_cards = Scorecard.objects.filter(shortcut_name="FAI Precision")
    precision_cards.update(
        compulsory_timing_tolerance_seconds=10,
        maximum_task_duration_minutes=None,
        maximum_task_duration_penalty=100,
        fuel_deadline_penalty=100,
        anr_route_to_sp_penalty=200,
        anr_route_from_fp_penalty=200,
        duration_normalization_policy="",
        duration_residual_fuel_required=False,
        circle_radius_min_m=200,
        circle_radius_max_m=750,
    )


def create_scorecards():
    default_scorecard_fai_precision_2020.get_default_scorecard()
    default_scorecard_fai_precision_2020_without_procedure_turn.get_default_scorecard()
    default_scorecard_fai_air_rally_2020.get_default_scorecard()
    default_scorecard_fai_anr_2017.get_default_scorecard()
    default_scorecard_fai_anr_2022.get_default_scorecard()
    default_scorecard_nlf_precision_2020.get_default_scorecard()
    default_scorecard_poker_run.get_default_scorecard()
    default_scorecard_landing.get_default_scorecard()
    default_scorecard_airsports.get_default_scorecard()
    default_scorecard_airsport_challenge.get_default_scorecard()
    default_scorecard_nordic_asr.get_default_scorecard()
    _seed_cima_runtime_defaults()
