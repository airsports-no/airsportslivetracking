import datetime
from unittest.mock import MagicMock, patch

from django.test import TestCase

from display.calculators.backtracking_and_procedure_turns import BacktrackingAndProcedureTurnsCalculator
from display.calculators.gate_calculator import GateCalculator
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
from display.utilities.cima_task_type_definitions import CONTRACT_NAVIGATION_TIME_CONTROLS
from utilities.mock_utilities import TraccarMock


class TestCompiledEffectiveRouteAccess(TestCase):
    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, *args):
        create_scorecards()
        self.scorecard = Scorecard.get_originals().get(shortcut_name="FAI Precision")
        with open("display/tests/NM.csv", "r") as file:
            editable_route, _ = EditableRoute.create_from_csv("Compiled access", file.readlines()[1:])
            self.route = editable_route.create_precision_route(True, self.scorecard)

        self.contest = Contest.objects.create(
            name="Compiled access contest",
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc),
            time_zone="Europe/Oslo",
        )
        self.navigation_task = NavigationTask.create(
            name="Compiled access task",
            contest=self.contest,
            route=self.route,
            original_scorecard=self.scorecard,
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc),
        )
        crew = Crew.objects.create(member1=Person.objects.create(first_name="Pilot", last_name="Access"))
        team = Team.objects.create(crew=crew, aeroplane=Aeroplane.objects.create(registration="LN-ACCESS"))
        start_time = datetime.datetime(2020, 8, 1, 8, 5, tzinfo=datetime.timezone.utc)
        self.contestant = Contestant.objects.create(
            navigation_task=self.navigation_task,
            team=team,
            takeoff_time=start_time,
            tracker_start_time=start_time - datetime.timedelta(minutes=30),
            finished_by_time=start_time + datetime.timedelta(hours=2),
            tracker_device_id="compiled-access",
            contestant_number=1,
            minutes_to_starting_point=6,
            air_speed=75,
            wind_direction=165,
            wind_speed=8,
        )

    def test_contestant_effective_waypoint_names_defaults_to_route_waypoints(self):
        names = self.contestant.get_effective_waypoint_names()
        self.assertEqual(names[0], self.navigation_task.route.waypoints[0].name)
        self.assertEqual(names[-1], self.navigation_task.route.waypoints[-1].name)

    def test_contestant_effective_waypoint_names_prefers_compiled_configuration(self):
        editable_route = EditableRoute.objects.create(
            name="Contract access primitives",
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
                        "properties": {"id": "wp-sp", "name": "SP", "pointType": "sp", "featureType": "route_waypoint", "sequence": 0},
                        "geometry": {"type": "Point", "coordinates": [11.0, 60.0]},
                    },
                    {
                        "type": "Feature",
                        "properties": {"id": "wp-mp", "name": "MP", "pointType": "tp", "featureType": "route_waypoint", "sequence": 1},
                        "geometry": {"type": "Point", "coordinates": [11.1, 60.1]},
                    },
                    {
                        "type": "Feature",
                        "properties": {"id": "wp-fp", "name": "FP", "pointType": "fp", "featureType": "route_waypoint", "sequence": 2},
                        "geometry": {"type": "Point", "coordinates": [11.2, 60.2]},
                    },
                    {
                        "type": "Feature",
                        "properties": {"id": "cat-1", "name": "A", "pointType": "tp", "featureType": "catalogue_turnpoint"},
                        "geometry": {"type": "Point", "coordinates": [11.2, 60.2]},
                    },
                ],
            },
        )
        self.navigation_task.task_subtype = CONTRACT_NAVIGATION_TIME_CONTROLS
        self.navigation_task.editable_route = editable_route
        self.navigation_task.save(update_fields=["task_subtype", "editable_route"])
        ContestantTaskCompiler(self.contestant).compile(
            declaration_payload={"declared_sequence": ["A", "MP", "FP"], "declared_t_seconds": 600},
            force=True,
        )

        names = self.contestant.get_effective_waypoint_names()
        self.assertEqual(names, ["SP", "A", "MP", "FP"])

    @patch("display.calculators.positions_and_gates.Gate.pre_project")
    @patch("display.calculators.gate_calculator.calculate_extended_gate")
    def test_gate_calculator_uses_effective_waypoint_names(self, _mock_extended_gate, _mock_pre_project):
        editable_route = EditableRoute.objects.create(
            name="Contract calc primitives",
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
                        "properties": {"id": "wp-sp", "name": "SP", "pointType": "sp", "featureType": "route_waypoint", "sequence": 0},
                        "geometry": {"type": "Point", "coordinates": [11.0, 60.0]},
                    },
                    {
                        "type": "Feature",
                        "properties": {"id": "wp-mp", "name": "MP", "pointType": "tp", "featureType": "route_waypoint", "sequence": 1},
                        "geometry": {"type": "Point", "coordinates": [11.1, 60.1]},
                    },
                    {
                        "type": "Feature",
                        "properties": {"id": "wp-fp", "name": "FP", "pointType": "fp", "featureType": "route_waypoint", "sequence": 2},
                        "geometry": {"type": "Point", "coordinates": [11.2, 60.2]},
                    },
                    {
                        "type": "Feature",
                        "properties": {"id": "cat-1", "name": "A", "pointType": "tp", "featureType": "catalogue_turnpoint"},
                        "geometry": {"type": "Point", "coordinates": [11.2, 60.2]},
                    },
                ],
            },
        )
        self.navigation_task.task_subtype = CONTRACT_NAVIGATION_TIME_CONTROLS
        self.navigation_task.editable_route = editable_route
        self.navigation_task.save(update_fields=["task_subtype", "editable_route"])
        ContestantTaskCompiler(self.contestant).compile(
            declaration_payload={"declared_sequence": ["A", "MP", "FP"], "declared_t_seconds": 600},
            force=True,
        )

        calculator = GateCalculator(
            self.contestant,
            self.scorecard,
            self.route,
            MagicMock(),
            live_processing=False,
            projector=self.navigation_task.get_projector(),
        )
        gate_names = [gate.name for gate in calculator.gates]
        self.assertEqual(gate_names, ["SP", "A", "MP", "FP"])
        self.assertAlmostEqual(calculator.gates[1].latitude, 60.2)
        self.assertAlmostEqual(calculator.gates[1].longitude, 11.2)

    @patch("display.calculators.positions_and_gates.Gate.pre_project")
    def test_backtracking_calculator_uses_effective_waypoint_names(self, _mock_pre_project):
        editable_route = EditableRoute.objects.create(
            name="Contract backtracking primitives",
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
                        "properties": {"id": "wp-sp", "name": "SP", "pointType": "sp", "featureType": "route_waypoint", "sequence": 0},
                        "geometry": {"type": "Point", "coordinates": [11.0, 60.0]},
                    },
                    {
                        "type": "Feature",
                        "properties": {"id": "wp-mp", "name": "MP", "pointType": "tp", "featureType": "route_waypoint", "sequence": 1},
                        "geometry": {"type": "Point", "coordinates": [11.1, 60.1]},
                    },
                    {
                        "type": "Feature",
                        "properties": {"id": "wp-fp", "name": "FP", "pointType": "fp", "featureType": "route_waypoint", "sequence": 2},
                        "geometry": {"type": "Point", "coordinates": [11.2, 60.2]},
                    },
                    {
                        "type": "Feature",
                        "properties": {"id": "cat-1", "name": "A", "pointType": "tp", "featureType": "catalogue_turnpoint"},
                        "geometry": {"type": "Point", "coordinates": [11.2, 60.2]},
                    },
                ],
            },
        )
        self.navigation_task.task_subtype = CONTRACT_NAVIGATION_TIME_CONTROLS
        self.navigation_task.editable_route = editable_route
        self.navigation_task.save(update_fields=["task_subtype", "editable_route"])
        ContestantTaskCompiler(self.contestant).compile(
            declaration_payload={"declared_sequence": ["A", "MP", "FP"], "declared_t_seconds": 600},
            force=True,
        )

        calculator = BacktrackingAndProcedureTurnsCalculator(
            self.contestant,
            self.scorecard,
            self.route,
            MagicMock(),
            live_processing=False,
            projector=self.navigation_task.get_projector(),
        )
        gate_names = [gate.name for gate in calculator.gates]
        self.assertEqual(gate_names, ["SP", "A", "MP", "FP"])
        self.assertAlmostEqual(calculator.gates[1].latitude, 60.2)
        self.assertAlmostEqual(calculator.gates[1].longitude, 11.2)
