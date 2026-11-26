"""Hand-computed examples for the catalogue oracle (catalogue_oracle.py). No database."""

from django.test import SimpleTestCase

from display.calculators.tests import catalogue_oracle as oracle


class FinalScoreTest(SimpleTestCase):
    def test_the_best_pilot_of_the_task_gets_the_task_value(self):
        self.assertEqual(oracle.final_scores([800, 400, 200]), [1000, 500, 250])

    def test_a_different_task_value(self):
        self.assertEqual(oracle.final_scores([800, 400], task_value=1500), [1500, 750])

    def test_a_single_pilot_scores_the_task_value_whatever_the_quality(self):
        self.assertEqual(oracle.final_scores([123]), [1000])

    def test_nobody_above_zero_scores_zero(self):
        self.assertEqual(oracle.final_scores([0, -50]), [0, 0])

    def test_a_negative_quality_scores_zero(self):
        self.assertEqual(oracle.final_scores([600, -100]), [1000, 0])

    def test_percentage_penalty_is_taken_off_after_the_normalisation(self):
        # Q 300 of a best 600 is 500 points; 50% of that is 250. The best pilot's penalty does not change Qmax.
        self.assertEqual(oracle.final_scores([600, 300], [[0.5], []]), [500, 500])
        self.assertEqual(oracle.final_scores([600, 300], [[], [0.5]]), [1000, 250])

    def test_penalties_of_one_pilot_add_up_and_stop_at_one_hundred_percent(self):
        self.assertEqual(oracle.final_scores([100], [[0.5, 0.2]]), [300])
        self.assertEqual(oracle.final_scores([100], [[0.5, 0.5, 0.5]]), [0])

    def test_half_a_point_is_rounded_up(self):
        self.assertEqual(oracle.round_half_up(0.5), 1)
        self.assertEqual(oracle.round_half_up(2.5), 3)
        self.assertEqual(oracle.round_half_up(2.49), 2)
        self.assertEqual(oracle.round_half_up(-0.5), 0)
        # 1000 x 201 / 400 = 502.5
        self.assertEqual(oracle.final_scores([400, 201]), [1000, 503])

    def test_the_published_score_is_never_negative(self):
        self.assertEqual(oracle.finish_score(-12.0), 0)


class HiddenGatesTest(SimpleTestCase):
    @staticmethod
    def sequence(*gates):
        return [(gate, 1) for gate in gates]

    def test_the_catalogue_example_one_two_four_three_five_six_five_seven_counts_as_five_gates(self):
        crossings = self.sequence(1, 2, 4, 3, 5, 6, 5, 7)
        self.assertEqual(oracle.correct_hidden_gates(crossings), [1, 2, 4, 6, 7])
        self.assertEqual(len(oracle.correct_hidden_gates(crossings)), 5)

    def test_every_gate_in_order_counts(self):
        self.assertEqual(oracle.correct_hidden_gates(self.sequence(1, 2, 3)), [1, 2, 3])

    def test_a_gate_crossed_the_wrong_way_does_not_count(self):
        self.assertEqual(oracle.correct_hidden_gates([(1, 1), (2, -1), (3, 1)]), [1, 3])

    def test_a_gate_crossed_twice_in_any_direction_is_invalid(self):
        self.assertEqual(oracle.correct_hidden_gates([(1, 1), (2, 1), (2, -1), (3, 1)]), [1, 3])
        self.assertEqual(oracle.correct_hidden_gates([(1, 1), (1, 1), (2, 1)]), [2])

    def test_a_gate_not_crossed_does_not_count(self):
        self.assertEqual(oracle.correct_hidden_gates(self.sequence(1, 3)), [1, 3])


class TimeErrorTest(SimpleTestCase):
    def test_error_is_absolute_and_capped_at_emax(self):
        self.assertEqual(oracle.time_error(-25), 25)
        self.assertEqual(oracle.time_error(25), 25)
        self.assertEqual(oracle.time_error(500), 180)

    def test_a_gate_not_flown_counts_emax(self):
        self.assertEqual(oracle.time_error(None), 180)
        self.assertEqual(oracle.time_error(None, emax=120), 120)


class CurveNavigationTest(SimpleTestCase):
    def test_perfect_flight(self):
        # Qh = 1000, Qt = 180 x 3 - 0.
        self.assertEqual(oracle.q_curve_navigation(4, 4, [0, 0, 0]), 1540)

    def test_three_of_four_hidden_gates_and_some_timing_errors(self):
        # Qh = 750, Qt = 540 - (10 + 20 + 180 for a gate not flown) = 330.
        self.assertEqual(oracle.q_curve_navigation(4, 3, [10, -20, None]), 1080)

    def test_without_time_gates_only_the_spatial_part_counts(self):
        self.assertEqual(oracle.q_curve_navigation(5, 4, []), 800)

    def test_final_score_against_the_best_pilot(self):
        best = oracle.q_curve_navigation(4, 4, [0, 0, 0])
        other = oracle.q_curve_navigation(4, 3, [10, -20, None])
        self.assertEqual(oracle.final_scores([best, other]), [1000, 701])  # 1000 x 1080 / 1540 = 701.3


