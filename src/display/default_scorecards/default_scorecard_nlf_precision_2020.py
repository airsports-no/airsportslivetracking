#
from display.models import GateScore, Scorecard, TASK_PRECISION


def get_default_scorecard():
    scorecard, created = Scorecard.objects.get_or_create(name="NLF Precision 2020")
    scorecard.backtracking_penalty = 200
    scorecard.backtracking_grace_time_seconds = 5
    scorecard.use_procedure_turns = True
    scorecard.task_type = [TASK_PRECISION]
    scorecard.calculator = Scorecard.PRECISION

    regular_gate_score = GateScore.objects.get_or_create(name=f"{scorecard.name}_regular")[0]
    regular_gate_score.extended_gate_width = 6  # used for PT
    regular_gate_score.bad_crossing_extended_gate_penalty = 0
    regular_gate_score.graceperiod_before = 2
    regular_gate_score.graceperiod_after = 2
    regular_gate_score.maximum_penalty = 100
    regular_gate_score.penalty_per_second = 3
    regular_gate_score.missed_penalty = 100
    regular_gate_score.missed_procedure_turn_penalty = 200
    regular_gate_score.save()

    scorecard.takeoff_gate_score = GateScore.objects.get_or_create(name=f"{scorecard.name}_takeoff")[0]
    scorecard.takeoff_gate_score.extended_gate_width = 0
    scorecard.takeoff_gate_score.bad_crossing_extended_gate_penalty = 0
    scorecard.takeoff_gate_score.graceperiod_before = 0
    scorecard.takeoff_gate_score.graceperiod_after = 60
    scorecard.takeoff_gate_score.maximum_penalty = 200
    scorecard.takeoff_gate_score.penalty_per_second = 200
    scorecard.takeoff_gate_score.missed_penalty = 0
    scorecard.takeoff_gate_score.missed_procedure_turn_penalty = 0
    scorecard.takeoff_gate_score.save()

    scorecard.landing_gate_score = GateScore.objects.get_or_create(name=f"{scorecard.name}_landing")[0]
    scorecard.landing_gate_score.extended_gate_width = 0
    scorecard.landing_gate_score.bad_crossing_extended_gate_penalty = 0
    scorecard.landing_gate_score.graceperiod_before = 0
    scorecard.landing_gate_score.graceperiod_after = 60
    scorecard.landing_gate_score.maximum_penalty = 0
    scorecard.landing_gate_score.penalty_per_second = 0
    scorecard.landing_gate_score.missed_penalty = 0
    scorecard.landing_gate_score.missed_procedure_turn_penalty = 0
    scorecard.landing_gate_score.save()

    scorecard.turning_point_gate_score = regular_gate_score
    scorecard.secret_gate_score = regular_gate_score
    scorecard.starting_point_gate_score = GateScore.objects.get_or_create(name=f"{scorecard.name}_startingpoint")[0]
    scorecard.starting_point_gate_score.extended_gate_width = 2
    scorecard.starting_point_gate_score.bad_crossing_extended_gate_penalty = 200
    scorecard.starting_point_gate_score.graceperiod_before = 2
    scorecard.starting_point_gate_score.graceperiod_after = 2
    scorecard.starting_point_gate_score.maximum_penalty = 100
    scorecard.starting_point_gate_score.penalty_per_second = 3
    scorecard.starting_point_gate_score.missed_penalty = 100
    scorecard.starting_point_gate_score.missed_procedure_turn_penalty = 200
    scorecard.starting_point_gate_score.save()

    scorecard.finish_point_gate_score = regular_gate_score
    scorecard.save()

    return scorecard
