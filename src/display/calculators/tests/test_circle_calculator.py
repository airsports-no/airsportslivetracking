import datetime
import math
from queue import Queue
from unittest.mock import MagicMock, patch

from django.test import TestCase

from display.calculators.calculator import GatePassedEvent, OrchestratorState
from display.calculators.calculator_factory import calculator_factory
from display.calculators.circle_calculator import CIRCLE_MAXIMUM_SCORE, FEET_PER_METRE, CircleCalculator
from display.default_scorecards.create_scorecards import create_scorecards
from display.calculators.update_score_message import PENALTY, PERCENTAGE_PENALTY
from display.models import Aeroplane, Contest, Contestant, Crew, EditableRoute, NavigationTask, Person, Scorecard, Team
from display.utilities.task_types import CIRCLE
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

    # --- The flight itself: positions around CM through calculate_enroute, the gates as events. ---------------------
    #
    # Coordinates below are metres in the frame of the circle: `along` is the direction of the straight run (SP to CM
    # and beyond) and `left` is to its left; CM is the origin. A left circle runs counter-clockwise in this frame.

    def _calculator(self, **scorecard_values):
        scorecard = self.navigation_task.scorecard
        for key, value in scorecard_values.items():
            setattr(scorecard, key, value)
        if scorecard_values:
            scorecard.save(update_fields=["config"])
        self.contestant.navigation_task = self.navigation_task
        calculator = CircleCalculator(
            self.contestant,
            scorecard,
            self.route,
            Queue(),
            live_processing=False,
            projector=self.navigation_task.get_projector(),
        )
        self.assertTrue(calculator._frame_ready)
        self._clock = datetime.datetime(2020, 8, 1, 8, 10, tzinfo=datetime.timezone.utc)
        self._track = []
        self._state = OrchestratorState(
            last_gate=None,
            last_visible_gate=None,
            next_gate=None,
            in_range_of_gate=None,
            projector=self.projector,
            has_passed_finishpoint=False,
            recalculation_completed=True,
        )
        return calculator

    def _frame_position(self, calculator, along, left, altitude=1000.0):
        """A position `along` and `left` metres from CM in the frame of the straight run."""
        ux, uy = calculator._approach
        x = calculator._cm[0] + along * ux - left * uy
        y = calculator._cm[1] + along * uy + left * ux
        longitude, latitude = self.projector.from_projection.transform(x, y)
        self._clock += datetime.timedelta(seconds=1)
        position = MagicMock()
        position.time = self._clock
        position.latitude = latitude
        position.longitude = longitude
        position.altitude = altitude
        position.projected_x = x
        position.projected_y = y
        return position

    def _fly_to(self, calculator, along, left, altitude=1000.0):
        position = self._frame_position(calculator, along, left, altitude)
        self._track.append(position)
        calculator.calculate_enroute(self._track, self._state)
        return position

    def _gate(self, calculator, name, position):
        gate = MagicMock()
        gate.name = name
        calculator.on_gate_passed(GatePassedEvent(gate, position, position.time, previous_gate=None))

    def _start_and_straight_run(self, calculator, run_to=400.0, straight=True):
        """SP crossed, then the straight run over CM; X is crossed on the run beyond CM."""
        start = self._frame_position(calculator, -1000.0, 0.0 if straight else 400.0)
        self._gate(calculator, "SP-C", start)
        for along in range(-900, int(run_to) + 1, 100):
            position = self._fly_to(calculator, float(along), 0.0 if straight else 400.0)
            if along == 100:
                self._gate(calculator, "X", position)

    def _circle(
        self,
        calculator,
        radius=500.0,
        degrees=540.0,
        clockwise=False,
        altitude=1000.0,
        centre=(0.0, 0.0),
        step_deg=5.0,
    ):
        """The circle from the end of the straight run: `radius` and `altitude` may be functions of the angle."""
        sign = -1.0 if clockwise else 1.0
        angle = step_deg
        while angle <= degrees + 1e-9:
            r = radius(angle) if callable(radius) else radius
            a = altitude(angle) if callable(altitude) else altitude
            theta = math.radians(sign * angle)
            self._fly_to(calculator, centre[0] + r * math.cos(theta), centre[1] + r * math.sin(theta), a)
            angle += step_deg
        return self._track[-1]

    def _messages(self, calculator):
        messages = []
        while not calculator.score_processing_queue.empty():
            messages.append(calculator.score_processing_queue.get_nowait())
        return messages

    def _exit(self, calculator, last):
        self._gate(calculator, "WP", last)

    def _scored(self, messages):
        return {m.score_type: m for m in messages}

    def test_a_perfect_circle_loses_nothing(self):
        calculator = self._calculator()
        self._start_and_straight_run(calculator, run_to=500)
        last = self._circle(calculator)
        self._exit(calculator, last)
        messages = self._messages(calculator)
        self.assertEqual(
            ["circle_start", "circle_entry", "circle_score", "circle_exit"], [m.score_type for m in messages]
        )
        score = messages[2]
        self.assertEqual(PENALTY, score.kind)
        # the points lost of the 250; the crossing of X lies on the chord between two samples
        self.assertLess(score.score, 0.5)
        self.assertIn("Rmin 500 m, Rmax 500 m", score.message)

    def test_the_score_is_the_formula_over_the_scored_arc(self):
        calculator = self._calculator()
        self._start_and_straight_run(calculator, run_to=500)
        # 450 m at 180 degrees, 550 m at 360 degrees: Rmin/Rmax = 0.818, P = 159.1
        last = self._circle(calculator, radius=lambda angle: 500.0 + 50.0 * math.cos(math.radians(angle)))
        self._exit(calculator, last)
        score = self._scored(self._messages(calculator))["circle_score"]
        self.assertAlmostEqual(CIRCLE_MAXIMUM_SCORE - score.score, (450.0 / 550.0 - 0.5) * 500.0, delta=0.5)

    def test_the_radius_limits_apply_over_the_whole_scored_arc(self):
        for label, radius, expected in [
            ("too small at one point", lambda angle: 150.0 if 300.0 <= angle <= 305.0 else 500.0, "Rmin 150 m"),
            ("too large at one point", lambda angle: 800.0 if 400.0 <= angle <= 405.0 else 500.0, "Rmax 800 m"),
        ]:
            with self.subTest(label):
                self._track = []
                calculator = self._calculator()
                self._start_and_straight_run(calculator, run_to=500)
                last = self._circle(calculator, radius=radius, step_deg=1.0)
                self._exit(calculator, last)
                messages = self._messages(calculator)
                self.assertEqual(
                    ["circle_start", "circle_entry", "circle_invalid_radius"], [m.score_type for m in messages]
                )
                self.assertEqual(CIRCLE_MAXIMUM_SCORE, messages[2].score)
                self.assertIn(expected, messages[2].message)
                self.assertIn("200-750 m", messages[2].message)

    def test_a_radius_outside_the_limits_in_the_first_180_degrees_or_after_the_arc_is_not_scored(self):
        calculator = self._calculator()
        self._start_and_straight_run(calculator, run_to=500)
        # 800 m in the unscored half turn, 100 m after the second crossing of X: neither is part of the scored arc
        radius = lambda angle: 800.0 if angle <= 150.0 else (100.0 if angle > 545.0 else 500.0)  # noqa: E731
        altitude = lambda angle: 1300.0 if angle <= 150.0 or angle > 545.0 else 1000.0  # noqa: E731
        last = self._circle(calculator, radius=radius, altitude=altitude, degrees=700.0)
        self._exit(calculator, last)
        messages = self._messages(calculator)
        self.assertEqual(
            ["circle_start", "circle_entry", "circle_score", "circle_exit"], [m.score_type for m in messages]
        )
        self.assertLess(messages[2].score, 0.5)

    def test_a_clockwise_circle_loses_the_whole_task(self):
        calculator = self._calculator()
        self._start_and_straight_run(calculator, run_to=500)
        last = self._circle(calculator, clockwise=True)
        self._exit(calculator, last)
        messages = self._messages(calculator)
        self.assertEqual(["circle_start", "circle_entry", "circle_invalid_direction"], [m.score_type for m in messages])
        self.assertEqual(CIRCLE_MAXIMUM_SCORE, messages[2].score)
        self.assertIn("clockwise", messages[2].message)

    def test_a_left_circle_is_left_whichever_way_it_leaves(self):
        calculator = self._calculator()
        self._start_and_straight_run(calculator, run_to=500)
        self._circle(calculator)
        # leaves to the opposite side of where it entered
        last = self._fly_to(calculator, -300.0, -300.0)
        self._exit(calculator, last)
        self.assertEqual(
            ["circle_start", "circle_entry", "circle_score", "circle_exit"],
            [m.score_type for m in self._messages(calculator)],
        )

    def test_a_circle_around_another_point_than_cm_does_not_complete_the_scored_arc(self):
        calculator = self._calculator()
        self._start_and_straight_run(calculator, run_to=500)
        # Radius 300 m around a point 450 m to the left of CM: CM is outside the flown circle, the aircraft never goes
        # round it
        last = self._circle(calculator, radius=300.0, centre=(0.0, 450.0), degrees=540.0)
        self._exit(calculator, last)
        messages = self._messages(calculator)
        penalty = [m for m in messages if m.score_type == "circle_centre_outside"]
        self.assertEqual(1, len(penalty))
        self.assertEqual(PERCENTAGE_PENALTY, penalty[0].kind)
        self.assertEqual(100, penalty[0].score)
        self.assertIn("CM outside", penalty[0].message)
        self.assertNotIn("circle_incomplete_scored_arc", [m.score_type for m in messages])
        self.assertNotIn("circle_score", [m.score_type for m in messages])

    def test_x_crossed_once_is_an_incomplete_circle(self):
        calculator = self._calculator()
        self._start_and_straight_run(calculator, run_to=500)
        last = self._circle(calculator, degrees=300.0)  # past 180 degrees and no further than X again at 360
        self._exit(calculator, last)
        messages = self._messages(calculator)
        self.assertEqual("circle_incomplete_scored_arc", messages[-1].score_type)
        self.assertIn("crossed once and not again", messages[-1].message)
        self.assertEqual(CIRCLE_MAXIMUM_SCORE, messages[-1].score)

    def test_x_never_crossed_is_an_incomplete_circle(self):
        calculator = self._calculator()
        self._start_and_straight_run(calculator, run_to=500)
        last = self._circle(calculator, degrees=120.0)
        self._exit(calculator, last)
        messages = self._messages(calculator)
        self.assertEqual("circle_incomplete_scored_arc", messages[-1].score_type)
        self.assertIn("not crossed after the first 180 degrees", messages[-1].message)

    def test_a_flight_that_never_reaches_the_exit_is_still_scored_by_finalise(self):
        calculator = self._calculator()
        self._start_and_straight_run(calculator, run_to=500)
        self._circle(calculator, degrees=300.0)
        self.assertEqual(["circle_start", "circle_entry"], [m.score_type for m in self._messages(calculator)])
        calculator.finalise(self._track)
        messages = self._messages(calculator)
        self.assertEqual(["circle_incomplete_scored_arc"], [m.score_type for m in messages])
        self.assertEqual(CIRCLE_MAXIMUM_SCORE, messages[0].score)
        calculator.finalise(self._track)  # once only
        self.assertEqual([], self._messages(calculator))

    def test_a_completed_circle_without_an_exit_is_scored_by_finalise(self):
        calculator = self._calculator()
        self._start_and_straight_run(calculator, run_to=500)
        self._circle(calculator)
        self._messages(calculator)
        calculator.finalise(self._track)
        self.assertEqual(["circle_score"], [m.score_type for m in self._messages(calculator)])

    def test_a_flight_that_never_passed_sp_is_explained_at_finalise(self):
        calculator = self._calculator()
        calculator.finalise([self._frame_position(calculator, -800.0, 0.0)])
        messages = self._messages(calculator)
        self.assertEqual(["circle_incomplete_scored_arc"], [m.score_type for m in messages])
        self.assertIn("circle start (SP) was not passed", messages[0].message)
        calculator = self._calculator()
        calculator.finalise([])  # no positions, nothing to explain
        self.assertEqual([], self._messages(calculator))

    def test_entry_beside_cm_loses_the_whole_task(self):
        calculator = self._calculator()
        self._start_and_straight_run(calculator, run_to=500, straight=False)
        messages = self._messages(calculator)
        self.assertEqual(["circle_start", "circle_invalid_entry_line"], [m.score_type for m in messages])
        last = self._circle(calculator)
        self._exit(calculator, last)
        self.assertEqual([], self._messages(calculator))  # the circle after it adds nothing

    def test_the_entry_is_judged_from_the_track_when_the_x_gate_is_never_crossed(self):
        for straight, expected in [(True, ["circle_start", "circle_score", "circle_exit"]), (False, None)]:
            with self.subTest(straight=straight):
                self._track = []
                calculator = self._calculator()
                start = self._frame_position(calculator, -1000.0, 0.0 if straight else 400.0)
                self._gate(calculator, "SP-C", start)
                for along in range(-900, 501, 100):
                    self._fly_to(calculator, float(along), 0.0 if straight else 400.0)
                last = self._circle(calculator, centre=(0.0, 0.0))
                self._exit(calculator, last)
                types = [m.score_type for m in self._messages(calculator)]
                if expected:
                    self.assertEqual(expected, types)
                else:
                    self.assertEqual(["circle_start", "circle_invalid_entry_line"], types)

    def test_the_altitude_rule_is_a_percentage_penalty_on_the_spread_in_feet_of_metres(self):
        # (spread in metres, penalised): 200 ft is 60.96 m. 70 m would be under the band if it were read as feet.
        cases = [(0.0, False), (50.0, False), (60.0, False), (62.0, True), (70.0, True), (300.0, True)]
        for spread_m, penalised in cases:
            with self.subTest(spread_m=spread_m):
                self._track = []
                calculator = self._calculator()
                self._start_and_straight_run(calculator, run_to=500)
                altitude = lambda angle: 1000.0 + (spread_m if 300.0 <= angle <= 310.0 else 0.0)  # noqa: E731
                last = self._circle(calculator, altitude=altitude)
                self._exit(calculator, last)
                messages = self._scored(self._messages(calculator))
                if not penalised:
                    self.assertNotIn("circle_altitude_penalty", messages)
                    continue
                penalty = messages["circle_altitude_penalty"]
                self.assertEqual(PERCENTAGE_PENALTY, penalty.kind)
                self.assertEqual(20, penalty.score)
                self.assertIn(f"{spread_m * FEET_PER_METRE:.0f} ft", penalty.message)
                self.assertIn("200 ft band", penalty.message)

    def test_the_altitude_band_and_percentage_come_from_the_scorecard(self):
        calculator = self._calculator(circle_altitude_band_ft=100, circle_altitude_penalty_percent=35)
        self._start_and_straight_run(calculator, run_to=500)
        last = self._circle(calculator, altitude=lambda angle: 1000.0 + (40.0 if 300.0 <= angle <= 310.0 else 0.0))
        self._exit(calculator, last)
        penalty = self._scored(self._messages(calculator))["circle_altitude_penalty"]
        self.assertEqual((PERCENTAGE_PENALTY, 35), (penalty.kind, penalty.score))
        self.assertIn("100 ft band", penalty.message)

    def test_altitude_outside_the_scored_arc_does_not_count(self):
        calculator = self._calculator()
        self._start_and_straight_run(calculator, run_to=500)
        altitude = lambda angle: 1000.0 + (200.0 if angle <= 150.0 or angle > 545.0 else 0.0)  # noqa: E731
        last = self._circle(calculator, altitude=altitude, degrees=700.0)
        self._exit(calculator, last)
        self.assertNotIn("circle_altitude_penalty", self._scored(self._messages(calculator)))

    def test_the_work_per_position_does_not_grow_with_the_track(self):
        calculator = self._calculator()
        self._start_and_straight_run(calculator, run_to=500)
        self._circle(calculator, step_deg=0.5, degrees=540.0)
        for name, value in vars(calculator).items():
            if isinstance(value, (list, dict, set)) and name not in ("start_names", "entry_names", "exit_names"):
                self.assertLessEqual(len(value), 10, name)
