#
from display.models import GateScore, Scorecard, NavigationTask


# No procedure turn
# Extended starting gate 2NM
# No penalty for backtracking within 45 seconds for more than 90° turns

def get_default_scorecard():
    scorecard, created = Scorecard.objects.get_or_create(name="FAI Air Rally 2020")
    scorecard.backtracking_penalty = 100
    scorecard.backtracking_grace_time_seconds = 5
    scorecard.backtracking_maximum_penalty = 1000
    scorecard.use_procedure_turns = False
    scorecard.task_type = [NavigationTask.PRECISION]
    scorecard.calculator = Scorecard.PRECISION

    regular_gate_score = GateScore.objects.get_or_create(name=f"{scorecard.name}_regular")[0]
    regular_gate_score.extended_gate_width = 0.3
    regular_gate_score.bad_crossing_extended_gate_penalty = 0
    regular_gate_score.graceperiod_before = 2
    regular_gate_score.graceperiod_after = 2
    regular_gate_score.maximum_penalty = 100
    regular_gate_score.penalty_per_second = 3
    regular_gate_score.missed_penalty = 100
    regular_gate_score.missed_procedure_turn_penalty = 0
    regular_gate_score.backtracking_after_steep_gate_grace_period_seconds = 45
    regular_gate_score.save()

    scorecard.takeoff_gate_score = GateScore.objects.get_or_create(name=f"{scorecard.name}_takeoff")[0]
    scorecard.takeoff_gate_score.extended_gate_width = 0
    scorecard.takeoff_gate_score.bad_crossing_extended_gate_penalty = 0
    scorecard.takeoff_gate_score.graceperiod_before = 0
    scorecard.takeoff_gate_score.graceperiod_after = 60
    scorecard.takeoff_gate_score.maximum_penalty = 100
    scorecard.takeoff_gate_score.penalty_per_second = 3
    scorecard.takeoff_gate_score.missed_penalty = 0
    scorecard.takeoff_gate_score.missed_procedure_turn_penalty = 0
    scorecard.takeoff_gate_score.backtracking_after_steep_gate_grace_period_seconds = 0
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
    scorecard.landing_gate_score.backtracking_after_steep_gate_grace_period_seconds = 0
    scorecard.landing_gate_score.save()

    scorecard.turning_point_gate_score = regular_gate_score
    scorecard.secret_gate_score = regular_gate_score
    scorecard.starting_point_gate_score = regular_gate_score
    scorecard.finish_point_gate_score = regular_gate_score
    scorecard.save()

    return scorecard
