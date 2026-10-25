"""
Deleting a contest that has navigation tasks. Its navigation tasks' own pre_delete signal removes their results task, and
the results signals then looked the already deleted task up again: DELETE /api/v1/contests/{pk}/ answered 500 (Task
matching query does not exist) for every contest with a navigation task.
"""

import datetime
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
from display.models import Contest, NavigationTask, Route
from display.models.scoring_table_models import Task, TaskTest
from utilities.mock_utilities import TraccarMock


@patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
@patch("display.signals.get_traccar_instance", return_value=TraccarMock)
class TestContestDeleteWithNavigationTasks(APITestCase):
    def make_contest(self, name, tasks):
        contest = Contest.objects.create(
            name=name,
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1),
            location="60, 11",
        )
        now = datetime.datetime.now(datetime.timezone.utc)
        for index in range(tasks):
            NavigationTask.create(
                name=f"{name} task {index}",
                original_scorecard=get_default_scorecard(),
                route=Route.objects.create(name=f"Route {name} {index}"),
                contest=contest,
                start_time=now,
                finish_time=now + datetime.timedelta(days=1),
            )
        return contest

    def test_a_contest_with_navigation_tasks_can_be_deleted(self, *args):
        contest = self.make_contest("Doomed", tasks=2)
        self.assertEqual(TaskTest.objects.filter(task__contest=contest).count(), 2)
        contest.delete()
        self.assertFalse(Contest.objects.filter(pk=contest.pk).exists())
        self.assertFalse(NavigationTask.objects.filter(name__startswith="Doomed").exists())
        self.assertFalse(Task.objects.filter(contest_id=contest.pk).exists())

    def test_the_rest_endpoint_deletes_it_too(self, *args):
        contest = self.make_contest("Doomed by API", tasks=1)
        user = get_user_model().objects.create(email="contest-deleter@example.com", is_superuser=True, is_staff=True)
        self.client.force_login(user=user)
        response = self.client.delete(reverse("contests-detail", kwargs={"pk": contest.pk}))
        self.assertEqual(response.status_code, 204, getattr(response, "content", b"")[:300])
        self.assertFalse(Contest.objects.filter(pk=contest.pk).exists())
