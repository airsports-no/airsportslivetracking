import datetime
from unittest.mock import patch

from django.test import TestCase

from display.default_scorecards.create_scorecards import create_scorecards
from display.models import Contest, EditableRoute, NavigationTask, Route, Scorecard
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
        self.assertEqual(compiled.compiled_payload["compiled_primitives"], {})

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
                        "properties": {
                            "id": "kt-1",
                            "name": "KT1",
                            "pointType": "tp",
                            "featureType": "known_time_gate",
                        },
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
        self.assertEqual(compiled.compiled_payload["compiled_primitives"]["known_time_gate"], ["KT1"])
        self.assertEqual(compiled.compiled_payload["compiled_primitives"]["hidden_gate"], ["HG1"])

    def test_task_compiler_recompiles_after_in_place_editable_route_edit(self):
        """Regression test: compile(force=False) must pick up an editable
        route edited in place (same pk, e.g. via a standard PATCH/PUT to
        EditableRouteViewSet) instead of serving a stale compiled payload."""
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
                        "properties": {"id": "hg-1", "name": "HG1", "pointType": "tp", "featureType": "hidden_gate"},
                        "geometry": {"type": "Point", "coordinates": [11.3, 60.3]},
                    },
                ],
            },
        )
        self.navigation_task.editable_route = editable_route
        self.navigation_task.save(update_fields=["editable_route"])

        first = TaskCompiler(self.navigation_task).compile(force=True)
        self.assertEqual(first.compiled_payload["compiled_primitives"]["hidden_gate"], ["HG1"])

        # Edit the route content in place (same pk) - e.g. adding a second
        # hidden gate - mirroring a standard PATCH/PUT to EditableRouteViewSet.
        editable_route.route["features"].append(
            {
                "type": "Feature",
                "properties": {"id": "hg-2", "name": "HG2", "pointType": "tp", "featureType": "hidden_gate"},
                "geometry": {"type": "Point", "coordinates": [11.4, 60.4]},
            }
        )
        editable_route.save()

        second = TaskCompiler(self.navigation_task).compile(force=False)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(
            sorted(second.compiled_payload["compiled_primitives"]["hidden_gate"]),
            ["HG1", "HG2"],
        )

    def test_task_compiler_marks_curve_navigation_missing_route_path_invalid(self):
        # known_time_gate/hidden_gate are not required on the route itself for curve navigation -
        # route_path is the only structural prerequisite.
        self.navigation_task.task_subtype = CURVE_NAVIGATION_TIME_ESTIMATION
        self.navigation_task.editable_route = EditableRoute.objects.create(
            name="Missing primitives", route={"type": "FeatureCollection", "features": []}
        )
        self.navigation_task.save(update_fields=["task_subtype", "editable_route"])

        compiled = TaskCompiler(self.navigation_task).compile(force=True)
        self.assertFalse(compiled.compiled_payload["is_valid"])
        self.assertIn("route_path", " ".join(compiled.compiled_payload["validation_errors"]))

    def test_task_compiler_allows_curve_navigation_without_known_time_gate_or_hidden_gate(self):
        self.navigation_task.task_subtype = CURVE_NAVIGATION_TIME_ESTIMATION
        self.navigation_task.editable_route = EditableRoute.objects.create(
            name="Curve navigation minimal",
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
                            "id": "wp-1",
                            "name": "SP",
                            "pointType": "sp",
                            "featureType": "route_waypoint",
                            "width": 1852,
                            "isTiming": True,
                            "isPassing": True,
                            "sequence": 0,
                        },
                        "geometry": {"type": "Point", "coordinates": [11.0, 60.0]},
                    },
                    {
                        "type": "Feature",
                        "properties": {
                            "id": "wp-2",
                            "name": "FP",
                            "pointType": "fp",
                            "featureType": "route_waypoint",
                            "width": 1852,
                            "isTiming": True,
                            "isPassing": True,
                            "sequence": 1,
                        },
                        "geometry": {"type": "Point", "coordinates": [11.1, 60.1]},
                    },
                ],
            },
        )
        self.navigation_task.save(update_fields=["task_subtype", "editable_route"])

        compiled = TaskCompiler(self.navigation_task).compile(force=True)
        self.assertTrue(compiled.compiled_payload["is_valid"], compiled.compiled_payload["validation_errors"])

    def test_precision_navigation_requires_start_intermediate_and_finish(self):
        self.navigation_task.task_subtype = PRECISION_NAVIGATION
        self.navigation_task.editable_route = EditableRoute.objects.create(
            name="Precision navigation invalid",
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
                            "id": "wp-1",
                            "name": "SP",
                            "pointType": "sp",
                            "featureType": "route_waypoint",
                            "width": 1852,
                            "isTiming": True,
                            "isPassing": True,
                            "sequence": 0,
                        },
                        "geometry": {"type": "Point", "coordinates": [11.0, 60.0]},
                    },
                    {
                        "type": "Feature",
                        "properties": {
                            "id": "wp-2",
                            "name": "FP",
                            "pointType": "fp",
                            "featureType": "route_waypoint",
                            "width": 1852,
                            "isTiming": True,
                            "isPassing": True,
                            "sequence": 1,
                        },
                        "geometry": {"type": "Point", "coordinates": [11.1, 60.1]},
                    },
                ],
            },
        )
        self.navigation_task.save(update_fields=["task_subtype", "editable_route"])

        compiled = TaskCompiler(self.navigation_task).compile(force=True)
        self.assertFalse(compiled.compiled_payload["is_valid"])
        joined_errors = " ".join(compiled.compiled_payload["validation_errors"])
        self.assertIn("at least one intermediate turn point", joined_errors)

    def test_precision_navigation_allows_route_without_hidden_gate(self):
        # Hidden gates are optional on every task type, not a structural prerequisite.
        self.navigation_task.task_subtype = PRECISION_NAVIGATION
        self.navigation_task.editable_route = EditableRoute.objects.create(
            name="Precision navigation without hidden gate",
            route={
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"featureType": "route_path"},
                        "geometry": {"type": "LineString", "coordinates": [[11.0, 60.0], [11.1, 60.1], [11.2, 60.2]]},
                    },
                    {
                        "type": "Feature",
                        "properties": {
                            "id": "wp-1",
                            "name": "SP",
                            "pointType": "sp",
                            "featureType": "route_waypoint",
                            "width": 1852,
                            "isTiming": True,
                            "isPassing": True,
                            "sequence": 0,
                        },
                        "geometry": {"type": "Point", "coordinates": [11.0, 60.0]},
                    },
                    {
                        "type": "Feature",
                        "properties": {
                            "id": "wp-2",
                            "name": "TP1",
                            "pointType": "tp",
                            "featureType": "route_waypoint",
                            "width": 1852,
                            "isTiming": True,
                            "isPassing": True,
                            "sequence": 1,
                        },
                        "geometry": {"type": "Point", "coordinates": [11.1, 60.1]},
                    },
                    {
                        "type": "Feature",
                        "properties": {
                            "id": "wp-3",
                            "name": "FP",
                            "pointType": "fp",
                            "featureType": "route_waypoint",
                            "width": 1852,
                            "isTiming": True,
                            "isPassing": True,
                            "sequence": 2,
                        },
                        "geometry": {"type": "Point", "coordinates": [11.2, 60.2]},
                    },
                ],
            },
        )
        self.navigation_task.save(update_fields=["task_subtype", "editable_route"])

        compiled = TaskCompiler(self.navigation_task).compile(force=True)
        self.assertTrue(compiled.compiled_payload["is_valid"], compiled.compiled_payload["validation_errors"])

    def test_contract_navigation_requires_sp_mp_fp_route_backbone(self):
        self.navigation_task.task_subtype = CONTRACT_NAVIGATION_TIME_CONTROLS
        self.navigation_task.editable_route = EditableRoute.objects.create(
            name="Contract invalid backbone",
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
                            "id": "wp-1",
                            "name": "SP",
                            "pointType": "sp",
                            "featureType": "route_waypoint",
                            "width": 1852,
                            "isTiming": True,
                            "isPassing": True,
                            "sequence": 0,
                        },
                        "geometry": {"type": "Point", "coordinates": [11.0, 60.0]},
                    },
                    {
                        "type": "Feature",
                        "properties": {
                            "id": "wp-2",
                            "name": "A",
                            "pointType": "tp",
                            "featureType": "route_waypoint",
                            "width": 1852,
                            "isTiming": False,
                            "isPassing": True,
                            "sequence": 1,
                        },
                        "geometry": {"type": "Point", "coordinates": [11.1, 60.1]},
                    },
                    {
                        "type": "Feature",
                        "properties": {
                            "id": "wp-3",
                            "name": "FP",
                            "pointType": "fp",
                            "featureType": "route_waypoint",
                            "width": 1852,
                            "isTiming": True,
                            "isPassing": True,
                            "sequence": 2,
                        },
                        "geometry": {"type": "Point", "coordinates": [11.2, 60.2]},
                    },
                    {
                        "type": "Feature",
                        "properties": {
                            "id": "cat-1",
                            "name": "C1",
                            "pointType": "tp",
                            "featureType": "catalogue_turnpoint",
                        },
                        "geometry": {"type": "Point", "coordinates": [11.3, 60.3]},
                    },
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
                    {
                        "type": "Feature",
                        "properties": {"featureType": "route_path"},
                        "geometry": {"type": "LineString", "coordinates": [[11.0, 60.0], [11.1, 60.1]]},
                    },
                    {
                        "type": "Feature",
                        "properties": {
                            "id": "wp-1",
                            "name": "SP",
                            "pointType": "sp",
                            "featureType": "route_waypoint",
                            "width": 1852,
                            "isTiming": True,
                            "isPassing": True,
                            "sequence": 0,
                        },
                        "geometry": {"type": "Point", "coordinates": [11.0, 60.0]},
                    },
                    {
                        "type": "Feature",
                        "properties": {
                            "id": "wp-2",
                            "name": "MP",
                            "pointType": "tp",
                            "featureType": "route_waypoint",
                            "width": 1852,
                            "isTiming": True,
                            "isPassing": True,
                            "sequence": 1,
                        },
                        "geometry": {"type": "Point", "coordinates": [11.1, 60.1]},
                    },
                    {
                        "type": "Feature",
                        "properties": {
                            "id": "wp-3",
                            "name": "FP",
                            "pointType": "fp",
                            "featureType": "route_waypoint",
                            "width": 1852,
                            "isTiming": True,
                            "isPassing": True,
                            "sequence": 2,
                        },
                        "geometry": {"type": "Point", "coordinates": [11.2, 60.2]},
                    },
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
        self.assertEqual(compiled.compiled_payload["compiled_primitives"]["observation_photo"], ["Photo 1"])
        self.assertEqual(compiled.compiled_payload["compiled_primitives"]["unknown_leg"], ["UL1"])

    def test_task_compiler_allows_known_circuit_without_observation_photo(self):
        # Observation photos are optional evidence, not a structural prerequisite.
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
                        "properties": {
                            "id": "wp-1",
                            "name": "SP",
                            "pointType": "sp",
                            "featureType": "route_waypoint",
                            "width": 1852,
                            "isTiming": True,
                            "isPassing": True,
                            "sequence": 0,
                        },
                        "geometry": {"type": "Point", "coordinates": [11.0, 60.0]},
                    },
                    {
                        "type": "Feature",
                        "properties": {
                            "id": "wp-2",
                            "name": "FP",
                            "pointType": "fp",
                            "featureType": "route_waypoint",
                            "width": 1852,
                            "isTiming": True,
                            "isPassing": True,
                            "sequence": 1,
                        },
                        "geometry": {"type": "Point", "coordinates": [11.1, 60.1]},
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
        self.assertTrue(compiled.compiled_payload["is_valid"], compiled.compiled_payload["validation_errors"])

    def test_task_compiler_marks_unknown_legs_missing_unknown_leg_waypoint_invalid(self):
        # The defining feature of an unknown-legs route is a backbone waypoint of pointType
        # "unknown_leg" - a plain SP/FP route without one is invalid.
        self.navigation_task.task_subtype = UNKNOWN_LEGS
        self.navigation_task.editable_route = EditableRoute.objects.create(
            name="Unknown legs missing trigger",
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
                            "id": "wp-1",
                            "name": "SP",
                            "pointType": "sp",
                            "featureType": "route_waypoint",
                            "width": 1852,
                            "isTiming": True,
                            "isPassing": True,
                            "sequence": 0,
                        },
                        "geometry": {"type": "Point", "coordinates": [11.0, 60.0]},
                    },
                    {
                        "type": "Feature",
                        "properties": {
                            "id": "wp-2",
                            "name": "FP",
                            "pointType": "fp",
                            "featureType": "route_waypoint",
                            "width": 1852,
                            "isTiming": True,
                            "isPassing": True,
                            "sequence": 1,
                        },
                        "geometry": {"type": "Point", "coordinates": [11.1, 60.1]},
                    },
                ],
            },
        )
        self.navigation_task.save(update_fields=["task_subtype", "editable_route"])

        compiled = TaskCompiler(self.navigation_task).compile(force=True)
        self.assertFalse(compiled.compiled_payload["is_valid"])
        self.assertIn("unknown_leg", " ".join(compiled.compiled_payload["validation_errors"]))

    def test_task_compiler_allows_unknown_legs_without_observation_photo(self):
        # Observation photos are optional evidence, not a structural prerequisite.
        self.navigation_task.task_subtype = UNKNOWN_LEGS
        self.navigation_task.editable_route = EditableRoute.objects.create(
            name="Unknown legs without observation photos",
            route={
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"featureType": "route_path"},
                        "geometry": {"type": "LineString", "coordinates": [[11.0, 60.0], [11.1, 60.1], [11.2, 60.2]]},
                    },
                    {
                        "type": "Feature",
                        "properties": {
                            "id": "wp-sp",
                            "name": "SP",
                            "pointType": "sp",
                            "featureType": "route_waypoint",
                            "width": 1852,
                            "isTiming": True,
                            "isPassing": True,
                            "sequence": 0,
                        },
                        "geometry": {"type": "Point", "coordinates": [11.0, 60.0]},
                    },
                    {
                        "type": "Feature",
                        "properties": {
                            "id": "wp-trg",
                            "name": "TRG1",
                            "pointType": "ul",
                            "featureType": "route_waypoint",
                            "width": 1852,
                            "isTiming": False,
                            "isPassing": True,
                            "sequence": 1,
                            "unknownLegHeading": 105,
                        },
                        "geometry": {"type": "Point", "coordinates": [11.1, 60.1]},
                    },
                    {
                        "type": "Feature",
                        "properties": {
                            "id": "wp-fp",
                            "name": "FP",
                            "pointType": "fp",
                            "featureType": "route_waypoint",
                            "width": 1852,
                            "isTiming": True,
                            "isPassing": True,
                            "sequence": 2,
                        },
                        "geometry": {"type": "Point", "coordinates": [11.2, 60.2]},
                    },
                    {
                        "type": "Feature",
                        "properties": {
                            "id": "dummy-1",
                            "name": "TRG1-D1",
                            "pointType": "dummy",
                            "featureType": "dummy_branch_waypoint",
                            "width": 1852,
                            "isTiming": False,
                            "isPassing": True,
                            "triggerPointId": "wp-trg",
                            "branchSequence": 0,
                            "sequence": 3,
                        },
                        "geometry": {"type": "Point", "coordinates": [11.15, 60.15]},
                    },
                ],
            },
        )
        self.navigation_task.save(update_fields=["task_subtype", "editable_route"])

        compiled = TaskCompiler(self.navigation_task).compile(force=True)
        self.assertTrue(compiled.compiled_payload["is_valid"], compiled.compiled_payload["validation_errors"])

    def test_unknown_legs_compiles_segment_and_actual_route_payload(self):
        self.navigation_task.task_subtype = UNKNOWN_LEGS
        self.navigation_task.editable_route = EditableRoute.objects.create(
            name="Unknown legs compiled route",
            route={
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"featureType": "route_path"},
                        "geometry": {
                            "type": "LineString",
                            "coordinates": [
                                [11.0, 60.0],
                                [11.1, 60.1],
                                [11.2, 60.2],
                                [11.3, 60.3],
                                [11.4, 60.4],
                                [11.5, 60.5],
                            ],
                        },
                    },
                    {
                        "type": "Feature",
                        "properties": {
                            "id": "wp-sp",
                            "name": "SP",
                            "pointType": "sp",
                            "featureType": "route_waypoint",
                            "width": 1852,
                            "isTiming": True,
                            "isPassing": True,
                            "sequence": 0,
                        },
                        "geometry": {"type": "Point", "coordinates": [11.0, 60.0]},
                    },
                    {
                        "type": "Feature",
                        "properties": {
                            "id": "wp-a",
                            "name": "A",
                            "pointType": "tp",
                            "featureType": "route_waypoint",
                            "width": 1852,
                            "isTiming": False,
                            "isPassing": True,
                            "sequence": 1,
                        },
                        "geometry": {"type": "Point", "coordinates": [11.1, 60.1]},
                    },
                    {
                        "type": "Feature",
                        "properties": {
                            "id": "wp-trg",
                            "name": "TRG1",
                            "pointType": "ul",
                            "featureType": "route_waypoint",
                            "width": 1852,
                            "isTiming": False,
                            "isPassing": True,
                            "sequence": 2,
                            "unknownLegHeading": 105,
                        },
                        "geometry": {"type": "Point", "coordinates": [11.2, 60.2]},
                    },
                    {
                        "type": "Feature",
                        "properties": {
                            "id": "wp-b",
                            "name": "B",
                            "pointType": "tp",
                            "featureType": "route_waypoint",
                            "width": 1852,
                            "isTiming": False,
                            "isPassing": True,
                            "sequence": 4,
                        },
                        "geometry": {"type": "Point", "coordinates": [11.4, 60.4]},
                    },
                    {
                        "type": "Feature",
                        "properties": {
                            "id": "wp-fp",
                            "name": "FP",
                            "pointType": "fp",
                            "featureType": "route_waypoint",
                            "width": 1852,
                            "isTiming": True,
                            "isPassing": True,
                            "sequence": 5,
                        },
                        "geometry": {"type": "Point", "coordinates": [11.5, 60.5]},
                    },
                    {
                        "type": "Feature",
                        "properties": {
                            "id": "dummy-1",
                            "name": "TRG1-D1",
                            "pointType": "dummy",
                            "featureType": "dummy_branch_waypoint",
                            "width": 1852,
                            "isTiming": False,
                            "isPassing": True,
                            "triggerPointId": "wp-trg",
                            "branchSequence": 0,
                            "sequence": 6,
                        },
                        "geometry": {"type": "Point", "coordinates": [11.3, 60.3]},
                    },
                    {
                        "type": "Feature",
                        "properties": {"id": "hg-1", "name": "HG1", "pointType": "tp", "featureType": "hidden_gate"},
                        "geometry": {"type": "Point", "coordinates": [11.22, 60.22]},
                    },
                    {
                        "type": "Feature",
                        "properties": {"id": "rts-1", "name": "Route to SP", "featureType": "route_to_sp_path"},
                        "geometry": {"type": "LineString", "coordinates": [[10.9, 59.9], [11.0, 60.0]]},
                    },
                    {
                        "type": "Feature",
                        "properties": {"id": "rfp-1", "name": "Route from FP", "featureType": "route_from_fp_path"},
                        "geometry": {"type": "LineString", "coordinates": [[11.5, 60.5], [11.6, 60.6]]},
                    },
                    {
                        "type": "Feature",
                        "properties": {"id": "obs-1", "name": "Photo 1", "featureType": "observation_photo"},
                        "geometry": {"type": "Point", "coordinates": [11.25, 60.25]},
                    },
                ],
            },
        )
        self.navigation_task.save(update_fields=["task_subtype", "editable_route"])

        compiled = TaskCompiler(self.navigation_task).compile(force=True)

        self.assertTrue(compiled.compiled_payload["is_valid"])
        self.assertEqual(compiled.compiled_payload["compiled_primitives"]["unknown_leg"], ["TRG1"])
        self.assertEqual(
            [segment["name"] for segment in compiled.compiled_payload["unknown_legs_segments"]],
            ["segment_1", "segment_2"],
        )
        self.assertEqual(
            compiled.compiled_payload["unknown_legs_segments"][0]["actual_waypoint_names"],
            ["SP", "HG1", "A", "TRG1"],
        )
        self.assertEqual(
            compiled.compiled_payload["unknown_legs_segments"][0]["display_waypoint_names"],
            ["SP", "HG1", "A", "TRG1", "TRG1-D1"],
        )
        self.assertEqual(
            compiled.compiled_payload["unknown_legs_segments"][0]["display_coordinates_by_name"]["TRG1-D1"],
            [11.3, 60.3],
        )
        self.assertEqual(
            compiled.compiled_payload["unknown_legs_segments"][0]["dummy_branch_waypoints"],
            [{"name": "TRG1-D1", "coordinates": [11.3, 60.3], "trigger_point_id": "wp-trg", "branch_sequence": 0}],
        )
        self.assertEqual(
            compiled.compiled_payload["unknown_legs_actual_route"]["waypoint_names"],
            ["SP", "HG1", "A", "TRG1", "B", "FP"],
        )
        self.assertEqual(
            [item["name"] for item in compiled.compiled_payload["unknown_legs_actual_route"]["waypoints"]],
            ["SP", "HG1", "A", "TRG1", "B", "FP"],
        )
        self.assertEqual(
            compiled.compiled_payload["unknown_legs_actual_route"]["unknown_leg_connectors"][0]["from"],
            "TRG1",
        )
        self.assertEqual(
            compiled.compiled_payload["unknown_legs_actual_route"]["unknown_leg_connectors"][0]["trigger_point_id"],
            "wp-trg",
        )
        self.assertEqual(
            compiled.compiled_payload["unknown_legs_actual_route"]["unknown_leg_connectors"][0]["to"],
            "B",
        )
        self.assertEqual(
            compiled.compiled_payload["unknown_legs_hidden_gates"],
            [{"name": "HG1", "coordinates": [11.22, 60.22]}],
        )

    def test_unknown_legs_treats_hidden_route_backbone_points_as_hidden_gates(self):
        self.navigation_task.task_subtype = UNKNOWN_LEGS
        self.navigation_task.editable_route = EditableRoute.objects.create(
            name="Unknown legs route-backbone hidden gates",
            route={
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"featureType": "route_path"},
                        "geometry": {
                            "type": "LineString",
                            "coordinates": [
                                [11.0, 60.0],
                                [11.1, 60.1],
                                [11.2, 60.2],
                                [11.3, 60.3],
                                [11.4, 60.4],
                                [11.5, 60.5],
                                [11.6, 60.6],
                            ],
                        },
                    },
                    {
                        "type": "Feature",
                        "properties": {
                            "id": "wp-sp",
                            "name": "SP",
                            "pointType": "sp",
                            "featureType": "route_waypoint",
                            "width": 1852,
                            "isTiming": True,
                            "isPassing": True,
                            "sequence": 0,
                        },
                        "geometry": {"type": "Point", "coordinates": [11.0, 60.0]},
                    },
                    {
                        "type": "Feature",
                        "properties": {
                            "id": "wp-h1",
                            "name": "HG1",
                            "pointType": "hidden_gate",
                            "featureType": "route_waypoint",
                            "width": 1852,
                            "isTiming": False,
                            "isPassing": True,
                            "sequence": 1,
                        },
                        "geometry": {"type": "Point", "coordinates": [11.1, 60.1]},
                    },
                    {
                        "type": "Feature",
                        "properties": {
                            "id": "wp-trg",
                            "name": "TRG1",
                            "pointType": "ul",
                            "featureType": "route_waypoint",
                            "width": 1852,
                            "isTiming": False,
                            "isPassing": True,
                            "sequence": 2,
                            "unknownLegHeading": 105,
                        },
                        "geometry": {"type": "Point", "coordinates": [11.2, 60.2]},
                    },
                    {
                        "type": "Feature",
                        "properties": {
                            "id": "wp-h2",
                            "name": "HG2",
                            "pointType": "hidden_gate",
                            "featureType": "route_waypoint",
                            "width": 1852,
                            "isTiming": False,
                            "isPassing": True,
                            "sequence": 4,
                        },
                        "geometry": {"type": "Point", "coordinates": [11.4, 60.4]},
                    },
                    {
                        "type": "Feature",
                        "properties": {
                            "id": "wp-fp",
                            "name": "FP",
                            "pointType": "fp",
                            "featureType": "route_waypoint",
                            "width": 1852,
                            "isTiming": True,
                            "isPassing": True,
                            "sequence": 5,
                        },
                        "geometry": {"type": "Point", "coordinates": [11.5, 60.5]},
                    },
                    {
                        "type": "Feature",
                        "properties": {
                            "id": "dummy-1",
                            "name": "TRG1-D1",
                            "pointType": "dummy",
                            "featureType": "dummy_branch_waypoint",
                            "width": 1852,
                            "isTiming": False,
                            "isPassing": True,
                            "triggerPointId": "wp-trg",
                            "branchSequence": 0,
                            "sequence": 6,
                        },
                        "geometry": {"type": "Point", "coordinates": [11.3, 60.3]},
                    },
                    {
                        "type": "Feature",
                        "properties": {"id": "rts-1", "name": "Route to SP", "featureType": "route_to_sp_path"},
                        "geometry": {"type": "LineString", "coordinates": [[10.9, 59.9], [11.0, 60.0]]},
                    },
                    {
                        "type": "Feature",
                        "properties": {"id": "rfp-1", "name": "Route from FP", "featureType": "route_from_fp_path"},
                        "geometry": {"type": "LineString", "coordinates": [[11.5, 60.5], [11.6, 60.6]]},
                    },
                    {
                        "type": "Feature",
                        "properties": {"id": "obs-1", "name": "Photo 1", "featureType": "observation_photo"},
                        "geometry": {"type": "Point", "coordinates": [11.25, 60.25]},
                    },
                ],
            },
        )
        self.navigation_task.save(update_fields=["task_subtype", "editable_route"])

        compiled = TaskCompiler(self.navigation_task).compile(force=True)

        self.assertTrue(compiled.compiled_payload["is_valid"], compiled.compiled_payload["validation_errors"])
        self.assertEqual(compiled.compiled_payload["compiled_primitives"]["hidden_gate"], ["HG1", "HG2"])
        self.assertEqual(
            [item["name"] for item in compiled.compiled_payload["unknown_legs_hidden_gates"]],
            ["HG1", "HG2"],
        )
        self.assertEqual(
            compiled.compiled_payload["unknown_legs_actual_route"]["waypoint_names"],
            ["SP", "HG1", "TRG1", "HG2", "FP"],
        )

    def test_unknown_legs_treats_hidden_route_backbone_points_authored_as_secret_the_same_way(self):
        """Canonical-form twin of test_unknown_legs_treats_hidden_route_backbone_points_as_hidden_gates:
        new authoring uses pointType 'secret' instead of the legacy 'hidden_gate' alias, and must
        produce byte-identical compiled output."""
        self.navigation_task.task_subtype = UNKNOWN_LEGS
        self.navigation_task.editable_route = EditableRoute.objects.create(
            name="Unknown legs route-backbone secret gates",
            route={
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"featureType": "route_path"},
                        "geometry": {
                            "type": "LineString",
                            "coordinates": [
                                [11.0, 60.0],
                                [11.1, 60.1],
                                [11.2, 60.2],
                                [11.3, 60.3],
                                [11.4, 60.4],
                                [11.5, 60.5],
                                [11.6, 60.6],
                            ],
                        },
                    },
                    {
                        "type": "Feature",
                        "properties": {
                            "id": "wp-sp",
                            "name": "SP",
                            "pointType": "sp",
                            "featureType": "route_waypoint",
                            "width": 1852,
                            "isTiming": True,
                            "isPassing": True,
                            "sequence": 0,
                        },
                        "geometry": {"type": "Point", "coordinates": [11.0, 60.0]},
                    },
                    {
                        "type": "Feature",
                        "properties": {
                            "id": "wp-h1",
                            "name": "HG1",
                            "pointType": "secret",
                            "featureType": "route_waypoint",
                            "width": 1852,
                            "isTiming": False,
                            "isPassing": True,
                            "sequence": 1,
                        },
                        "geometry": {"type": "Point", "coordinates": [11.1, 60.1]},
                    },
                    {
                        "type": "Feature",
                        "properties": {
                            "id": "wp-trg",
                            "name": "TRG1",
                            "pointType": "ul",
                            "featureType": "route_waypoint",
                            "width": 1852,
                            "isTiming": False,
                            "isPassing": True,
                            "sequence": 2,
                            "unknownLegHeading": 105,
                        },
                        "geometry": {"type": "Point", "coordinates": [11.2, 60.2]},
                    },
                    {
                        "type": "Feature",
                        "properties": {
                            "id": "wp-h2",
                            "name": "HG2",
                            "pointType": "secret",
                            "featureType": "route_waypoint",
                            "width": 1852,
                            "isTiming": False,
                            "isPassing": True,
                            "sequence": 4,
                        },
                        "geometry": {"type": "Point", "coordinates": [11.4, 60.4]},
                    },
                    {
                        "type": "Feature",
                        "properties": {
                            "id": "wp-fp",
                            "name": "FP",
                            "pointType": "fp",
                            "featureType": "route_waypoint",
                            "width": 1852,
                            "isTiming": True,
                            "isPassing": True,
                            "sequence": 5,
                        },
                        "geometry": {"type": "Point", "coordinates": [11.5, 60.5]},
                    },
                    {
                        "type": "Feature",
                        "properties": {
                            "id": "dummy-1",
                            "name": "TRG1-D1",
                            "pointType": "dummy",
                            "featureType": "dummy_branch_waypoint",
                            "width": 1852,
                            "isTiming": False,
                            "isPassing": True,
                            "triggerPointId": "wp-trg",
                            "branchSequence": 0,
                            "sequence": 6,
                        },
                        "geometry": {"type": "Point", "coordinates": [11.3, 60.3]},
                    },
                    {
                        "type": "Feature",
                        "properties": {"id": "rts-1", "name": "Route to SP", "featureType": "route_to_sp_path"},
                        "geometry": {"type": "LineString", "coordinates": [[10.9, 59.9], [11.0, 60.0]]},
                    },
                    {
                        "type": "Feature",
                        "properties": {"id": "rfp-1", "name": "Route from FP", "featureType": "route_from_fp_path"},
                        "geometry": {"type": "LineString", "coordinates": [[11.5, 60.5], [11.6, 60.6]]},
                    },
                    {
                        "type": "Feature",
                        "properties": {"id": "obs-1", "name": "Photo 1", "featureType": "observation_photo"},
                        "geometry": {"type": "Point", "coordinates": [11.25, 60.25]},
                    },
                ],
            },
        )
        self.navigation_task.save(update_fields=["task_subtype", "editable_route"])

        compiled = TaskCompiler(self.navigation_task).compile(force=True)

        self.assertTrue(compiled.compiled_payload["is_valid"], compiled.compiled_payload["validation_errors"])
        self.assertEqual(compiled.compiled_payload["compiled_primitives"]["hidden_gate"], ["HG1", "HG2"])
        self.assertEqual(
            [item["name"] for item in compiled.compiled_payload["unknown_legs_hidden_gates"]],
            ["HG1", "HG2"],
        )
        self.assertEqual(
            compiled.compiled_payload["unknown_legs_actual_route"]["waypoint_names"],
            ["SP", "HG1", "TRG1", "HG2", "FP"],
        )

    def test_unknown_legs_hides_post_trigger_secret_stretch_from_visible_segments(self):
        self.navigation_task.task_subtype = UNKNOWN_LEGS
        self.navigation_task.editable_route = EditableRoute.objects.create(
            name="Unknown legs post-trigger hidden stretch",
            route={
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"featureType": "route_path"},
                        "geometry": {
                            "type": "LineString",
                            "coordinates": [
                                [11.0, 60.0],
                                [11.1, 60.1],
                                [11.2, 60.2],
                                [11.25, 60.25],
                                [11.4, 60.4],
                                [11.5, 60.5],
                            ],
                        },
                    },
                    {
                        "type": "Feature",
                        "properties": {
                            "id": "wp-sp",
                            "name": "SP",
                            "pointType": "sp",
                            "featureType": "route_waypoint",
                            "width": 1852,
                            "isTiming": True,
                            "isPassing": True,
                            "sequence": 0,
                        },
                        "geometry": {"type": "Point", "coordinates": [11.0, 60.0]},
                    },
                    {
                        "type": "Feature",
                        "properties": {
                            "id": "wp-trg",
                            "name": "TRG1",
                            "pointType": "ul",
                            "featureType": "route_waypoint",
                            "width": 1852,
                            "isTiming": False,
                            "isPassing": True,
                            "sequence": 1,
                            "unknownLegHeading": 105,
                        },
                        "geometry": {"type": "Point", "coordinates": [11.1, 60.1]},
                    },
                    {
                        "type": "Feature",
                        "properties": {
                            "id": "wp-h1",
                            "name": "Secret 9",
                            "pointType": "secret",
                            "featureType": "route_waypoint",
                            "width": 1852,
                            "isTiming": False,
                            "isPassing": True,
                            "sequence": 2,
                        },
                        "geometry": {"type": "Point", "coordinates": [11.25, 60.25]},
                    },
                    {
                        "type": "Feature",
                        "properties": {
                            "id": "wp-b",
                            "name": "WP 4",
                            "pointType": "tp",
                            "featureType": "route_waypoint",
                            "width": 1852,
                            "isTiming": False,
                            "isPassing": True,
                            "sequence": 3,
                        },
                        "geometry": {"type": "Point", "coordinates": [11.4, 60.4]},
                    },
                    {
                        "type": "Feature",
                        "properties": {
                            "id": "wp-fp",
                            "name": "FP",
                            "pointType": "fp",
                            "featureType": "route_waypoint",
                            "width": 1852,
                            "isTiming": True,
                            "isPassing": True,
                            "sequence": 4,
                        },
                        "geometry": {"type": "Point", "coordinates": [11.5, 60.5]},
                    },
                    {
                        "type": "Feature",
                        "properties": {
                            "id": "dummy-1",
                            "name": "TRG1-D1",
                            "pointType": "dummy",
                            "featureType": "dummy_branch_waypoint",
                            "width": 1852,
                            "isTiming": False,
                            "isPassing": True,
                            "triggerPointId": "wp-trg",
                            "branchSequence": 0,
                            "sequence": 5,
                        },
                        "geometry": {"type": "Point", "coordinates": [11.2, 60.2]},
                    },
                    {
                        "type": "Feature",
                        "properties": {"id": "rts-1", "name": "Route to SP", "featureType": "route_to_sp_path"},
                        "geometry": {"type": "LineString", "coordinates": [[10.9, 59.9], [11.0, 60.0]]},
                    },
                    {
                        "type": "Feature",
                        "properties": {"id": "rfp-1", "name": "Route from FP", "featureType": "route_from_fp_path"},
                        "geometry": {"type": "LineString", "coordinates": [[11.5, 60.5], [11.6, 60.6]]},
                    },
                    {
                        "type": "Feature",
                        "properties": {"id": "obs-1", "name": "Photo 1", "featureType": "observation_photo"},
                        "geometry": {"type": "Point", "coordinates": [11.15, 60.15]},
                    },
                ],
            },
        )
        self.navigation_task.save(update_fields=["task_subtype", "editable_route"])

        compiled = TaskCompiler(self.navigation_task).compile(force=True)

        self.assertTrue(compiled.compiled_payload["is_valid"], compiled.compiled_payload["validation_errors"])
        self.assertEqual(
            compiled.compiled_payload["unknown_legs_segments"][0]["display_waypoint_names"],
            ["SP", "TRG1", "TRG1-D1"],
        )
        self.assertEqual(
            compiled.compiled_payload["unknown_legs_segments"][1]["display_waypoint_names"],
            ["WP 4", "FP"],
        )
        self.assertEqual(
            [item["name"] for item in compiled.compiled_payload["unknown_legs_hidden_gates"]],
            ["Secret 9"],
        )
        self.assertEqual(
            compiled.compiled_payload["unknown_legs_actual_route"]["waypoint_names"],
            ["SP", "TRG1", "Secret 9", "WP 4", "FP"],
        )

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
        self.assertEqual(compiled.compiled_payload["compiled_primitives"]["route_to_sp_path"], ["Route to SP"])
        self.assertEqual(compiled.compiled_payload["compiled_primitives"]["route_from_fp_path"], ["Route from FP"])
        self.assertEqual(
            compiled.compiled_payload["compiled_auxiliary_paths"]["route_to_sp_path"],
            [[[10.9, 59.9], [11.0, 60.0]]],
        )
        self.assertEqual(
            compiled.compiled_payload["compiled_auxiliary_paths"]["route_from_fp_path"],
            [[[11.1, 60.1], [11.2, 60.2]]],
        )

    def test_task_compiler_allows_anr_without_auxiliary_paths(self):
        # route_to_sp_path/route_from_fp_path are optional auxiliary compliance features (see
        # anr_corridor_calculator.py) that most routes never author - omitting them does not make
        # the task invalid.
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
                    },
                    {
                        "type": "Feature",
                        "properties": {
                            "id": "wp-1",
                            "name": "SP",
                            "pointType": "sp",
                            "featureType": "route_waypoint",
                            "width": 1852,
                            "isTiming": True,
                            "isPassing": True,
                            "sequence": 0,
                        },
                        "geometry": {"type": "Point", "coordinates": [11.0, 60.0]},
                    },
                    {
                        "type": "Feature",
                        "properties": {
                            "id": "wp-2",
                            "name": "FP",
                            "pointType": "fp",
                            "featureType": "route_waypoint",
                            "width": 1852,
                            "isTiming": True,
                            "isPassing": True,
                            "sequence": 1,
                        },
                        "geometry": {"type": "Point", "coordinates": [11.1, 60.1]},
                    },
                ],
            },
        )
        self.navigation_task.save(update_fields=["task_subtype", "editable_route"])

        compiled = TaskCompiler(self.navigation_task).compile(force=True)
        self.assertTrue(compiled.compiled_payload["is_valid"], compiled.compiled_payload["validation_errors"])
