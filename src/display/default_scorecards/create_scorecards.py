from display.default_scorecards import (
    default_scorecard_fai_precision_2020,
    default_scorecard_nlf_precision_2020,
    default_scorecard_fai_air_rally_2020,
    default_scorecard_fai_anr_2017,
    default_scorecard_poker_run,
    default_scorecard_landing,
    default_scorecard_airsports,
    default_scorecard_fai_precision_2020_without_procedure_turn,
    default_scorecard_fai_anr_2022,
    default_scorecard_airsport_challenge,
    default_scorecard_cima_precision_2023,
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
    default_scorecard_cima_precision_2023.get_default_scorecard()
