"""
The own score on the Now endpoint says what it is out of and whether it can still fall (CIMA tasks), so the phone app
can show "874 of 1000" and a "Provisional" note. The values come from the functions the contest results use.
"""

from unittest.mock import patch

from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from display.models import ContestantTrack
from display.models.my_user import MyUser
from display.tests.test_task_scoring import TaskScoringTestCase
from display.utilities.task_types import CIRCLE, PRECISION_NAVIGATION

KEYS = ("score_scale", "scores_provisional", "provisional_explanation")


class TestScoreScaleOnTheNowEndpoint(TaskScoringTestCase):
    task_subtype = PRECISION_NAVIGATION

    def setUp(self):
        super().setUp()
        self.user = MyUser.objects.create(username="now-pilot", email="now-pilot@example.com")
        self.contest.is_public = True
        self.contest.save()
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def now_entry(self, contestant):
        contestant.navigation_task.show_live_score_in_app = True
        contestant.navigation_task.is_public = True
        contestant.navigation_task.save()
        contestant.refresh_from_db()
        with patch(
            "display.viewsets.Contestant.get_contestant_for_device_at_time", return_value=[(contestant, False)]
        ):
            response = self.client.get("/api/v1/userprofile/get_current_app_navigation_task/")
        self.assertEqual(200, response.status_code)
        return response.json()[0]["active_contestants"][0]

    def test_a_best_in_task_cima_score_is_out_of_the_task_value_and_provisional_until_every_flight_is_finished(self):
        a, b, _ = self.contestants
        self.fly(a, 1200)
        self.fly(b, 1200, {"points": -300})
        entry = self.now_entry(b)
        self.assertEqual(750, entry["score"])
        self.assertEqual(1000, entry["score_scale"])
        self.assertTrue(entry["scores_provisional"])
        self.assertIn("Provisional", entry["provisional_explanation"])
        ContestantTrack.objects.filter(contestant__navigation_task=self.task).update(calculator_finished=True)
        entry = self.now_entry(b)
        self.assertEqual(1000, entry["score_scale"])
        self.assertFalse(entry["scores_provisional"])
        self.assertIsNone(entry["provisional_explanation"])

    def test_a_circle_task_is_out_of_250_and_never_provisional(self):
        circle = self.make_task(CIRCLE)
        contestant = self.make_contestant(circle)
        ContestantTrack.objects.filter(contestant=contestant).update(score=240)
        entry = self.now_entry(contestant)
        self.assertEqual(240, entry["score"])
        self.assertEqual(250, entry["score_scale"])
        self.assertFalse(entry["scores_provisional"])
        self.assertIsNone(entry["provisional_explanation"])

    def test_a_legacy_task_has_no_scale_and_is_not_provisional(self):
        legacy = self.make_task(None)
        contestant = self.make_contestant(legacy)
        ContestantTrack.objects.filter(contestant=contestant).update(score=42)
        entry = self.now_entry(contestant)
        self.assertEqual(42, entry["score"])
        self.assertEqual(
            {"score_scale": None, "scores_provisional": False, "provisional_explanation": None},
            {key: entry[key] for key in KEYS},
        )

    def test_a_contestant_without_a_track_has_no_scale_and_is_not_provisional(self):
        a, _, _ = self.contestants
        ContestantTrack.objects.filter(contestant=a).delete()
        entry = self.now_entry(a)
        self.assertIsNone(entry["score"])
        self.assertEqual(
            {"score_scale": None, "scores_provisional": False, "provisional_explanation": None},
            {key: entry[key] for key in KEYS},
        )

    def test_the_fields_cost_at_most_two_queries_and_none_for_a_legacy_task(self):
        legacy = self.make_task(None)
        legacy_contestant = self.make_contestant(legacy)
        ContestantTrack.objects.filter(contestant=legacy_contestant).update(score=1)
        a, _, _ = self.contestants
        self.fly(a, 1200)
        from display.viewsets import score_context_for

        for contestant, maximum in ((legacy_contestant, 0), (a, 2)):
            contestant.refresh_from_db()
            contestant.navigation_task.scorecard  # loaded by the request already
            with CaptureQueriesContext(connection) as queries:
                score_context_for(contestant, 1, {})
            self.assertLessEqual(len(queries), maximum, [q["sql"] for q in queries])
