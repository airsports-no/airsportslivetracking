import datetime
from unittest.mock import patch

from django.test import TestCase

from display.default_scorecards.create_scorecards import create_scorecards
from display.models import Contest, NavigationTask, Route, Scorecard, EditableRoute
from display.services.task_compiler import TaskCompiler
from display.utilities.cima_task_type_definitions import (
    ANR_CATALOGUE,
    CIRCLE,
    CONTRACT_NAVIGATION_TIME_CONTROLS,
    CURVE_NAVIGATION_TIME_ESTIMATION,
    DURATION,
    KNOWN_CIRCUIT,
    PRECISION_NAVIGATION,
    UNKNOWN_LEGS,
)
from utilities.mock_utilities import TraccarMock


class TestCompiledNavigationTask(TestCase):
    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, *args):
        create_scorecards()
        self.scorecard = Scorecard.get_originals().get(shortcut_name="FAI Precision")
        self.route = Route.objects.create(name="Compiled route", waypoints=[], takeoff_gates=[], landing_gates=[])
        self.contest = Contest.objects.create(
            name="Compiled contest",
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc),
            time_zone="Europe/Oslo",
        )
        self.navigation_task = NavigationTask.create(
            name="Compiled task",
            contest=self.contest,
            route=self.route,
            original_scorecard=self.scorecard,
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc),
            task_subtype=CURVE_NAVIGATION_TIME_ESTIMATION,
            task_config={"source": "test"},
        )

    def test_task_compiler_creates_compiled_navigation_task(self):
        compiled = TaskCompiler(self.navigation_task).compile()
        self.assertEqual(compiled.navigation_task, self.navigation_task)
        self.assertEqual(compiled.task_subtype, CURVE_NAVIGATION_TIME_ESTIMATION)
        self.assertEqual(compiled.compiled_family_route, self.navigation_task.route)
        self.assertEqual(compiled.compiled_payload["coarse_task_family"], "precision")
        self.assertEqual(compiled.compiled_payload["task_config"], {"source": "test"})
        self.assertEqual(compiled.compiled_payload["primitives"], {})

    def test_task_compiler_reuses_existing_compiled_navigation_task(self):
        first = TaskCompiler(self.navigation_task).compile()
        second = TaskCompiler(self.navigation_task).compile()
        self.assertEqual(first.pk, second.pk)

    def test_task_compiler_extracts_known_time_and_hidden_gate_primitives_from_editable_route(self):
        editable_route = EditableRoute.objects.create(
            name="Primitive source",
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
                        "properties": {"id": "kt-1", "name": "KT1", "pointType": "tp", "featureType": "known_time_gate"},
                        "geometry": {"type": "Point", "coordinates": [11.2, 60.2]},
                    },
                    {
                        "type": "Feature",
                        "properties": {"id": "hg-1", "name": "HG1", "pointType": "tp", "featureType": "hidden_gate"},
                        "geometry": {"type": "Point", "coordinates": [11.3, 60.3]},
                    },
                ],
            },
        )
        self.navigation_task.editable_route = editable_route
        self.navigation_task.save(update_fields=["editable_route"])

        compiled = TaskCompiler(self.navigation_task).compile(force=True)
        self.assertEqual(compiled.compiled_payload["primitives"]["known_time_gate"], ["KT1"])
        self.assertEqual(compiled.compiled_payload["primitives"]["hidden_gate"], ["HG1"])

    def test_task_compiler_marks_missing_required_primitives_invalid(self):
        self.navigation_task.task_subtype = CURVE_NAVIGATION_TIME_ESTIMATION
        self.navigation_task.editable_route = EditableRoute.objects.create(
            name="Missing primitives",
            route={
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"featureType": "route_path"},
                        "geometry": {"type": "LineString", "coordinates": [[11.0, 60.0], [11.1, 60.1]]},
                    }
                ],
            },
        )
        self.navigation_task.save(update_fields=["task_subtype", "editable_route"])

        compiled = TaskCompiler(self.navigation_task).compile(force=True)
        self.assertFalse(compiled.compiled_payload["is_valid"])
        self.assertIn("known_time_gate", " ".join(compiled.compiled_payload["validation_errors"]))
        self.assertIn("hidden_gate", " ".join(compiled.compiled_payload["validation_errors"]))

    def test_precision_navigation_requires_start_intermediate_finish_and_hidden_gate(self):
        self.navigation_task.task_subtype = PRECISION_NAVIGATION
        self.navigation_task.editable_route = EditableRoute.objects.create(
            name="Precision navigation invalid",
            route={
                "type": "FeatureCollection",
                "features": [
                    {"type": "Feature", "properties": {"featureType": "route_path"}, "geometry": {"type": "LineString", "coordinates": [[11.0, 60.0], [11.1, 60.1]]}},
                    {"type": "Feature", "properties": {"id": "wp-1", "name": "SP", "pointType": "sp", "featureType": "route_waypoint", "width": 1852, "isTiming": True, "isPassing": True, "sequence": 0}, "geometry": {"type": "Point", "coordinates": [11.0, 60.0]}},
                    {"type": "Feature", "properties": {"id": "wp-2", "name": "FP", "pointType": "fp", "featureType": "route_waypoint", "width": 1852, "isTiming": True, "isPassing": True, "sequence": 1}, "geometry": {"type": "Point", "coordinates": [11.1, 60.1]}},
                ],
            },
        )
        self.navigation_task.save(update_fields=["task_subtype", "editable_route"])

        compiled = TaskCompiler(self.navigation_task).compile(force=True)
        self.assertFalse(compiled.compiled_payload["is_valid"])
        joined_errors = " ".join(compiled.compiled_payload["validation_errors"])
        self.assertIn("at least one intermediate turn point", joined_errors)

    def test_contract_navigation_requires_sp_mp_fp_route_backbone(self):
        self.navigation_task.task_subtype = CONTRACT_NAVIGATION_TIME_CONTROLS
        self.navigation_task.editable_route = EditableRoute.objects.create(
            name="Contract invalid backbone",
            route={
                "type": "FeatureCollection",
                "features": [
                    {"type": "Feature", "properties": {"featureType": "route_path"}, "geometry": {"type": "LineString", "coordinates": [[11.0, 60.0], [11.1, 60.1]]}},
                    {"type": "Feature", "properties": {"id": "wp-1", "name": "SP", "pointType": "sp", "featureType": "route_waypoint", "width": 1852, "isTiming": True, "isPassing": True, "sequence": 0}, "geometry": {"type": "Point", "coordinates": [11.0, 60.0]}},
                    {"type": "Feature", "properties": {"id": "wp-2", "name": "A", "pointType": "tp", "featureType": "route_waypoint", "width": 1852, "isTiming": False, "isPassing": True, "sequence": 1}, "geometry": {"type": "Point", "coordinates": [11.1, 60.1]}},
                    {"type": "Feature", "properties": {"id": "wp-3", "name": "FP", "pointType": "fp", "featureType": "route_waypoint", "width": 1852, "isTiming": True, "isPassing": True, "sequence": 2}, "geometry": {"type": "Point", "coordinates": [11.2, 60.2]}},
                    {"type": "Feature", "properties": {"id": "cat-1", "name": "C1", "pointType": "tp", "featureType": "catalogue_turnpoint"}, "geometry": {"type": "Point", "coordinates": [11.3, 60.3]}},
                ],
            },
        )
        self.navigation_task.save(update_fields=["task_subtype", "editable_route"])

        compiled = TaskCompiler(self.navigation_task).compile(force=True)
        self.assertFalse(compiled.compiled_payload["is_valid"])
        self.assertIn("SP, MP, and FP", " ".join(compiled.compiled_payload["validation_errors"]))

    def test_contract_navigation_requires_at_least_one_free_catalogue_waypoint(self):
        self.navigation_task.task_subtype = CONTRACT_NAVIGATION_TIME_CONTROLS
        self.navigation_task.editable_route = EditableRoute.objects.create(
            name="Contract missing free waypoint",
            route={
                "type": "FeatureCollection",
                "features": [
                    {"type": "Feature", "properties": {"featureType": "route_path"}, "geometry": {"type": "LineString", "coordinates": [[11.0, 60.0], [11.1, 60.1]]}},
                    {"type": "Feature", "properties": {"id": "wp-1", "name": "SP", "pointType": "sp", "featureType": "route_waypoint", "width": 1852, "isTiming": True, "isPassing": True, "sequence": 0}, "geometry": {"type": "Point", "coordinates": [11.0, 60.0]}},
                    {"type": "Feature", "properties": {"id": "wp-2", "name": "MP", "pointType": "tp", "featureType": "route_waypoint", "width": 1852, "isTiming": True, "isPassing": True, "sequence": 1}, "geometry": {"type": "Point", "coordinates": [11.1, 60.1]}},
                    {"type": "Feature", "properties": {"id": "wp-3", "name": "FP", "pointType": "fp", "featureType": "route_waypoint", "width": 1852, "isTiming": True, "isPassing": True, "sequence": 2}, "geometry": {"type": "Point", "coordinates": [11.2, 60.2]}},
                ],
            },
        )
        self.navigation_task.save(update_fields=["task_subtype", "editable_route"])

        compiled = TaskCompiler(self.navigation_task).compile(force=True)
        self.assertFalse(compiled.compiled_payload["is_valid"])
        self.assertIn("at least one free catalogue waypoint", " ".join(compiled.compiled_payload["validation_errors"]))

    def test_task_compiler_marks_circle_missing_center_invalid(self):
        self.navigation_task.task_subtype = CIRCLE
        self.navigation_task.editable_route = EditableRoute.objects.create(
            name="Missing circle center",
            route={
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"featureType": "route_path"},
                        "geometry": {"type": "LineString", "coordinates": [[11.0, 60.0], [11.1, 60.1]]},
                    }
                ],
            },
        )
        self.navigation_task.save(update_fields=["task_subtype", "editable_route"])

        compiled = TaskCompiler(self.navigation_task).compile(force=True)
        self.assertFalse(compiled.compiled_payload["is_valid"])
        self.assertIn("circle_center_marker", " ".join(compiled.compiled_payload["validation_errors"]))

    def test_task_compiler_extracts_observation_photo_and_unknown_leg_primitives(self):
        editable_route = EditableRoute.objects.create(
            name="Known circuit primitive source",
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
                        "properties": {
                            "id": "ul-1",
                            "name": "UL1",
                            "pointType": "ul",
                            "featureType": "route_waypoint",
                            "width": 1852,
                            "isTiming": False,
                            "isPassing": False,
                            "sequence": 0,
                        },
                        "geometry": {"type": "Point", "coordinates": [11.2, 60.2]},
                    },
                    {
                        "type": "Feature",
                        "properties": {"id": "obs-1", "name": "Photo 1", "featureType": "observation_photo"},
                        "geometry": {"type": "Point", "coordinates": [11.3, 60.3]},
                    },
                    {
                        "type": "Feature",
                        "properties": {"id": "hg-1", "name": "HG1", "pointType": "tp", "featureType": "hidden_gate"},
                        "geometry": {"type": "Point", "coordinates": [11.4, 60.4]},
                    },
                ],
            },
        )
        self.navigation_task.editable_route = editable_route
        self.navigation_task.task_subtype = KNOWN_CIRCUIT
        self.navigation_task.save(update_fields=["editable_route", "task_subtype"])

        compiled = TaskCompiler(self.navigation_task).compile(force=True)
        self.assertEqual(compiled.compiled_payload["primitives"]["observation_photo"], ["Photo 1"])
        self.assertEqual(compiled.compiled_payload["primitives"]["unknown_leg"], ["UL1"])

    def test_task_compiler_marks_known_circuit_missing_observation_photo_invalid(self):
        self.navigation_task.task_subtype = KNOWN_CIRCUIT
        self.navigation_task.editable_route = EditableRoute.objects.create(
            name="Missing observation photos",
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
                        "properties": {"id": "hg-1", "name": "HG1", "pointType": "tp", "featureType": "hidden_gate"},
                        "geometry": {"type": "Point", "coordinates": [11.2, 60.2]},
                    },
                ],
            },
        )
        self.navigation_task.save(update_fields=["task_subtype", "editable_route"])

        compiled = TaskCompiler(self.navigation_task).compile(force=True)
        self.assertFalse(compiled.compiled_payload["is_valid"])
        self.assertIn("observation_photo", " ".join(compiled.compiled_payload["validation_errors"]))

    def test_task_compiler_marks_unknown_legs_missing_observation_photo_invalid(self):
        self.navigation_task.task_subtype = UNKNOWN_LEGS
        self.navigation_task.editable_route = EditableRoute.objects.create(
            name="Unknown legs missing observation photos",
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
                        "properties": {
                            "id": "ul-1",
                            "name": "UL1",
                            "pointType": "ul",
                            "featureType": "route_waypoint",
                            "width": 1852,
                            "isTiming": False,
                            "isPassing": False,
                            "sequence": 0,
                        },
                        "geometry": {"type": "Point", "coordinates": [11.2, 60.2]},
                    },
                ],
            },
        )
        self.navigation_task.save(update_fields=["task_subtype", "editable_route"])

        compiled = TaskCompiler(self.navigation_task).compile(force=True)
        self.assertFalse(compiled.compiled_payload["is_valid"])
        self.assertIn("observation_photo", " ".join(compiled.compiled_payload["validation_errors"]))

    def test_task_compiler_preserves_duration_task_config(self):
        self.navigation_task.task_subtype = DURATION
        self.navigation_task.task_config = {
            "duration_normalization_policy": "raw_minutes",
            "duration_landing_area_polygon": [[11.0, 60.0], [11.2, 60.0], [11.2, 60.2], [11.0, 60.2]],
            "duration_residual_fuel_required": True,
        }
        self.navigation_task.save(update_fields=["task_subtype", "task_config"])

        compiled = TaskCompiler(self.navigation_task).compile(force=True)
        self.assertEqual(compiled.task_subtype, DURATION)
        self.assertEqual(
            compiled.compiled_payload["task_config"],
            {
                "duration_normalization_policy": "raw_minutes",
                "duration_landing_area_polygon": [[11.0, 60.0], [11.2, 60.0], [11.2, 60.2], [11.0, 60.2]],
                "duration_residual_fuel_required": True,
            },
        )

    def test_task_compiler_extracts_anr_auxiliary_paths(self):
        self.navigation_task.task_subtype = ANR_CATALOGUE
        self.navigation_task.editable_route = EditableRoute.objects.create(
            name="ANR primitive source",
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
                        "properties": {"id": "rts-1", "name": "Route to SP", "featureType": "route_to_sp_path"},
                        "geometry": {"type": "LineString", "coordinates": [[10.9, 59.9], [11.0, 60.0]]},
                    },
                    {
                        "type": "Feature",
                        "properties": {"id": "rfp-1", "name": "Route from FP", "featureType": "route_from_fp_path"},
                        "geometry": {"type": "LineString", "coordinates": [[11.1, 60.1], [11.2, 60.2]]},
                    },
                ],
            },
        )
        self.navigation_task.save(update_fields=["task_subtype", "editable_route"])

        compiled = TaskCompiler(self.navigation_task).compile(force=True)
        self.assertEqual(compiled.compiled_payload["primitives"]["route_to_sp_path"], ["Route to SP"])
        self.assertEqual(compiled.compiled_payload["primitives"]["route_from_fp_path"], ["Route from FP"])
        self.assertEqual(
            compiled.compiled_payload["compiled_auxiliary_paths"]["route_to_sp_path"],
            [[[10.9, 59.9], [11.0, 60.0]]],
        )
        self.assertEqual(
            compiled.compiled_payload["compiled_auxiliary_paths"]["route_from_fp_path"],
            [[[11.1, 60.1], [11.2, 60.2]]],
        )

    def test_task_compiler_marks_anr_missing_auxiliary_paths_invalid(self):
        self.navigation_task.task_subtype = ANR_CATALOGUE
        self.navigation_task.editable_route = EditableRoute.objects.create(
            name="ANR missing aux routes",
            route={
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"featureType": "route_path"},
                        "geometry": {"type": "LineString", "coordinates": [[11.0, 60.0], [11.1, 60.1]]},
                    }
                ],
            },
        )
        self.navigation_task.save(update_fields=["task_subtype", "editable_route"])

        compiled = TaskCompiler(self.navigation_task).compile(force=True)
        self.assertFalse(compiled.compiled_payload["is_valid"])
        joined_errors = " ".join(compiled.compiled_payload["validation_errors"])
        self.assertIn("route_to_sp_path", joined_errors)
        self.assertIn("route_from_fp_path", joined_errors)
