import datetime
from unittest.mock import MagicMock, patch

from django.test import TestCase

from display.calculators.calculator import LandingPassedEvent, TakeoffPassedEvent
from display.calculators.calculator_factory import calculator_factory
from display.calculators.duration_calculator import DurationCalculator
from display.calculators.update_score_message import UpdateScoreMessage
from display.utilities.cima_task_type_definitions import DURATION
from display.utilities.coordinate_utilities import Projector
from display.utilities.navigation_task_type_definitions import PRECISION


class TestDurationCalculator(TestCase):
    def setUp(self):
        self.projector = Projector(60, 11)
        self.queue = MagicMock()
        self.contestant = MagicMock()
        self.contestant.navigation_task.task_subtype = DURATION
        self.contestant.navigation_task.editable_route = None
        self.scorecard = MagicMock()
        self.scorecard.prohibited_zone_penalty = 200
        self.scorecard.duration_normalization_policy = ""
        self.route = MagicMock()
        self.route.landing_gates = []
        self.calculator = DurationCalculator(
            self.contestant,
            self.scorecard,
            self.route,
            self.queue,
            live_processing=False,
            projector=self.projector,
        )

    def _make_gate(self, name):
        gate = MagicMock()
        gate.name = name
        gate.type = "tp"
        gate.expected_time = datetime.datetime(2026, 8, 1, 10, 0, tzinfo=datetime.timezone.utc)
        return gate

    def _make_position(self, when):
        position = MagicMock()
        position.time = when
        position.latitude = 60.0
        position.longitude = 11.0
        return position

    def _make_polygon(self, west=10.9, south=59.9, east=11.1, north=60.1):
        return [(west, south), (east, south), (east, north), (west, north)]

    def test_duration_calculator_records_airborne_duration_on_landing(self):
        takeoff_time = datetime.datetime(2026, 8, 1, 10, 0, tzinfo=datetime.timezone.utc)
        landing_time = datetime.datetime(2026, 8, 1, 11, 7, 30, tzinfo=datetime.timezone.utc)
        takeoff_gate = self._make_gate("T/O")
        landing_gate = self._make_gate("LDG")
        takeoff_position = self._make_position(takeoff_time)
        landing_position = self._make_position(landing_time)

        self.calculator.on_takeoff_passed(TakeoffPassedEvent(takeoff_gate, takeoff_position, takeoff_time))
        self.calculator.on_landing_passed(LandingPassedEvent(landing_gate, landing_position, landing_time))

        self.queue.put_nowait.assert_called_once()
        message = self.queue.put_nowait.call_args[0][0]
        self.assertIsInstance(message, UpdateScoreMessage)
        self.assertEqual(message.score_type, "duration_airborne_time")
        self.assertEqual(message.message, "airborne duration recorded")
        self.assertEqual(message.score, 0)
        self.assertEqual(message.planned, takeoff_time)
        self.assertEqual(message.actual, landing_time)

    def test_duration_calculator_ignores_landing_without_validated_takeoff(self):
        landing_time = datetime.datetime(2026, 8, 1, 11, 7, 30, tzinfo=datetime.timezone.utc)
        landing_gate = self._make_gate("LDG")
        landing_position = self._make_position(landing_time)

        self.calculator.on_landing_passed(LandingPassedEvent(landing_gate, landing_position, landing_time))

        self.queue.put_nowait.assert_not_called()

    def test_duration_calculator_emits_raw_minutes_score_when_policy_configured(self):
        self.scorecard.duration_normalization_policy = "raw_minutes"
        takeoff_time = datetime.datetime(2026, 8, 1, 10, 0, tzinfo=datetime.timezone.utc)
        landing_time = datetime.datetime(2026, 8, 1, 11, 7, 30, tzinfo=datetime.timezone.utc)
        takeoff_gate = self._make_gate("T/O")
        landing_gate = self._make_gate("LDG")
        takeoff_position = self._make_position(takeoff_time)
        landing_position = self._make_position(landing_time)

        self.calculator.on_takeoff_passed(TakeoffPassedEvent(takeoff_gate, takeoff_position, takeoff_time))
        self.calculator.on_landing_passed(LandingPassedEvent(landing_gate, landing_position, landing_time))

        self.assertEqual(self.queue.put_nowait.call_count, 2)
        recorded_message = self.queue.put_nowait.call_args_list[0][0][0]
        normalized_message = self.queue.put_nowait.call_args_list[1][0][0]
        self.assertEqual(recorded_message.score_type, "duration_airborne_time")
        self.assertEqual(normalized_message.score_type, "duration_normalized_score")
        self.assertEqual(normalized_message.message, "duration normalized using raw minutes")
        self.assertEqual(normalized_message.score, 67.5)

    def test_duration_calculator_emits_landing_area_penalty_when_outside_specified_area(self):
        editable_route = MagicMock()
        editable_route.get_duration_landing_area_polygons.return_value = [
            {"geometry": {"coordinates": [self._make_polygon(west=11.2, south=60.2, east=11.4, north=60.4)]}}
        ]
        self.contestant.navigation_task.editable_route = editable_route
        takeoff_time = datetime.datetime(2026, 8, 1, 10, 0, tzinfo=datetime.timezone.utc)
        landing_time = datetime.datetime(2026, 8, 1, 11, 0, tzinfo=datetime.timezone.utc)
        takeoff_gate = self._make_gate("T/O")
        landing_gate = self._make_gate("LDG")
        takeoff_position = self._make_position(takeoff_time)
        landing_position = self._make_position(landing_time)
        landing_position.latitude = 60.0
        landing_position.longitude = 11.0

        self.calculator.on_takeoff_passed(TakeoffPassedEvent(takeoff_gate, takeoff_position, takeoff_time))
        self.calculator.on_landing_passed(LandingPassedEvent(landing_gate, landing_position, landing_time))

        self.assertEqual(self.queue.put_nowait.call_count, 2)
        penalty_message = self.queue.put_nowait.call_args_list[1][0][0]
        self.assertEqual(penalty_message.score_type, "duration_landing_area_outside")
        self.assertEqual(penalty_message.message, "landing outside specified area")
        self.assertEqual(penalty_message.score, 200)

    def test_duration_calculator_uses_polygon_geometry_not_bounding_box(self):
        editable_route = MagicMock()
        editable_route.get_duration_landing_area_polygons.return_value = [
            {
                "geometry": {
                    "coordinates": [[
                        (11.0, 60.0),
                        (11.2, 60.0),
                        (11.2, 60.02),
                        (11.02, 60.02),
                        (11.02, 60.2),
                        (11.0, 60.2),
                        (11.0, 60.0),
                    ]]
                }
            }
        ]
        self.contestant.navigation_task.editable_route = editable_route
        takeoff_time = datetime.datetime(2026, 8, 1, 10, 0, tzinfo=datetime.timezone.utc)
        landing_time = datetime.datetime(2026, 8, 1, 11, 0, tzinfo=datetime.timezone.utc)
        takeoff_gate = self._make_gate("T/O")
        landing_gate = self._make_gate("LDG")
        takeoff_position = self._make_position(takeoff_time)
        landing_position = self._make_position(landing_time)
        landing_position.latitude = 60.10
        landing_position.longitude = 11.10

        self.calculator.on_takeoff_passed(TakeoffPassedEvent(takeoff_gate, takeoff_position, takeoff_time))
        self.calculator.on_landing_passed(LandingPassedEvent(landing_gate, landing_position, landing_time))

        self.assertEqual(self.queue.put_nowait.call_count, 2)
        penalty_message = self.queue.put_nowait.call_args_list[1][0][0]
        self.assertEqual(penalty_message.score_type, "duration_landing_area_outside")

    @patch("display.calculators.calculator_factory.Orchestrator")
    def test_calculator_factory_includes_duration_calculator_for_duration_subtype(self, orchestrator_mock):
        contestant = MagicMock()
        contestant.navigation_task.task_subtype = DURATION
        contestant.navigation_task.scorecard.calculator = PRECISION
        contestant.navigation_task.route.waypoints = [MagicMock()]
        contestant.navigation_task.route.takeoff_gates = []
        contestant.navigation_task.route.landing_gates = []
        contestant.gate_times = {}

        calculator_factory(contestant, MagicMock(), live_processing=False, projector=self.projector)

        calculators = orchestrator_mock.call_args[0][2]
        self.assertIn(DurationCalculator, calculators)
