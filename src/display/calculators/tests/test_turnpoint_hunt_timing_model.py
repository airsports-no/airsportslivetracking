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
from display.utilities.cima_task_type_definitions import LIMITED_FUEL_TURNPOINT_HUNT, TURNPOINT_HUNT
from utilities.mock_utilities import TraccarMock


class TestTurnpointHuntTimingModel(TestCase):
    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, *args):
        create_scorecards()
        self.scorecard = Scorecard.get_originals().get(shortcut_name="FAI Precision")
        with open("display/tests/NM.csv", "r") as file:
            editable_route, _ = EditableRoute.create_from_csv("Turnpoint timing", file.readlines()[1:])
            self.route = editable_route.create_precision_route(True, self.scorecard)

        self.contest = Contest.objects.create(
            name="Turnpoint timing contest",
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc),
            time_zone="Europe/Oslo",
        )
        self.navigation_task = NavigationTask.create(
            name="Turnpoint timing task",
            contest=self.contest,
            route=self.route,
            original_scorecard=self.scorecard,
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc),
            task_subtype=TURNPOINT_HUNT,
        )
        crew = Crew.objects.create(member1=Person.objects.create(first_name="Pilot", last_name="TurnpointTiming"))
        team = Team.objects.create(crew=crew, aeroplane=Aeroplane.objects.create(registration="LN-TPH-TIME"))
        start_time = datetime.datetime(2020, 8, 1, 8, 5, tzinfo=datetime.timezone.utc)
        self.contestant = Contestant.objects.create(
            navigation_task=self.navigation_task,
            team=team,
            takeoff_time=start_time,
            tracker_start_time=start_time - datetime.timedelta(minutes=30),
            finished_by_time=start_time + datetime.timedelta(hours=2),
            tracker_device_id="turnpoint-timing",
            contestant_number=1,
            minutes_to_starting_point=6,
            air_speed=75,
            wind_direction=165,
            wind_speed=8,
        )

    def _set_editable_route(self):
        editable_route = EditableRoute.objects.create(
            name="Turnpoint timing primitives",
            route={
                "type": "FeatureCollection",
                "features": [
                    {"type": "Feature", "properties": {"featureType": "route_path"}, "geometry": {"type": "LineString", "coordinates": [[11.0, 60.0], [11.1, 60.1]]}},
                    {"type": "Feature", "properties": {"id": "cat-1", "name": "A", "pointType": "tp", "featureType": "catalogue_turnpoint", "scoreValue": 42}, "geometry": {"type": "Point", "coordinates": [11.2, 60.2]}},
                    {"type": "Feature", "properties": {"id": "cat-2", "name": "B", "pointType": "tp", "featureType": "catalogue_turnpoint", "scoreValue": 17}, "geometry": {"type": "Point", "coordinates": [11.3, 60.3]}},
                    {"type": "Feature", "properties": {"id": "kt-1", "name": "CP1", "pointType": "tp", "featureType": "known_time_gate"}, "geometry": {"type": "Point", "coordinates": [11.25, 60.25]}},
                    {"type": "Feature", "properties": {"id": "kt-2", "name": "CP2", "pointType": "tp", "featureType": "known_time_gate"}, "geometry": {"type": "Point", "coordinates": [11.35, 60.35]}},
                    {"type": "Feature", "properties": {"id": "kt-3", "name": "CP3", "pointType": "tp", "featureType": "known_time_gate"}, "geometry": {"type": "Point", "coordinates": [11.45, 60.45]}},
                    {"type": "Feature", "properties": {"id": "obs-1", "name": "A", "featureType": "observation_photo"}, "geometry": {"type": "Point", "coordinates": [11.5, 60.5]}},
                    {"type": "Feature", "properties": {"id": "obs-2", "name": "B", "featureType": "observation_photo"}, "geometry": {"type": "Point", "coordinates": [11.51, 60.51]}},
                ],
            },
        )
        self.navigation_task.editable_route = editable_route
        self.navigation_task.save(update_fields=["editable_route"])

    def _compile_turnpoint_hunt(self, subtype=TURNPOINT_HUNT, fuel_metadata=None, cp1='2020-08-01T08:15:00Z'):
        self.navigation_task.task_subtype = subtype
        self.navigation_task.save(update_fields=['task_subtype'])
        payload = {
            'compulsory_point_times': {
                'CP1': cp1,
                'CP2': '2020-08-01T08:16:00Z',
                'CP3': '2020-08-01T08:17:00Z',
            }
        }
        if fuel_metadata is not None:
            payload['fuel_metadata'] = fuel_metadata
        return ContestantTaskCompiler(self.contestant).compile(declaration_payload=payload, force=True)

    def _build_calculator(self):
        with patch('display.calculators.positions_and_gates.Gate.pre_project'), patch(
            'display.calculators.gate_calculator.calculate_extended_gate'
        ):
            return GateCalculator(
                self.contestant,
                self.navigation_task.scorecard,
                self.route,
                Queue(),
                live_processing=False,
                projector=self.navigation_task.get_projector(),
            )

    def test_turnpoint_hunt_gate_calculator_uses_compulsory_gate_times(self):
        self._set_editable_route()
        self._compile_turnpoint_hunt()
        calculator = self._build_calculator()
        expected_times = {gate.name: gate.expected_time for gate in calculator.gates}
        self.assertEqual(expected_times['CP1'].isoformat(), '2020-08-01T08:15:00+00:00')
        self.assertEqual(expected_times['CP2'].isoformat(), '2020-08-01T08:16:00+00:00')
        self.assertEqual(expected_times['CP3'].isoformat(), '2020-08-01T08:17:00+00:00')
        self.assertNotIn('A', expected_times)
        self.assertNotIn('B', expected_times)

    def test_turnpoint_hunt_compiled_payload_includes_unordered_free_targets(self):
        self._set_editable_route()
        compiled = self._compile_turnpoint_hunt()
        self.assertEqual(compiled.compiled_effective_route_payload['free_target_names'], ['A', 'B'])
        self.assertEqual(compiled.compiled_effective_route_payload['scored_target_values'], {'A': 42.0, 'B': 17.0})
        self.assertEqual(compiled.compiled_effective_route_payload['free_target_evidence'], {'A': ['A'], 'B': ['B']})

    def test_limited_fuel_turnpoint_hunt_gate_times_preserve_fuel_metadata(self):
        self._set_editable_route()
        compiled = self._compile_turnpoint_hunt(
            subtype=LIMITED_FUEL_TURNPOINT_HUNT,
            fuel_metadata={'declared_endurance_minutes': 95},
        )
        self.assertEqual(compiled.compiled_effective_route_payload['fuel_metadata'], {'declared_endurance_minutes': 95})
        self.assertEqual(compiled.compiled_effective_route_payload['fuel_deadline'], '2020-08-01T09:40:00+00:00')
        self.assertEqual(compiled.compiled_effective_route_payload['compulsory_timing_gate_names'], ['CP1', 'CP2', 'CP3'])

    def test_turnpoint_hunt_requires_exactly_three_compulsory_point_times(self):
        self._set_editable_route()
        compiled = ContestantTaskCompiler(self.contestant).compile(
            declaration_payload={'compulsory_point_times': {'CP1': '2020-08-01T08:15:00Z'}},
            force=True,
        )
        self.assertFalse(compiled.is_valid)
        self.assertIn('exactly three compulsory point times', ' '.join(compiled.validation_errors))

    def test_turnpoint_hunt_compulsory_timing_gate_within_tolerance_is_information(self):
        self._set_editable_route()
        self._compile_turnpoint_hunt()
        calculator = self._build_calculator()
        gate_by_name = {gate.name: gate for gate in calculator.gates}
        cp1 = gate_by_name['CP1']
        passing_time = cp1.expected_time + datetime.timedelta(seconds=5)
        event = GatePassedEvent(
            cp1,
            type('Pos', (), {'time': passing_time, 'latitude': cp1.latitude, 'longitude': cp1.longitude})(),
            passing_time,
            previous_gate=calculator.starting_line,
        )
        calculator.on_gate_passed(event)
        calculator.score_processing_queue.get_nowait()
        second_msg = calculator.score_processing_queue.get_nowait()
        self.assertEqual(second_msg.score_type, 'turnpoint_hunt_compulsory_timing')
        self.assertEqual(second_msg.message, 'compulsory timing gate within 10 s')
        self.assertEqual(second_msg.score, 0)

    def test_turnpoint_hunt_compulsory_timing_gate_outside_tolerance_is_anomaly(self):
        self._set_editable_route()
        self._compile_turnpoint_hunt()
        calculator = self._build_calculator()
        gate_by_name = {gate.name: gate for gate in calculator.gates}
        cp1 = gate_by_name['CP1']
        passing_time = cp1.expected_time + datetime.timedelta(seconds=20)
        event = GatePassedEvent(
            cp1,
            type('Pos', (), {'time': passing_time, 'latitude': cp1.latitude, 'longitude': cp1.longitude})(),
            passing_time,
            previous_gate=calculator.starting_line,
        )
        calculator.on_gate_passed(event)
        calculator.score_processing_queue.get_nowait()
        second_msg = calculator.score_processing_queue.get_nowait()
        self.assertEqual(second_msg.score_type, 'turnpoint_hunt_compulsory_timing')
        self.assertEqual(second_msg.message, 'compulsory timing gate outside 10 s')
        self.assertGreater(second_msg.score, 0)
