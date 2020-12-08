#
from display.models import GateScore, Scorecard

fai_precision_flying_2020, created = Scorecard.objects.get_or_create(name="FAI Precision 2020")
if created:
    fai_precision_flying_2020.backtracking_penalty = 200
    fai_precision_flying_2020.backtracking_grace_time_seconds = 5
    regular_gate_score = GateScore.objects.create(extended_gate_width=6,
                                                  bad_crossing_extended_gate_penalty=0,
                                                  graceperiod_before=2,
                                                  graceperiod_after=2,
                                                  maximum_penalty=100,
                                                  penalty_per_second=3,
                                                  missed_penalty=100,
                                                  missed_procedure_turn_penalty=200)
    fai_precision_flying_2020.takeoff_gate_score = GateScore.objects.create(extended_gate_width=0,
                                                                            bad_crossing_extended_gate_penalty=0,
                                                                            graceperiod_before=0,
                                                                            graceperiod_after=60,
                                                                            maximum_penalty=200,
                                                                            penalty_per_second=200,
                                                                            missed_penalty=0,
                                                                            missed_procedure_turn_penalty=0)
    fai_precision_flying_2020.landing_gate_score = GateScore.objects.create(extended_gate_width=0,
                                                                            bad_crossing_extended_gate_penalty=0,
                                                                            graceperiod_before=0,
                                                                            graceperiod_after=60,
                                                                            maximum_penalty=0,
                                                                            penalty_per_second=0,
                                                                            missed_penalty=0,
                                                                            missed_procedure_turn_penalty=0)
    fai_precision_flying_2020.turning_point_gate_score = regular_gate_score
    fai_precision_flying_2020.secret_gate_score = regular_gate_score
    fai_precision_flying_2020.starting_point_gate_score = GateScore.objects.create(extended_gate_width=2,
                                                                                   bad_crossing_extended_gate_penalty=200,
                                                                                   graceperiod_before=2,
                                                                                   graceperiod_after=2,
                                                                                   maximum_penalty=100,
                                                                                   penalty_per_second=3,
                                                                                   missed_penalty=100,
                                                                                   missed_procedure_turn_penalty=200)
    fai_precision_flying_2020.finish_point_gate_score = regular_gate_score
    fai_precision_flying_2020.save()


def get_default_scorecard():
    return fai_precision_flying_2020
