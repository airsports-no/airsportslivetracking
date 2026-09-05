import datetime
from queue import Queue
from unittest.mock import MagicMock, patch

from django.test import TestCase

from display.calculators.calculator import GatePassedEvent, OrchestratorState
from display.calculators.calculator_factory import calculator_factory
from display.calculators.circle_calculator import CIRCLE_MAXIMUM_SCORE, CircleCalculator
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
        self.navigation_task.scorecard.save(update_fields=["config"])
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
                        "properties": {
                            "id": "cm-1",
                            "name": "CM",
                            "pointType": "circle_center",
                            "featureType": "circle_center_marker",
                        },
                        "geometry": {"type": "Point", "coordinates": [11.2, 60.2]},
                    },
                    {
                        "type": "Feature",
                        "properties": {
                            "id": "cs-1",
                            "name": "SP-C",
                            "pointType": "circle_start",
                            "featureType": "circle_start_marker",
                        },
                        "geometry": {"type": "Point", "coordinates": [11.1, 60.1]},
                    },
                    {
                        "type": "Feature",
                        "properties": {
                            "id": "ce-1",
                            "name": "X",
                            "pointType": "circle_entry",
                            "featureType": "circle_entry_marker",
                        },
                        "geometry": {"type": "Point", "coordinates": [11.3, 60.3]},
                    },
                    {
                        "type": "Feature",
                        "properties": {
                            "id": "cx-1",
                            "name": "WP",
                            "pointType": "circle_exit",
                            "featureType": "circle_exit_marker",
                        },
                        "geometry": {"type": "Point", "coordinates": [11.35, 60.35]},
                    },
                ],
            },
        )
        self.navigation_task.save(update_fields=["editable_route"])
        self.projector = self.navigation_task.get_projector()

    def _make_event(
        self,
        gate_name: str,
        timestamp: datetime.datetime,
        latitude: float = 60.0,
        longitude: float = 11.0,
        altitude: float = 0.0,
    ):
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
        self.navigation_task.scorecard.save(update_fields=["config"])
        self.contestant.navigation_task = self.navigation_task
        calculator = CircleCalculator(
            self.contestant,
            self.scorecard,
            self.route,
            Queue(),
            live_processing=False,
            projector=self.navigation_task.get_projector(),
        )
        with (
            patch.object(calculator, "_is_clockwise_turn", return_value=False),
            patch.object(calculator, "_is_radius_outside_limits", return_value=False),
            patch.object(calculator, "_has_invalid_score_ratio", return_value=False),
            patch.object(calculator, "_has_completed_scored_arc", return_value=True),
            patch.object(calculator, "_is_center_outside_flown_circle", return_value=False),
        ):
            calculator.on_gate_passed(
                self._make_event("SP-C", datetime.datetime(2020, 8, 1, 8, 10, tzinfo=datetime.timezone.utc), 60.1, 11.1)
            )
            calculator.on_gate_passed(
                self._make_event("X", datetime.datetime(2020, 8, 1, 8, 12, tzinfo=datetime.timezone.utc), 60.3, 11.3)
            )
            calculator.on_gate_passed(
                self._make_event(
                    "WP", datetime.datetime(2020, 8, 1, 8, 18, tzinfo=datetime.timezone.utc), 60.2015, 11.2015
                )
            )

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
        calculator.on_gate_passed(
            self._make_event("WP", datetime.datetime(2020, 8, 1, 8, 18, tzinfo=datetime.timezone.utc), 60.35, 11.35)
        )

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
        calculator.on_gate_passed(
            self._make_event("X", datetime.datetime(2020, 8, 1, 8, 12, tzinfo=datetime.timezone.utc), 60.3, 11.3)
        )

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
        calculator.on_gate_passed(
            self._make_event("SP-C", datetime.datetime(2020, 8, 1, 8, 10, tzinfo=datetime.timezone.utc), 60.1, 11.1)
        )
        calculator.on_gate_passed(
            self._make_event("X", datetime.datetime(2020, 8, 1, 8, 12, tzinfo=datetime.timezone.utc), 60.22, 11.10)
        )

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
        calculator.on_gate_passed(
            self._make_event("SP-C", datetime.datetime(2020, 8, 1, 8, 10, tzinfo=datetime.timezone.utc), 60.1, 11.1)
        )
        calculator.on_gate_passed(
            self._make_event("X", datetime.datetime(2020, 8, 1, 8, 12, tzinfo=datetime.timezone.utc), 60.22, 11.10)
        )
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
        calculator.on_gate_passed(
            self._make_event("SP-C", datetime.datetime(2020, 8, 1, 8, 10, tzinfo=datetime.timezone.utc), 60.1, 11.1)
        )
        calculator.on_gate_passed(
            self._make_event("X", datetime.datetime(2020, 8, 1, 8, 12, tzinfo=datetime.timezone.utc), 60.3, 11.3)
        )
        calculator.on_gate_passed(
            self._make_event("WP", datetime.datetime(2020, 8, 1, 8, 18, tzinfo=datetime.timezone.utc), 60.15, 11.35)
        )

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
        calculator.on_gate_passed(
            self._make_event("SP-C", datetime.datetime(2020, 8, 1, 8, 10, tzinfo=datetime.timezone.utc), 60.1, 11.1)
        )
        calculator.on_gate_passed(
            self._make_event("X", datetime.datetime(2020, 8, 1, 8, 12, tzinfo=datetime.timezone.utc), 60.3, 11.3)
        )
        calculator.on_gate_passed(
            self._make_event("WP", datetime.datetime(2020, 8, 1, 8, 18, tzinfo=datetime.timezone.utc), 60.8, 11.8)
        )

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
        self.navigation_task.scorecard.save(update_fields=["config"])
        self.contestant.navigation_task = self.navigation_task
        calculator = CircleCalculator(
            self.contestant,
            self.scorecard,
            self.route,
            Queue(),
            live_processing=False,
            projector=self.navigation_task.get_projector(),
        )
        with (
            patch.object(calculator, "_is_clockwise_turn", return_value=False),
            patch.object(calculator, "_is_radius_outside_limits", return_value=False),
            patch.object(calculator, "_has_invalid_score_ratio", return_value=True),
        ):
            calculator.progress_radius_samples = [200.0, 450.0]
            calculator.on_gate_passed(
                self._make_event("SP-C", datetime.datetime(2020, 8, 1, 8, 10, tzinfo=datetime.timezone.utc), 60.1, 11.1)
            )
            calculator.on_gate_passed(
                self._make_event("X", datetime.datetime(2020, 8, 1, 8, 12, tzinfo=datetime.timezone.utc), 60.3, 11.3)
            )
            calculator.on_gate_passed(
                self._make_event(
                    "WP", datetime.datetime(2020, 8, 1, 8, 18, tzinfo=datetime.timezone.utc), 60.2015, 11.2015
                )
            )

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
        self.navigation_task.scorecard.save(update_fields=["config"])
        self.contestant.navigation_task = self.navigation_task
        calculator = CircleCalculator(
            self.contestant,
            self.scorecard,
            self.route,
            Queue(),
            live_processing=False,
            projector=self.navigation_task.get_projector(),
        )
        with (
            patch.object(calculator, "_is_clockwise_turn", return_value=False),
            patch.object(calculator, "_is_radius_outside_limits", return_value=False),
            patch.object(calculator, "_has_invalid_score_ratio", return_value=False),
            patch.object(calculator, "_has_completed_scored_arc", return_value=True),
            patch.object(calculator, "_is_center_outside_flown_circle", return_value=True),
        ):
            calculator.progress_radius_samples = [250.0, 260.0, 255.0]
            calculator.on_gate_passed(
                self._make_event("SP-C", datetime.datetime(2020, 8, 1, 8, 10, tzinfo=datetime.timezone.utc), 60.1, 11.1)
            )
            calculator.on_gate_passed(
                self._make_event("X", datetime.datetime(2020, 8, 1, 8, 12, tzinfo=datetime.timezone.utc), 60.3, 11.3)
            )
            calculator.on_gate_passed(
                self._make_event(
                    "WP", datetime.datetime(2020, 8, 1, 8, 18, tzinfo=datetime.timezone.utc), 60.3015, 11.3315
                )
            )

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
        self.navigation_task.scorecard.save(update_fields=["config"])
        self.contestant.navigation_task = self.navigation_task
        calculator = CircleCalculator(
            self.contestant,
            self.scorecard,
            self.route,
            Queue(),
            live_processing=False,
            projector=self.navigation_task.get_projector(),
        )
        with (
            patch.object(calculator, "_is_clockwise_turn", return_value=False),
            patch.object(calculator, "_is_radius_outside_limits", return_value=False),
            patch.object(calculator, "_has_invalid_score_ratio", return_value=False),
            patch.object(calculator, "_has_completed_scored_arc", return_value=True),
            patch.object(calculator, "_is_center_outside_flown_circle", return_value=False),
        ):
            calculator.on_gate_passed(
                self._make_event(
                    "SP-C",
                    datetime.datetime(2020, 8, 1, 8, 10, tzinfo=datetime.timezone.utc),
                    60.1,
                    11.1,
                    altitude=1000,
                )
            )
            calculator.on_gate_passed(
                self._make_event(
                    "X", datetime.datetime(2020, 8, 1, 8, 12, tzinfo=datetime.timezone.utc), 60.3, 11.3, altitude=1000
                )
            )
            calculator.altitude_samples_ft.extend([1000.0, 1305.0])
            calculator.on_gate_passed(
                self._make_event(
                    "WP",
                    datetime.datetime(2020, 8, 1, 8, 18, tzinfo=datetime.timezone.utc),
                    60.2015,
                    11.2015,
                    altitude=1305,
                )
            )

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
        # third.score is the penalty magnitude emitted for "circle_score" (CIRCLE_MAXIMUM_SCORE
        # minus the achieved value, not the achieved value itself - see circle_calculator.py's
        # on_gate_passed), so recover the achieved value before checking the 20% relationship.
        achieved_circle_score = CIRCLE_MAXIMUM_SCORE - third.score
        self.assertAlmostEqual(fourth.score, round(achieved_circle_score * 0.2, 1))
        self.assertEqual(fifth.score_type, "circle_exit")

    def test_circle_calculator_marks_incomplete_scored_arc_as_anomaly(self):
        self.navigation_task.scorecard.circle_radius_min_m = 0
        self.navigation_task.scorecard.circle_radius_max_m = 2000
        self.navigation_task.scorecard.save(update_fields=["config"])
        self.contestant.navigation_task = self.navigation_task
        calculator = CircleCalculator(
            self.contestant,
            self.scorecard,
            self.route,
            Queue(),
            live_processing=False,
            projector=self.navigation_task.get_projector(),
        )
        with (
            patch.object(calculator, "_is_clockwise_turn", return_value=False),
            patch.object(calculator, "_is_radius_outside_limits", return_value=False),
            patch.object(calculator, "_has_invalid_score_ratio", return_value=False),
        ):
            calculator.on_gate_passed(
                self._make_event("SP-C", datetime.datetime(2020, 8, 1, 8, 10, tzinfo=datetime.timezone.utc), 60.1, 11.1)
            )
            calculator.on_gate_passed(
                self._make_event("X", datetime.datetime(2020, 8, 1, 8, 12, tzinfo=datetime.timezone.utc), 60.3, 11.3)
            )
            calculator.on_gate_passed(
                self._make_event(
                    "WP", datetime.datetime(2020, 8, 1, 8, 18, tzinfo=datetime.timezone.utc), 60.2015, 11.2015
                )
            )

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

    # --- Boundary / lifecycle tests added to close the "no real flight data"
    # gap for this new CIMA calculator (see synthetic_helpers.py module
    # docstring for the general test-writing methodology). ---

    def test_circle_calculator_540_degree_progress_boundary(self):
        """final_score_ready flips exactly when cumulative progress reaches
        540 degrees (_record_progress_sample, circle_calculator.py:213-214),
        not before."""
        calculator = CircleCalculator(
            self.contestant,
            self.scorecard,
            self.route,
            Queue(),
            live_processing=False,
            projector=self.navigation_task.get_projector(),
        )
        # Each step below is a 90 degree increment around the circle center;
        # cumulative_progress_deg after N steps is 90*N.
        bearings = [
            0,
            90,
            180,
            270,
            360,
            450,
            540,
        ]  # cumulative: 90,180,270,360,450,540,630 (first sample is baseline, contributes 0)
        for bearing in bearings[:-1]:
            pos = self._circle_position(bearing, 260)
            calculator._record_progress_sample(pos)
            self.assertLess(calculator.cumulative_progress_deg, 540)
            self.assertFalse(
                calculator.final_score_ready, f"should not be ready at {calculator.cumulative_progress_deg} degrees"
            )
        # One more 90 degree step: cumulative goes from 540 to 630, crossing the boundary.
        pos = self._circle_position(bearings[-1], 260)
        calculator._record_progress_sample(pos)
        self.assertGreaterEqual(calculator.cumulative_progress_deg, 540)
        self.assertTrue(calculator.final_score_ready)

    def test_circle_calculator_180_degree_collection_lower_bound(self):
        """Radius samples for scoring are only collected once cumulative
        progress exceeds 180 degrees (circle_calculator.py:218-219) - the
        first half-turn is deliberately ignored (entry transient)."""
        calculator = CircleCalculator(
            self.contestant,
            self.scorecard,
            self.route,
            Queue(),
            live_processing=False,
            projector=self.navigation_task.get_projector(),
        )
        # First sample only sets the baseline angle (no delta yet, per the
        # `if self.last_circle_angle_deg is None: return` early exit).
        calculator._record_progress_sample(self._circle_position(0, 260))
        self.assertEqual(calculator.progress_radius_samples, [])

        # +90: cumulative=90, still <=180 -> no radius sample collected yet.
        calculator._record_progress_sample(self._circle_position(90, 260))
        self.assertLessEqual(calculator.cumulative_progress_deg, 180)
        self.assertEqual(calculator.progress_radius_samples, [])

        # +91 more (cumulative=181): now just past the 180 threshold -> this
        # sample (and only this one so far) should start being collected.
        calculator._record_progress_sample(self._circle_position(181, 260))
        self.assertGreater(calculator.cumulative_progress_deg, 180)
        self.assertEqual(len(calculator.progress_radius_samples), 1)

    def test_circle_calculator_540_degree_collection_upper_bound(self):
        """Radius-sample collection stops once cumulative progress exceeds
        540 degrees (circle_calculator.py:220-221) - samples past 1.5 turns
        are excluded from scoring."""
        calculator = CircleCalculator(
            self.contestant,
            self.scorecard,
            self.route,
            Queue(),
            live_processing=False,
            projector=self.navigation_task.get_projector(),
        )
        # Walk from 0 to 530 degrees in 90-degree steps (stays comfortably
        # inside the 180-540 collection window for the last few samples),
        # then take one final step that pushes cumulative past 540.
        for bearing in [0, 90, 180, 270, 360, 450, 530]:
            calculator._record_progress_sample(self._circle_position(bearing, 260))
        samples_before_boundary = len(calculator.progress_radius_samples)
        self.assertGreater(samples_before_boundary, 0)
        self.assertLessEqual(calculator.cumulative_progress_deg, 540)

        # +20 more: cumulative now 550, past 540 -> this sample must NOT be collected.
        calculator._record_progress_sample(self._circle_position(550, 260))
        self.assertGreater(calculator.cumulative_progress_deg, 540)
        self.assertEqual(len(calculator.progress_radius_samples), samples_before_boundary)

    def test_circle_calculator_altitude_spread_boundary(self):
        """Altitude spread of exactly 200ft incurs no penalty; 201ft does
        (circle_calculator.py:270-273, `spread <= 200`)."""
        calculator = CircleCalculator(
            self.contestant,
            self.scorecard,
            self.route,
            Queue(),
            live_processing=False,
            projector=self.navigation_task.get_projector(),
        )
        calculator.altitude_samples_ft = [1000.0, 1200.0]  # spread == 200
        self.assertEqual(calculator._calculate_altitude_penalty(100.0), 0.0)

        calculator.altitude_samples_ft = [1000.0, 1201.0]  # spread == 201
        self.assertEqual(calculator._calculate_altitude_penalty(100.0), round(100.0 * 0.2, 1))

    def test_circle_calculator_clockwise_epsilon_boundary(self):
        """_is_clockwise_turn only flags direction once the signed angular
        delta is meaningfully negative (circle_calculator.py:172,
        `delta < -1e-6`) - a position essentially on the entry radial (delta
        ~ 0) must not be flagged as clockwise."""
        calculator = CircleCalculator(
            self.contestant,
            self.scorecard,
            self.route,
            Queue(),
            live_processing=False,
            projector=self.navigation_task.get_projector(),
        )
        calculator.start_position = self._circle_position(0, 260)
        calculator.entry_position = self._circle_position(0, 260)
        # Essentially the same angle as entry (well within float noise) -> not clockwise.
        self.assertFalse(calculator._is_clockwise_turn(self._circle_position(0.0000001, 260)))
        # A small but real increasing-compass-bearing step (clockwise on a
        # compass) -> flagged.
        self.assertTrue(calculator._is_clockwise_turn(self._circle_position(5, 260)))

    def test_circle_calculator_degenerate_single_sample_fallback(self):
        """When entry is immediately followed by exit with no progress
        samples collected (the entry-to-exit turn stayed under the 180
        degree collection threshold), _calculate_circle_score falls back to
        radius_samples_m, which at exit contains exactly the one exit-time
        sample (circle_calculator.py:229-231). With a single sample,
        rmin == rmax, so the ratio is 1.0 and the score is the maximum 250.

        CURRENT BEHAVIOR (flagged, not a locked-in "this is correct" test):
        an near-instantaneous circle - one that barely turns before exiting -
        scores full marks under this fallback, since there's no second sample
        to reveal an inconsistent radius. Whether that's the intended
        design (vs. e.g. treating too little arc as automatically
        "incomplete", which the separate _has_completed_scored_arc check
        already partially guards against via `final_score_ready`) is a
        question for the domain owner, not something this test asserts is
        "right" - it only pins down what the code currently does.
        """
        calculator = CircleCalculator(
            self.contestant,
            self.scorecard,
            self.route,
            Queue(),
            live_processing=False,
            projector=self.navigation_task.get_projector(),
        )
        calculator.progress_radius_samples = []
        calculator.radius_samples_m = [260.0]
        self.assertFalse(calculator._has_invalid_score_ratio())
        self.assertEqual(calculator._calculate_circle_score(), 250.0)

    def test_circle_calculator_happy_path_full_lifecycle(self):
        """The canonical correct-contestant scenario: start -> valid straight
        entry -> just under two full turns at a constant radius -> exit.
        Asserts the exact ordered emission with no anomalies, exercising the
        state machine end to end rather than isolating one anomaly branch
        at a time like the existing tests do."""
        self.navigation_task.scorecard.circle_radius_min_m = 0
        self.navigation_task.scorecard.circle_radius_max_m = 2000
        self.navigation_task.scorecard.save(update_fields=["config"])
        self.contestant.navigation_task = self.navigation_task
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
        radius = 260
        start_time = datetime.datetime(2020, 8, 1, 8, 10, tzinfo=datetime.timezone.utc)
        entry_time = start_time + datetime.timedelta(minutes=2)
        calculator.on_gate_passed(self._make_event("SP-C", start_time, 60.1, 11.1))
        calculator.on_gate_passed(self._make_event("X", entry_time, 60.3, 11.3))

        # Constant-radius flight around the circle for just under 2 full
        # turns (700 degrees), well past the 540 degree scoring threshold.
        # Compass bearing decreasing == counter-clockwise (the required
        # direction; increasing bearing is clockwise and correctly rejected
        # by _is_clockwise_turn).
        track = []
        for bearing in range(700, 0, -20):
            track.append(self._circle_position(bearing, radius))
            calculator.calculate_enroute(track, state)

        # Exit exactly where the flown circle left off (NOT the circle
        # center - passing the center degenerates the angle computation
        # used by _is_clockwise_turn/_calculate_radius_m).
        exit_time = entry_time + datetime.timedelta(minutes=6)
        last_position = track[-1]
        calculator.on_gate_passed(self._make_event("WP", exit_time, last_position.latitude, last_position.longitude))

        messages = [calculator.score_processing_queue.get_nowait() for _ in range(4)]
        self.assertEqual(
            [m.score_type for m in messages], ["circle_start", "circle_entry", "circle_score", "circle_exit"]
        )
        # Near-constant radius (real geodesic placement introduces a little
        # noise, a few tenths of a meter) -> ratio close to but not
        # necessarily exactly 1.0 -> near-max achieved score -> near-zero
        # penalty (messages[2].score is CIRCLE_MAXIMUM_SCORE minus the
        # achieved value, not the achieved value itself - see
        # circle_calculator.py's on_gate_passed).
        self.assertLessEqual(messages[2].score, 5.0)
        self.assertTrue(calculator.score_processing_queue.empty())

    def test_circle_calculator_deviation_path_invalid_ratio_blocks_score(self):
        """Deviation scenario: the contestant does not hold a constant
        radius (varies enough that rmin/rmax <= 0.5), so the flight is
        invalid and no circle_score is ever emitted - confirming the
        anomaly-before-score ordering for a genuinely varying flown path
        (not a patched-out anomaly check like the other anomaly tests)."""
        self.navigation_task.scorecard.circle_radius_min_m = 0
        self.navigation_task.scorecard.circle_radius_max_m = 2000
        self.navigation_task.scorecard.save(update_fields=["config"])
        self.contestant.navigation_task = self.navigation_task
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
        start_time = datetime.datetime(2020, 8, 1, 8, 10, tzinfo=datetime.timezone.utc)
        entry_time = start_time + datetime.timedelta(minutes=2)
        calculator.on_gate_passed(self._make_event("SP-C", start_time, 60.1, 11.1))
        calculator.on_gate_passed(self._make_event("X", entry_time, 60.3, 11.3))

        # Radius swings between 200 and 500 (ratio 0.4, well under the 0.5
        # threshold) over just under two turns, flown counter-clockwise
        # (decreasing compass bearing).
        track = []
        for i, bearing in enumerate(range(700, 0, -20)):
            radius = 200 if i % 2 == 0 else 500
            track.append(self._circle_position(bearing, radius))
            calculator.calculate_enroute(track, state)

        exit_time = entry_time + datetime.timedelta(minutes=6)
        last_position = track[-1]
        calculator.on_gate_passed(self._make_event("WP", exit_time, last_position.latitude, last_position.longitude))

        messages = [calculator.score_processing_queue.get_nowait() for _ in range(3)]
        self.assertEqual(
            [m.score_type for m in messages], ["circle_start", "circle_entry", "circle_invalid_score_ratio"]
        )
        self.assertTrue(calculator.score_processing_queue.empty())
        for message in messages:
            self.assertNotEqual(message.score_type, "circle_score")
