"""
Regression test for REST API finding #4 (2026-08-28 review): ContestViewSet.update_task_summary
and update_test_result authorized against contest X via get_object(), then wrote from raw
request data (task/task_test ids) with no validation those objects belong to contest X. An
organiser of ANY contest (holding change_contest only on their own contest) could overwrite
another contest's published results/scores by supplying a foreign task/task_test id - unlike the
sibling update_contest_summary, which correctly pins contest=contest.
"""

import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from guardian.shortcuts import assign_perm
from rest_framework import status
from rest_framework.test import APITestCase

from display.models import Contest, Task, TaskSummary, TaskTest, TeamTestScore


class TestTaskSummaryCrossContestWrite(APITestCase):
    def setUp(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        self.own_contest = Contest.objects.create(
            name="Own Contest",
            start_time=now,
            finish_time=now + datetime.timedelta(hours=1),
            location="60.0,11.0",
        )
        self.foreign_contest = Contest.objects.create(
            name="Foreign Contest",
            start_time=now,
            finish_time=now + datetime.timedelta(hours=1),
            location="60.0,11.0",
        )
        self.foreign_task = Task.objects.create(contest=self.foreign_contest, name="foreign-task", heading="Foreign Task")
        self.foreign_task_test = TaskTest.objects.create(task=self.foreign_task, name="foreign-test", heading="Foreign Test")

        self.organizer = get_user_model().objects.create(email="organizer@example.com")
        assign_perm("view_contest", self.organizer, self.own_contest)
        assign_perm("change_contest", self.organizer, self.own_contest)
        self.client.force_login(user=self.organizer)

    def test_update_task_summary_rejects_task_from_another_contest(self):
        url = reverse("contests-update-task-summary", kwargs={"pk": self.own_contest.pk})
        response = self.client.put(url, data={"team": 1, "task": self.foreign_task.pk, "points": 99}, format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(TaskSummary.objects.filter(task=self.foreign_task).exists())

    def test_update_test_result_rejects_task_test_from_another_contest(self):
        url = reverse("contests-update-test-result", kwargs={"pk": self.own_contest.pk})
        response = self.client.put(url, data={"team": 1, "task_test": self.foreign_task_test.pk, "points": 99}, format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(TeamTestScore.objects.filter(task_test=self.foreign_task_test).exists())
