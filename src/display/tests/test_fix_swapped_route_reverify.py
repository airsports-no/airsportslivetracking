"""
Regression test (local code review, management-commands section, finding #6): fix_swapped_route
swapped whatever route id list it was handed with no re-verification - a route that had since
been fixed, or was never actually swapped (a false positive from find_swapped_routes's "doesn't
make it worse" heuristic), would get unconditionally inverted, turning a good route bad.
"""

import datetime
from io import StringIO
from tempfile import TemporaryDirectory

from django.core.management import CommandError, call_command
from django.test import TestCase

from display.default_scorecards.create_scorecards import create_scorecards
from display.models import Contest, EditableRoute, NavigationTask, Route, Scorecard


class TestFixSwappedRouteReverify(TestCase):
    def setUp(self):
        create_scorecards()
        scorecard = Scorecard.get_originals().get(shortcut_name="FAI Precision")
        self.contest = Contest.objects.create(
            name="Reverify contest",
            location="60.2,11.2",
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc),
            time_zone="Europe/Oslo",
        )
        self.editable_route = EditableRoute.objects.create(
            name="Correctly-ordered route",
            route={
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"featureType": "route_path"},
                        "geometry": {"type": "LineString", "coordinates": [[11.2, 60.2], [11.3, 60.3]]},
                    },
                ],
            },
        )
        navigation_task = NavigationTask.objects.create(
            name="Reverify task",
            contest=self.contest,
            route=Route.objects.create(name="Reverify route"),
            original_scorecard=scorecard,
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc),
        )
        navigation_task.editable_route = self.editable_route
        navigation_task.save(update_fields=["editable_route"])

    def test_refuses_to_swap_a_route_that_is_not_currently_suspicious(self):
        out, err = StringIO(), StringIO()
        call_command(
            "fix_swapped_route",
            str(self.editable_route.id),
            "--dry-run",
            stdout=out,
            stderr=err,
        )

        self.assertIn("refusing to swap", err.getvalue())
        self.editable_route.refresh_from_db()
        self.assertEqual(
            self.editable_route.route["features"][0]["geometry"]["coordinates"],
            [[11.2, 60.2], [11.3, 60.3]],
        )

    def test_force_overrides_the_reverification(self):
        out = StringIO()
        with TemporaryDirectory() as backup_dir:
            call_command(
                "fix_swapped_route",
                str(self.editable_route.id),
                "--force",
                "--backup-dir",
                backup_dir,
                stdout=out,
            )

        self.editable_route.refresh_from_db()
        self.assertEqual(
            self.editable_route.route["features"][0]["geometry"]["coordinates"],
            [[60.2, 11.2], [60.3, 11.3]],
        )

    def test_rejects_a_negative_threshold(self):
        with self.assertRaises(CommandError):
            call_command("fix_swapped_route", str(self.editable_route.id), "--threshold-km", "-1", "--dry-run")

    def test_rejects_an_improvement_ratio_below_one(self):
        # Below 1, swapped_dist * ratio < dist becomes easier to satisfy, which could
        # reclassify a correctly-ordered route as SUSPICIOUS and swap it without --force.
        with self.assertRaises(CommandError):
            call_command(
                "fix_swapped_route", str(self.editable_route.id), "--improvement-ratio", "0.5", "--dry-run"
            )
