import datetime
from unittest.mock import patch

from django.test import TestCase

from display.default_scorecards.create_scorecards import create_scorecards
from display.models import (
    Aeroplane,
    Contest,
    Contestant,
    Crew,
    EditableRoute,
    NavigationTask,
    Person,
    Scorecard,
    Team,
)
from display.services.contestant_task_compiler import ContestantTaskCompiler
from display.utilities.cima_task_type_definitions import (
    ANR_CATALOGUE,
    CONTRACT_NAVIGATION_TIME_CONTROLS,
    CURVE_NAVIGATION_TIME_ESTIMATION,
    KNOWN_CIRCUIT,
    LIMITED_FUEL_TURNPOINT_HUNT,
    TURNPOINT_HUNT,
    UNKNOWN_LEGS,
)
from utilities.mock_utilities import TraccarMock


class TestContestantTaskConfiguration(TestCase):
    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, *args):
        create_scorecards()
        self.scorecard = Scorecard.get_originals().get(shortcut_name="FAI Precision")
        with open("display/tests/NM.csv", "r") as file:
            editable_route, _ = EditableRoute.create_from_csv("Config test", file.readlines()[1:])
            self.route = editable_route.create_precision_route(True, self.scorecard)
        self.editable_route = EditableRoute.objects.create(
            name="Contestant config primitives",
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
                        "properties": {"id": "kt-1", "name": "SP", "pointType": "tp", "featureType": "known_time_gate"},
                        "geometry": {"type": "Point", "coordinates": [11.0, 60.0]},
                    },
                    {
                        "type": "Feature",
                        "properties": {"id": "hg-1", "name": "HG1", "pointType": "tp", "featureType": "hidden_gate"},
                        "geometry": {"type": "Point", "coordinates": [11.2, 60.2]},
                    },
                ],
            },
        )
        self.contest = Contest.objects.create(
            name="Contestant config contest",
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc),
            time_zone="Europe/Oslo",
        )
        self.navigation_task = NavigationTask.create(
            name="Contestant config task",
            contest=self.contest,
            route=self.route,
            editable_route=self.editable_route,
            original_scorecard=self.scorecard,
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc),
            task_subtype=CURVE_NAVIGATION_TIME_ESTIMATION,
        )
        crew = Crew.objects.create(member1=Person.objects.create(first_name="Pilot", last_name="One"))
        team = Team.objects.create(crew=crew, aeroplane=Aeroplane.objects.create(registration="LN-CONFIG"))
        start_time = datetime.datetime(2020, 8, 1, 8, 5, tzinfo=datetime.timezone.utc)
        self.contestant = Contestant.objects.create(
            navigation_task=self.navigation_task,
            team=team,
            takeoff_time=start_time,
            tracker_start_time=start_time - datetime.timedelta(minutes=30),
            finished_by_time=start_time + datetime.timedelta(hours=2),
            tracker_device_id="config-test",
            contestant_number=1,
            minutes_to_starting_point=6,
            air_speed=75,
            wind_direction=165,
            wind_speed=8,
        )

    def test_contestant_task_compiler_creates_configuration(self):
        compiled = ContestantTaskCompiler(self.contestant).compile(
            declaration_payload={"known_time_gate_predictions": {"SP": "2020-08-01T08:11:00Z"}}
        )
        self.assertEqual(compiled.contestant, self.contestant)
        self.assertEqual(compiled.task_subtype, CURVE_NAVIGATION_TIME_ESTIMATION)
        self.assertTrue(compiled.is_valid)
        self.assertEqual(
            compiled.declaration_payload,
            {"known_time_gate_predictions": {"SP": "2020-08-01T08:11:00Z"}},
        )
        self.assertIn("SP", compiled.compiled_gate_times_payload)

    def test_contestant_gate_times_prefers_compiled_configuration(self):
        compiled = ContestantTaskCompiler(self.contestant).compile(
            declaration_payload={"known_time_gate_predictions": {"SP": "2020-08-01T08:11:00Z"}}
        )
        self.assertTrue(compiled.is_valid)
        gate_times = self.contestant.gate_times
        self.assertEqual(gate_times["SP"].isoformat(), "2020-08-01T08:11:00+00:00")

    def test_contestant_task_compiler_includes_compiled_task_primitives(self):
        editable_route = EditableRoute.objects.create(
            name="Primitive backed config",
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
                ],
            },
        )
        self.navigation_task.editable_route = editable_route
        self.navigation_task.save(update_fields=["editable_route"])

        compiled = ContestantTaskCompiler(self.contestant).compile(
            declaration_payload={"known_time_gate_predictions": {"KT1": "2020-08-01T08:12:00Z"}},
            force=True,
        )
        self.assertIn("compiled_task_primitives", compiled.compiled_effective_route_payload)
        self.assertEqual(
            compiled.compiled_effective_route_payload["compiled_task_primitives"]["known_time_gate"],
            ["KT1"],
        )

    def test_curve_navigation_requires_known_time_gate_predictions_for_compiled_gate_times(self):
        compiled = ContestantTaskCompiler(self.contestant).compile(
            declaration_payload={"known_time_gate_predictions": {"SP": "2020-08-01T08:11:00Z"}},
            force=True,
        )
        self.assertIn("known_time_gate_predictions", compiled.declaration_payload)
        self.assertEqual(compiled.compiled_gate_times_payload["SP"], "2020-08-01T08:11:00+00:00")

    def test_curve_navigation_rejects_declaration_beyond_tmax(self):
        self.navigation_task.task_config = {"curve_navigation_tmax_seconds": 600}
        self.navigation_task.save(update_fields=["task_config"])

        compiled = ContestantTaskCompiler(self.contestant).compile(
            declaration_payload={
                "known_time_gate_predictions": {
                    "SP": "2020-08-01T08:11:00Z",
                    "FP": "2020-08-01T08:22:30Z",
                }
            },
            force=True,
        )

        self.assertFalse(compiled.is_valid)
        self.assertIn("Curve navigation declarations may not exceed Tmax.", compiled.validation_errors)

    def test_contract_navigation_compiles_declared_sequence_from_catalogue_turnpoints(self):
        editable_route = EditableRoute.objects.create(
            name="Contract nav primitives",
            route={
                "type": "FeatureCollection",
                "features": [
                    {"type": "Feature", "properties": {"featureType": "route_path"}, "geometry": {"type": "LineString", "coordinates": [[11.0, 60.0], [11.1, 60.1]]}},
                    {"type": "Feature", "properties": {"id": "wp-sp", "name": "SP", "pointType": "sp", "featureType": "route_waypoint", "width": 1852, "isTiming": True, "isPassing": True, "sequence": 0}, "geometry": {"type": "Point", "coordinates": [11.0, 60.0]}},
                    {"type": "Feature", "properties": {"id": "wp-mp", "name": "MP", "pointType": "tp", "featureType": "route_waypoint", "width": 1852, "isTiming": True, "isPassing": True, "sequence": 1}, "geometry": {"type": "Point", "coordinates": [11.1, 60.1]}},
                    {"type": "Feature", "properties": {"id": "wp-fp", "name": "FP", "pointType": "fp", "featureType": "route_waypoint", "width": 1852, "isTiming": True, "isPassing": True, "sequence": 2}, "geometry": {"type": "Point", "coordinates": [11.2, 60.2]}},
                    {"type": "Feature", "properties": {"id": "cat-1", "name": "A", "pointType": "tp", "featureType": "catalogue_turnpoint"}, "geometry": {"type": "Point", "coordinates": [11.2, 60.2]}},
                    {"type": "Feature", "properties": {"id": "cat-2", "name": "B", "pointType": "tp", "featureType": "catalogue_turnpoint"}, "geometry": {"type": "Point", "coordinates": [11.3, 60.3]}},
                    {"type": "Feature", "properties": {"id": "cat-3", "name": "MP", "pointType": "tp", "featureType": "catalogue_turnpoint"}, "geometry": {"type": "Point", "coordinates": [11.25, 60.25]}},
                ],
            },
        )
        self.navigation_task.task_subtype = CONTRACT_NAVIGATION_TIME_CONTROLS
        self.navigation_task.task_config = {"contract_time_seconds": 600}
        self.navigation_task.editable_route = editable_route
        self.navigation_task.save(update_fields=["task_subtype", "task_config", "editable_route"])

        compiled = ContestantTaskCompiler(self.contestant).compile(
            declaration_payload={"declared_sequence": ["A", "B", "MP", "FP"]},
            force=True,
        )
        self.assertTrue(compiled.is_valid)
        self.assertEqual(
            compiled.compiled_effective_route_payload["declared_sequence"],
            ["A", "B", "MP", "FP"],
        )
        self.assertEqual(
            compiled.compiled_effective_route_payload["effective_waypoint_names"],
            ["SP", "A", "B", "MP", "FP"],
        )
        self.assertEqual(compiled.compiled_effective_route_payload["time_model"]["t_seconds"], 600)

    def test_turnpoint_hunt_compiles_compulsory_point_times_without_predicted_sequence(self):
        editable_route = EditableRoute.objects.create(
            name="Turnpoint hunt primitives",
            route={
                "type": "FeatureCollection",
                "features": [
                    {"type": "Feature", "properties": {"id": "cat-1", "name": "A", "pointType": "tp", "featureType": "catalogue_turnpoint"}, "geometry": {"type": "Point", "coordinates": [11.2, 60.2]}},
                    {"type": "Feature", "properties": {"id": "cat-2", "name": "B", "pointType": "tp", "featureType": "catalogue_turnpoint"}, "geometry": {"type": "Point", "coordinates": [11.3, 60.3]}},
                    {"type": "Feature", "properties": {"id": "kt-1", "name": "CP1", "pointType": "tp", "featureType": "known_time_gate"}, "geometry": {"type": "Point", "coordinates": [11.25, 60.25]}},
                    {"type": "Feature", "properties": {"id": "kt-2", "name": "CP2", "pointType": "tp", "featureType": "known_time_gate"}, "geometry": {"type": "Point", "coordinates": [11.35, 60.35]}},
                    {"type": "Feature", "properties": {"id": "kt-3", "name": "CP3", "pointType": "tp", "featureType": "known_time_gate"}, "geometry": {"type": "Point", "coordinates": [11.45, 60.45]}},
                    {"type": "Feature", "properties": {"id": "obs-1", "name": "A", "featureType": "observation_photo"}, "geometry": {"type": "Point", "coordinates": [11.35, 60.35]}},
                    {"type": "Feature", "properties": {"id": "obs-2", "name": "B", "featureType": "observation_photo"}, "geometry": {"type": "Point", "coordinates": [11.36, 60.36]}},
                ],
            },
        )
        self.navigation_task.task_subtype = TURNPOINT_HUNT
        self.navigation_task.editable_route = editable_route
        self.navigation_task.save(update_fields=["task_subtype", "editable_route"])

        compiled = ContestantTaskCompiler(self.contestant).compile(
            declaration_payload={
                "compulsory_point_times": {
                    "CP1": "2020-08-01T08:15:00Z",
                    "CP2": "2020-08-01T08:16:00Z",
                    "CP3": "2020-08-01T08:17:00Z",
                },
            },
            force=True,
        )

        self.assertTrue(compiled.is_valid)
        self.assertEqual(compiled.compiled_gate_times_payload["CP1"], "2020-08-01T08:15:00+00:00")
        self.assertEqual(compiled.compiled_effective_route_payload["compulsory_point_names"], ["CP1", "CP2", "CP3"])
        self.assertEqual(compiled.compiled_effective_route_payload["free_target_names"], ["A", "B"])
        self.assertEqual(compiled.compiled_effective_route_payload["free_target_evidence"], {"A": ["A"], "B": ["B"]})

    def test_limited_fuel_turnpoint_hunt_preserves_fuel_metadata(self):
        editable_route = EditableRoute.objects.create(
            name="Limited fuel primitives",
            route={
                "type": "FeatureCollection",
                "features": [
                    {"type": "Feature", "properties": {"id": "cat-1", "name": "A", "pointType": "tp", "featureType": "catalogue_turnpoint"}, "geometry": {"type": "Point", "coordinates": [11.2, 60.2]}},
                    {"type": "Feature", "properties": {"id": "kt-1", "name": "CP1", "pointType": "tp", "featureType": "known_time_gate"}, "geometry": {"type": "Point", "coordinates": [11.25, 60.25]}},
                    {"type": "Feature", "properties": {"id": "kt-2", "name": "CP2", "pointType": "tp", "featureType": "known_time_gate"}, "geometry": {"type": "Point", "coordinates": [11.35, 60.35]}},
                    {"type": "Feature", "properties": {"id": "kt-3", "name": "CP3", "pointType": "tp", "featureType": "known_time_gate"}, "geometry": {"type": "Point", "coordinates": [11.45, 60.45]}},
                    {"type": "Feature", "properties": {"id": "obs-1", "name": "A", "featureType": "observation_photo"}, "geometry": {"type": "Point", "coordinates": [11.35, 60.35]}},
                ],
            },
        )
        self.navigation_task.task_subtype = LIMITED_FUEL_TURNPOINT_HUNT
        self.navigation_task.editable_route = editable_route
        self.navigation_task.save(update_fields=["task_subtype", "editable_route"])

        compiled = ContestantTaskCompiler(self.contestant).compile(
            declaration_payload={
                "compulsory_point_times": {
                    "CP1": "2020-08-01T08:16:00Z",
                    "CP2": "2020-08-01T08:17:00Z",
                    "CP3": "2020-08-01T08:18:00Z",
                },
                "fuel_metadata": {"declared_endurance_minutes": 95},
            },
            force=True,
        )

        self.assertTrue(compiled.is_valid)
        self.assertEqual(compiled.declaration_payload["fuel_metadata"], {"declared_endurance_minutes": 95})
        self.assertEqual(compiled.compiled_effective_route_payload["fuel_metadata"], {"declared_endurance_minutes": 95})
        self.assertEqual(compiled.compiled_gate_times_payload["CP1"], "2020-08-01T08:16:00+00:00")
        self.assertEqual(compiled.compiled_effective_route_payload["compulsory_timing_gate_names"], ["CP1", "CP2", "CP3"])

    def test_turnpoint_hunt_requires_exactly_three_compulsory_point_times(self):
        editable_route = EditableRoute.objects.create(
            name="Turnpoint validation primitives",
            route={
                "type": "FeatureCollection",
                "features": [
                    {"type": "Feature", "properties": {"id": "cat-1", "name": "A", "pointType": "tp", "featureType": "catalogue_turnpoint"}, "geometry": {"type": "Point", "coordinates": [11.2, 60.2]}},
                    {"type": "Feature", "properties": {"id": "kt-1", "name": "CP1", "pointType": "tp", "featureType": "known_time_gate"}, "geometry": {"type": "Point", "coordinates": [11.25, 60.25]}},
                    {"type": "Feature", "properties": {"id": "kt-2", "name": "CP2", "pointType": "tp", "featureType": "known_time_gate"}, "geometry": {"type": "Point", "coordinates": [11.35, 60.35]}},
                    {"type": "Feature", "properties": {"id": "kt-3", "name": "CP3", "pointType": "tp", "featureType": "known_time_gate"}, "geometry": {"type": "Point", "coordinates": [11.45, 60.45]}},
                    {"type": "Feature", "properties": {"id": "obs-1", "name": "A", "featureType": "observation_photo"}, "geometry": {"type": "Point", "coordinates": [11.35, 60.35]}},
                ],
            },
        )
        self.navigation_task.task_subtype = TURNPOINT_HUNT
        self.navigation_task.editable_route = editable_route
        self.navigation_task.save(update_fields=["task_subtype", "editable_route"])

        compiled = ContestantTaskCompiler(self.contestant).compile(
            declaration_payload={
                "compulsory_point_times": {
                    "CP1": "2020-08-01T08:15:00Z",
                    "CP2": "2020-08-01T08:16:00Z",
                },
            },
            force=True,
        )

        self.assertFalse(compiled.is_valid)
        joined_errors = " ".join(compiled.validation_errors)
        self.assertIn("exactly three compulsory point times", joined_errors)

    def test_anr_catalogue_includes_auxiliary_paths_in_effective_payload(self):
        editable_route = EditableRoute.objects.create(
            name="ANR auxiliary paths",
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
                        "geometry": {"type": "LineString", "coordinates": [[11.1, 60.1], [11.2, 60.0]]},
                    },
                ],
            },
        )
        self.navigation_task.task_subtype = ANR_CATALOGUE
        self.navigation_task.editable_route = editable_route
        self.navigation_task.save(update_fields=["task_subtype", "editable_route"])

        compiled = ContestantTaskCompiler(self.contestant).compile(force=True)

        self.assertTrue(compiled.is_valid)
        self.assertEqual(
            compiled.compiled_effective_route_payload["compiled_auxiliary_paths"]["route_to_sp_path"],
            [[[10.9, 59.9], [11.0, 60.0]]],
        )
        self.assertEqual(
            compiled.compiled_effective_route_payload["compiled_auxiliary_paths"]["route_from_fp_path"],
            [[[11.1, 60.1], [11.2, 60.0]]],
        )

    def test_anr_catalogue_propagates_missing_auxiliary_path_validation(self):
        editable_route = EditableRoute.objects.create(
            name="ANR missing auxiliary paths",
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
        self.navigation_task.task_subtype = ANR_CATALOGUE
        self.navigation_task.editable_route = editable_route
        self.navigation_task.save(update_fields=["task_subtype", "editable_route"])

        compiled = ContestantTaskCompiler(self.contestant).compile(force=True)

        self.assertFalse(compiled.is_valid)
        joined_errors = " ".join(compiled.validation_errors)
        self.assertIn("route_to_sp_path", joined_errors)
        self.assertIn("route_from_fp_path", joined_errors)

    def test_known_circuit_includes_observation_photos_in_effective_payload(self):
        editable_route = EditableRoute.objects.create(
            name="Known circuit evidence primitives",
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
                    {
                        "type": "Feature",
                        "properties": {"id": "obs-1", "name": "Photo 1", "featureType": "observation_photo"},
                        "geometry": {"type": "Point", "coordinates": [11.35, 60.35]},
                    },
                ],
            },
        )
        self.navigation_task.task_subtype = KNOWN_CIRCUIT
        self.navigation_task.editable_route = editable_route
        self.navigation_task.save(update_fields=["task_subtype", "editable_route"])

        compiled = ContestantTaskCompiler(self.contestant).compile(force=True)

        self.assertTrue(compiled.is_valid)
        self.assertEqual(
            compiled.compiled_effective_route_payload["observation_judging_mode"],
            "external_manual",
        )
        self.assertEqual(
            compiled.compiled_effective_route_payload["manual_adjudication_categories"],
            ["observation", "map"],
        )
        self.assertEqual(
            compiled.compiled_effective_route_payload["observation_photos"][0]["name"],
            "Photo 1",
        )
        self.assertEqual(
            compiled.compiled_effective_route_payload["observation_photos"][0]["coordinates"],
            [11.35, 60.35],
        )
        self.assertEqual(
            compiled.compiled_effective_route_payload["observation_photos"][0]["evidence_category"],
            "observation",
        )
        self.assertEqual(
            compiled.compiled_effective_route_payload["hidden_gate_names"],
            ["HG1"],
        )

    def test_unknown_legs_includes_unknown_leg_and_observation_photo_payload(self):
        editable_route = EditableRoute.objects.create(
            name="Unknown legs evidence primitives",
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
                        "geometry": {"type": "Point", "coordinates": [11.35, 60.35]},
                    },
                ],
            },
        )
        self.navigation_task.task_subtype = UNKNOWN_LEGS
        self.navigation_task.editable_route = editable_route
        self.navigation_task.save(update_fields=["task_subtype", "editable_route"])

        compiled = ContestantTaskCompiler(self.contestant).compile(force=True)

        self.assertTrue(compiled.is_valid)
        self.assertEqual(
            compiled.compiled_effective_route_payload["observation_judging_mode"],
            "external_manual",
        )
        self.assertEqual(
            compiled.compiled_effective_route_payload["manual_adjudication_categories"],
            ["observation", "map"],
        )
        self.assertEqual(compiled.compiled_effective_route_payload["unknown_leg_names"], ["UL1"])
        self.assertEqual(
            compiled.compiled_effective_route_payload["observation_photos"][0]["name"],
            "Photo 1",
        )
        self.assertEqual(
            compiled.compiled_effective_route_payload["observation_photos"][0]["evidence_category"],
            "observation",
        )

    def test_known_circuit_effective_payload_is_available_via_contestant_configuration(self):
        editable_route = EditableRoute.objects.create(
            name="Known circuit contestant payload",
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
                    {
                        "type": "Feature",
                        "properties": {"id": "obs-1", "name": "Photo 1", "featureType": "observation_photo"},
                        "geometry": {"type": "Point", "coordinates": [11.35, 60.35]},
                    },
                ],
            },
        )
        self.navigation_task.task_subtype = KNOWN_CIRCUIT
        self.navigation_task.editable_route = editable_route
        self.navigation_task.save(update_fields=["task_subtype", "editable_route"])

        ContestantTaskCompiler(self.contestant).compile(force=True)

        payload = self.contestant.contestanttaskconfiguration.compiled_effective_route_payload
        self.assertEqual(payload["hidden_gate_names"], ["HG1"])
        self.assertEqual(payload["observation_judging_mode"], "external_manual")
        self.assertEqual(payload["manual_adjudication_categories"], ["observation", "map"])
        self.assertEqual(payload["observation_photos"][0]["name"], "Photo 1")

    def test_duration_effective_payload_preserves_duration_review_config(self):
        self.navigation_task.task_subtype = "duration"
        self.navigation_task.scorecard.duration_normalization_policy = "raw_minutes"
        self.navigation_task.scorecard.duration_residual_fuel_required = True
        self.navigation_task.scorecard.save(update_fields=["duration_normalization_policy", "duration_residual_fuel_required"])
        self.navigation_task.editable_route = EditableRoute.objects.create(
            name="Duration review primitives",
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
                            "id": "dla-1",
                            "name": "Duration Landing Area",
                            "featureType": "zone",
                            "polygonType": "duration_landing_area",
                        },
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[[11.0, 60.0], [11.2, 60.0], [11.2, 60.2], [11.0, 60.2], [11.0, 60.0]]],
                        },
                    },
                ],
            },
        )
        self.navigation_task.save(update_fields=["task_subtype", "editable_route"])

        compiled = ContestantTaskCompiler(self.contestant).compile(force=True)

        self.assertTrue(compiled.is_valid)
        self.assertEqual(
            compiled.compiled_effective_route_payload["duration_review"],
            {
                "duration_normalization_policy": "raw_minutes",
                "duration_landing_area_polygon": [[11.0, 60.0], [11.2, 60.0], [11.2, 60.2], [11.0, 60.2]],
                "duration_residual_fuel_required": True,
            },
        )
