"""
Regression test for REST API finding #8 (2026-08-28 review): ScorecardNestedSerialiser.update
persisted the scorecard via Scorecard.objects.filter(pk=instance.pk).update(**validated_data),
which doesn't emit pre_save/post_save, so two signals never ran when a scorecard was edited via
the API: update_contestant_initial_score (propagates an initial_score delta onto every
contestant's live score) and sync_scorecard_sorting_direction (mirrors score_sorting_direction
onto the linked TaskTest/Task, used by the results table). The admin/form path (which goes
through save()) was unaffected.
"""

import datetime

from django.test import TestCase

from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
from display.models import Aeroplane, Contest, Contestant, Crew, NavigationTask, Person, Route, Team
from display.serialisers import ScorecardNestedSerialiser


class TestScorecardUpdateSignals(TestCase):
    def setUp(self):
        self.contest = Contest.objects.create(
            name="Scorecard Signal Contest",
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1),
            location="60, 11",
        )
        route = Route.objects.create(name="Route")
        now = datetime.datetime.now(datetime.timezone.utc)
        self.navigation_task = NavigationTask.create(
            name="Scorecard Signal Task",
            original_scorecard=get_default_scorecard(),
            route=route,
            contest=self.contest,
            start_time=now,
            finish_time=now + datetime.timedelta(days=1),
        )
        crew = Crew.objects.create(member1=Person.objects.create(first_name="A", last_name="B", email="scorecard@example.com"))
        team = Team.objects.create(crew=crew, aeroplane=Aeroplane.objects.create(registration="LN-SCS"))
        self.contestant = Contestant.objects.create(
            team=team,
            navigation_task=self.navigation_task,
            takeoff_time=now + datetime.timedelta(hours=1),
            finished_by_time=now + datetime.timedelta(hours=2),
            tracker_start_time=now + datetime.timedelta(minutes=30),
            tracker_device_id="test_device",
            contestant_number=1,
        )

    def test_update_propagates_initial_score_delta_to_contestants(self):
        scorecard = self.navigation_task.scorecard
        original_initial_score = scorecard.initial_score
        self.assertEqual(self.contestant.contestanttrack.score, 0)

        ScorecardNestedSerialiser().update(scorecard, {"initial_score": original_initial_score + 25, "gate_scores": []})

        self.contestant.contestanttrack.refresh_from_db()
        self.assertEqual(self.contestant.contestanttrack.score, 25)

    def test_update_syncs_sorting_direction_to_linked_task_test(self):
        scorecard = self.navigation_task.scorecard
        tasktest = self.navigation_task.tasktest
        opposite_direction = "desc" if scorecard.score_sorting_direction == "asc" else "asc"
        self.assertNotEqual(tasktest.sorting, opposite_direction)

        ScorecardNestedSerialiser().update(scorecard, {"score_sorting_direction": opposite_direction, "gate_scores": []})

        tasktest.refresh_from_db()
        tasktest.task.refresh_from_db()
        self.assertEqual(tasktest.sorting, opposite_direction)
        self.assertEqual(tasktest.task.summary_score_sorting_direction, opposite_direction)
