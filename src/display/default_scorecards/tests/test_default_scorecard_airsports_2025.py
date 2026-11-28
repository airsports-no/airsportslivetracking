"""
The "Air Sports Race 2025 (Annex 9)" scorecard holds the navigation penalties of FAI Sporting Code Section 10, Annex 9,
table 6.7.5, and is the scorecard a new Air Sports Race task gets unless the organiser picks another one.
"""

import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from display.default_scorecards.create_scorecards import create_scorecards
from display.default_scorecards.default_scorecard_airsport_challenge import (
    get_default_scorecard as get_challenge_2023_scorecard,
)
from display.default_scorecards.default_scorecard_airsports import get_default_scorecard as get_previous_scorecard
from display.default_scorecards.default_scorecard_airsports_2025 import (
    CHALLENGE_SHORTCUT_NAME,
    SHORTCUT_NAME,
    get_airsport_challenge_scorecard,
    get_default_scorecard,
)
from display.models import Contest, EditableRoute, NavigationTask, Scorecard
from display.utilities.gate_definitions import FINISHPOINT, SECRETPOINT, STARTINGPOINT, TAKEOFF_GATE, TURNPOINT
from display.utilities.task_types import (
    AIRSPORT_CHALLENGE,
    AIRSPORTS,
    DEFAULT_SCORECARD_SHORTCUT_NAMES,
    get_calculators_for_task,
    validate_subtype_family_compatibility,
)

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


class TestAirSportChallenge2025Scorecard(TestCase):
    def setUp(self):
        self.scorecard = get_airsport_challenge_scorecard()

    def test_it_is_a_scorecard_of_the_challenge_family(self):
        self.assertEqual([AIRSPORT_CHALLENGE], self.scorecard.task_type)
        self.assertEqual(AIRSPORT_CHALLENGE, self.scorecard.calculator)
        self.assertEqual(CHALLENGE_SHORTCUT_NAME, self.scorecard.shortcut_name)

    def test_it_holds_the_same_rules_as_the_air_sports_race_scorecard(self):
        race = get_default_scorecard()
        self.assertNotEqual(race.pk, self.scorecard.pk)
        self.assertEqual(race.config["gates"], self.scorecard.config["gates"])
        for field in (
            "score_sorting_direction",
            "backtracking_penalty",
            "backtracking_maximum_penalty",
            "corridor_outside_penalty",
            "corridor_grace_time",
            "corridor_maximum_penalty",
            "penalty_zone_penalty_per_second",
            "penalty_zone_maximum",
            "prohibited_zone_penalty",
        ):
            with self.subTest(field=field):
                self.assertEqual(getattr(race, field), getattr(self.scorecard, field))

    def test_takeoff_allows_three_seconds_early(self):
        self.assertEqual(0, self.scorecard.get_gate_timing_score_for_gate_type(TAKEOFF_GATE, PLANNED, _crossing(-2.9)))
        self.assertEqual(200, self.scorecard.get_gate_timing_score_for_gate_type(TAKEOFF_GATE, PLANNED, _crossing(-10)))

    def test_creating_it_again_updates_the_same_scorecard(self):
        self.assertEqual(self.scorecard.pk, get_airsport_challenge_scorecard().pk)

    def test_the_older_scorecard_is_left_as_it_was(self):
        older = get_challenge_2023_scorecard()
        self.assertNotEqual(older.pk, self.scorecard.pk)
        self.assertEqual("Air Sport Challenge 2023", older.name)
        self.assertEqual([AIRSPORT_CHALLENGE], older.task_type)
        self.assertEqual(200, older.prohibited_zone_penalty)
        self.assertEqual(0, older.get_gate_scorecard(TAKEOFF_GATE).graceperiod_before)


