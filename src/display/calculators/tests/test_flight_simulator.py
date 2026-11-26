"""Tests of the synthetic flight simulator itself (flight_simulator.py).

The first group needs no database: it checks the shape and timing of generated tracks. The second group builds a real
task and runs generated tracks through the calculators; it only asserts what the simulator is responsible for (the
track crosses the gates when and where it should, and the pipeline runs deterministically), not how the scorecards
judge a deviation - that is for the scenario tests built on top of the simulator.
"""

import datetime
import math

from django.test import SimpleTestCase, TestCase

from display.calculators.tests.flight_simulator import (
    AltitudeProfile,
    AltitudeSegment,
    DoubleCrossing,
    LateralOffset,
    MissGate,
    Orbit,
    ProcedureTurn,
    Reverse,
    SidewaysExcursion,
    SkipGate,
    TimeOffset,
    VisitOrder,
    WrongDirectionCrossing,
    _signed_bearing_change,
    build_task,
    circle_flight,
    gate_line_xy,
    generate_track,
    line_crossings,
    make_score_applier,
    precision_route_geojson,
    run_flight,
    waypoint,
)
from display.utilities.coordinate_utilities import Projector, calculate_bearing, project_position_lat_lon

START = datetime.datetime(2020, 8, 1, 8, 11, tzinfo=datetime.timezone.utc)
NAMES = ["SP", "TP1", "TP2", "FP"]
LEG_SECONDS = {"TP1": 300, "TP2": 560, "FP": 860}  # seconds after SP; the legs are 6000, 5000 and 6000 m
HALF_WIDTH = 926.0  # 1 NM wide gates


def _waypoints_and_times():
    geojson = precision_route_geojson()
    points = [f["geometry"]["coordinates"] for f in geojson["features"] if f["geometry"]["type"] == "Point"]
    waypoints = [waypoint(name, lat, lon) for name, (lon, lat) in zip(NAMES, points)]
    gate_times = {"SP": START}
    gate_times.update({name: START + datetime.timedelta(seconds=seconds) for name, seconds in LEG_SECONDS.items()})
    return waypoints, gate_times