class PrecisionNavigationTest(SimpleTestCase):
    def test_perfect_flight(self):
        self.assertEqual(oracle.q_precision_navigation(6, [0] * 5), 1080)

    def test_errors_are_negative_points_and_a_gate_not_crossed_costs_emax(self):
        # 4 gates x 180 = 720; errors 7 + 30 + 180 (not crossed) + 200 capped at 180 = 397.
        self.assertEqual(oracle.q_precision_navigation(4, [7, -30, None, 200]), 720 - 397)


class ContractNavigationTest(SimpleTestCase):
    def test_v_is_the_points_flown_in_order_minus_the_declared_points_not_flown(self):
        self.assertEqual(oracle.contract_v(flown_in_order=5, not_flown_or_out_of_order=0), 5)
        self.assertEqual(oracle.contract_v(flown_in_order=5, not_flown_or_out_of_order=2), 3)

    def test_perfect_flight_of_the_pilot_with_most_points(self):
        # Qp = 1000 x 6 / 6, Qt = 540.
        self.assertEqual(oracle.q_contract_navigation(6, 6, [0, 0, 0]), 1540)

    def test_a_pilot_with_fewer_points_and_time_errors(self):
        # Qp = 1000 x 3 / 6 = 500; Qt = 540 - (4 + 10 + 180) = 346.
        self.assertEqual(oracle.q_contract_navigation(3, 6, [4, -10, None]), 846)

    def test_declaring_many_points_beats_declaring_none(self):
        many = oracle.q_contract_navigation(oracle.contract_v(6, 0), 6, [0, 0, 0])
        none = oracle.q_contract_navigation(oracle.contract_v(0, 0), 6, [0, 0, 0])
        self.assertEqual((many, none), (1540, 540))
        self.assertEqual(oracle.final_scores([many, none]), [1000, 351])  # 1000 x 540 / 1540 = 350.6


class ObservationNavigationTest(SimpleTestCase):
    def test_hidden_gates_and_time_gates(self):
        # Qh = 3 x 100; Qt = (180 - 0) + (180 - 40) + (180 - 180 capped) = 320.
        self.assertEqual(oracle.q_observation_navigation(3, [0, 40, 500]), 620)

    def test_gates_not_crossed_add_nothing(self):
        self.assertEqual(oracle.q_observation_navigation(2, []), 200)

    def test_speed_term(self):
        self.assertEqual(oracle.q_observation_navigation(0, [], speed_value=200, speed=60, speed_max=80), 150)


class TurnpointHuntTest(SimpleTestCase):
    def test_photos_and_time_gates(self):
        # 4 photos x 100 + 3 gates x 200 + 250 sequence bonus.
        q = oracle.q_turnpoint_hunt([100] * 4, [0, 3, -9], sequence_bonus=250, full_sequence=True)
        self.assertEqual(q, 1250)

    def test_a_timing_error_inside_the_tolerance_costs_nothing(self):
        self.assertEqual(oracle.timing_gate_penalty(8), 0)
        self.assertEqual(oracle.timing_gate_penalty(-10), 0)

    def test_a_timing_error_beyond_the_tolerance_costs_ten_points_per_second_beyond_it(self):
        self.assertEqual(oracle.timing_gate_penalty(25), 150)
        self.assertEqual(oracle.timing_gate_penalty(-25), 150)

    def test_a_gate_not_flown_scores_nothing(self):
        self.assertEqual(oracle.q_turnpoint_hunt([], [0, 0, None]), 400)

    def test_bonus_only_for_the_full_correct_sequence(self):
        self.assertEqual(oracle.q_turnpoint_hunt([100], [0], sequence_bonus=250, full_sequence=False), 300)

    def test_a_wrong_photo_costs_half_its_value_and_the_maximum_duration_ten_points_per_second(self):
        q = oracle.q_turnpoint_hunt([100, 100], [], wrong_photo_values=[100, 60], seconds_over_maximum_duration=7)
        self.assertEqual(q, 200 - 80 - 70)

    def test_limited_fuel_hunt_has_no_sequence_bonus(self):
        q = oracle.q_limited_fuel_turnpoint_hunt([100], [0], sequence_bonus=250, full_sequence=True)
        self.assertEqual(q, 300)

    def test_quarantine_breach_is_a_full_penalty_on_the_score(self):
        qs = [oracle.q_turnpoint_hunt([100] * 3, [0, 0, 0]), oracle.q_turnpoint_hunt([100] * 2, [0, 0, 0])]
        # Qmax is the best Q before percentage penalties: 1000 x 800 / 900 = 888.9.
        self.assertEqual(oracle.final_scores(qs, [[oracle.FULL_PENALTY], []]), [0, 889])


