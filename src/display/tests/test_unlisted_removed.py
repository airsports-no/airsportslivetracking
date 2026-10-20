"""
Unlisted (public, but not featured) is gone: the migration makes what was reachable by a link alone private, and
is_featured, kept for the apps that still read it, always equals is_public.
"""

import datetime
import importlib

from django.apps import apps
from django.test import TestCase

from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
from display.models import Contest, NavigationTask, Route

migration = importlib.import_module("display.migrations.0201_remove_unlisted")


def make_contest(name, **fields):
    now = datetime.datetime.now(datetime.timezone.utc)
    contest = Contest.objects.create(
        name=name, start_time=now, finish_time=now + datetime.timedelta(days=1), location="60, 11"
    )
    Contest.objects.filter(pk=contest.pk).update(**fields)  # update(): the states save() no longer produces
    return contest


def make_task(contest, name, **fields):
    now = datetime.datetime.now(datetime.timezone.utc)
    task = NavigationTask.create(
        name=name,
        original_scorecard=get_default_scorecard(),
        route=Route.objects.create(name=name),
        contest=contest,
        start_time=now,
        finish_time=now + datetime.timedelta(days=1),
    )
    NavigationTask.objects.filter(pk=task.pk).update(**fields)
    return task


class TestUnlistedMigration(TestCase):
    def test_unlisted_becomes_private_and_is_featured_follows_is_public(self):
        public = make_contest("public", is_public=True, is_featured=True)
        unlisted = make_contest("unlisted", is_public=True, is_featured=False)
        private = make_contest("private", is_public=False, is_featured=False)
        odd = make_contest("odd", is_public=False, is_featured=True)
        public_task = make_task(public, "public task", is_public=True, is_featured=True)
        unlisted_task = make_task(public, "unlisted task", is_public=True, is_featured=False)

        migration.unlisted_becomes_private(apps, None)

        for contest, expected in ((public, True), (unlisted, False), (private, False), (odd, False)):
            contest.refresh_from_db()
            self.assertEqual((contest.is_public, contest.is_featured), (expected, expected), contest.name)
        public_task.refresh_from_db()
        unlisted_task.refresh_from_db()
        self.assertEqual((public_task.is_public, public_task.is_featured), (True, True))
        self.assertEqual((unlisted_task.is_public, unlisted_task.is_featured), (False, False))


class TestIsFeaturedFollowsIsPublic(TestCase):
    def test_save_keeps_them_equal(self):
        contest = make_contest("c")
        contest.is_public = True
        contest.save()
        self.assertTrue(Contest.objects.get(pk=contest.pk).is_featured)
        contest.is_public = False
        contest.save(update_fields=["is_public"])
        self.assertFalse(Contest.objects.get(pk=contest.pk).is_featured)

    def test_share_helpers(self):
        contest = make_contest("c")
        task = make_task(contest, "t")
        task.make_public()
        contest.refresh_from_db()
        self.assertEqual((contest.share_string, task.share_string), ("Public", "Public"))
        self.assertTrue(contest.is_featured and task.is_featured)
        contest.make_private()
        task.refresh_from_db()
        self.assertEqual((contest.share_string, task.share_string), ("Private", "Private"))
        self.assertFalse(contest.is_featured or task.is_featured)