class TrackGenerationTest(SimpleTestCase):
    def setUp(self):
        self.waypoints, self.gate_times = _waypoints_and_times()
        self.projector = Projector(self.waypoints[0].latitude, self.waypoints[0].longitude)
        self._xy_cache = {}

    def track(self, *deviations, **options):
        return generate_track(self.waypoints, self.gate_times, deviations=deviations, **options)

    def crossings(self, track, gate):
        line = gate_line_xy(self.waypoints, NAMES.index(gate), HALF_WIDTH, self.projector)
        return line_crossings(track, line, self.projector)

    def seconds_from_expected(self, time, gate):
        return (time - self.gate_times[gate]).total_seconds()

    def xy(self, position):
        if position not in self._xy_cache:
            point = self.projector.project_point(position.latitude, position.longitude)
            self._xy_cache[position] = (point.projected_x, point.projected_y)
        return self._xy_cache[position]

    def position_at(self, track, seconds_after_start):
        """The sample closest to `seconds_after_start` seconds after the SP time."""
        target = START + datetime.timedelta(seconds=seconds_after_start)
        return min(track, key=lambda position: abs((position.time - target).total_seconds()))

    # -- the undisturbed track ----------------------------------------------------------------------------------

    def test_track_is_one_hertz_with_lead_in_and_lead_out(self):
        track = self.track()
        gaps = {(b.time - a.time).total_seconds() for a, b in zip(track, track[1:])}
        self.assertEqual(gaps, {1.0})
        self.assertLessEqual((self.gate_times["SP"] - track[0].time).total_seconds(), 60)
        self.assertGreater((self.gate_times["SP"] - track[0].time).total_seconds(), 55)
        self.assertGreater((track[-1].time - self.gate_times["FP"]).total_seconds(), 55)

    def test_no_sample_lies_on_a_whole_second(self):
        # Gate times are whole seconds, so samples half a second off the grid never sit exactly on a gate line.
        self.assertTrue(all(position.time.microsecond == 500000 for position in self.track()))

    def test_every_gate_line_is_crossed_once_in_the_route_direction_at_the_expected_time(self):
        track = self.track()
        for gate in NAMES:
            crossings = self.crossings(track, gate)
            self.assertEqual(len(crossings), 1, gate)
            time, direction = crossings[0]
            self.assertEqual(direction, 1)
            self.assertAlmostEqual(self.seconds_from_expected(time, gate), 0, delta=0.5, msg=gate)

    def test_speed_and_course_follow_the_leg(self):
        position = self.position_at(self.track(), 150)  # halfway along SP -> TP1: 6000 m in 300 s, due east
        self.assertAlmostEqual(position.speed, 20.0 / (1852.0 / 3600.0), delta=0.5)
        self.assertAlmostEqual(
            position.course,
            calculate_bearing(
                (self.waypoints[0].latitude, self.waypoints[0].longitude),
                (self.waypoints[1].latitude, self.waypoints[1].longitude),
            ),
            delta=1.0,
        )

    def test_generating_twice_gives_identical_positions(self):
        deviations = [TimeOffset("TP1", 15), Orbit("TP2", radius_m=200)]
        self.assertEqual(self.track(*deviations), self.track(*deviations))

    # -- deviations -----------------------------------------------------------------------------------------------

    def test_time_offset_late_and_early(self):
        for seconds in (20, -20):
            track = self.track(TimeOffset("TP1", seconds))
            self.assertAlmostEqual(
                self.seconds_from_expected(self.crossings(track, "TP1")[0][0], "TP1"), seconds, delta=0.5
            )
            # The other gates are untouched.
            for gate in ("SP", "TP2", "FP"):
                self.assertAlmostEqual(
                    self.seconds_from_expected(self.crossings(track, gate)[0][0], gate), 0, delta=0.5, msg=gate
                )

    def test_time_offset_that_does_not_fit_between_the_neighbours_is_rejected(self):
        with self.assertRaises(ValueError):
            self.track(TimeOffset("TP1", 400))

    def test_lateral_offset_moves_the_crossing_along_the_gate_line(self):
        track = self.track(LateralOffset("TP1", 300.0))
        line = gate_line_xy(self.waypoints, 1, HALF_WIDTH, self.projector)
        crossings = line_crossings(track, line, self.projector)
        self.assertEqual(len(crossings), 1)
        crossing_xy = self.xy(self.position_at(track, 300))
        centre = self.projector.project_point(self.waypoints[1].latitude, self.waypoints[1].longitude)
        self.assertAlmostEqual(
            math.hypot(crossing_xy[0] - centre.projected_x, crossing_xy[1] - centre.projected_y), 300, delta=25
        )

    def test_missing_a_gate_passes_outside_the_end_of_the_gate_line(self):
        track = self.track(MissGate("TP1"))
        self.assertEqual(self.crossings(track, "TP1"), [])
        centre = self.projector.project_point(self.waypoints[1].latitude, self.waypoints[1].longitude)
        closest = min(math.hypot(self.xy(p)[0] - centre.projected_x, self.xy(p)[1] - centre.projected_y) for p in track)
        self.assertGreater(closest, HALF_WIDTH)
        # Everything else still happens on time.
        for gate in ("SP", "TP2", "FP"):
            self.assertAlmostEqual(self.seconds_from_expected(self.crossings(track, gate)[0][0], gate), 0, delta=0.5)

    def test_missing_a_gate_on_the_left_side(self):
        track = self.track(MissGate("TP1", side="left"))
        self.assertEqual(self.crossings(track, "TP1"), [])

    def test_skipping_a_gate_flies_straight_past_it(self):
        track = self.track(SkipGate("TP1"))
        self.assertEqual(self.crossings(track, "TP1"), [])
        for gate in ("SP", "TP2", "FP"):
            self.assertAlmostEqual(self.seconds_from_expected(self.crossings(track, gate)[0][0], gate), 0, delta=0.5)

    def test_double_crossing_crosses_the_line_twice_in_the_route_direction(self):
        track = self.track(DoubleCrossing("TP1", gap_s=60))
        crossings = self.crossings(track, "TP1")
        self.assertEqual([direction for _, direction in crossings], [1, 1])
        self.assertAlmostEqual(self.seconds_from_expected(crossings[0][0], "TP1"), 0, delta=0.5)
        self.assertAlmostEqual((crossings[1][0] - crossings[0][0]).total_seconds(), 60, delta=1.0)
        self.assertAlmostEqual(self.seconds_from_expected(self.crossings(track, "TP2")[0][0], "TP2"), 0, delta=0.5)

    def test_crossing_in_the_wrong_direction_crosses_the_line_once_against_the_route(self):
        track = self.track(WrongDirectionCrossing("TP1"))
        crossings = self.crossings(track, "TP1")
        self.assertEqual([direction for _, direction in crossings], [-1])
        self.assertAlmostEqual(self.seconds_from_expected(crossings[0][0], "TP1"), 0, delta=0.5)

    def test_visiting_gates_in_another_order(self):
        track = self.track(VisitOrder(["SP", "TP2", "TP1", "FP"]))
        visited = {}
        for waypoint_ in self.waypoints:
            centre = self.projector.project_point(waypoint_.latitude, waypoint_.longitude)
            closest = min(
                track,
                key=lambda p: math.hypot(self.xy(p)[0] - centre.projected_x, self.xy(p)[1] - centre.projected_y),
            )
            visited[waypoint_.name] = closest.time
        self.assertEqual(sorted(visited, key=visited.get), ["SP", "TP2", "TP1", "FP"])
        # The gates keep their time slots: TP2 is now visited when TP1 was due.
        self.assertAlmostEqual(self.seconds_from_expected(visited["TP2"], "TP1"), 0, delta=1.0)

    def test_orbit_is_a_full_circle_of_the_requested_radius_and_direction(self):
        tp1 = self.projector.project_point(self.waypoints[1].latitude, self.waypoints[1].longitude)
        leg_length = math.hypot(tp1.projected_x, tp1.projected_y)
        heading = (tp1.projected_x / leg_length, tp1.projected_y / leg_length)
        duration = 2 * math.pi * 200 / (leg_length / 300.0)
        for direction, sign in (("left", -1), ("right", 1)):
            track = self.track(Orbit("SP", fraction=0.5, radius_m=200, direction=direction))
            normal = (-heading[1], heading[0]) if direction == "left" else (heading[1], -heading[0])
            centre = (
                tp1.projected_x / 2 + normal[0] * 200,
                tp1.projected_y / 2 + normal[1] * 200,
            )
            window = [p for p in track if 150.0 <= (p.time - START).total_seconds() <= 150.0 + duration]
            self.assertGreater(len(window), 55)
            for position in window:
                x, y = self.xy(position)
                self.assertAlmostEqual(math.hypot(x - centre[0], y - centre[1]), 200, delta=1.0)
            bearings = [math.degrees(math.atan2(self.xy(p)[0] - centre[0], self.xy(p)[1] - centre[1])) for p in window]
            turned = sum(_signed_bearing_change(a, b) for a, b in zip(bearings, bearings[1:]))
            # Counter-clockwise (left) means the bearing seen from the centre decreases; one sample short of 360.
            self.assertAlmostEqual(turned, sign * 355, delta=12)

    def test_orbit_that_does_not_fit_on_the_leg_is_rejected(self):
        with self.assertRaises(ValueError):
            self.track(Orbit("SP", radius_m=800))

    def test_reverse_flies_backwards_for_the_given_time_and_then_resumes(self):
        track = self.track(Reverse("SP", seconds=10))
        before = self.position_at(track, 150)
        reversing = self.position_at(track, 155)
        deepest = self.position_at(track, 160)
        resumed = self.position_at(track, 175)
        self.assertAlmostEqual(reversing.course, 270.0, delta=2.0)
        self.assertLess(self.xy(deepest)[0], self.xy(before)[0] - 150)  # 10 s at 20 m/s
        self.assertAlmostEqual(resumed.course, 90.0, delta=2.0)
        self.assertGreater(self.xy(resumed)[0], self.xy(before)[0])
        # Everything after the reversal is back on schedule.
        self.assertAlmostEqual(self.seconds_from_expected(self.crossings(track, "TP1")[0][0], "TP1"), 0, delta=0.5)

    def test_sideways_excursion_leaves_the_leg_line_and_returns(self):
        track = self.track(SidewaysExcursion("SP", distance_m=400, duration_s=30, fraction=0.5, ramp_s=10))
        start = self.xy(self.position_at(track, 0))
        end = self.xy(self.position_at(track, 300))
        length = math.hypot(end[0] - start[0], end[1] - start[1])

        def lateral(position):
            """Metres to the right of the SP -> TP1 line (right of an eastbound flight is south)."""
            x, y = self.xy(position)
            return ((x - start[0]) * (end[1] - start[1]) - (y - start[1]) * (end[0] - start[0])) / length

        window = [p for p in track if 150 <= (p.time - START).total_seconds() <= 200]
        outside = [
            p
            for p in track
            if 0 <= (p.time - START).total_seconds() < 148 or 202 < (p.time - START).total_seconds() <= 300
        ]
        self.assertAlmostEqual(max(abs(lateral(p)) for p in window), 400, delta=3)
        self.assertLess(max(abs(lateral(p)) for p in outside), 3)
        # Pointing to the right of the direction of flight (east, so south of the line).
        self.assertGreater(lateral(self.position_at(track, 175)), 390)

    def test_altitude_profile_step_and_excursion(self):
        profile = AltitudeProfile(
            base=1000.0,
            segments=(
                AltitudeSegment(
                    START + datetime.timedelta(seconds=100), START + datetime.timedelta(seconds=140), 1600.0
                ),
                AltitudeSegment(START + datetime.timedelta(seconds=400), None, 800.0),
            ),
        )
        track = self.track(altitude=profile)
        by_second = {int((p.time - START).total_seconds()): p.altitude for p in track}
        self.assertEqual(by_second[50], 1000.0)
        self.assertEqual(by_second[120], 1600.0)
        self.assertEqual(by_second[150], 1000.0)
        self.assertEqual(by_second[500], 800.0)

    def test_constant_altitude(self):
        self.assertEqual({p.altitude for p in self.track(altitude=1234.0)}, {1234.0})

    def test_lead_in_and_out_follow_the_first_and_last_leg(self):
        track = self.track()
        self.assertAlmostEqual(track[0].course, 90.0, delta=1.0)
        self.assertAlmostEqual(
            track[-1].course,
            calculate_bearing(
                (self.waypoints[2].latitude, self.waypoints[2].longitude),
                (self.waypoints[3].latitude, self.waypoints[3].longitude),
            ),
            delta=1.0,
        )