class CircleTest(SimpleTestCase):
    def test_a_perfect_circle_scores_the_maximum(self):
        self.assertEqual(oracle.circle_final_score(500, 500), 250)

    def test_radius_ratio_formula(self):
        # (450 / 500 - 0.5) x 500 = 200
        self.assertEqual(oracle.circle_final_score(450, 500), 200)
        # (400 / 600 - 0.5) x 500 = 83.33
        self.assertEqual(oracle.circle_final_score(400, 600), 83)

    def test_ratio_of_one_half_or_less_scores_zero(self):
        self.assertEqual(oracle.circle_final_score(250, 500), 0)
        self.assertEqual(oracle.circle_final_score(200, 500), 0)

    def test_clockwise_scores_zero(self):
        self.assertEqual(oracle.circle_final_score(500, 500, clockwise=True), 0)

    def test_centre_outside_the_circle_or_start_and_centre_not_overflown_scores_zero(self):
        self.assertEqual(oracle.circle_final_score(500, 500, centre_outside_circle=True), 0)
        self.assertEqual(oracle.circle_final_score(500, 500, start_and_centre_overflown=False), 0)

    def test_leaving_the_radius_limits_scores_zero(self):
        self.assertEqual(oracle.circle_final_score(190, 200), 0)
        self.assertEqual(oracle.circle_final_score(700, 760), 0)
        self.assertEqual(oracle.circle_final_score(200, 200), 250)
        self.assertEqual(oracle.circle_final_score(750, 750), 250)

    def test_altitude_band_exceeded_costs_twenty_percent(self):
        self.assertEqual(oracle.circle_final_score(500, 500, altitude_spread_ft=201), 200)
        self.assertEqual(oracle.circle_final_score(500, 500, altitude_spread_ft=200), 250)

    def test_the_altitude_penalty_is_taken_off_the_formula_score(self):
        # (275 / 500 - 0.5) x 500 = 25, less 20%.
        self.assertEqual(oracle.circle_final_score(275, 500, altitude_spread_ft=300), 20)


class AnrTest(SimpleTestCase):
    def test_perfect_flight(self):
        self.assertEqual(oracle.q_anr(), 2000)
        self.assertEqual(oracle.anr_final_score(oracle.q_anr()), 1000)

    def test_corridor_five_seconds_free_then_three_points_per_full_second(self):
        self.assertEqual(oracle.anr_corridor_penalty(5.9), 0)
        self.assertEqual(oracle.anr_corridor_penalty(6.0), 3)
        self.assertEqual(oracle.anr_corridor_penalty(25.7), 60)

    def test_each_excursion_is_scored_separately(self):
        self.assertEqual(oracle.q_anr(corridor_excursions_s=[10, 4, 8]), 2000 - 15 - 0 - 9)

    def test_sp_and_fp_timing(self):
        self.assertEqual(oracle.anr_time_penalty(1.0), 0)
        self.assertEqual(oracle.anr_time_penalty(-1.0), 0)
        self.assertEqual(oracle.anr_time_penalty(4.5), 9)  # 4 full seconds, one of them free
        self.assertEqual(oracle.anr_time_penalty(500), 200)
        self.assertEqual(oracle.anr_time_penalty(None), 200)

    def test_backtracking_costs_two_hundred_each_and_the_score_is_out_of_two_thousand(self):
        q = oracle.q_anr(sp_error=11, fp_error=None, backtracking_or_circling=1, corridor_excursions_s=[15])
        # 2000 - 30 (corridor) - 30 (SP) - 200 (FP not crossed) - 200 (backtracking)
        self.assertEqual(q, 1540)
        self.assertEqual(oracle.anr_final_score(q), 770)

    def test_the_score_does_not_depend_on_the_other_pilots(self):
        self.assertEqual(oracle.anr_final_score(1000), 500)

    def test_a_full_penalty_scores_zero(self):
        self.assertEqual(oracle.anr_final_score(2000, [oracle.FULL_PENALTY]), 0)


class DurationTest(SimpleTestCase):
    def test_the_longest_flight_scores_the_task_value(self):
        qs = [oracle.q_duration(5400), oracle.q_duration(3600), oracle.q_duration(1800)]
        self.assertEqual(oracle.final_scores(qs), [1000, 667, 333])

    def test_landing_outside_the_area_with_a_briefed_percentage(self):
        qs = [oracle.q_duration(3600), oracle.q_duration(3600)]
        self.assertEqual(oracle.final_scores(qs, [[], [0.5]]), [1000, 500])
