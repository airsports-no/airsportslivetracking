"""
Regression test for REST API finding #14 (2026-08-28 review): TaskSerialiser/TaskTestSerialiser
are fields = "__all__", including the contest/task FK, with no perform_create pinning and no
cross-contest validation. An organiser with change_contest on contest A could create or move a
task into contest B by supplying {"contest": B}, or attach/move a TaskTest onto a task in
contest B by supplying {"task": <id in contest B>}.
"""

import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from guardian.shortcuts import assign_perm
from rest_framework import status
from rest_framework.test import APITestCase

from display.models import Contest, Task, TaskTest


class TestTaskCrossContestWrites(APITestCase):
    def setUp(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        self.own_contest = Contest.objects.create(
            name="Own Contest", start_time=now, finish_time=now + datetime.timedelta(hours=1), location="60.0,11.0"
        )
        self.foreign_contest = Contest.objects.create(
            name="Foreign Contest", start_time=now, finish_time=now + datetime.timedelta(hours=1), location="60.0,11.0"
        )
        self.own_task = Task.objects.create(contest=self.own_contest, name="own-task", heading="Own Task")
        self.foreign_task = Task.objects.create(contest=self.foreign_contest, name="foreign-task", heading="Foreign Task")

        self.organizer = get_user_model().objects.create(email="organizer@example.com")
        assign_perm("view_contest", self.organizer, self.own_contest)
        assign_perm("change_contest", self.organizer, self.own_contest)
        self.client.force_login(user=self.organizer)

    def test_create_task_ignores_client_supplied_contest(self):
        url = reverse("tasks-list", kwargs={"contest_pk": self.own_contest.pk})
        response = self.client.post(url, data={"contest": self.foreign_contest.pk, "name": "sneaky", "heading": "Sneaky"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created = Task.objects.get(pk=response.json()["id"])
        self.assertEqual(created.contest_id, self.own_contest.pk)

    def test_update_task_cannot_move_it_to_another_contest(self):
        url = reverse("tasks-detail", kwargs={"contest_pk": self.own_contest.pk, "pk": self.own_task.pk})
        response = self.client.patch(url, data={"contest": self.foreign_contest.pk}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.own_task.refresh_from_db()
        self.assertEqual(self.own_task.contest_id, self.own_contest.pk)

    def test_create_task_test_rejects_task_from_another_contest(self):
        url = reverse("tasktests-list", kwargs={"contest_pk": self.own_contest.pk})
        response = self.client.post(url, data={"task": self.foreign_task.pk, "name": "sneaky-test", "heading": "Sneaky Test"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(TaskTest.objects.filter(task=self.foreign_task).exists())

    def test_update_task_test_rejects_moving_to_task_in_another_contest(self):
        own_task_test = TaskTest.objects.create(task=self.own_task, name="own-test", heading="Own Test")
        url = reverse("tasktests-detail", kwargs={"contest_pk": self.own_contest.pk, "pk": own_task_test.pk})
        response = self.client.patch(url, data={"task": self.foreign_task.pk}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        own_task_test.refresh_from_db()
        self.assertEqual(own_task_test.task_id, self.own_task.pk)