class ProcedureTurnTest(SimpleTestCase):
    """Turns of 160 degrees at TP1 and TP2 (a 400 s leg at 20 m/s each), flown with and without procedure turns."""

    def setUp(self):
        geojson = precision_route_geojson(legs=((90.0, 8000.0), (250.0, 8000.0), (90.0, 8000.0)))
        points = [f["geometry"]["coordinates"] for f in geojson["features"] if f["geometry"]["type"] == "Point"]
        self.waypoints = [waypoint(name, lat, lon) for name, (lon, lat) in zip(NAMES, points)]
        self.gate_times = {name: START + datetime.timedelta(seconds=400 * i) for i, name in enumerate(NAMES)}
        self.projector = Projector(self.waypoints[0].latitude, self.waypoints[0].longitude)

    def track(self, *deviations):
        return generate_track(self.waypoints, self.gate_times, deviations=deviations, projector=self.projector)

    def xy(self, position):
        point = self.projector.project_point(position.latitude, position.longitude)
        return point.projected_x, point.projected_y

    def distance_to(self, position, gate):
        centre = self.projector.project_point(
            self.waypoints[NAMES.index(gate)].latitude, self.waypoints[NAMES.index(gate)].longitude
        )
        x, y = self.xy(position)
        return math.hypot(x - centre.projected_x, y - centre.projected_y)

    def sample_at(self, track, gate):
        return min(track, key=lambda position: abs((position.time - self.gate_times[gate]).total_seconds()))

    def turned_between(self, track, first_gate, second_gate):
        """The signed change of course (positive: right) between the samples at two gate times."""
        window = [p for p in track if self.gate_times[first_gate] <= p.time <= self.gate_times[second_gate]]
        return sum(_signed_bearing_change(a.course, b.course) for a, b in zip(window, window[1:]))

    def test_the_gate_is_passed_on_time_and_the_next_gate_is_reached_on_time(self):
        track = self.track(ProcedureTurn("TP1"))
        self.assertLess(self.distance_to(self.sample_at(track, "TP1"), "TP1"), 25)
        self.assertLess(self.distance_to(self.sample_at(track, "TP2"), "TP2"), 25)

    def test_the_default_procedure_turn_goes_the_long_way_round(self):
        # A 160 degree right turn at TP1 is flown as a 200 degree left turn.
        self.assertAlmostEqual(self.turned_between(self.track(ProcedureTurn("TP1")), "TP1", "TP2"), -200.0, delta=12.0)
        # A 160 degree left turn at TP2 is flown as a 200 degree right turn.
        self.assertAlmostEqual(self.turned_between(self.track(ProcedureTurn("TP2")), "TP2", "FP"), 200.0, delta=12.0)

    def test_forcing_the_direction_makes_the_short_turn(self):
        track = self.track(ProcedureTurn("TP1", direction="right"))
        self.assertAlmostEqual(self.turned_between(track, "TP1", "TP2"), 160.0, delta=12.0)

    def test_the_aircraft_overshoots_the_gate_before_turning(self):
        track = self.track(ProcedureTurn("TP1", overshoot_m=600.0))
        after = [
            p
            for p in track
            if self.gate_times["TP1"] <= p.time <= self.gate_times["TP1"] + datetime.timedelta(seconds=40)
        ]
        self.assertGreater(max(self.distance_to(p, "TP1") for p in after), 550)

    def test_a_procedure_turn_that_does_not_fit_before_the_next_gate_is_rejected(self):
        with self.assertRaises(ValueError):
            self.track(ProcedureTurn("TP1", radius_m=4000.0))


