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
    add_contestant,
    build_task,
    catalogue_turnpoint_feature,
    circle_flight,
    circle_route_geojson,
    contract_route_geojson,
    duration_flight,
    gate_crossings,
    gate_line_xy,
    generate_track,
    hunt_route_geojson,
    known_time_gate_feature,
    landing_area_feature,
    line_crossings,
    local_point,
    make_score_applier,
    precision_route_geojson,
    run_flight,
    runway_gate_feature,
    waypoint,
)
from display.utilities.cima_task_type_definitions import (
    CIRCLE,
    CONTRACT_NAVIGATION_TIME_CONTROLS,
    KNOWN_CIRCUIT,
    UNKNOWN_LEGS,
)
from display.utilities.coordinate_utilities import (
    Projector,
    calculate_bearing,
    calculate_distance_lat_lon,
    project_position_lat_lon,
)

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


def _features(geojson, feature_type):
    return [f for f in geojson["features"] if f["properties"].get("featureType") == feature_type]


def _distance_m(a, b):
    """The geodesic distance between two (lat, lon) points (the local projection is a little off at 60 degrees)."""
    return calculate_distance_lat_lon(a, b)


class DistanceAssertions:
    def assertDistance(self, a, b, expected):
        """The distance is `expected` metres within 0.6% (the position helpers and the distance function differ by
        0.25% at 60 degrees north)."""
        self.assertAlmostEqual(_distance_m(a, b), expected, delta=0.006 * expected)


