import datetime
from unittest.mock import patch

from django.test import TestCase

from display.default_scorecards.create_scorecards import create_scorecards
from display.models import Contest, EditableRoute, NavigationTask, Route, Scorecard
from display.services.task_compiler import TaskCompiler
from display.utilities.cima_task_type_definitions import CIRCLE
from utilities.mock_utilities import TraccarMock


class TestCircleCompiledNavigationTask(TestCase):
    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, *args):
        create_scorecards()
        self.scorecard = Scorecard.get_originals().get(shortcut_name="FAI Precision")
        self.route = Route.objects.create(name="Circle compiled route", waypoints=[], takeoff_gates=[], landing_gates=[])
        self.contest = Contest.objects.create(
            name="Circle compiled contest",
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc),
            time_zone="Europe/Oslo",
        )
        self.navigation_task = NavigationTask.create(
            name="Circle compiled task",
            contest=self.contest,
            route=self.route,
            original_scorecard=self.scorecard,
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc),
            task_subtype=CIRCLE,
            task_config={"circle_radius_min_m": 200, "circle_radius_max_m": 750},
        )

    def test_task_compiler_extracts_circle_primitives(self):
        editable_route = EditableRoute.objects.create(
            name="Circle primitive source",
            route={
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"featureType": "route_path"},
                        "geometry": {"type": "LineString", "coordinates": [[11.0, 60.0], [11.1, 60.1]]},
                    },
                    {
                        "type": "Feature",
                        "properties": {"id": "cm-1", "name": "CM", "pointType": "circle_center", "featureType": "circle_center_marker"},
                        "geometry": {"type": "Point", "coordinates": [11.2, 60.2]},
                    },
                    {
                        "type": "Feature",
                        "properties": {"id": "cs-1", "name": "SP", "pointType": "circle_start", "featureType": "circle_start_marker"},
                        "geometry": {"type": "Point", "coordinates": [11.1, 60.1]},
                    },
                    {
                        "type": "Feature",
                        "properties": {"id": "ce-1", "name": "X", "pointType": "circle_entry", "featureType": "circle_entry_marker"},
                        "geometry": {"type": "Point", "coordinates": [11.15, 60.15]},
                    },
                    {
                        "type": "Feature",
                        "properties": {"id": "cx-1", "name": "WP", "pointType": "circle_exit", "featureType": "circle_exit_marker"},
                        "geometry": {"type": "Point", "coordinates": [11.25, 60.25]},
                    },
                ],
            },
        )
        self.navigation_task.editable_route = editable_route
        self.navigation_task.save(update_fields=["editable_route"])

        compiled = TaskCompiler(self.navigation_task).compile(force=True)
        self.assertEqual(compiled.compiled_payload["compiled_primitives"]["circle_center_marker"], ["CM"])
        self.assertEqual(compiled.compiled_payload["compiled_primitives"]["circle_start_marker"], ["SP"])
        self.assertEqual(compiled.compiled_payload["compiled_primitives"]["circle_entry_marker"], ["X"])
        self.assertEqual(compiled.compiled_payload["compiled_primitives"]["circle_exit_marker"], ["WP"])

    def test_task_compiler_marks_circle_missing_start_entry_exit_invalid(self):
        editable_route = EditableRoute.objects.create(
            name="Missing circle primitives",
            route={
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"featureType": "route_path"},
                        "geometry": {"type": "LineString", "coordinates": [[11.0, 60.0], [11.1, 60.1]]},
                    },
                    {
                        "type": "Feature",
                        "properties": {"id": "cm-1", "name": "CM", "pointType": "circle_center", "featureType": "circle_center_marker"},
                        "geometry": {"type": "Point", "coordinates": [11.2, 60.2]},
                    },
                ],
            },
        )
        self.navigation_task.editable_route = editable_route
        self.navigation_task.save(update_fields=["editable_route"])

        compiled = TaskCompiler(self.navigation_task).compile(force=True)
        self.assertFalse(compiled.compiled_payload["is_valid"])
        joined_errors = " ".join(compiled.compiled_payload["validation_errors"])
        self.assertIn("circle_start_marker", joined_errors)
        self.assertIn("circle_entry_marker", joined_errors)
        self.assertIn("circle_exit_marker", joined_errors)

    def test_task_compiler_preserves_circle_radius_task_config(self):
        compiled = TaskCompiler(self.navigation_task).compile(force=True)
        self.assertEqual(compiled.task_subtype, CIRCLE)
        self.assertEqual(
            compiled.compiled_payload["task_config"],
            {"circle_radius_min_m": 200, "circle_radius_max_m": 750},
        )