class CircleFlightTest(SimpleTestCase):
    CENTRE = (60.0, 11.0)

    def setUp(self):
        self.projector = Projector(*self.CENTRE)

    def flight(self, **options):
        start_point = project_position_lat_lon(self.CENTRE, 270.0, 800.0)  # west of the centre, flying east
        exit_point = project_position_lat_lon(self.CENTRE, 300.0, 900.0)
        return circle_flight(start_point, self.CENTRE, exit_point, start_time=START, **options)

    def distance_and_bearing(self, position):
        projected = self.projector.project_point(position.latitude, position.longitude)
        return (
            math.hypot(projected.projected_x, projected.projected_y),
            math.degrees(math.atan2(projected.projected_x, projected.projected_y)) % 360.0,
        )

    def circle_samples(self, track, minimum_distance, direction="left", sweep=810.0):
        """(position, swept angle) for the samples flown on the circle: after the pass over the centre, at least
        `minimum_distance` from it, until the swept angle (unwrapped from the entry bearing, east) passes `sweep`."""
        distances = [self.distance_and_bearing(p)[0] for p in track]
        after_centre = distances.index(min(distances))
        sign = 1.0 if direction == "left" else -1.0
        previous, total, samples = 90.0, 0.0, []
        for position, distance in list(zip(track, distances))[after_centre:]:
            if distance < minimum_distance and not samples:
                continue
            bearing = self.distance_and_bearing(position)[1]
            change = sign * -_signed_bearing_change(previous, bearing)
            if samples and abs(change) > 15.0:
                break
            total += change
            previous = bearing
            if total > sweep:
                break
            samples.append((position, total))
        return samples

    def test_start_point_is_passed_at_the_start_time_and_the_track_is_one_hertz(self):
        track = self.flight()
        start = project_position_lat_lon(self.CENTRE, 270.0, 800.0)
        closest = min(
            track,
            key=lambda p: math.hypot(p.latitude - start[0], (p.longitude - start[1]) * math.cos(math.radians(60))),
        )
        self.assertLess(abs((closest.time - START).total_seconds()), 1.0)
        self.assertEqual({(b.time - a.time).total_seconds() for a, b in zip(track, track[1:])}, {1.0})

    def test_constant_radius_circle(self):
        for direction in ("left", "right"):
            track = self.flight(direction=direction, radius_m=500.0, sweep_deg=810.0)
            samples = self.circle_samples(track, 450.0, direction)
            on_circle = [(p, a) for p, a in samples if abs(self.distance_and_bearing(p)[0] - 500.0) < 1.0]
            # 810 degrees of a 500 m circle at 75 kt takes about 183 s.
            self.assertGreater(len(on_circle), 170, direction)
            self.assertLess(len(on_circle), 195, direction)
            angles = [a for _, a in on_circle]
            self.assertAlmostEqual(angles[-1], 810.0, delta=10.0)
            self.assertTrue(all(b > a for a, b in zip(angles, angles[1:])), direction)

    def test_direction_left_is_counter_clockwise_and_right_is_clockwise(self):
        for direction, sign in (("left", -1), ("right", 1)):
            samples = self.circle_samples(self.flight(direction=direction, radius_m=500.0), 450.0, direction)
            bearings = [self.distance_and_bearing(p)[1] for p, _ in samples[2:40]]
            changes = [_signed_bearing_change(a, b) for a, b in zip(bearings, bearings[1:])]
            self.assertTrue(all(change * sign > 0 for change in changes), direction)

    def test_radius_as_a_function_of_the_swept_angle(self):
        def radius(angle):
            return 300.0 + 200.0 * angle / 810.0

        samples = self.circle_samples(self.flight(direction="left", radius_m=radius, sweep_deg=810.0), 330.0)
        checked = 0
        for position, angle in samples:
            if 15.0 <= angle <= 790.0:
                self.assertAlmostEqual(self.distance_and_bearing(position)[0], radius(angle), delta=3.0)
                checked += 1
        self.assertGreater(checked, 100)

    def test_the_sweep_is_configurable(self):
        full = self.circle_samples(self.flight(radius_m=500.0, sweep_deg=810.0), 450.0)
        short = self.circle_samples(self.flight(radius_m=500.0, sweep_deg=450.0), 450.0, sweep=450.0)
        self.assertGreater(len(full), len(short) + 60)

    def test_the_track_leaves_towards_the_exit_point(self):
        track = self.flight(direction="left", radius_m=500.0, sweep_deg=810.0)
        exit_point = project_position_lat_lon(self.CENTRE, 300.0, 900.0)
        closest = min(
            math.hypot(p.latitude - exit_point[0], (p.longitude - exit_point[1]) * math.cos(math.radians(60)))
            for p in track
        )
        self.assertLess(closest * 111_000, 30.0)


