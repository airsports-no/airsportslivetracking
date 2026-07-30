import datetime
from queue import Queue
from unittest.mock import MagicMock, patch

from django.test import TestCase

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


class TestContractNavigationTimingModel(TestCase):
    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, *args):
        create_scorecards()
        self.scorecard = Scorecard.get_originals().get(shortcut_name="FAI Precision")
        with open("display/tests/NM.csv", "r") as file:
            editable_route, _ = EditableRoute.create_from_csv("Contract timing", file.readlines()[1:])
            self.route = editable_route.create_precision_route(True, self.scorecard)

        self.contest = Contest.objects.create(
            name="Contract timing contest",
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc),
            time_zone="Europe/Oslo",
        )
        self.navigation_task = NavigationTask.create(
            name="Contract timing task",
            contest=self.contest,
            route=self.route,
            original_scorecard=self.scorecard,
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc),
            task_subtype=CONTRACT_NAVIGATION_TIME_CONTROLS,
            task_config={"contract_time_seconds": 600},
        )
        crew = Crew.objects.create(member1=Person.objects.create(first_name="Pilot", last_name="Timing"))
        team = Team.objects.create(crew=crew, aeroplane=Aeroplane.objects.create(registration="LN-TIMING"))
        start_time = datetime.datetime(2020, 8, 1, 8, 5, tzinfo=datetime.timezone.utc)
        self.contestant = Contestant.objects.create(
            navigation_task=self.navigation_task,
            team=team,
            takeoff_time=start_time,
            tracker_start_time=start_time - datetime.timedelta(minutes=30),
            finished_by_time=start_time + datetime.timedelta(hours=2),
            tracker_device_id="contract-timing",
            contestant_number=1,
            minutes_to_starting_point=6,
            air_speed=75,
            wind_direction=165,
            wind_speed=8,
        )

    def _contract_editable_route(self, include_after_point: bool = False):
        features = [
            {"type": "Feature", "properties": {"featureType": "route_path"}, "geometry": {"type": "LineString", "coordinates": [[11.0, 60.0], [11.1, 60.1]]}},
            {"type": "Feature", "properties": {"id": "wp-sp", "name": "SP", "pointType": "sp", "featureType": "route_waypoint", "width": 1852, "isTiming": True, "isPassing": True, "sequence": 0}, "geometry": {"type": "Point", "coordinates": [11.0, 60.0]}},
            {"type": "Feature", "properties": {"id": "wp-mp", "name": "MP", "pointType": "tp", "featureType": "route_waypoint", "width": 1852, "isTiming": True, "isPassing": True, "sequence": 1}, "geometry": {"type": "Point", "coordinates": [11.1, 60.1]}},
            {"type": "Feature", "properties": {"id": "wp-fp", "name": "FP", "pointType": "fp", "featureType": "route_waypoint", "width": 1852, "isTiming": True, "isPassing": True, "sequence": 2}, "geometry": {"type": "Point", "coordinates": [11.2, 60.2]}},
            {"type": "Feature", "properties": {"id": "cat-1", "name": "A", "pointType": "tp", "featureType": "catalogue_turnpoint"}, "geometry": {"type": "Point", "coordinates": [11.2, 60.21]}},
        ]
        if include_after_point:
            features.append(
                {"type": "Feature", "properties": {"id": "cat-3", "name": "C", "pointType": "tp", "featureType": "catalogue_turnpoint"}, "geometry": {"type": "Point", "coordinates": [11.35, 60.35]}}
            )
        return EditableRoute.objects.create(
            name="Contract timing primitives",
            route={"type": "FeatureCollection", "features": features},
        )

    def test_contract_navigation_time_model_uses_t_and_2t(self):
        editable_route = self._contract_editable_route()
        self.navigation_task.editable_route = editable_route
        self.navigation_task.save(update_fields=["editable_route"])

        compiled = ContestantTaskCompiler(self.contestant).compile(
            declaration_payload={"declared_sequence": ["A", "MP", "FP"]},
            force=True,
        )
        sp_time = datetime.datetime.fromisoformat(compiled.compiled_gate_times_payload["SP"])
        mp_time = datetime.datetime.fromisoformat(compiled.compiled_gate_times_payload["MP"])
        fp_time = datetime.datetime.fromisoformat(compiled.compiled_gate_times_payload["FP"])
        self.assertEqual((mp_time - sp_time).total_seconds(), 600)
        self.assertEqual((fp_time - mp_time).total_seconds(), 600)
        self.assertEqual((fp_time - sp_time).total_seconds(), 1200)

    def test_contract_navigation_gate_calculator_uses_compiled_times(self):
        editable_route = self._contract_editable_route()
        self.navigation_task.editable_route = editable_route
        self.navigation_task.save(update_fields=["editable_route"])
        ContestantTaskCompiler(self.contestant).compile(
            declaration_payload={"declared_sequence": ["A", "MP", "FP"]},
            force=True,
        )

        with patch("display.calculators.positions_and_gates.Gate.pre_project"), patch(
            "display.calculators.gate_calculator.calculate_extended_gate"
        ):
            calculator = GateCalculator(
                self.contestant,
                self.scorecard,
                self.route,
                MagicMock(),
                live_processing=False,
                projector=self.navigation_task.get_projector(),
            )
        expected_times = {gate.name: gate.expected_time for gate in calculator.gates}
        self.assertEqual((expected_times["MP"] - expected_times["SP"]).total_seconds(), 600)
        self.assertEqual((expected_times["FP"] - expected_times["MP"]).total_seconds(), 600)
        self.assertEqual((expected_times["FP"] - expected_times["SP"]).total_seconds(), 1200)

    def test_contract_navigation_builds_before_after_mp_time_model(self):
        editable_route = self._contract_editable_route(include_after_point=True)
        self.navigation_task.editable_route = editable_route
        self.navigation_task.save(update_fields=["editable_route"])

        compiled = ContestantTaskCompiler(self.contestant).compile(
            declaration_payload={"declared_sequence": ["A", "MP", "C", "FP"]},
            force=True,
        )
        self.assertEqual(compiled.compiled_effective_route_payload["time_model"]["before_mp_sequence"], ["A"])
        self.assertEqual(compiled.compiled_effective_route_payload["time_model"]["after_mp_sequence"], ["C"])

    def test_contract_navigation_only_times_sp_mp_and_fp(self):
        editable_route = self._contract_editable_route(include_after_point=True)
        self.navigation_task.editable_route = editable_route
        self.navigation_task.save(update_fields=["editable_route"])
        compiled = ContestantTaskCompiler(self.contestant).compile(
            declaration_payload={"declared_sequence": ["A", "MP", "C", "FP"]},
            force=True,
        )

        effective_waypoints = {
            item["name"]: item for item in compiled.compiled_effective_route_payload["effective_waypoints"]
        }
        self.assertFalse(effective_waypoints["A"]["time_check"])
        self.assertTrue(effective_waypoints["MP"]["time_check"])
        self.assertFalse(effective_waypoints["C"]["time_check"])
        self.assertTrue(effective_waypoints["FP"]["time_check"])

    def test_contract_navigation_marks_post_mp_point_invalid_if_flown_before_mp_time(self):
        editable_route = self._contract_editable_route(include_after_point=True)
        self.navigation_task.editable_route = editable_route
        self.navigation_task.save(update_fields=["editable_route"])
        ContestantTaskCompiler(self.contestant).compile(
            declaration_payload={"declared_sequence": ["A", "MP", "C", "FP"]},
            force=True,
        )

        with patch("display.calculators.positions_and_gates.Gate.pre_project"), patch(
            "display.calculators.gate_calculator.calculate_extended_gate"
        ):
            calculator = GateCalculator(
                self.contestant,
                self.scorecard,
                self.route,
                Queue(),
                live_processing=False,
                projector=self.navigation_task.get_projector(),
            )

        gate_by_name = {gate.name: gate for gate in calculator.gates}
        c_gate = gate_by_name["C"]
        early_time = gate_by_name["MP"].expected_time - datetime.timedelta(seconds=1)
        event = type(
            "Evt",
            (),
            {
                "gate": c_gate,
                "position": type("Pos", (), {"time": early_time, "latitude": c_gate.latitude, "longitude": c_gate.longitude})(),
                "intersection_time": early_time,
                "previous_gate": gate_by_name["A"],
            },
        )()

        calculator.on_gate_passed(event)

        self.assertTrue(c_gate.missed)
        score_msg = calculator.score_processing_queue.get_nowait()
        self.assertEqual(score_msg.message, "invalid post-MP point flown before MP time")