class RouteHelpersTest(DistanceAssertions, SimpleTestCase):
    """The route GeoJSON helpers: what they put on the map."""

    def test_local_point_is_east_and_south_of_the_origin(self):
        origin = (60.0, 11.0)
        self.assertDistance(origin, local_point(origin, 3000.0, 0.0), 3000.0)
        east_south = local_point(origin, 3000.0, 4000.0)
        self.assertDistance(origin, east_south, 5000.0)
        self.assertLess(east_south[0], origin[0])  # south
        self.assertGreater(east_south[1], origin[1])  # east
        self.assertGreater(local_point(origin, 0.0, -1000.0)[0], origin[0])  # negative: north

    def test_hidden_gates_are_numbered_in_route_order_at_the_given_fractions_of_the_legs(self):
        geojson = precision_route_geojson(hidden_gates={0: [0.5], 1: [0.25, 0.75]})
        waypoints = _features(geojson, "route_waypoint")
        self.assertEqual([w["properties"]["name"] for w in waypoints], ["SP", "HG1", "TP1", "HG2", "HG3", "TP2", "FP"])
        self.assertEqual([w["properties"]["sequence"] for w in waypoints], list(range(7)))
        by_name = {w["properties"]["name"]: w for w in waypoints}
        self.assertEqual(by_name["HG1"]["properties"]["pointType"], "secret")

        def point(name):
            lon, lat = by_name[name]["geometry"]["coordinates"]
            return lat, lon

        self.assertDistance(point("SP"), point("HG1"), 3000.0)
        self.assertDistance(point("TP1"), point("HG2"), 1250.0)
        self.assertDistance(point("TP1"), point("HG3"), 3750.0)
        self.assertEqual(len(_features(geojson, "route_path")[0]["geometry"]["coordinates"]), 7)

    def test_hidden_gates_are_narrow_untimed_gates_unless_asked_otherwise(self):
        waypoints = _features(precision_route_geojson(hidden_gates={0: [0.5]}), "route_waypoint")
        hidden = next(w for w in waypoints if w["properties"]["name"] == "HG1")["properties"]
        self.assertEqual((hidden["width"], hidden["isTiming"]), (300.0, False))
        self.assertTrue(next(w for w in waypoints if w["properties"]["name"] == "TP1")["properties"]["isTiming"])
        timed = precision_route_geojson(hidden_gates={0: [0.5]}, hidden_timing=True, hidden_width_m=500.0)
        hidden = next(w for w in _features(timed, "route_waypoint") if w["properties"]["name"] == "HG1")["properties"]
        self.assertEqual((hidden["width"], hidden["isTiming"]), (500.0, True))

    def test_the_finish_point_starts_no_leg(self):
        with self.assertRaises(ValueError):
            precision_route_geojson(hidden_gates={3: [0.5]})

    def test_untimed_waypoints(self):
        waypoints = _features(precision_route_geojson(untimed=["TP1", "FP"]), "route_waypoint")
        self.assertEqual(
            {w["properties"]["name"]: w["properties"]["isTiming"] for w in waypoints},
            {
                "SP": True,
                "TP1": False,
                "TP2": True,
                "FP": False,
            },
        )

    def test_unknown_leg_points_have_extension_waypoints_that_hang_on_them(self):
        geojson = precision_route_geojson(unknown_legs={"TP1": [(30.0, 3000.0), (60.0, 2000.0)]})
        waypoints = {w["properties"]["name"]: w for w in _features(geojson, "route_waypoint")}
        self.assertEqual(waypoints["TP1"]["properties"]["pointType"], "ul")
        extensions = _features(geojson, "dummy_branch_waypoint")
        self.assertEqual([e["properties"]["name"] for e in extensions], ["EXT1", "EXT2"])
        self.assertEqual(
            {e["properties"]["triggerPointId"] for e in extensions}, {waypoints["TP1"]["properties"]["id"]}
        )
        self.assertEqual([e["properties"]["branchSequence"] for e in extensions], [0, 1])
        corner = tuple(reversed(waypoints["TP1"]["geometry"]["coordinates"]))
        first = tuple(reversed(extensions[0]["geometry"]["coordinates"]))
        self.assertDistance(corner, first, 3000.0)
        # The extension waypoints are not on the route backbone.
        self.assertNotIn("EXT1", waypoints)

    def test_contract_route_has_a_three_point_backbone_and_free_catalogue_points(self):
        geojson = contract_route_geojson(catalogue={"A": (2500.0, -1500.0), "B": (6000.0, 1500.0)})
        backbone = _features(geojson, "route_waypoint")
        self.assertEqual(
            [(w["properties"]["name"], w["properties"]["pointType"]) for w in backbone],
            [("SP", "sp"), ("MP", "tp"), ("FP", "fp")],
        )
        catalogue = _features(geojson, "catalogue_turnpoint")
        self.assertEqual([c["properties"]["name"] for c in catalogue], ["A", "B"])
        a = tuple(reversed(catalogue[0]["geometry"]["coordinates"]))
        self.assertDistance((60.0, 11.0), a, math.hypot(2500.0, 1500.0))
        self.assertGreater(a[0], 60.0)  # -1500 is north

    def test_hunt_route_has_no_backbone_and_three_timed_points(self):
        geojson = hunt_route_geojson(
            compulsory={"CP1": (0.0, 0.0), "CP2": (6000.0, 0.0), "CP3": (12000.0, 0.0)},
            catalogue={"A": (3000.0, -1500.0, 100)},
        )
        self.assertEqual(_features(geojson, "route_path"), [])
        self.assertEqual(_features(geojson, "route_waypoint"), [])
        self.assertEqual(
            [f["properties"]["name"] for f in _features(geojson, "known_time_gate")], ["CP1", "CP2", "CP3"]
        )
        (target,) = _features(geojson, "catalogue_turnpoint")
        self.assertEqual(target["properties"]["scoreValue"], 100)

    def test_catalogue_and_timed_point_features(self):
        point = (60.0, 11.0)
        self.assertNotIn("scoreValue", catalogue_turnpoint_feature("A", point)["properties"])
        feature = known_time_gate_feature("CP1", point, 926.0)
        self.assertEqual(
            (feature["properties"]["featureType"], feature["properties"]["width"]), ("known_time_gate", 926.0)
        )
        self.assertEqual(feature["geometry"]["coordinates"], [11.0, 60.0])

    def test_circle_route_has_the_four_markers_at_the_given_offsets_from_the_centre(self):
        centre = (59.9, 10.6)
        geojson = circle_route_geojson(centre, start_m=(-1000.0, 0.0), entry_m=(150.0, 0.0), exit_m=(0.0, 600.0))
        markers = {f["properties"]["name"]: f for f in geojson["features"]}
        self.assertEqual(
            {name: f["properties"]["featureType"] for name, f in markers.items()},
            {
                "SP": "circle_start_marker",
                "X": "circle_entry_marker",
                "CM": "circle_center_marker",
                "WP": "circle_exit_marker",
            },
        )
        self.assertEqual(
            {name: f["properties"]["pointType"] for name, f in markers.items()},
            {
                "SP": "circle_start",
                "X": "circle_entry",
                "CM": "circle_center",
                "WP": "circle_exit",
            },
        )

        def point(name):
            lon, lat = markers[name]["geometry"]["coordinates"]
            return lat, lon

        self.assertEqual(point("CM"), centre)
        self.assertDistance(centre, point("SP"), 1000.0)
        self.assertLess(point("SP")[1], centre[1])  # west
        self.assertDistance(centre, point("WP"), 600.0)
        self.assertGreater(point("WP")[0], centre[0])  # north

    def test_runway_gates_and_the_landing_area(self):
        start = (60.0, 11.0)
        takeoff = runway_gate_feature("takeoff", start, 0.0)
        landing = runway_gate_feature("landing", start, 18000.0, 1000.0)
        self.assertEqual(
            (takeoff["properties"]["featureType"], takeoff["properties"]["name"]), ("takeoff_gate", "Takeoff 1")
        )
        self.assertEqual(
            (landing["properties"]["featureType"], landing["properties"]["name"]), ("landing_gate", "Landing 1")
        )
        first, second = (tuple(reversed(c)) for c in landing["geometry"]["coordinates"])
        self.assertDistance(first, second, 2000.0)
        area = landing_area_feature(start, (17000.0, 19000.0), (-500.0, 500.0))
        self.assertEqual(area["properties"]["polygonType"], "duration_landing_area")
        ring = area["geometry"]["coordinates"][0]
        self.assertEqual((len(ring), ring[0] == ring[-1]), (5, True))
        self.assertDistance(tuple(reversed(ring[0])), tuple(reversed(ring[1])), 2000.0)


