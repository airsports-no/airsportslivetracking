#
from display.models import GateScore, Scorecard, NavigationTask


def get_default_scorecard():
    scorecard, created = Scorecard.objects.get_or_create(name="Airsports")
    scorecard.backtracking_penalty = 10
    scorecard.backtracking_grace_time_seconds = 5
    scorecard.backtracking_maximum_penalty = 100
    scorecard.use_procedure_turns = False
    scorecard.task_type = [NavigationTask.AIRSPORTS]
    scorecard.calculator = Scorecard.AIRSPORTS
    scorecard.corridor_maximum_penalty = -1
    scorecard.corridor_outside_penalty = 1  # verified
    scorecard.corridor_grace_time = 5  # verified
    scorecard.below_minimum_altitude_penalty = 500  # verified
    scorecard.below_minimum_altitude_maximum_penalty = 500  # verified
    scorecard.prohibited_zone_penalty = 100
    scorecard.penalty_zone_grace_time = 0
    scorecard.penalty_zone_penalty_per_second = 1
    scorecard.penalty_zone_maximum = 100

    regular_gate_score = GateScore.objects.get_or_create(name=f"{scorecard.name}_regular")[0]
    regular_gate_score.extended_gate_width = 0
    regular_gate_score.bad_crossing_extended_gate_penalty = 0
    regular_gate_score.graceperiod_before = 1  # verified
    regular_gate_score.graceperiod_after = 1  # verified
    regular_gate_score.maximum_penalty = 200  # verified
    regular_gate_score.penalty_per_second = 1  # verified
    regular_gate_score.missed_penalty = 10  # verified
    regular_gate_score.backtracking_after_steep_gate_grace_period_seconds = 0
    regular_gate_score.backtracking_after_gate_grace_period_nm = 0.5
    regular_gate_score.missed_procedure_turn_penalty = 0
    regular_gate_score.save()

    scorecard.takeoff_gate_score = GateScore.objects.get_or_create(name=f"{scorecard.name}_takeoff")[0]
    scorecard.takeoff_gate_score.extended_gate_width = 0
    scorecard.takeoff_gate_score.bad_crossing_extended_gate_penalty = 0
    scorecard.takeoff_gate_score.graceperiod_after = 60  # verified
    scorecard.takeoff_gate_score.maximum_penalty = 200  # verified
    scorecard.takeoff_gate_score.backtracking_after_steep_gate_grace_period_seconds = 0
    scorecard.takeoff_gate_score.backtracking_after_gate_grace_period_nm = 0.5
    scorecard.takeoff_gate_score.penalty_per_second = 200  # verified
    scorecard.takeoff_gate_score.missed_penalty = 0
    scorecard.takeoff_gate_score.missed_procedure_turn_penalty = 0
    scorecard.takeoff_gate_score.save()

    scorecard.landing_gate_score = GateScore.objects.get_or_create(name=f"{scorecard.name}_landing")[0]
    scorecard.landing_gate_score.extended_gate_width = 0
    scorecard.landing_gate_score.bad_crossing_extended_gate_penalty = 0
    scorecard.landing_gate_score.graceperiod_before = 9999999999
    scorecard.landing_gate_score.graceperiod_after = 0
    scorecard.landing_gate_score.backtracking_after_steep_gate_grace_period_seconds = 0
    scorecard.landing_gate_score.backtracking_after_gate_grace_period_nm = 0.5
    scorecard.landing_gate_score.maximum_penalty = 0
    scorecard.landing_gate_score.penalty_per_second = 0
    scorecard.landing_gate_score.missed_penalty = 0
    scorecard.landing_gate_score.missed_procedure_turn_penalty = 0
    scorecard.landing_gate_score.save()

    scorecard.turning_point_gate_score = regular_gate_score
    scorecard.secret_gate_score = regular_gate_score
    scorecard.starting_point_gate_score = GateScore.objects.get_or_create(name=f"{scorecard.name}_startingpoint")[0]
    scorecard.starting_point_gate_score.extended_gate_width = 0.6  # verified
    scorecard.starting_point_gate_score.bad_crossing_extended_gate_penalty = 200
    scorecard.starting_point_gate_score.graceperiod_before = 1  # verified
    scorecard.starting_point_gate_score.graceperiod_after = 1  # verified
    scorecard.starting_point_gate_score.backtracking_after_steep_gate_grace_period_seconds = 0
    scorecard.starting_point_gate_score.backtracking_after_gate_grace_period_nm = 0.5
    scorecard.starting_point_gate_score.maximum_penalty = 200  # verified
    scorecard.starting_point_gate_score.penalty_per_second = 3  # verified
    scorecard.starting_point_gate_score.missed_penalty = 200  # verified
    scorecard.starting_point_gate_score.missed_procedure_turn_penalty = 0
    scorecard.starting_point_gate_score.save()

    scorecard.finish_point_gate_score = regular_gate_score
    scorecard.save()

    return scorecard