class TestAirSportChallengeDefaultScorecard(TestCase):
    def setUp(self):
        create_scorecards()
        self.client = APIClient()
        self.client.force_authenticate(get_user_model().objects.create(email="air-sport-challenge-default@example.com"))

    def test_it_is_the_default_of_the_family(self):
        self.assertEqual(CHALLENGE_SHORTCUT_NAME, DEFAULT_SCORECARD_SHORTCUT_NAMES[AIRSPORT_CHALLENGE])

    def test_the_picker_lists_it_first_and_keeps_the_older_one(self):
        response = self.client.get(f"/api/v1/scorecards/choices/?task_type={AIRSPORT_CHALLENGE}")
        self.assertEqual(response.status_code, 200, response.content)
        shortcut_names = [entry["shortcut_name"] for entry in response.json()]
        self.assertEqual(CHALLENGE_SHORTCUT_NAME, shortcut_names[0])
        self.assertIn("AirSport Challenge", shortcut_names)

    def test_the_picker_for_air_sports_race_does_not_offer_it(self):
        response = self.client.get(f"/api/v1/scorecards/choices/?task_type={AIRSPORTS}")
        self.assertNotIn(CHALLENGE_SHORTCUT_NAME, [entry["shortcut_name"] for entry in response.json()])


class TestAirSportChallengeTasksAndScorecards(TestCase):
    def setUp(self):
        create_scorecards()
        user = get_user_model().objects.create(email="air-sport-challenge-tasks@example.com")
        self.contest = Contest.objects.create(
            name="Challenge contest",
            time_zone="Europe/Oslo",
            start_time=PLANNED,
            finish_time=PLANNED + datetime.timedelta(hours=8),
            location="60.0,11.0",
            created_by=user,
        )
        with open("display/tests/NM.csv", "r") as file:
            self.editable_route, _ = EditableRoute.create_from_csv("ChallengeRoute", file.readlines()[1:])

    def make_task(self, name: str, shortcut_name: str, task_subtype=None):
        scorecard = Scorecard.get_originals().get(shortcut_name=shortcut_name)
        return NavigationTask.create(
            name=name,
            contest=self.contest,
            route=self.editable_route.create_airsports_route(False, scorecard),
            original_scorecard=scorecard,
            start_time=PLANNED,
            finish_time=PLANNED + datetime.timedelta(hours=8),
            task_subtype=task_subtype,
        )

    def test_a_new_task_made_from_the_family_default_has_the_annex_9_scorecard(self):
        task = self.make_task("New", DEFAULT_SCORECARD_SHORTCUT_NAMES[AIRSPORT_CHALLENGE])
        self.assertEqual("Air Sport Challenge 2025 (Annex 9)", task.original_scorecard.name)
        self.assertEqual(AIRSPORT_CHALLENGE, task.coarse_task_family)
        self.assertEqual(200, task.scorecard.get_gate_scorecard(TURNPOINT).maximum_penalty)
        self.assertEqual(3, task.scorecard.get_gate_scorecard(TAKEOFF_GATE).graceperiod_before)

    def test_a_task_made_from_the_older_scorecard_keeps_it(self):
        task = self.make_task("Older", "AirSport Challenge")
        self.assertEqual("Air Sport Challenge 2023", task.original_scorecard.name)
        self.assertEqual(0, task.scorecard.get_gate_scorecard(TAKEOFF_GATE).graceperiod_before)
        # Creating the scorecards again (a deployment) leaves the task as it was
        create_scorecards()
        task.refresh_from_db()
        self.assertEqual("Air Sport Challenge 2023", task.original_scorecard.name)
        self.assertEqual(0, task.scorecard.get_gate_scorecard(TAKEOFF_GATE).graceperiod_before)

    def test_both_scorecards_run_the_same_calculators(self):
        new = self.make_task("New", CHALLENGE_SHORTCUT_NAME)
        older = self.make_task("Older", "AirSport Challenge")
        self.assertEqual(get_calculators_for_task(new), get_calculators_for_task(older))

    def test_the_challenge_task_type_is_valid_for_the_scorecard(self):
        validate_subtype_family_compatibility("legacy_airsport_challenge", AIRSPORT_CHALLENGE)
        task = self.make_task("Typed", CHALLENGE_SHORTCUT_NAME, task_subtype="legacy_airsport_challenge")
        self.assertEqual("legacy_airsport_challenge", task.task_subtype)