class GateCrossingsTest(SimpleTestCase):
    def setUp(self):
        self.waypoints, self.gate_times = _waypoints_and_times()
        self.projector = Projector(self.waypoints[0].latitude, self.waypoints[0].longitude)

    def crossings(self, *deviations, gates=None):
        track = generate_track(self.waypoints, self.gate_times, deviations=deviations)
        return gate_crossings(self.waypoints, self.gate_times, track, self.projector, gates)

    def test_every_gate_is_crossed_once_along_the_route_on_time(self):
        for name, found in self.crossings().items():
            with self.subTest(gate=name):
                self.assertEqual(len(found), 1)
                self.assertEqual(found[0].direction, 1)
                self.assertLess(abs(found[0].error_s), 1.0)

    def test_the_error_is_the_time_after_the_expected_time(self):
        found = self.crossings(TimeOffset("TP1", 20))["TP1"]
        self.assertAlmostEqual(found[0].error_s, 20.0, delta=1.0)
        self.assertEqual(found[0].time - self.gate_times["TP1"], datetime.timedelta(seconds=found[0].error_s))

    def test_a_double_crossing_gives_two_crossings_in_time_order(self):
        found = self.crossings(DoubleCrossing("TP1", gap_s=60.0))["TP1"]
        self.assertEqual([c.direction for c in found], [1, 1])
        self.assertLess(found[0].time, found[1].time)
        self.assertAlmostEqual((found[1].time - found[0].time).total_seconds(), 60.0, delta=1.5)

    def test_a_wrong_direction_crossing_has_direction_minus_one(self):
        found = self.crossings(WrongDirectionCrossing("TP1"))["TP1"]
        self.assertEqual([c.direction for c in found], [-1])

    def test_a_missed_gate_has_no_crossing(self):
        self.assertEqual(self.crossings(MissGate("TP1"))["TP1"], [])

    def test_only_the_wanted_gates_are_reported(self):
        self.assertEqual(sorted(self.crossings(gates=["TP2", "FP"])), ["FP", "TP2"])

    def test_gates_without_an_expected_time_are_left_out(self):
        gate_times = {name: time for name, time in self.gate_times.items() if name != "TP1"}
        track = generate_track(self.waypoints, self.gate_times)
        self.assertNotIn("TP1", gate_crossings(self.waypoints, gate_times, track, self.projector))


class DurationFlightTest(DistanceAssertions, SimpleTestCase):
    START = (60.0, 11.0)

    def flight(self, **options):
        landing = local_point(self.START, 18000.0, 0.0)
        return duration_flight(self.START, landing, takeoff_time=START, airborne_s=1800.0, **options)

    def test_it_stands_still_flies_and_stands_still_again(self):
        track = self.flight(hold_before_s=90.0, hold_after_s=100.0)
        before = [p for p in track if p.time < START]
        flying = [p for p in track if START <= p.time <= START + datetime.timedelta(seconds=1800)]
        after = [p for p in track if p.time > START + datetime.timedelta(seconds=1800)]
        self.assertEqual({p.speed for p in before}, {0.0})
        self.assertEqual({p.speed for p in after}, {0.0})
        self.assertAlmostEqual(len(before), 90, delta=1)
        self.assertAlmostEqual(len(after), 100, delta=1)
        # 18 km in 1800 s is 10 m/s, 19.4 knots.
        self.assertTrue(all(abs(p.speed - 19.44) < 0.1 for p in flying[1:-1]))

    def test_it_takes_off_at_the_takeoff_time_and_touches_down_after_the_airborne_time(self):
        track = self.flight()
        first_moving = next(p for p in track if p.speed > 1.0)
        self.assertAlmostEqual((first_moving.time - START).total_seconds(), 0.0, delta=1.0)
        last_moving = [p for p in track if p.speed > 1.0][-1]
        self.assertAlmostEqual((last_moving.time - START).total_seconds(), 1800.0, delta=1.0)
        self.assertDistance(self.START, (last_moving.latitude, last_moving.longitude), 18000.0)


