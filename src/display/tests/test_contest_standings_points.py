"""
The overall result of a contest made from standings points (display/services/contest_standings_points.py): the pure
calculation, then the contest, its tasks and its results in the database.
"""

import datetime

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from display.models import (
    Aeroplane,
    Contest,
    ContestSummary,
    ContestTeam,
    Crew,
    Person,
    Task,
    TaskSummary,
    TaskTest,
    Team,
    TeamTestScore,
)
from display.models.contest import default_standings_points_table, validate_points_table
from display.services.contest_standings_points import compute_standings_points, standings_points_details
from display.services.series_standings import LegResults


def leg(task_id, scores, highest_wins=False, registered=()):
    return LegResults(
        contest_id=task_id,
        name=f"Task {task_id}",
        weight=1.0,
        highest_wins=highest_wins,
        scores=scores,
        registered=set(registered) - set(scores),
    )


class TestComputeStandingsPoints(SimpleTestCase):
    def test_each_task_gives_points_for_the_place_and_the_totals_are_added(self):
        legs = [leg(1, {"a": 10, "b": 20, "c": 30}), leg(2, {"a": 5, "b": 1, "c": 9})]
        result = compute_standings_points(legs, [25, 20, 16])
        self.assertEqual(result["totals"], {"a": 25 + 20, "b": 20 + 25, "c": 16 + 16})
        self.assertEqual(result["tasks"][1]["b"], {"place": 2, "points": 20})

    def test_ties_share_a_place_and_the_next_place_is_skipped(self):
        result = compute_standings_points([leg(1, {"a": 10, "b": 10, "c": 20})], [25, 20, 16])
        self.assertEqual(result["tasks"][1]["a"]["place"], 1)
        self.assertEqual(result["tasks"][1]["b"]["place"], 1)
        self.assertEqual(result["tasks"][1]["c"], {"place": 3, "points": 16})
        self.assertEqual(result["totals"], {"a": 25, "b": 25, "c": 16})

    def test_a_team_without_a_result_gets_nothing_for_the_task(self):
        legs = [leg(1, {"a": 10, "b": 20}), leg(2, {"a": 5}, registered=["a", "b"])]
        result = compute_standings_points(legs, [25, 20])
        self.assertEqual(result["totals"], {"a": 25 + 25, "b": 20 + 0})
        self.assertNotIn("b", result["tasks"][2])

    def test_tasks_are_ranked_by_their_own_direction(self):
        legs = [leg(1, {"a": 10, "b": 20}, highest_wins=False), leg(2, {"a": 10, "b": 20}, highest_wins=True)]
        result = compute_standings_points(legs, [25, 20])
        self.assertEqual(result["tasks"][1]["a"]["place"], 1)
        self.assertEqual(result["tasks"][2]["b"]["place"], 1)
        self.assertEqual(result["totals"], {"a": 45, "b": 45})

    def test_places_beyond_a_short_table_give_nothing(self):
        result = compute_standings_points([leg(1, {"a": 1, "b": 2, "c": 3, "d": 4})], [5, 3])
        self.assertEqual(result["totals"], {"a": 5, "b": 3, "c": 0, "d": 0})

    def test_equal_totals_are_separated_by_countback(self):
        # x: first and third, y: two seconds, z: third and first. 10 + 4 = 7 + 7 would need a table that adds up
        legs = [leg(1, {"x": 1, "y": 2, "z": 3}), leg(2, {"z": 1, "y": 2, "x": 3})]
        result = compute_standings_points(legs, [10, 7, 4])
        self.assertEqual(result["totals"], {"x": 14, "y": 14, "z": 14})
        self.assertEqual(result["ranks"]["y"], 3, "y has no first place")
        self.assertEqual((result["ranks"]["x"], result["ranks"]["z"]), (1, 1), "level on everything shares the rank")

    def test_nothing_without_tasks(self):
        self.assertEqual(compute_standings_points([], [25]), {"totals": {}, "ranks": {}, "tasks": {}})


class TestPointsTableValidation(SimpleTestCase):
    def test_a_list_of_non_negative_numbers_is_valid(self):
        validate_points_table([25, 20.5, 0])
        validate_points_table([])

    def test_anything_else_is_not(self):
        for table in (None, "25,20", [25, -1], [25, "20"], [True], {"a": 1}):
            with self.assertRaises(ValidationError, msg=repr(table)):
                validate_points_table(table)


def make_team(index):
    pilot = Person.objects.create(first_name=f"Pilot{index}", last_name="Test", email=f"p{index}@example.com")
    crew = Crew.objects.create(member1=pilot)
    aeroplane = Aeroplane.objects.create(registration=f"LN-{index:03d}")
    return Team.objects.create(crew=crew, aeroplane=aeroplane)


