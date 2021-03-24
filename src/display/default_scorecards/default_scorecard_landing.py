#
from display.models import GateScore, Scorecard, NavigationTask


def get_default_scorecard():
    scorecard, created = Scorecard.objects.get_or_create(name="Landing")
    scorecard.backtracking_penalty = 0
    scorecard.backtracking_grace_time_seconds = 5
    scorecard.use_procedure_turns = False
    scorecard.task_type = [NavigationTask.LANDING]
    scorecard.calculator = Scorecard.LANDING
    scorecard.prohibited_zone_penalty = 0


    regular_gate_score = GateScore.objects.get_or_create(name=f"{scorecard.name}_regular")[0]
    regular_gate_score.extended_gate_width = 6
    regular_gate_score.bad_crossing_extended_gate_penalty = 0
    regular_gate_score.graceperiod_before = 2
    regular_gate_score.graceperiod_after = 2
    regular_gate_score.maximum_penalty = 0
    regular_gate_score.penalty_per_second = 0
    regular_gate_score.missed_penalty = 0
    regular_gate_score.missed_procedure_turn_penalty = 0
    regular_gate_score.backtracking_after_steep_gate_grace_period_seconds = 0
    regular_gate_score.save()

    scorecard.turning_point_gate_score = regular_gate_score
    scorecard.secret_gate_score = regular_gate_score
    scorecard.finish_point_gate_score = regular_gate_score
    scorecard.takeoff_gate_score = regular_gate_score
    scorecard.landing_gate_score = regular_gate_score
    scorecard.starting_point_gate_score = regular_gate_score
    scorecard.save()

    return scorecard
