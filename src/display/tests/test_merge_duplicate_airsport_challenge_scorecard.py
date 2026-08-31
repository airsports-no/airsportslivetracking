"""
Regression test (local code review, scheduling/scorecards section, finding #6): a rename-target
typo in default_scorecard_airsport_challenge.get_default_scorecard() spawned a permanently
out-of-sync duplicate Scorecard ("AirSport Challenge 2023") alongside the canonical row every
subsequent run actually keeps updated ("Air Sport Challenge 2023") - in the dev DB, 87
NavigationTasks referenced the stale duplicate. Migration 0170 merges them; this test exercises
the merge function directly against real data rather than relying on migration-runner timing.
"""

import datetime
import importlib

from django.apps import apps
from django.test import TestCase

from display.models import Contest, NavigationTask, Route, Scorecard

merge_duplicate_scorecard = importlib.import_module(
    "display.migrations.0170_merge_duplicate_airsport_challenge_scorecard"
).merge_duplicate_scorecard

OLD_NAME = "AirSport Challenge 2023"
CANONICAL_NAME = "Air Sport Challenge 2023"


class TestMergeDuplicateAirsportChallengeScorecard(TestCase):
    def _make_navigation_task(self, name, original_scorecard):
        contest = Contest.objects.create(
            name=f"{name} contest",
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc),
            time_zone="Europe/Oslo",
        )
        return NavigationTask.objects.create(
            name=name,
            contest=contest,
            route=Route.objects.create(name=f"{name} route"),
            original_scorecard=original_scorecard,
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc),
        )

    def test_reassigns_references_and_deletes_the_duplicate_when_both_rows_exist(self):
        old = Scorecard.objects.create(name=OLD_NAME, shortcut_name="merge-test-old")
        canonical = Scorecard.objects.create(name=CANONICAL_NAME, shortcut_name="merge-test-canonical")
        task = self._make_navigation_task("Merge task", old)

        merge_duplicate_scorecard(apps, None)

        task.refresh_from_db()
        self.assertEqual(task.original_scorecard_id, canonical.pk)
        self.assertFalse(Scorecard.objects.filter(name=OLD_NAME).exists())
        self.assertTrue(Scorecard.objects.filter(pk=canonical.pk).exists())

    def test_renames_in_place_when_only_the_duplicate_exists(self):
        old = Scorecard.objects.create(name=OLD_NAME, shortcut_name="merge-test-solo")

        merge_duplicate_scorecard(apps, None)

        old.refresh_from_db()
        self.assertEqual(old.name, CANONICAL_NAME)
        self.assertEqual(Scorecard.objects.filter(name__in=[OLD_NAME, CANONICAL_NAME]).count(), 1)

    def test_noop_when_neither_row_exists(self):
        # Must not raise even though neither Scorecard.DoesNotExist branch has anything to do.
        merge_duplicate_scorecard(apps, None)
        self.assertFalse(Scorecard.objects.filter(name__in=[OLD_NAME, CANONICAL_NAME]).exists())
