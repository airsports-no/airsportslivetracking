from display.default_scorecards import default_scorecard_fai_precision_2020, default_scorecard_nlf_precision_2020, \
    default_scorecard_fai_air_rally_2020, default_scorecard_fai_anr_2017


def create_scorecards():
    default_scorecard_fai_precision_2020.get_default_scorecard()
    default_scorecard_fai_air_rally_2020.get_default_scorecard()
    default_scorecard_fai_anr_2017.get_default_scorecard()
    default_scorecard_nlf_precision_2020.get_default_scorecard()
