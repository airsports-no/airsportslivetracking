"""
The contest audience (display/services/contest_visibility.py): a view grant opens a private contest and its private
tasks as a spectator sees a public one, never the organiser screens, which need change_contest.
"""

import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from guardian.shortcuts import assign_perm

from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
from display.models import Contest, NavigationTask, Route, Task
from display.services.contest_visibility import (
    audience_contests,
    can_view_contest,
    can_view_navigation_task,
    visible_contests,
)


class ContestVisibilityTestBase(TestCase):
    def setUp(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        self.public = self._contest("Public", is_public=True)
        self.private = self._contest("Private", is_public=False)
        self.private_task = NavigationTask.create(
            name="Private task",
            original_scorecard=get_default_scorecard(),
            route=Route.objects.create(name="Route"),
            contest=self.private,
            start_time=now,
            finish_time=now + datetime.timedelta(days=1),
        )
        self.private_results_task = Task.objects.create(name="Results task", heading="Results", contest=self.private)

        user_model = get_user_model()
        self.outsider = user_model.objects.create(email="outsider@example.com")
        self.viewer = user_model.objects.create(email="viewer@example.com")
        self.editor = user_model.objects.create(email="editor@example.com")
        assign_perm("view_contest", self.viewer, self.private)
        for permission in ("view_contest", "change_contest", "add_contest", "delete_contest"):
            assign_perm(permission, self.editor, self.private)

    def _contest(self, name, **visibility):
        now = datetime.datetime.now(datetime.timezone.utc)
        return Contest.objects.create(
            name=name, start_time=now, finish_time=now + datetime.timedelta(days=1), location="60, 11", **visibility
        )


class TestVisibilityHelpers(ContestVisibilityTestBase):
    def test_audience_is_the_view_grants(self):
        self.assertEqual(set(audience_contests(self.viewer)), {self.private})
        self.assertEqual(set(audience_contests(self.outsider)), set())
        self.assertEqual(set(audience_contests(None)), set())

    def test_public_contests_are_visible_to_all_and_private_ones_to_their_audience(self):
        self.assertEqual(set(visible_contests(None)), {self.public})
        self.assertEqual(set(visible_contests(self.outsider)), {self.public})
        self.assertEqual(set(visible_contests(self.viewer)), {self.public, self.private})

    def test_private_contest_and_task_only_for_the_audience(self):
        self.assertFalse(can_view_contest(None, self.private))
        self.assertFalse(can_view_contest(self.outsider, self.private))
        self.assertTrue(can_view_contest(self.viewer, self.private))
        self.assertFalse(can_view_navigation_task(self.outsider, self.private_task))
        self.assertTrue(can_view_navigation_task(self.viewer, self.private_task))


class TestAudienceReads(ContestVisibilityTestBase):
    def _task_url(self):
        return f"/api/v1/contests/{self.private.pk}/navigationtasks/{self.private_task.pk}/"

    def test_contest_list_holds_listed_contests_and_the_users_audiences(self):
        self.client.force_login(self.outsider)
        names = {contest["name"] for contest in self.client.get("/api/v1/contests/").json()["results"]}
        self.assertEqual(names, {"Public"})
        self.client.force_login(self.viewer)
        names = {contest["name"] for contest in self.client.get("/api/v1/contests/").json()["results"]}
        self.assertEqual(names, {"Public", "Private"})

    def test_private_contest_only_for_its_audience(self):
        self.assertEqual(self.client.get(f"/api/v1/contests/{self.private.pk}/").status_code, 404)
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(f"/api/v1/contests/{self.private.pk}/").status_code, 404)
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get(f"/api/v1/contests/{self.private.pk}/").status_code, 200)

    def test_audience_opens_a_private_task(self):
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(self._task_url()).status_code, 404)
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get(self._task_url()).status_code, 200)
        self.assertEqual(self.client.get(self._task_url() + "contestants/").status_code, 200)

    def test_results_tasks_of_a_private_contest_are_not_listed_for_outsiders(self):
        url = f"/api/v1/contests/{self.private.pk}/tasks/"
        self.assertEqual(self.client.get(url).json(), [])
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(url).json(), [])
        self.client.force_login(self.viewer)
        self.assertIn("Results task", [task["name"] for task in self.client.get(url).json()])


class TestOrganiserReads(ContestVisibilityTestBase):
    """The audience sees what a spectator sees; organiser screens need change_contest."""

    def _organiser_urls(self):
        base = f"/api/v1/contests/{self.private.pk}/navigationtasks/{self.private_task.pk}/"
        return [
            base + "scorecard/",
            base + "flight_order_configuration/",
            reverse("navigationtask_scoredetails", kwargs={"pk": self.private_task.pk}),
            reverse("navigationtask_getflightordersstatus", kwargs={"pk": self.private_task.pk}),
        ]

    def test_audience_cannot_open_organiser_screens(self):
        self.client.force_login(self.viewer)
        for url in self._organiser_urls():
            with self.subTest(url=url):
                self.assertIn(self.client.get(url).status_code, (302, 403, 404))

    def test_editor_opens_organiser_screens(self):
        self.client.force_login(self.editor)
        for url in self._organiser_urls():
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)


class TestOngoingNavigationCaching(ContestVisibilityTestBase):
    def test_signed_in_list_is_never_shared_cached(self):
        self.client.force_login(self.viewer)
        response = self.client.get("/api/v1/contests/ongoing_navigation/")
        self.assertEqual(response["Cache-Control"], "private, no-cache")

    def test_anonymous_list_is_cdn_cached(self):
        response = self.client.get("/api/v1/contests/ongoing_navigation/")
        self.assertIn("public", response["Cache-Control"])
