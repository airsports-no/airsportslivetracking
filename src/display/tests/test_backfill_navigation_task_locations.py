"""
Regression coverage for `manage.py backfill_navigation_task_locations` (display.services.
admin_system_stats.get_country_stats reads NavigationTask._nominatim directly and never
triggers a live lookup on a miss - this command is the deliberate, rate-limited way to actually
fill that cache in bulk). NavigationTask._geo_reference() itself no-ops under
settings.IS_UNIT_TESTING (keeps the whole suite off the real, rate-limited Nominatim service), so
these tests patch it directly to exercise the command's own candidate-selection/reporting logic
rather than re-testing geocoding itself.
"""

import datetime
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from display.default_scorecards.create_scorecards import create_scorecards
from display.models import Contest, NavigationTask, Route, Scorecard


class TestBackfillNavigationTaskLocations(TestCase):
    def setUp(self):
        create_scorecards()
        self.scorecard = Scorecard.get_originals().get(shortcut_name="FAI Precision")
        self.contest = Contest.objects.create(
            name="Backfill Contest",
            time_zone="Europe/Oslo",
            start_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 8, 1, 20, 0, tzinfo=datetime.timezone.utc),
            location="60.0,11.0",
        )

    def _make_task(self, name, route, nominatim=None):
        task = NavigationTask.objects.create(
            name=name,
            contest=self.contest,
            route=route,
            original_scorecard=self.scorecard,
            start_time=self.contest.start_time,
            finish_time=self.contest.finish_time,
        )
        if nominatim is not None:
            NavigationTask.objects.filter(pk=task.pk).update(_nominatim=nominatim)
        return NavigationTask.objects.get(pk=task.pk)

    def _route_with_location(self, name):
        return Route.objects.create(
            name=name,
            waypoints=[SimpleNamespace(latitude=60.0, longitude=11.0)],
            takeoff_gates=[],
            landing_gates=[],
        )

    def _route_without_location(self, name):
        return Route.objects.create(name=name, waypoints=[], takeoff_gates=[], landing_gates=[])

    def test_dry_run_reports_counts_and_touches_nothing(self):
        self._make_task("Already resolved", self._route_with_location("r1"), nominatim={"address": {"country": "Norway"}})
        self._make_task("Needs resolving", self._route_with_location("r2"))
        self._make_task("No location at all", self._route_without_location("r3"))

        out = StringIO()
        with patch.object(NavigationTask, "_geo_reference") as mock_geo_reference:
            call_command("backfill_navigation_task_locations", "--dry-run", stdout=out)

        mock_geo_reference.assert_not_called()
        output = out.getvalue()
        self.assertIn("1 navigation task(s) to resolve", output)
        self.assertIn("1 more have no cached geocode but also no route location", output)

    def test_processes_only_resolvable_unresolved_tasks_and_reports_success(self):
        self._make_task("Already resolved", self._route_with_location("r1"), nominatim={"address": {"country": "Norway"}})
        needs_resolving = self._make_task("Needs resolving", self._route_with_location("r2"))
        self._make_task("No location at all", self._route_without_location("r3"))

        def fake_geo_reference(self):
            NavigationTask.objects.filter(pk=self.pk).update(_nominatim={"address": {"country": "Sweden", "country_code": "se"}})

        out = StringIO()
        with patch.object(NavigationTask, "_geo_reference", fake_geo_reference):
            call_command("backfill_navigation_task_locations", "--delay", "0", stdout=out)

        needs_resolving.refresh_from_db()
        self.assertEqual("Sweden", needs_resolving._nominatim["address"]["country"])
        self.assertIn("Done: 1 resolved, 0 failed.", out.getvalue())

    def test_a_failed_lookup_is_counted_and_does_not_stop_the_batch(self):
        failing_task = self._make_task("Will fail", self._route_with_location("r1"))
        succeeding_task = self._make_task("Will succeed", self._route_with_location("r2"))

        def fake_geo_reference(self):
            if self.pk == failing_task.pk:
                raise RuntimeError("simulated Nominatim outage")
            NavigationTask.objects.filter(pk=self.pk).update(_nominatim={"address": {"country": "Denmark"}})

        out = StringIO()
        err = StringIO()
        with patch.object(NavigationTask, "_geo_reference", fake_geo_reference):
            call_command("backfill_navigation_task_locations", "--delay", "0", stdout=out, stderr=err)

        succeeding_task.refresh_from_db()
        self.assertEqual("Denmark", succeeding_task._nominatim["address"]["country"])
        self.assertIn("Done: 1 resolved, 1 failed.", out.getvalue())
        self.assertIn("simulated Nominatim outage", err.getvalue())

    def test_limit_caps_how_many_are_processed(self):
        for i in range(3):
            self._make_task(f"Task {i}", self._route_with_location(f"r{i}"))

        call_count = 0

        def fake_geo_reference(self):
            nonlocal call_count
            call_count += 1
            NavigationTask.objects.filter(pk=self.pk).update(_nominatim={"address": {"country": "Finland"}})

        out = StringIO()
        with patch.object(NavigationTask, "_geo_reference", fake_geo_reference):
            call_command("backfill_navigation_task_locations", "--limit", "2", "--delay", "0", stdout=out)

        self.assertEqual(2, call_count)
