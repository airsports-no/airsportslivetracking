"""
The "Air Sports Race 2025 (Annex 9)" scorecard holds the navigation penalties of FAI Sporting Code Section 10, Annex 9,
table 6.7.5, and is the scorecard a new Air Sports Race task gets unless the organiser picks another one.
"""

import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from display.default_scorecards.create_scorecards import create_scorecards
from display.default_scorecards.default_scorecard_airsports import get_default_scorecard as get_previous_scorecard
from display.default_scorecards.default_scorecard_airsports_2025 import SHORTCUT_NAME, get_default_scorecard
from display.utilities.gate_definitions import FINISHPOINT, SECRETPOINT, STARTINGPOINT, TAKEOFF_GATE, TURNPOINT
from display.utilities.navigation_task_type_definitions import AIRSPORTS, DEFAULT_SCORECARD_SHORTCUT_NAMES

PLANNED = datetime.datetime(2025, 6, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)


def _crossing(seconds_late: float) -> datetime.datetime:
    return PLANNED + datetime.timedelta(seconds=seconds_late)


class TestAirSportsRace2025Scorecard(TestCase):
    def setUp(self):
        self.scorecard = get_default_scorecard()

    def test_known_gates_cost_two_points_per_second_after_two_seconds(self):
        for gate_type in (STARTINGPOINT, TURNPOINT, FINISHPOINT):
            with self.subTest(gate_type=gate_type):
                self.assertEqual(
                    0, self.scorecard.get_gate_timing_score_for_gate_type(gate_type, PLANNED, _crossing(1.9))
                )
                self.assertEqual(
                    0, self.scorecard.get_gate_timing_score_for_gate_type(gate_type, PLANNED, _crossing(-1.9))
                )
                self.assertEqual(
                    6, self.scorecard.get_gate_timing_score_for_gate_type(gate_type, PLANNED, _crossing(5))
                )
                self.assertEqual(
                    6, self.scorecard.get_gate_timing_score_for_gate_type(gate_type, PLANNED, _crossing(-5))
                )
                self.assertEqual(
                    200, self.scorecard.get_gate_timing_score_for_gate_type(gate_type, PLANNED, _crossing(500))
                )
                self.assertEqual(200, self.scorecard.get_gate_timing_score_for_gate_type(gate_type, PLANNED, None))

    def test_hidden_gates_cost_one_point_per_second_and_at_most_100(self):
        self.assertEqual(0, self.scorecard.get_gate_timing_score_for_gate_type(SECRETPOINT, PLANNED, _crossing(1.9)))
        self.assertEqual(3, self.scorecard.get_gate_timing_score_for_gate_type(SECRETPOINT, PLANNED, _crossing(5)))
        self.assertEqual(100, self.scorecard.get_gate_timing_score_for_gate_type(SECRETPOINT, PLANNED, _crossing(500)))
        self.assertEqual(100, self.scorecard.get_gate_timing_score_for_gate_type(SECRETPOINT, PLANNED, None))

    def test_takeoff_is_free_from_three_seconds_early_to_a_minute_late(self):
        self.assertEqual(0, self.scorecard.get_gate_timing_score_for_gate_type(TAKEOFF_GATE, PLANNED, _crossing(-2.9)))
        self.assertEqual(0, self.scorecard.get_gate_timing_score_for_gate_type(TAKEOFF_GATE, PLANNED, _crossing(59)))
        self.assertEqual(200, self.scorecard.get_gate_timing_score_for_gate_type(TAKEOFF_GATE, PLANNED, _crossing(-10)))
        self.assertEqual(200, self.scorecard.get_gate_timing_score_for_gate_type(TAKEOFF_GATE, PLANNED, _crossing(90)))

    def test_corridor_and_penalty_zone_cost_one_point_per_second_without_a_maximum(self):
        self.assertEqual(1, self.scorecard.corridor_outside_penalty)
        self.assertEqual(5, self.scorecard.corridor_grace_time)
        self.assertEqual(0, self.scorecard.corridor_maximum_penalty)
        enter = PLANNED
        self.assertEqual(0, self.scorecard.calculate_penalty_zone_score(enter, _crossing(5)))
        self.assertEqual(295, self.scorecard.calculate_penalty_zone_score(enter, _crossing(300)))

    def test_prohibited_zone_and_backtracking_cost_100(self):
        self.assertEqual(100, self.scorecard.prohibited_zone_penalty)
        self.assertEqual(5, self.scorecard.prohibited_zone_grace_time)
        self.assertEqual(100, self.scorecard.backtracking_penalty)
        self.assertEqual(100, self.scorecard.backtracking_maximum_penalty)
        self.assertEqual(5, self.scorecard.backtracking_grace_time_seconds)

    def test_fewest_penalties_win(self):
        self.assertEqual("asc", self.scorecard.score_sorting_direction)

    def test_the_previous_scorecard_is_left_as_it_was(self):
        previous = get_previous_scorecard()
        self.assertNotEqual(previous.pk, self.scorecard.pk)
        self.assertEqual(200, previous.prohibited_zone_penalty)
        self.assertEqual(1, previous.get_gate_scorecard(TURNPOINT).graceperiod_after)

    def test_creating_it_again_updates_the_same_scorecard(self):
        self.assertEqual(self.scorecard.pk, get_default_scorecard().pk)


class TestAirSportsRaceDefaultScorecard(TestCase):
    def setUp(self):
        create_scorecards()
        self.client = APIClient()
        self.client.force_authenticate(get_user_model().objects.create(email="air-sports-race-default@example.com"))

    def test_it_is_the_default_of_the_family(self):
        self.assertEqual(SHORTCUT_NAME, DEFAULT_SCORECARD_SHORTCUT_NAMES[AIRSPORTS])

    def test_the_picker_lists_it_first_and_keeps_the_others(self):
        response = self.client.get(f"/api/v1/scorecards/choices/?task_type={AIRSPORTS}")
        self.assertEqual(response.status_code, 200, response.content)
        shortcut_names = [entry["shortcut_name"] for entry in response.json()]
        self.assertEqual(SHORTCUT_NAME, shortcut_names[0])
        self.assertIn("Air Sports Race", shortcut_names)
        self.assertIn("Nordic Air Sports Race", shortcut_names)