class WizardTaskHelpersTest(TestCase):
    """The additions to build_task: several tasks and pilots in one test, declarations, whole-second times."""

    def test_two_tasks_can_be_built_in_one_test(self):
        first = build_task(precision_route_geojson())
        second = build_task(precision_route_geojson())
        self.assertNotEqual(first.contest.name, second.contest.name)
        self.assertNotEqual(first.contestant.team_id, second.contestant.team_id)

    def test_another_pilot_shares_the_task_and_gets_a_track_of_their_own(self):
        task = build_task(precision_route_geojson())
        other = add_contestant(task)
        self.assertEqual(other.navigation_task, task.navigation_task)
        self.assertEqual(other.contestant.contestant_number, 2)
        self.assertNotEqual(other.contestant.pk, task.contestant.pk)
        self.assertNotEqual(other.contestant.tracker_device_id, task.contestant.tracker_device_id)
        third = add_contestant(task)
        self.assertEqual(third.contestant.contestant_number, 3)
        self.assertEqual(task.navigation_task.contestant_set.count(), 3)
        result = other.run(other.generate_track())
        self.assertEqual(result.missed_gates, [])

    def test_declare_compiles_a_declaration_for_the_pilot(self):
        task = build_task(
            precision_route_geojson(hidden_gates={1: [0.5]}),
            task_subtype=KNOWN_CIRCUIT,
            scorecard_shortcut="CIMA Precision",
        )
        declared_time = task.gate_times["TP2"] + datetime.timedelta(seconds=40)
        declared = task.declare({"turnpoint_time_overrides": {"TP2": declared_time.isoformat()}})
        self.assertEqual(declared.gate_times["TP2"], declared_time)
        self.assertEqual(declared.contestant.pk, task.contestant.pk)
        self.assertEqual(task.gate_times["TP2"], declared_time - datetime.timedelta(seconds=40))

    def test_whole_second_gate_times(self):
        task = build_task(
            precision_route_geojson(hidden_gates={1: [0.5]}),
            task_subtype=KNOWN_CIRCUIT,
            scorecard_shortcut="CIMA Precision",
            whole_second_gate_times=True,
        )
        self.assertTrue(all(time.microsecond == 0 for time in task.gate_times.values()))
        declared = task.declare(
            {"turnpoint_time_overrides": {"TP2": (task.gate_times["TP2"] + datetime.timedelta(seconds=36)).isoformat()}}
        )
        self.assertTrue(all(time.microsecond == 0 for time in declared.gate_times.values()))
        rough = build_task(precision_route_geojson(), task_subtype=KNOWN_CIRCUIT, scorecard_shortcut="CIMA Precision")
        self.assertTrue(any(time.microsecond for time in rough.gate_times.values()))

    def test_an_adaptive_start_pilot_has_gate_times_counted_from_midnight_until_the_start(self):
        task = build_task(
            contract_route_geojson(catalogue={"A": (2500.0, -1500.0)}),
            task_subtype=CONTRACT_NAVIGATION_TIME_CONTROLS,
            scorecard_shortcut="CIMA Precision",
            adaptive_start=True,
        ).declare({"declared_sequence": ["A", "MP", "FP"], "declared_t_seconds": 240})
        self.assertTrue(task.contestant.adaptive_start)
        self.assertEqual(task.gate_times["SP"].hour, 0)
        self.assertEqual(task.gate_times["MP"] - task.gate_times["SP"], datetime.timedelta(seconds=240))

    def test_a_circle_task_and_an_unknown_legs_task_build_from_the_helpers(self):
        circle = build_task(
            circle_route_geojson((59.9, 10.6)), task_subtype=CIRCLE, scorecard_shortcut="CIMA Precision"
        )
        self.assertEqual([w.name for w in circle.effective_waypoints], ["SP", "X", "CM", "WP"])
        unknown = build_task(
            precision_route_geojson(unknown_legs={"TP1": [(30.0, 3000.0)]}),
            task_subtype=UNKNOWN_LEGS,
            scorecard_shortcut="CIMA Precision",
        )
        self.assertTrue(unknown.contestant.contestanttaskconfiguration.is_valid)
        self.assertEqual([w.name for w in unknown.effective_waypoints], ["SP", "TP1", "TP2", "FP"])
