"""
Regression test for a SEVERE finding (2026-08-28 review, templates section finding #6):
navigation_task_view_detailed_score (the /scoredetails/ page) had no permission decorator at
all, unlike every neighboring scorecard view (navigation_task_restore_original_scorecard_view,
navigation_task_scorecard_override_view, navigation_task_gatescore_override_view) and unlike its
own parent page (NavigationTaskDetailView, which links to it and already requires
display.view_contest with no public-visibility bypass). Anyone, unauthenticated, could read the
navigation task name, contest name, and full scoring configuration of a private/unlisted contest.
"""

import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from guardian.shortcuts import assign_perm

from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
from display.models import Contest, NavigationTask, Route


class TestScorecardDetailAuthorization(TestCase):
    def setUp(self):
        self.contest = Contest.objects.create(
            name="Private contest",
            is_public=False,
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1),
            location="60, 11",
        )
        route = Route.objects.create(name="Route")
        now = datetime.datetime.now(datetime.timezone.utc)
        self.navigation_task = NavigationTask.create(
            name="Test task",
            original_scorecard=get_default_scorecard(),
            route=route,
            contest=self.contest,
            start_time=now,
            finish_time=now + datetime.timedelta(days=1),
        )
        self.url = reverse("navigationtask_scoredetails", kwargs={"pk": self.navigation_task.pk})

        self.outsider = get_user_model().objects.create(email="outsider@example.com")
        self.organizer = get_user_model().objects.create(email="organizer@example.com")
        assign_perm("view_contest", self.organizer, self.contest)

    def test_anonymous_user_cannot_view_scorecard_details(self):
        response = self.client.get(self.url)
        self.assertNotEqual(response.status_code, 200)

    def test_authenticated_outsider_cannot_view_scorecard_details(self):
        self.client.force_login(user=self.outsider)
        response = self.client.get(self.url)
        self.assertNotEqual(response.status_code, 200)

    def test_user_with_view_permission_can_view_scorecard_details(self):
        self.client.force_login(user=self.organizer)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test task")