class TestContestOverallResult(TestCase):
    def setUp(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        self.contest = Contest.objects.create(
            name="Race",
            start_time=now,
            finish_time=now + datetime.timedelta(days=1),
            location="60, 11",
            summary_score_sorting_direction=Contest.ASCENDING,
            is_public=True,
        )
        self.teams = [make_team(i) for i in range(3)]
        for team in self.teams:
            ContestTeam.objects.create(contest=self.contest, team=team)
        # Task 1: lowest wins. Task 2: highest wins
        self.tests = []
        for index, direction in enumerate((Task.ASCENDING, Task.DESCENDING), start=1):
            task = Task.objects.create(
                contest=self.contest, name=f"T{index}", heading=f"T{index}", index=index, summary_score_sorting_direction=direction
            )
            self.tests.append(TaskTest.objects.create(task=task, name="Test", heading="Test", index=0))

    def put(self, team, task_index, points):
        TeamTestScore.objects.update_or_create(team=team, task_test=self.tests[task_index], defaults={"points": points})

    def overall(self):
        return {summary.team_id: summary.points for summary in ContestSummary.objects.filter(contest=self.contest)}

    def fill(self):
        a, b, c = self.teams
        for team, first, second in ((a, 10, 100), (b, 20, 300), (c, 30, 200)):
            self.put(team, 0, first)
            self.put(team, 1, second)
        return a, b, c

    def use_standings_points(self, table=None):
        self.contest.overall_result_method = Contest.STANDINGS_POINTS
        if table is not None:
            self.contest.standings_points_table = table
        self.contest.save()

    def test_a_contest_left_on_the_default_sums_the_task_scores(self):
        a, b, c = self.fill()
        self.assertEqual(self.contest.overall_result_method, Contest.SUM_OF_SCORES)
        self.assertEqual(self.contest.standings_points_table, default_standings_points_table())
        self.assertEqual(self.overall(), {a.pk: 110, b.pk: 320, c.pk: 230})
        self.assertEqual(self.contest.overall_sorting_direction, Contest.ASCENDING)
        self.assertIsNone(standings_points_details(self.contest))

    def test_standings_points_are_the_sum_of_the_points_for_the_place_in_each_task(self):
        a, b, c = self.fill()
        self.use_standings_points()
        # Task 1 (lowest wins): a, b, c. Task 2 (highest wins): b, c, a
        self.assertEqual(self.overall(), {a.pk: 25 + 16, b.pk: 20 + 25, c.pk: 16 + 20})
        self.assertEqual(self.contest.overall_sorting_direction, Contest.DESCENDING)

    def test_changing_one_score_changes_the_points_of_the_other_teams(self):
        a, b, c = self.fill()
        self.use_standings_points()
        self.put(c, 0, 5)  # c is now first in task 1; a and b drop one place
        self.assertEqual(self.overall(), {a.pk: 20 + 16, b.pk: 16 + 25, c.pk: 25 + 20})

    def test_a_new_result_creates_the_overall_result_of_a_team_and_a_missing_result_gives_nothing(self):
        a, b, c = self.teams
        self.use_standings_points()
        self.put(a, 0, 10)
        self.put(b, 0, 20)
        self.assertEqual(self.overall(), {a.pk: 25, b.pk: 20})
        self.put(c, 1, 50)  # c only has a result in task 2
        self.assertEqual(self.overall(), {a.pk: 25, b.pk: 20, c.pk: 25})

    def test_switching_the_method_recomputes_both_ways(self):
        a, b, c = self.fill()
        self.use_standings_points()
        self.assertEqual(self.overall()[a.pk], 41)
        self.contest.overall_result_method = Contest.SUM_OF_SCORES
        self.contest.save()
        self.assertEqual(self.overall(), {a.pk: 110, b.pk: 320, c.pk: 230})
        self.assertEqual(self.contest.overall_sorting_direction, Contest.ASCENDING)

    def test_changing_the_table_recomputes(self):
        a, b, c = self.fill()
        self.use_standings_points([10, 5])
        self.assertEqual(self.overall(), {a.pk: 10 + 0, b.pk: 5 + 10, c.pk: 0 + 5})
        self.contest.standings_points_table = [3, 2, 1]
        self.contest.save()
        self.assertEqual(self.overall(), {a.pk: 3 + 1, b.pk: 2 + 3, c.pk: 1 + 2})

    def test_deleting_a_task_removes_its_points(self):
        a, b, c = self.fill()
        self.use_standings_points()
        Task.objects.get(contest=self.contest, name="T2").delete()
        self.assertEqual(self.overall(), {a.pk: 25, b.pk: 20, c.pk: 16})

    def test_a_manually_edited_summary_is_left_alone_without_autosum(self):
        self.contest.autosum_scores = False
        self.contest.save()
        self.use_standings_points()
        a, b, c = self.teams
        ContestSummary.objects.create(contest=self.contest, team=a, points=7)
        self.put(a, 0, 10)
        self.assertEqual(self.overall(), {a.pk: 7})

    def test_the_results_carry_places_points_and_the_descending_order(self):
        a, b, c = self.fill()
        self.use_standings_points()
        data = APIClient().get(reverse("contests-results-details", kwargs={"pk": self.contest.pk})).json()
        self.assertEqual(data["overall_result_method"], "standings_points")
        self.assertEqual(data["summary_score_sorting_direction"], "desc")
        details = data["standings_points"]
        self.assertEqual(details["points_table"], default_standings_points_table())
        task_two = Task.objects.get(contest=self.contest, name="T2").pk
        self.assertEqual(details["tasks"][str(task_two)][str(b.pk)], {"place": 1, "points": 25})
        self.assertEqual(details["ranks"][str(b.pk)], 1)

    def test_the_results_of_a_default_contest_are_unchanged_apart_from_the_new_fields(self):
        self.fill()
        data = APIClient().get(reverse("contests-results-details", kwargs={"pk": self.contest.pk})).json()
        self.assertEqual(data["summary_score_sorting_direction"], "asc")
        self.assertIsNone(data["standings_points"])
        self.assertEqual(data["overall_result_method"], "sum_of_scores")

    def test_a_task_summary_exists_per_team_and_task(self):
        self.fill()
        self.assertEqual(TaskSummary.objects.filter(task__contest=self.contest).count(), 6)
