import datetime
from queue import Queue
from unittest.mock import MagicMock, patch

from django.test import TestCase

from display.calculators.calculator import GatePassedEvent, OrchestratorState
from display.calculators.calculator_factory import calculator_factory
from display.calculators.circle_calculator import CircleCalculator
from display.default_scorecards.create_scorecards import create_scorecards
from display.models import Aeroplane, Contest, Contestant, Crew, EditableRoute, NavigationTask, Person, Scorecard, Team
from display.utilities.cima_task_type_definitions import CIRCLE
from display.utilities.coordinate_utilities import project_position_lat_lon
from utilities.mock_utilities import TraccarMock


class TestCircleCalculator(TestCase):
    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, *args):
        create_scorecards()
        self.scorecard = Scorecard.get_originals().get(shortcut_name="FAI Precision")
        with open("display/tests/NM.csv", "r") as file:
            editable_route, _ = EditableRoute.create_from_csv("Circle calc", file.readlines()[1:])
            self.route = editable_route.create_precision_route(True, self.scorecard)

        self.contest = Contest.objects.create(
            name="Circle calc contest",
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc),
            time_zone="Europe/Oslo",
        )
        self.navigation_task = NavigationTask.create(
            name="Circle calc task",
            contest=self.contest,
            route=self.route,
            original_scorecard=self.scorecard,
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc),
            task_subtype=CIRCLE,
        )
        self.navigation_task.scorecard.circle_radius_min_m = 200
        self.navigation_task.scorecard.circle_radius_max_m = 750
        self.navigation_task.scorecard.save(update_fields=["circle_radius_min_m", "circle_radius_max_m"])
        crew = Crew.objects.create(member1=Person.objects.create(first_name="Circle", last_name="Pilot"))
        team = Team.objects.create(crew=crew, aeroplane=Aeroplane.objects.create(registration="LN-CIRCLE"))
        start_time = datetime.datetime(2020, 8, 1, 8, 5, tzinfo=datetime.timezone.utc)
        self.contestant = Contestant.objects.create(
            navigation_task=self.navigation_task,
            team=team,
            takeoff_time=start_time,
            tracker_start_time=start_time - datetime.timedelta(minutes=30),
            finished_by_time=start_time + datetime.timedelta(hours=2),
            tracker_device_id="circle-calc",
            contestant_number=1,
            minutes_to_starting_point=6,
            air_speed=75,
            wind_direction=165,
            wind_speed=8,
        )
        self.navigation_task.editable_route = EditableRoute.objects.create(
            name="Circle primitives",
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
                        "properties": {"id": "cs-1", "name": "SP-C", "pointType": "circle_start", "featureType": "circle_start_marker"},
                        "geometry": {"type": "Point", "coordinates": [11.1, 60.1]},
                    },
                    {
                        "type": "Feature",
                        "properties": {"id": "ce-1", "name": "X", "pointType": "circle_entry", "featureType": "circle_entry_marker"},
                        "geometry": {"type": "Point", "coordinates": [11.3, 60.3]},
                    },
                    {
                        "type": "Feature",
                        "properties": {"id": "cx-1", "name": "WP", "pointType": "circle_exit", "featureType": "circle_exit_marker"},
                        "geometry": {"type": "Point", "coordinates": [11.35, 60.35]},
                    },
                ],
            },
        )
        self.navigation_task.save(update_fields=["editable_route"])
        self.projector = self.navigation_task.get_projector()

    def _make_event(self, gate_name: str, timestamp: datetime.datetime, latitude: float = 60.0, longitude: float = 11.0, altitude: float = 0.0):
        gate = MagicMock()
        gate.name = gate_name
        gate.expected_time = timestamp
        gate.latitude = latitude
        gate.longitude = longitude
        position = MagicMock()
        position.time = timestamp
        position.latitude = latitude
        position.longitude = longitude
        position.altitude = altitude
        proj = self.projector.project_point(latitude, longitude)
        position.projected_x = proj.projected_x
        position.projected_y = proj.projected_y
        return GatePassedEvent(gate, position, timestamp, previous_gate=None)

    def _circle_point_from_center(self, bearing: float, distance_m: float, altitude: float = 0.0):
        latitude, longitude = project_position_lat_lon((60.2, 11.2), bearing, distance_m)
        return latitude, longitude, altitude

    def _circle_position(self, bearing: float, distance_m: float, altitude: float = 0.0):
        lat, lon, alt = self._circle_point_from_center(bearing, distance_m, altitude)
        projected = self.projector.project_point(lat, lon)
        return type(
            "Pos",
            (),
            {
                "latitude": lat,
                "longitude": lon,
                "altitude": alt,
                "projected_x": projected.projected_x,
                "projected_y": projected.projected_y,
            },
        )()

    def test_calculator_factory_includes_circle_calculator_for_circle_subtype(self):
        orchestrator = calculator_factory(
            self.contestant,
            Queue(),
            live_processing=False,
            projector=self.navigation_task.get_projector(),
        )
        self.assertTrue(any(isinstance(item, CircleCalculator) for item in orchestrator.calculators))

    def test_circle_calculator_emits_start_entry_and_exit_messages(self):
        self.navigation_task.scorecard.circle_radius_min_m = 0
        self.navigation_task.scorecard.circle_radius_max_m = 2000
        self.navigation_task.scorecard.save(update_fields=["circle_radius_min_m", "circle_radius_max_m"])
        self.contestant.navigation_task = self.navigation_task
        calculator = CircleCalculator(
            self.contestant,
            self.scorecard,
            self.route,
            Queue(),
            live_processing=False,
            projector=self.navigation_task.get_projector(),
        )
        with patch.object(calculator, "_is_clockwise_turn", return_value=False), patch.object(
            calculator, "_is_radius_outside_limits", return_value=False
        ), patch.object(calculator, "_has_invalid_score_ratio", return_value=False), patch.object(
            calculator, "_has_completed_scored_arc", return_value=True
        ), patch.object(calculator, "_is_center_outside_flown_circle", return_value=False):
            calculator.on_gate_passed(self._make_event("SP-C", datetime.datetime(2020, 8, 1, 8, 10, tzinfo=datetime.timezone.utc), 60.1, 11.1))
            calculator.on_gate_passed(self._make_event("X", datetime.datetime(2020, 8, 1, 8, 12, tzinfo=datetime.timezone.utc), 60.3, 11.3))
            calculator.on_gate_passed(self._make_event("WP", datetime.datetime(2020, 8, 1, 8, 18, tzinfo=datetime.timezone.utc), 60.2015, 11.2015))

        first = calculator.score_processing_queue.get_nowait()
        second = calculator.score_processing_queue.get_nowait()
        third = calculator.score_processing_queue.get_nowait()

        self.assertEqual(first.score_type, "circle_start")
        self.assertEqual(first.message, "circle start passed")
        self.assertEqual(second.score_type, "circle_entry")
        self.assertEqual(second.message, "circle entry passed")
        self.assertEqual(third.score_type, "circle_score")
        self.assertGreaterEqual(third.score, 0)
        fourth = calculator.score_processing_queue.get_nowait()
        self.assertEqual(fourth.score_type, "circle_exit")
        self.assertEqual(fourth.message, "circle exit passed")

    def test_circle_calculator_score_prefers_progress_samples(self):
        calculator = CircleCalculator(
            self.contestant,
            self.scorecard,
            self.route,
            Queue(),
            live_processing=False,
            projector=self.navigation_task.get_projector(),
        )
        calculator.progress_radius_samples = [200.0, 400.0]
        calculator.radius_samples_m = [200.0, 700.0]
        self.assertEqual(calculator._calculate_circle_score(), 0.0)

    def test_circle_calculator_marks_exit_before_entry_as_anomaly(self):
        calculator = CircleCalculator(
            self.contestant,
            self.scorecard,
            self.route,
            Queue(),
            live_processing=False,
            projector=self.navigation_task.get_projector(),
        )
        calculator.on_gate_passed(self._make_event("WP", datetime.datetime(2020, 8, 1, 8, 18, tzinfo=datetime.timezone.utc), 60.35, 11.35))

        message = calculator.score_processing_queue.get_nowait()
        self.assertEqual(message.score_type, "circle_invalid_exit")
        self.assertEqual(message.annotation_type, "anomaly")
        self.assertEqual(message.message, "circle exit before circle entry")

    def test_circle_calculator_marks_entry_before_start_as_anomaly(self):
        calculator = CircleCalculator(
            self.contestant,
            self.scorecard,
            self.route,
            Queue(),
            live_processing=False,
            projector=self.navigation_task.get_projector(),
        )
        calculator.on_gate_passed(self._make_event("X", datetime.datetime(2020, 8, 1, 8, 12, tzinfo=datetime.timezone.utc), 60.3, 11.3))

        message = calculator.score_processing_queue.get_nowait()
        self.assertEqual(message.score_type, "circle_invalid_entry")
        self.assertEqual(message.annotation_type, "anomaly")
        self.assertEqual(message.message, "circle entry before circle start")

    def test_circle_calculator_marks_non_straight_entry_as_anomaly(self):
        calculator = CircleCalculator(
            self.contestant,
            self.scorecard,
            self.route,
            Queue(),
            live_processing=False,
            projector=self.navigation_task.get_projector(),
        )
        calculator.on_gate_passed(self._make_event("SP-C", datetime.datetime(2020, 8, 1, 8, 10, tzinfo=datetime.timezone.utc), 60.1, 11.1))
        calculator.on_gate_passed(self._make_event("X", datetime.datetime(2020, 8, 1, 8, 12, tzinfo=datetime.timezone.utc), 60.22, 11.10))

        first = calculator.score_processing_queue.get_nowait()
        second = calculator.score_processing_queue.get_nowait()
        self.assertEqual(first.score_type, "circle_start")
        self.assertEqual(second.score_type, "circle_invalid_entry_line")
        self.assertEqual(second.annotation_type, "anomaly")
        self.assertEqual(second.message, "circle entry not flown over SP and CM")

    def test_circle_calculator_calculate_enroute_emits_entry_anomaly(self):
        calculator = CircleCalculator(
            self.contestant,
            self.scorecard,
            self.route,
            Queue(),
            live_processing=False,
            projector=self.navigation_task.get_projector(),
        )
        state = OrchestratorState(
            last_gate=None,
            last_visible_gate=None,
            next_gate=None,
            in_range_of_gate=None,
            projector=self.projector,
            has_passed_finishpoint=False,
            recalculation_completed=True,
        )
        calculator.on_gate_passed(self._make_event("SP-C", datetime.datetime(2020, 8, 1, 8, 10, tzinfo=datetime.timezone.utc), 60.1, 11.1))
        calculator.on_gate_passed(self._make_event("X", datetime.datetime(2020, 8, 1, 8, 12, tzinfo=datetime.timezone.utc), 60.22, 11.10))
        self.assertFalse(calculator.score_processing_queue.empty())

    def test_circle_calculator_marks_clockwise_turn_as_anomaly(self):
        calculator = CircleCalculator(
            self.contestant,
            self.scorecard,
            self.route,
            Queue(),
            live_processing=False,
            projector=self.navigation_task.get_projector(),
        )
        calculator.on_gate_passed(self._make_event("SP-C", datetime.datetime(2020, 8, 1, 8, 10, tzinfo=datetime.timezone.utc), 60.1, 11.1))
        calculator.on_gate_passed(self._make_event("X", datetime.datetime(2020, 8, 1, 8, 12, tzinfo=datetime.timezone.utc), 60.3, 11.3))
        calculator.on_gate_passed(self._make_event("WP", datetime.datetime(2020, 8, 1, 8, 18, tzinfo=datetime.timezone.utc), 60.15, 11.35))

        first = calculator.score_processing_queue.get_nowait()
        second = calculator.score_processing_queue.get_nowait()
        third = calculator.score_processing_queue.get_nowait()
        self.assertEqual(first.score_type, "circle_start")
        self.assertEqual(second.score_type, "circle_entry")
        self.assertEqual(third.score_type, "circle_invalid_direction")
        self.assertEqual(third.annotation_type, "anomaly")
        self.assertEqual(third.message, "circle flown clockwise")

    def test_circle_calculator_marks_radius_outside_limits_as_anomaly(self):
        calculator = CircleCalculator(
            self.contestant,
            self.scorecard,
            self.route,
            Queue(),
            live_processing=False,
            projector=self.navigation_task.get_projector(),
        )
        calculator.on_gate_passed(self._make_event("SP-C", datetime.datetime(2020, 8, 1, 8, 10, tzinfo=datetime.timezone.utc), 60.1, 11.1))
        calculator.on_gate_passed(self._make_event("X", datetime.datetime(2020, 8, 1, 8, 12, tzinfo=datetime.timezone.utc), 60.3, 11.3))
        calculator.on_gate_passed(self._make_event("WP", datetime.datetime(2020, 8, 1, 8, 18, tzinfo=datetime.timezone.utc), 60.8, 11.8))

        first = calculator.score_processing_queue.get_nowait()
        second = calculator.score_processing_queue.get_nowait()
        third = calculator.score_processing_queue.get_nowait()
        self.assertEqual(first.score_type, "circle_start")
        self.assertEqual(second.score_type, "circle_entry")
        self.assertEqual(third.score_type, "circle_invalid_radius")
        self.assertEqual(third.annotation_type, "anomaly")
        self.assertEqual(third.message, "circle radius outside allowed limits")

    def test_circle_calculator_marks_invalid_score_ratio_as_anomaly(self):
        self.navigation_task.scorecard.circle_radius_min_m = 0
        self.navigation_task.scorecard.circle_radius_max_m = 2000
        self.navigation_task.scorecard.save(update_fields=["circle_radius_min_m", "circle_radius_max_m"])
        self.contestant.navigation_task = self.navigation_task
        calculator = CircleCalculator(
            self.contestant,
            self.scorecard,
            self.route,
            Queue(),
            live_processing=False,
            projector=self.navigation_task.get_projector(),
        )
        with patch.object(calculator, "_is_clockwise_turn", return_value=False), patch.object(
            calculator, "_is_radius_outside_limits", return_value=False
        ), patch.object(calculator, "_has_invalid_score_ratio", return_value=True):
            calculator.progress_radius_samples = [200.0, 450.0]
            calculator.on_gate_passed(self._make_event("SP-C", datetime.datetime(2020, 8, 1, 8, 10, tzinfo=datetime.timezone.utc), 60.1, 11.1))
            calculator.on_gate_passed(self._make_event("X", datetime.datetime(2020, 8, 1, 8, 12, tzinfo=datetime.timezone.utc), 60.3, 11.3))
            calculator.on_gate_passed(self._make_event("WP", datetime.datetime(2020, 8, 1, 8, 18, tzinfo=datetime.timezone.utc), 60.2015, 11.2015))

        first = calculator.score_processing_queue.get_nowait()
        second = calculator.score_processing_queue.get_nowait()
        third = calculator.score_processing_queue.get_nowait()
        self.assertEqual(first.score_type, "circle_start")
        self.assertEqual(second.score_type, "circle_entry")
        self.assertEqual(third.score_type, "circle_invalid_score_ratio")
        self.assertEqual(third.annotation_type, "anomaly")
        self.assertEqual(third.message, "circle score ratio outside allowed limits")

    def test_circle_calculator_marks_center_outside_flown_circle_as_anomaly(self):
        self.navigation_task.scorecard.circle_radius_min_m = 0
        self.navigation_task.scorecard.circle_radius_max_m = 2000
        self.navigation_task.scorecard.save(update_fields=["circle_radius_min_m", "circle_radius_max_m"])
        self.contestant.navigation_task = self.navigation_task
        calculator = CircleCalculator(
            self.contestant,
            self.scorecard,
            self.route,
            Queue(),
            live_processing=False,
            projector=self.navigation_task.get_projector(),
        )
        with patch.object(calculator, "_is_clockwise_turn", return_value=False), patch.object(
            calculator, "_is_radius_outside_limits", return_value=False
        ), patch.object(calculator, "_has_invalid_score_ratio", return_value=False), patch.object(
            calculator, "_has_completed_scored_arc", return_value=True
        ), patch.object(calculator, "_is_center_outside_flown_circle", return_value=True):
            calculator.progress_radius_samples = [250.0, 260.0, 255.0]
            calculator.on_gate_passed(self._make_event("SP-C", datetime.datetime(2020, 8, 1, 8, 10, tzinfo=datetime.timezone.utc), 60.1, 11.1))
            calculator.on_gate_passed(self._make_event("X", datetime.datetime(2020, 8, 1, 8, 12, tzinfo=datetime.timezone.utc), 60.3, 11.3))
            calculator.on_gate_passed(self._make_event("WP", datetime.datetime(2020, 8, 1, 8, 18, tzinfo=datetime.timezone.utc), 60.3015, 11.3315))

        first = calculator.score_processing_queue.get_nowait()
        second = calculator.score_processing_queue.get_nowait()
        third = calculator.score_processing_queue.get_nowait()
        self.assertEqual(first.score_type, "circle_start")
        self.assertEqual(second.score_type, "circle_entry")
        self.assertEqual(third.score_type, "circle_invalid_center")
        self.assertEqual(third.annotation_type, "anomaly")
        self.assertEqual(third.message, "circle center marker outside flown circle")

    def test_circle_calculator_applies_altitude_spread_penalty(self):
        self.navigation_task.scorecard.circle_radius_min_m = 0
        self.navigation_task.scorecard.circle_radius_max_m = 2000
        self.navigation_task.scorecard.save(update_fields=["circle_radius_min_m", "circle_radius_max_m"])
        self.contestant.navigation_task = self.navigation_task
        calculator = CircleCalculator(
            self.contestant,
            self.scorecard,
            self.route,
            Queue(),
            live_processing=False,
            projector=self.navigation_task.get_projector(),
        )
        with patch.object(calculator, "_is_clockwise_turn", return_value=False), patch.object(
            calculator, "_is_radius_outside_limits", return_value=False
        ), patch.object(calculator, "_has_invalid_score_ratio", return_value=False), patch.object(
            calculator, "_has_completed_scored_arc", return_value=True
        ), patch.object(calculator, "_is_center_outside_flown_circle", return_value=False):
            calculator.on_gate_passed(self._make_event("SP-C", datetime.datetime(2020, 8, 1, 8, 10, tzinfo=datetime.timezone.utc), 60.1, 11.1, altitude=1000))
            calculator.on_gate_passed(self._make_event("X", datetime.datetime(2020, 8, 1, 8, 12, tzinfo=datetime.timezone.utc), 60.3, 11.3, altitude=1000))
            calculator.altitude_samples_ft.extend([1000.0, 1305.0])
            calculator.on_gate_passed(self._make_event("WP", datetime.datetime(2020, 8, 1, 8, 18, tzinfo=datetime.timezone.utc), 60.2015, 11.2015, altitude=1305))

        first = calculator.score_processing_queue.get_nowait()
        second = calculator.score_processing_queue.get_nowait()
        third = calculator.score_processing_queue.get_nowait()
        fourth = calculator.score_processing_queue.get_nowait()
        fifth = calculator.score_processing_queue.get_nowait()
        self.assertEqual(first.score_type, "circle_start")
        self.assertEqual(second.score_type, "circle_entry")
        self.assertEqual(third.score_type, "circle_score")
        self.assertEqual(fourth.score_type, "circle_altitude_penalty")
        self.assertEqual(fourth.annotation_type, "anomaly")
        self.assertEqual(fourth.message, "circle altitude spread penalty")
        self.assertAlmostEqual(fourth.score, round(third.score * 0.2, 1))
        self.assertEqual(fifth.score_type, "circle_exit")

    def test_circle_calculator_marks_incomplete_scored_arc_as_anomaly(self):
        self.navigation_task.scorecard.circle_radius_min_m = 0
        self.navigation_task.scorecard.circle_radius_max_m = 2000
        self.navigation_task.scorecard.save(update_fields=["circle_radius_min_m", "circle_radius_max_m"])
        self.contestant.navigation_task = self.navigation_task
        calculator = CircleCalculator(
            self.contestant,
            self.scorecard,
            self.route,
            Queue(),
            live_processing=False,
            projector=self.navigation_task.get_projector(),
        )
        with patch.object(calculator, "_is_clockwise_turn", return_value=False), patch.object(
            calculator, "_is_radius_outside_limits", return_value=False
        ), patch.object(calculator, "_has_invalid_score_ratio", return_value=False):
            calculator.on_gate_passed(self._make_event("SP-C", datetime.datetime(2020, 8, 1, 8, 10, tzinfo=datetime.timezone.utc), 60.1, 11.1))
            calculator.on_gate_passed(self._make_event("X", datetime.datetime(2020, 8, 1, 8, 12, tzinfo=datetime.timezone.utc), 60.3, 11.3))
            calculator.on_gate_passed(self._make_event("WP", datetime.datetime(2020, 8, 1, 8, 18, tzinfo=datetime.timezone.utc), 60.2015, 11.2015))

        first = calculator.score_processing_queue.get_nowait()
        second = calculator.score_processing_queue.get_nowait()
        third = calculator.score_processing_queue.get_nowait()
        self.assertEqual(first.score_type, "circle_start")
        self.assertEqual(second.score_type, "circle_entry")
        self.assertEqual(third.score_type, "circle_incomplete_scored_arc")
        self.assertEqual(third.annotation_type, "anomaly")
        self.assertEqual(third.message, "circle scored arc not completed")

    def test_circle_calculator_records_progress_and_ignores_first_180_degrees(self):
        calculator = CircleCalculator(
            self.contestant,
            self.scorecard,
            self.route,
            Queue(),
            live_processing=False,
            projector=self.navigation_task.get_projector(),
        )
        for bearing, radius in [(0, 220), (90, 240), (180, 260), (225, 300), (270, 320), (315, 340), (360, 360)]:
            pos = self._circle_position(bearing, radius)
            calculator._record_progress_sample(pos)

        self.assertGreaterEqual(calculator.cumulative_progress_deg, 360)
        self.assertEqual([round(value) for value in calculator.progress_radius_samples], [301, 321, 341, 360])

    def test_circle_calculator_calculate_enroute_accumulates_progress_samples(self):
        calculator = CircleCalculator(
            self.contestant,
            self.scorecard,
            self.route,
            Queue(),
            live_processing=False,
            projector=self.navigation_task.get_projector(),
        )
        calculator.entered = True
        calculator.entry_position = type("Pos", (), {"latitude": 60.3, "longitude": 11.3})()
        state = OrchestratorState(
            last_gate=None,
            last_visible_gate=None,
            next_gate=None,
            in_range_of_gate=None,
            projector=self.projector,
            has_passed_finishpoint=False,
            recalculation_completed=True,
        )
        track = []
        for bearing, radius in [(0, 220), (90, 240), (180, 260), (225, 300), (270, 320), (315, 340), (360, 360)]:
            track.append(self._circle_position(bearing, radius, altitude=1000 + bearing))
            calculator.calculate_enroute(track, state)

        self.assertGreaterEqual(calculator.cumulative_progress_deg, 360)
        self.assertEqual([round(value) for value in calculator.progress_radius_samples], [301, 321, 341, 360])
        self.assertGreaterEqual(len(calculator.altitude_samples_ft), 4)

    def test_circle_calculator_final_score_requires_completed_scored_arc(self):
        calculator = CircleCalculator(
            self.contestant,
            self.scorecard,
            self.route,
            Queue(),
            live_processing=False,
            projector=self.navigation_task.get_projector(),
        )
        calculator.progress_radius_samples = [300.0, 320.0, 340.0, 360.0]
        calculator.final_score_ready = False
        self.assertFalse(calculator._has_completed_scored_arc())
        calculator.final_score_ready = True
        self.assertTrue(calculator._has_completed_scored_arc())
