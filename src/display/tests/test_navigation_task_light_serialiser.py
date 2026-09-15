"""
Coverage for NavigationTasksLightSerialiser.task_subtype_definition - the field ContestSerialiser's
navigationtask_set exposes per task on GET /api/v1/contests/{id}/, which TaskCard.tsx uses to show
each task's type (coarse_family_label) and subtype (display_name) on its card.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from guardian.shortcuts import assign_perm

from display.models import Contest, NavigationTask, Route, Scorecard


class TestNavigationTasksLightSerialiserTaskSubtypeDefinition(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create(email="light-serialiser@example.com")
        self.user.user_permissions.add(
            Permission.objects.get(codename="view_contest"),
            Permission.objects.get(codename="change_contest"),
        )
        self.contest = Contest.objects.create(
            name="Light Serialiser Contest",
            time_zone="Europe/Oslo",
            start_time="2026-10-01T09:00:00+00:00",
            finish_time="2026-10-01T17:00:00+00:00",
            location="60.0,11.0",
            created_by=self.user,
        )
        assign_perm("view_contest", self.user, self.contest)
        assign_perm("change_contest", self.user, self.contest)
        self.client.force_login(self.user)

    def test_task_subtype_definition_included_for_a_precision_task(self):
        NavigationTask.objects.create(
            name="Precision Task",
            contest=self.contest,
            route=Route.objects.create(name="Precision route"),
            original_scorecard=Scorecard.objects.create(name="Precision card", shortcut_name="precision-card"),
            start_time="2026-10-01T09:00:00+00:00",
            finish_time="2026-10-01T17:00:00+00:00",
        )

        response = self.client.get(f"/api/v1/contests/{self.contest.pk}/")

        self.assertEqual(response.status_code, 200, response.content)
        tasks = response.json()["navigationtask_set"]
        self.assertEqual(len(tasks), 1)
        definition = tasks[0]["task_subtype_definition"]
        self.assertIsNotNone(definition)
        self.assertEqual(definition["coarse_family"], "precision")
        self.assertEqual(definition["coarse_family_label"], "Precision")
        self.assertEqual(definition["key"], "legacy_precision")
        self.assertEqual(definition["display_name"], "Legacy precision navigation")

    def test_task_subtype_definition_reflects_the_scorecards_calculator_family(self):
        NavigationTask.objects.create(
            name="ANR Task",
            contest=self.contest,
            route=Route.objects.create(name="ANR route"),
            original_scorecard=Scorecard.objects.create(
                name="ANR card", shortcut_name="anr-card", calculator="anr_corridor"
            ),
            start_time="2026-10-01T09:00:00+00:00",
            finish_time="2026-10-01T17:00:00+00:00",
        )

        response = self.client.get(f"/api/v1/contests/{self.contest.pk}/")

        self.assertEqual(response.status_code, 200, response.content)
        definition = response.json()["navigationtask_set"][0]["task_subtype_definition"]
        self.assertEqual(definition["coarse_family"], "anr_corridor")
        self.assertEqual(definition["coarse_family_label"], "ANR Corridor")
