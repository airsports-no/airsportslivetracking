import datetime
from queue import Queue
from unittest.mock import patch

from django.test import TestCase

from display.calculators.calculator import GatePassedEvent
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
from display.utilities.cima_task_type_definitions import KNOWN_CIRCUIT
from display.utilities.coordinate_utilities import calculate_distance_lat_lon
from utilities.mock_utilities import TraccarMock


class _Position:
    def __init__(self, time, latitude, longitude):
        self.time = time
        self.latitude = latitude
        self.longitude = longitude


class TestKnownCircuitSpeedKeeping(TestCase):
    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, *args):
        create_scorecards()
        self.scorecard = Scorecard.get_originals().get(shortcut_name="FAI Precision")
        with open("display/tests/NM.csv", "r") as file:
            editable_route, _ = EditableRoute.create_from_csv("Known circuit speed keeping", file.readlines()[1:])
            self.route = editable_route.create_precision_route(True, self.scorecard)

        self.contest = Contest.objects.create(
            name="Known circuit speed keeping contest",
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc),
            time_zone="Europe/Oslo",
        )
        self.navigation_task = NavigationTask.create(
            name="Known circuit speed keeping task",
            contest=self.contest,
            route=self.route,
            original_scorecard=self.scorecard,
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc),
            task_subtype=KNOWN_CIRCUIT,
        )
        crew = Crew.objects.create(member1=Person.objects.create(first_name="Pilot", last_name="KnownCircuit"))
        team = Team.objects.create(crew=crew, aeroplane=Aeroplane.objects.create(registration="LN-KC-SPD"))
        start_time = datetime.datetime(2020, 8, 1, 8, 5, tzinfo=datetime.timezone.utc)
        self.contestant = Contestant.objects.create(
            navigation_task=self.navigation_task,
            team=team,
            takeoff_time=start_time,
            tracker_start_time=start_time - datetime.timedelta(minutes=30),
            finished_by_time=start_time + datetime.timedelta(hours=2),
            tracker_device_id="known-circuit-speed",
            contestant_number=1,
            minutes_to_starting_point=6,
            air_speed=75,
            wind_direction=165,
            wind_speed=8,
        )
        self.navigation_task.editable_route = EditableRoute.objects.create(
            name="Known circuit speed keeping primitives",
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
        self.navigation_task.save(update_fields=["editable_route"])

    def _build_calculator(self):
        with patch("display.calculators.positions_and_gates.Gate.pre_project"), patch(
            "display.calculators.gate_calculator.calculate_extended_gate"
        ):
            return GateCalculator(
                self.contestant,
                self.navigation_task.scorecard,
                self.route,
                Queue(),
                live_processing=False,
                projector=self.navigation_task.get_projector(),
            )

    def _drain(self, calculator):
        messages = []
        while not calculator.score_processing_queue.empty():
            messages.append(calculator.score_processing_queue.get_nowait())
        return messages

    def _pass_gate(self, calculator, gate, time):
        calculator.on_gate_passed(GatePassedEvent(gate, _Position(time, gate.latitude, gate.longitude), time))
        return self._drain(calculator)

    def test_first_gate_never_scores_speed_keeping(self):
        compiled = ContestantTaskCompiler(self.contestant).compile(force=True)
        self.assertTrue(compiled.is_valid, compiled.validation_errors)
        calculator = self._build_calculator()
        sp = calculator.gates[0]

        messages = self._pass_gate(calculator, sp, sp.expected_time)
        self.assertNotIn("speed_keeping", [m.score_type for m in messages])

    def test_off_speed_leg_is_penalized(self):
        compiled = ContestantTaskCompiler(self.contestant).compile(force=True)
        self.assertTrue(compiled.is_valid, compiled.validation_errors)
        calculator = self._build_calculator()
        first_gate, second_gate = calculator.gates[0], calculator.gates[1]

        first_time = first_gate.expected_time
        self._pass_gate(calculator, first_gate, first_time)

        distance_m = calculate_distance_lat_lon(
            (first_gate.latitude, first_gate.longitude), (second_gate.latitude, second_gate.longitude)
        )
        # Fly the leg much faster than the declared 75kt air speed.
        fast_kt = 150
        elapsed_seconds = distance_m / (fast_kt * 1852 / 3600)
        second_time = first_time + datetime.timedelta(seconds=elapsed_seconds)

        messages = self._pass_gate(calculator, second_gate, second_time)
        speed_keeping_messages = [m for m in messages if m.score_type == "speed_keeping"]
        self.assertEqual(len(speed_keeping_messages), 1, messages)
        self.assertGreater(speed_keeping_messages[0].score, 0)

    def test_on_speed_leg_is_not_penalized(self):
        compiled = ContestantTaskCompiler(self.contestant).compile(force=True)
        self.assertTrue(compiled.is_valid, compiled.validation_errors)
        calculator = self._build_calculator()
        first_gate, second_gate = calculator.gates[0], calculator.gates[1]

        first_time = first_gate.expected_time
        self._pass_gate(calculator, first_gate, first_time)

        distance_m = calculate_distance_lat_lon(
            (first_gate.latitude, first_gate.longitude), (second_gate.latitude, second_gate.longitude)
        )
        # Fly the leg at exactly the declared 75kt air speed.
        elapsed_seconds = distance_m / (75 * 1852 / 3600)
        second_time = first_time + datetime.timedelta(seconds=elapsed_seconds)

        messages = self._pass_gate(calculator, second_gate, second_time)
        speed_keeping_messages = [m for m in messages if m.score_type == "speed_keeping"]
        self.assertEqual(len(speed_keeping_messages), 1, messages)
        self.assertEqual(speed_keeping_messages[0].score, 0)

    def test_overridden_leg_skips_speed_keeping_score(self):
        first_gate_name, second_gate_name = self.route.waypoints[0].name, self.route.waypoints[1].name
        compiled = ContestantTaskCompiler(self.contestant).compile(
            declaration_payload={"turnpoint_time_overrides": {second_gate_name: "2020-08-01T09:30:00Z"}},
            force=True,
        )
        self.assertTrue(compiled.is_valid, compiled.validation_errors)
        calculator = self._build_calculator()
        first_gate, second_gate = calculator.gates[0], calculator.gates[1]
        self.assertEqual(first_gate.name, first_gate_name)
        self.assertEqual(second_gate.name, second_gate_name)

        first_time = first_gate.expected_time
        self._pass_gate(calculator, first_gate, first_time)

        distance_m = calculate_distance_lat_lon(
            (first_gate.latitude, first_gate.longitude), (second_gate.latitude, second_gate.longitude)
        )
        fast_kt = 150
        elapsed_seconds = distance_m / (fast_kt * 1852 / 3600)
        second_time = first_time + datetime.timedelta(seconds=elapsed_seconds)

        messages = self._pass_gate(calculator, second_gate, second_time)
        self.assertNotIn("speed_keeping", [m.score_type for m in messages])