class DatabaseFlightTest(TestCase):
    """The generated track on a real, compiled task, through the real calculators and score application."""

    def setUp(self):
        self.task = build_task(precision_route_geojson())
        self.waypoints = self.task.effective_waypoints
        self.gate_times = self.task.gate_times

    def seconds_from_expected(self, result, gate):
        return (result.gate_passing_times[gate] - self.gate_times[gate]).total_seconds()

    def test_builder_creates_the_route_the_simulator_flies(self):
        self.assertEqual([w.name for w in self.waypoints], NAMES)
        self.assertEqual(set(NAMES) - set(self.gate_times), set())

    def test_perfect_track_passes_every_gate_within_a_second_of_the_expected_time(self):
        result = self.task.run(self.task.generate_track())
        for gate in NAMES:
            self.assertIsNotNone(result.gate_passing_times[gate], gate)
            self.assertLessEqual(abs(self.seconds_from_expected(result, gate)), 1.0, gate)
        self.assertEqual(result.missed_gates, [])

    def test_time_offset_shows_up_at_that_gate(self):
        result = self.task.run(self.task.generate_track([TimeOffset("TP1", 20)]))
        self.assertAlmostEqual(self.seconds_from_expected(result, "TP1"), 20.0, delta=1.0)
        self.assertLessEqual(abs(self.seconds_from_expected(result, "TP2")), 1.0)
        self.assertTrue(any(message.gate.name == "TP1" for message in result.messages_of_type("gate_score")))

    def test_skipped_gate_is_not_passed(self):
        result = self.task.run(self.task.generate_track([SkipGate("TP1")]))
        self.assertIsNone(result.gate_passing_times["TP1"])
        self.assertIn("TP1", result.missed_gates)
        self.assertIsNotNone(result.gate_passing_times["TP2"])

    def test_running_twice_gives_identical_messages_and_score(self):
        track = self.task.generate_track([TimeOffset("TP1", 20), SkipGate("TP2")])
        first = self.task.run(track)
        second = self.task.run(track)
        self.assertTrue(first.messages)
        self.assertEqual(first.summary(), second.summary())
        self.assertEqual(first.score, second.score)
        self.assertEqual(first.score_by_type, second.score_by_type)
        self.assertEqual(first.gate_passing_times, second.gate_passing_times)

    def test_generating_twice_gives_identical_positions(self):
        deviations = [TimeOffset("TP1", 20), Orbit("TP2", radius_m=200)]
        self.assertEqual(self.task.generate_track(deviations), self.task.generate_track(deviations))

    def test_score_by_type_covers_every_applied_message_type(self):
        result = self.task.run(self.task.generate_track([TimeOffset("TP1", 20)]))
        self.assertEqual(set(result.score_by_type), {message.score_type for message in result.messages})
        applier = make_score_applier(self.task.contestant)
        self.assertEqual(applier.score, self.task.contestant.navigation_task.scorecard.initial_score)

    def test_no_positions_gives_an_empty_result(self):
        result = run_flight(self.task.contestant, [])
        self.assertEqual(result.messages, [])
        self.assertEqual(result.score, self.task.contestant.navigation_task.scorecard.initial_score)
