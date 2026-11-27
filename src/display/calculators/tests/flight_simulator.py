"""Synthetic flight simulator and scoring runner for backend scoring tests.

Three parts, each usable on its own:

1. Track generation. `generate_track` turns the contestant's effective waypoints and gate times into 1 Hz positions that
   follow the legs and cross every gate at its expected time, with a lead-in before the first gate and a lead-out after
   the last one. Small, composable `Deviation` objects (time offset, missed gate, skipped gate, orbit, reversal, double
   crossing, ...) change the flight; `circle_flight` builds the 2.A7 circle manoeuvre.
2. Task building. `build_task` creates a task the way the wizard does (EditableRoute -> Route -> NavigationTask ->
   Contestant -> ContestantTaskCompiler); `precision_route_geojson` gives a simple route to fly.
3. Scoring. `run_flight` feeds positions through the real calculators (`calculator_factory`, live_processing=False) and
   applies every emitted score message with the real `ContestantProcessor.update_score_from_thread`, so the result
   holds both the messages and the final score.

Geometry is done in a local metric frame (east x, north y) from a `Projector`; positive lateral offsets are to the
right of the direction of flight. Samples are taken half a second off the whole-second grid by default so that no
sample lies exactly on a gate line (gate times are whole seconds), which would make the crossing ambiguous.
"""

import bisect
import datetime
import math
import uuid
from dataclasses import dataclass, field, replace
from queue import Queue
from types import SimpleNamespace
from typing import Callable, Iterable, Optional, Sequence
from unittest.mock import patch

from display.calculators.calculator_factory import calculator_factory
from display.calculators.contestant_processor import ContestantProcessor, ScoreAccumulator
from display.calculators.gate_calculator import GateCalculator
from display.calculators.update_score_message import UpdateScoreMessage
from display.models.contestant_utility_models import ContestantReceivedPosition
from display.utilities.coordinate_utilities import Projector, project_position_lat_lon

KNOT_IN_MS = 1852.0 / 3600.0
NAUTICAL_MILE_IN_M = 1852.0
UTC = datetime.timezone.utc


# ---------------------------------------------------------------------------------------------------------------------
# Small geometry helpers (metric frame: x east, y north)
# ---------------------------------------------------------------------------------------------------------------------


def _unit(dx: float, dy: float) -> tuple[float, float]:
    length = math.hypot(dx, dy)
    if length == 0:
        raise ValueError("Zero-length direction")
    return dx / length, dy / length


def _right(direction: tuple[float, float]) -> tuple[float, float]:
    """The unit vector to the right of a direction of flight."""
    return direction[1], -direction[0]


def _bearing_deg(dx: float, dy: float) -> float:
    return math.degrees(math.atan2(dx, dy)) % 360.0


def _signed_bearing_change(first: float, second: float) -> float:
    return (second - first + 540.0) % 360.0 - 180.0


def _xy_to_lat_lon(projector: Projector, x: float, y: float) -> tuple[float, float]:
    lon, lat = projector.from_projection.transform(x, y)
    return lat, lon


# ---------------------------------------------------------------------------------------------------------------------
# Positions and altitude
# ---------------------------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class SimPosition:
    """One generated position report. Speed is in knots, course in degrees true."""

    latitude: float
    longitude: float
    time: datetime.datetime
    altitude: float
    speed: float
    course: float

    def to_received_position(self, contestant=None) -> ContestantReceivedPosition:
        """An unsaved ContestantReceivedPosition, as the position processor hands to the orchestrator.

        projected_x/projected_y stay None: the orchestrator projects them itself when it has a projector.
        """
        return ContestantReceivedPosition(
            contestant=contestant,
            time=self.time,
            latitude=self.latitude,
            longitude=self.longitude,
            altitude=self.altitude,
            speed=self.speed,
            course=self.course,
        )


@dataclass(frozen=True)
class AltitudeSegment:
    """Fly at `altitude` from `start` until `end` (forever when end is None, i.e. a step)."""

    start: datetime.datetime
    end: Optional[datetime.datetime]
    altitude: float


@dataclass(frozen=True)
class AltitudeProfile:
    """Altitude as a function of time: a base altitude with optional steps and excursions (later ones win)."""

    base: float = 1000.0
    segments: tuple[AltitudeSegment, ...] = ()

    def at(self, time: datetime.datetime) -> float:
        altitude = self.base
        for segment in self.segments:
            if time >= segment.start and (segment.end is None or time < segment.end):
                altitude = segment.altitude
        return altitude


def _altitude_function(altitude) -> Callable[[datetime.datetime], float]:
    if isinstance(altitude, AltitudeProfile):
        return altitude.at
    if callable(altitude):
        return altitude
    return lambda _time: float(altitude)


# ---------------------------------------------------------------------------------------------------------------------
# The plan: timed knots joined by straight segments
# ---------------------------------------------------------------------------------------------------------------------


@dataclass
class Knot:
    """A point the aircraft passes at time `t` (seconds from the plan's reference time). Named knots are gates."""

    x: float
    y: float
    t: float
    name: Optional[str] = None
    width_m: float = 0.0


class Plan:
    """The flight as an ordered list of knots, flown at constant speed along straight segments between them."""

    def __init__(self, knots: list[Knot], projector: Projector, reference_time: datetime.datetime):
        self.knots = knots
        self.projector = projector
        self.reference_time = reference_time

    # -- lookups --------------------------------------------------------------------------------------------------

    def index_of(self, name: str) -> int:
        for index, knot in enumerate(self.knots):
            if knot.name == name:
                return index
        raise ValueError(f"Gate {name!r} is not in the plan")

    def next_named(self, index: int) -> int:
        for candidate in range(index + 1, len(self.knots)):
            if self.knots[candidate].name is not None:
                return candidate
        return len(self.knots) - 1

    def segment_direction(self, index: int) -> tuple[float, float]:
        """Unit direction of the segment starting at knot `index`."""
        start, end = self.knots[index], self.knots[index + 1]
        return _unit(end.x - start.x, end.y - start.y)

    def segment_speed(self, index: int) -> float:
        """Speed in m/s along the segment starting at knot `index`."""
        start, end = self.knots[index], self.knots[index + 1]
        return math.hypot(end.x - start.x, end.y - start.y) / (end.t - start.t)

    def tangent(self, index: int) -> tuple[float, float]:
        """Unit direction of flight through a knot: the bisector of the incoming and outgoing segments."""
        directions = []
        if index > 0:
            directions.append(self.segment_direction(index - 1))
        if index < len(self.knots) - 1:
            directions.append(self.segment_direction(index))
        return _unit(sum(d[0] for d in directions), sum(d[1] for d in directions))

    # -- editing --------------------------------------------------------------------------------------------------

    def insert_knot_at(self, t: float) -> int:
        """Make sure there is a knot at time `t` (interpolated on the segment containing it) and return its index."""
        times = [knot.t for knot in self.knots]
        if not times[0] <= t <= times[-1]:
            raise ValueError(f"Time {t} is outside the flight")
        index = min(bisect.bisect_right(times, t) - 1, len(self.knots) - 2)
        if abs(self.knots[index].t - t) < 1e-9:
            return index
        if abs(self.knots[index + 1].t - t) < 1e-9:
            return index + 1
        start, end = self.knots[index], self.knots[index + 1]
        fraction = (t - start.t) / (end.t - start.t)
        self.knots.insert(
            index + 1, Knot(start.x + fraction * (end.x - start.x), start.y + fraction * (end.y - start.y), t)
        )
        return index + 1

    def insert_path(
        self,
        after_index: int,
        points: Sequence[tuple[float, float]],
        t_start: float,
        t_end: float,
        to: Optional[tuple[float, float]] = None,
    ):
        """Insert `points` after knot `after_index`, timed by distance travelled from `t_start` to `t_end`.

        The path runs from the knot at `after_index` through `points`. Without `to` the last point is reached at
        `t_end`; with `to` (a point that already is a knot, reached at `t_end`) the path continues on to it.
        """
        origin = self.knots[after_index]
        chain = [(origin.x, origin.y), *points, *([to] if to else [])]
        lengths = [math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(chain, chain[1:])]
        total = sum(lengths)
        if total == 0:
            raise ValueError("Path has no length")
        travelled = 0.0
        new_knots = []
        for point, length in zip(points, lengths):
            travelled += length
            new_knots.append(Knot(point[0], point[1], t_start + (t_end - t_start) * travelled / total))
        self.knots[after_index + 1 : after_index + 1] = new_knots

    def validate(self):
        """Times must strictly increase: a deviation that does not fit between its neighbours is a ValueError."""
        for first, second in zip(self.knots, self.knots[1:]):
            if second.t <= first.t:
                raise ValueError(
                    f"Deviations do not fit: {first.name or 'point'} at {first.t:.1f}s is followed by "
                    f"{second.name or 'point'} at {second.t:.1f}s"
                )


# ---------------------------------------------------------------------------------------------------------------------
# Deviations
# ---------------------------------------------------------------------------------------------------------------------


class Deviation:
    """A change to the flight plan. Deviations are applied in `phase` order (stable within a phase)."""

    phase = 50

    def apply(self, plan: Plan):  # pragma: no cover - interface
        raise NotImplementedError


@dataclass
class VisitOrder(Deviation):
    """Visit the named gates in `order` instead of the route order. The gates keep their time slots in sequence."""

    order: Sequence[str]
    phase = 10

    def apply(self, plan: Plan):
        indices = sorted(plan.index_of(name) for name in self.order)
        slots = [plan.knots[index].t for index in indices]
        sources = {name: plan.knots[plan.index_of(name)] for name in self.order}
        for index, slot, name in zip(indices, slots, self.order):
            plan.knots[index] = replace(sources[name], t=slot)
        plan.validate()


@dataclass
class SkipGate(Deviation):
    """Fly directly from the previous gate to the next, never visiting `gate`."""

    gate: str
    phase = 20

    def apply(self, plan: Plan):
        del plan.knots[plan.index_of(self.gate)]
        plan.validate()


@dataclass
class LateralOffset(Deviation):
    """Pass `gate` `metres` to the right of the gate centre (negative: to the left)."""

    gate: str
    metres: float
    phase = 30

    def apply(self, plan: Plan):
        index = plan.index_of(self.gate)
        normal = _right(plan.tangent(index))
        plan.knots[index].x += normal[0] * self.metres
        plan.knots[index].y += normal[1] * self.metres


@dataclass
class MissGate(Deviation):
    """Pass `gate` outside the end of its gate line, `margin_m` beyond half the gate width."""

    gate: str
    margin_m: float = 150.0
    side: str = "right"
    phase = 30

    def apply(self, plan: Plan):
        index = plan.index_of(self.gate)
        distance = plan.knots[index].width_m / 2.0 + self.margin_m
        LateralOffset(self.gate, distance if self.side == "right" else -distance).apply(plan)


@dataclass
class TimeOffset(Deviation):
    """Cross `gate` `seconds` late (negative: early). Only that gate moves; the legs on each side are stretched."""

    gate: str
    seconds: float
    phase = 40

    def apply(self, plan: Plan):
        plan.knots[plan.index_of(self.gate)].t += self.seconds
        plan.validate()


def _point_on_leg(plan: Plan, leg: str, fraction: float) -> tuple[int, float]:
    """Insert a knot at `fraction` (by time) of the leg that starts at gate `leg`; return its index and time."""
    start = plan.index_of(leg)
    end = plan.next_named(start)
    t = plan.knots[start].t + fraction * (plan.knots[end].t - plan.knots[start].t)
    return plan.insert_knot_at(t), t


@dataclass
class Orbit(Deviation):
    """A full 360 degree circle of `radius_m` flown at `fraction` of the leg that starts at gate `leg`."""

    leg: str
    fraction: float = 0.5
    radius_m: float = 500.0
    direction: str = "left"
    speed_kt: Optional[float] = None
    step_deg: float = 5.0

    def apply(self, plan: Plan):
        index, t = _point_on_leg(plan, self.leg, self.fraction)
        heading = plan.segment_direction(index)
        speed = self.speed_kt * KNOT_IN_MS if self.speed_kt else plan.segment_speed(index)
        sign = 1.0 if self.direction == "left" else -1.0
        normal = (-heading[1], heading[0]) if sign > 0 else _right(heading)
        origin = plan.knots[index]
        centre = (origin.x + normal[0] * self.radius_m, origin.y + normal[1] * self.radius_m)
        start_angle = math.atan2(origin.y - centre[1], origin.x - centre[0])
        steps = round(360.0 / self.step_deg)
        points = [
            (
                centre[0] + self.radius_m * math.cos(start_angle + sign * 2 * math.pi * k / steps),
                centre[1] + self.radius_m * math.sin(start_angle + sign * 2 * math.pi * k / steps),
            )
            for k in range(1, steps + 1)
        ]
        plan.insert_path(index, points, t, t + 2 * math.pi * self.radius_m / speed)
        plan.validate()


@dataclass
class Reverse(Deviation):
    """Fly backwards along the leg that starts at gate `leg` for `seconds`, then turn round and resume."""

    leg: str
    seconds: float
    fraction: float = 0.5

    def apply(self, plan: Plan):
        index, t = _point_on_leg(plan, self.leg, self.fraction)
        heading = plan.segment_direction(index)
        distance = plan.segment_speed(index) * self.seconds
        origin = plan.knots[index]
        back = (origin.x - heading[0] * distance, origin.y - heading[1] * distance)
        plan.insert_path(index, [back, (origin.x, origin.y)], t, t + 2 * self.seconds)
        plan.validate()


@dataclass
class ProcedureTurn(Deviation):
    """Fly a procedure turn at `gate`: carry on `overshoot_m` past it, turn the long way round and rejoin the route.

    The loop turns the opposite way to the route's own turn at the gate (a 160 degree right turn becomes a 200 degree
    left turn), with a circle of `radius_m`, and ends on the heading that points at the next gate. `direction` forces
    "left" or "right" instead (which makes it a wrong-way procedure turn). The path is flown at the leg's speed, so
    it has to fit before the next gate time.
    """

    gate: str
    radius_m: float = 300.0
    overshoot_m: float = 600.0
    direction: Optional[str] = None
    step_deg: float = 5.0

    def apply(self, plan: Plan):
        index = plan.index_of(self.gate)
        if index == 0 or index == len(plan.knots) - 1:
            raise ValueError("Gate needs a neighbour on each side")
        knot, following = plan.knots[index], plan.knots[index + 1]
        heading_in = plan.segment_direction(index - 1)
        route_turn = _signed_bearing_change(
            _bearing_deg(*heading_in), _bearing_deg(*plan.segment_direction(index))
        )  # positive: right
        if self.direction:
            sign = 1.0 if self.direction == "right" else -1.0
        else:
            sign = -1.0 if route_turn > 0 else 1.0
        start = (knot.x + heading_in[0] * self.overshoot_m, knot.y + heading_in[1] * self.overshoot_m)
        normal = _right(heading_in) if sign > 0 else (-_right(heading_in)[0], -_right(heading_in)[1])
        centre = (start[0] + normal[0] * self.radius_m, start[1] + normal[1] * self.radius_m)
        start_angle = math.atan2(start[1] - centre[1], start[0] - centre[0])

        def point_at(angle_deg: float) -> tuple[float, float]:
            angle = start_angle - sign * math.radians(angle_deg)
            return centre[0] + self.radius_m * math.cos(angle), centre[1] + self.radius_m * math.sin(angle)

        heading_start = _bearing_deg(heading_in[0], heading_in[1])

        def aims_at_next_gate(angle_deg: float) -> bool:
            """True once the turn has swept round at least as far as the bearing of the next gate from here."""
            point = point_at(angle_deg)
            target = _bearing_deg(following.x - point[0], following.y - point[1])
            return angle_deg >= (sign * (target - heading_start)) % 360.0

        finish = next((a for a in range(1, 721) if aims_at_next_gate(a)), None)
        if finish is None:
            raise ValueError("The procedure turn does not come round to the next gate")
        steps = int(finish // self.step_deg)
        points = [start, *(point_at(k * self.step_deg) for k in range(1, steps + 1))]
        if finish - steps * self.step_deg > 1e-6:
            points.append(point_at(finish))
        length = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip([(knot.x, knot.y), *points], points))
        plan.insert_path(index, points, knot.t, knot.t + length / plan.segment_speed(index))
        plan.validate()


@dataclass
class DoubleCrossing(Deviation):
    """Cross `gate`, loop back round the end of its gate line and cross it again in the same direction.

    The second crossing is `gap_s` after the first. The loop stays `margin_m` beyond the gate line's end.
    """

    gate: str
    gap_s: float = 60.0
    distance_m: float = 300.0
    margin_m: float = 300.0

    def apply(self, plan: Plan):
        index = plan.index_of(self.gate)
        knot = plan.knots[index]
        forward = plan.tangent(index)
        right = _right(forward)
        side = knot.width_m / 2.0 + self.margin_m
        d = self.distance_m

        def at(along: float, across: float):
            return knot.x + forward[0] * along + right[0] * across, knot.y + forward[1] * along + right[1] * across

        loop = [at(d, 0), at(d, side), at(-d, side), at(-d, 0), at(0, 0)]
        plan.insert_path(index, loop, knot.t, knot.t + self.gap_s)
        plan.validate()


@dataclass
class WrongDirectionCrossing(Deviation):
    """Cross `gate` exactly once, flying against the direction of the route.

    The aircraft goes round the end of the gate line to the far side, crosses the gate backwards, and goes round the
    end of the line again to carry on, so the gate line itself is crossed once, in the wrong direction.
    """

    gate: str
    distance_m: float = 300.0
    margin_m: float = 300.0

    def apply(self, plan: Plan):
        index = plan.index_of(self.gate)
        if index == 0 or index == len(plan.knots) - 1:
            raise ValueError("Gate needs a neighbour on each side")
        knot = plan.knots[index]
        forward = plan.tangent(index)
        right = _right(forward)
        side = knot.width_m / 2.0 + self.margin_m
        d = self.distance_m

        def at(along: float, across: float):
            return knot.x + forward[0] * along + right[0] * across, knot.y + forward[1] * along + right[1] * across

        before = [at(-d, side), at(d, side), at(d, 0)]
        after = [at(-d, 0), at(-d, side), at(d, side)]
        previous, following = plan.knots[index - 1], plan.knots[index + 1]
        # After first so the indices of the earlier insertion stay valid.
        plan.insert_path(index, after, knot.t, following.t, to=(following.x, following.y))
        plan.insert_path(index - 1, before, previous.t, knot.t, to=(knot.x, knot.y))
        plan.validate()


@dataclass
class SidewaysExcursion(Deviation):
    """Leave the straight leg line sideways by `distance_m` for `duration_s` and return, on the leg from `leg`.

    The aircraft keeps its progress along the leg; it moves out over `ramp_s`, holds, and moves back over `ramp_s`.
    """

    leg: str
    distance_m: float
    duration_s: float
    fraction: float = 0.5
    ramp_s: float = 10.0
    side: str = "right"

    def apply(self, plan: Plan):
        start_index = plan.index_of(self.leg)
        end_index = plan.next_named(start_index)
        t0 = plan.knots[start_index].t + self.fraction * (plan.knots[end_index].t - plan.knots[start_index].t)
        times = [t0, t0 + self.ramp_s, t0 + self.ramp_s + self.duration_s, t0 + 2 * self.ramp_s + self.duration_s]
        if times[-1] > plan.knots[end_index].t:
            raise ValueError("Excursion does not fit on the leg")
        if any(t0 < knot.t < times[-1] for knot in plan.knots):
            raise ValueError("Excursion overlaps another deviation")
        indices = [plan.insert_knot_at(t) for t in times]
        heading = plan.segment_direction(indices[0])
        normal = _right(heading) if self.side == "right" else (-_right(heading)[0], -_right(heading)[1])
        for index in indices[1:3]:
            plan.knots[index].x += normal[0] * self.distance_m
            plan.knots[index].y += normal[1] * self.distance_m
        plan.validate()


# ---------------------------------------------------------------------------------------------------------------------
# Track generation
# ---------------------------------------------------------------------------------------------------------------------


def build_plan(
    waypoints: Sequence,
    gate_times: dict,
    projector: Projector,
    lead_in_s: float = 60.0,
    lead_out_s: float = 60.0,
) -> Plan:
    """The undisturbed flight: lead-in, every waypoint at its gate time, lead-out.

    Waypoints without a gate time (e.g. curve points) are timed by distance between their timed neighbours.
    """
    if len(waypoints) < 2:
        raise ValueError("At least two waypoints are needed")
    xy = []
    for waypoint in waypoints:
        point = projector.project_point(waypoint.latitude, waypoint.longitude)
        xy.append((point.projected_x, point.projected_y))
    cumulative = [0.0]
    for a, b in zip(xy, xy[1:]):
        cumulative.append(cumulative[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    timed = [index for index, waypoint in enumerate(waypoints) if waypoint.name in gate_times]
    if len(timed) < 2:
        raise ValueError("At least two waypoints need a gate time")
    reference_time = gate_times[waypoints[timed[0]].name]
    seconds = {index: (gate_times[waypoints[index].name] - reference_time).total_seconds() for index in timed}
    average_speed = (cumulative[timed[-1]] - cumulative[timed[0]]) / (seconds[timed[-1]] - seconds[timed[0]])
    times = []
    for index in range(len(waypoints)):
        if index in seconds:
            times.append(seconds[index])
            continue
        before = [i for i in timed if i < index]
        after = [i for i in timed if i > index]
        if before and after:
            a, b = before[-1], after[0]
            fraction = (cumulative[index] - cumulative[a]) / (cumulative[b] - cumulative[a])
            times.append(seconds[a] + fraction * (seconds[b] - seconds[a]))
        elif before:
            times.append(seconds[before[-1]] + (cumulative[index] - cumulative[before[-1]]) / average_speed)
        else:
            times.append(seconds[after[0]] - (cumulative[after[0]] - cumulative[index]) / average_speed)
    knots = [
        Knot(point[0], point[1], t, waypoint.name, float(getattr(waypoint, "width", 0) or 0) * NAUTICAL_MILE_IN_M)
        for waypoint, point, t in zip(waypoints, xy, times)
    ]
    for first, second in zip(knots, knots[1:]):
        if second.t <= first.t:
            raise ValueError(f"Gate times are not increasing between {first.name} and {second.name}")
    first_direction = _unit(knots[1].x - knots[0].x, knots[1].y - knots[0].y)
    first_speed = math.hypot(knots[1].x - knots[0].x, knots[1].y - knots[0].y) / (knots[1].t - knots[0].t)
    last_direction = _unit(knots[-1].x - knots[-2].x, knots[-1].y - knots[-2].y)
    last_speed = math.hypot(knots[-1].x - knots[-2].x, knots[-1].y - knots[-2].y) / (knots[-1].t - knots[-2].t)
    lead_in = Knot(
        knots[0].x - first_direction[0] * first_speed * lead_in_s,
        knots[0].y - first_direction[1] * first_speed * lead_in_s,
        knots[0].t - lead_in_s,
    )
    lead_out = Knot(
        knots[-1].x + last_direction[0] * last_speed * lead_out_s,
        knots[-1].y + last_direction[1] * last_speed * lead_out_s,
        knots[-1].t + lead_out_s,
    )
    return Plan([lead_in, *knots, lead_out], projector, reference_time)


def sample_plan(
    plan: Plan,
    altitude=1000.0,
    interval_s: float = 1.0,
    sample_offset_s: float = 0.5,
) -> list[SimPosition]:
    """Sample the plan at a fixed rate. Sample times are `sample_offset_s + n * interval_s` from the reference time."""
    altitude_at = _altitude_function(altitude)
    knots = plan.knots
    times = [knot.t for knot in knots]
    n = math.ceil((times[0] - sample_offset_s) / interval_s - 1e-9)
    positions = []
    while True:
        t = sample_offset_s + n * interval_s
        n += 1
        if t > times[-1] + 1e-9:
            break
        index = min(max(bisect.bisect_right(times, t) - 1, 0), len(knots) - 2)
        start, end = knots[index], knots[index + 1]
        fraction = (t - start.t) / (end.t - start.t)
        x = start.x + fraction * (end.x - start.x)
        y = start.y + fraction * (end.y - start.y)
        length = math.hypot(end.x - start.x, end.y - start.y)
        lat, lon = _xy_to_lat_lon(plan.projector, x, y)
        time = plan.reference_time + datetime.timedelta(seconds=t)
        positions.append(
            SimPosition(
                latitude=lat,
                longitude=lon,
                time=time,
                altitude=float(altitude_at(time)),
                speed=length / (end.t - start.t) / KNOT_IN_MS,
                course=_bearing_deg(end.x - start.x, end.y - start.y) if length > 0 else 0.0,
            )
        )
    return positions


def generate_track(
    waypoints: Sequence,
    gate_times: dict,
    *,
    deviations: Iterable[Deviation] = (),
    altitude=1000.0,
    projector: Optional[Projector] = None,
    lead_in_s: float = 60.0,
    lead_out_s: float = 60.0,
    interval_s: float = 1.0,
    sample_offset_s: float = 0.5,
) -> list[SimPosition]:
    """Generate a flight over `waypoints` that crosses each gate at `gate_times[name]`, with `deviations` applied.

    `waypoints` need name, latitude, longitude and (optionally) width in nautical miles - e.g. the result of
    `get_effective_route_waypoints`. `altitude` is a number, an `AltitudeProfile` or a function of the time.
    """
    projector = projector or Projector(waypoints[0].latitude, waypoints[0].longitude)
    plan = build_plan(waypoints, gate_times, projector, lead_in_s, lead_out_s)
    for deviation in sorted(deviations, key=lambda item: item.phase):
        deviation.apply(plan)
    plan.validate()
    return sample_plan(plan, altitude, interval_s, sample_offset_s)


# ---------------------------------------------------------------------------------------------------------------------
# Circle flight (task 2.A7)
# ---------------------------------------------------------------------------------------------------------------------


def circle_flight(
    start_point: tuple[float, float],
    centre: tuple[float, float],
    exit_point: tuple[float, float],
    *,
    start_time: datetime.datetime,
    direction: str = "left",
    radius_m=500.0,
    sweep_deg: float = 810.0,
    speed_kt: float = 75.0,
    lead_in_m: float = 1500.0,
    lead_out_m: float = 1500.0,
    altitude=1000.0,
    interval_s: float = 1.0,
    sample_offset_s: float = 0.5,
) -> list[SimPosition]:
    """Fly over `start_point` and `centre` in a straight line, circle the centre and leave towards `exit_point`.

    Points are (latitude, longitude). The aircraft continues past the centre to the circle's edge (the entry point on
    the line start point -> centre), then turns `direction` ("left" is counter-clockwise, "right" clockwise) through
    `sweep_deg`. `radius_m` is a number or a function of the angle swept so far in degrees. It then flies straight to
    `exit_point` and `lead_out_m` beyond. `start_time` is the time at the start point. Positions are generated in a
    projection centred on the circle centre.
    """
    radius = radius_m if callable(radius_m) else (lambda _angle: float(radius_m))
    projector = Projector(*centre)

    def to_xy(point):
        projected = projector.project_point(*point)
        return projected.projected_x, projected.projected_y

    start_xy, exit_xy = to_xy(start_point), to_xy(exit_point)
    approach = _unit(-start_xy[0], -start_xy[1])  # the centre is at the origin
    entry_bearing = _bearing_deg(*approach)
    sign = -1.0 if direction == "left" else 1.0
    points = [
        (start_xy[0] - approach[0] * lead_in_m, start_xy[1] - approach[1] * lead_in_m),
        start_xy,
        (0.0, 0.0),
    ]
    steps = max(1, math.ceil(sweep_deg))
    for k in range(steps + 1):
        angle = sweep_deg * k / steps
        bearing = math.radians(entry_bearing + sign * angle)
        r = radius(angle)
        points.append((r * math.sin(bearing), r * math.cos(bearing)))
    out = _unit(exit_xy[0] - points[-1][0], exit_xy[1] - points[-1][1])
    points.extend([exit_xy, (exit_xy[0] + out[0] * lead_out_m, exit_xy[1] + out[1] * lead_out_m)])
    deduplicated = [points[0]]
    for point in points[1:]:
        if math.hypot(point[0] - deduplicated[-1][0], point[1] - deduplicated[-1][1]) > 1e-6:
            deduplicated.append(point)
    speed = speed_kt * KNOT_IN_MS
    knots = []
    travelled = 0.0
    start_distance = None
    for index, point in enumerate(deduplicated):
        if index:
            travelled += math.hypot(point[0] - deduplicated[index - 1][0], point[1] - deduplicated[index - 1][1])
        if point == start_xy:
            start_distance = travelled
        knots.append(Knot(point[0], point[1], travelled / speed))
    shift = (start_distance or 0.0) / speed
    for knot in knots:
        knot.t -= shift
    plan = Plan(knots, projector, start_time)
    return sample_plan(plan, altitude, interval_s, sample_offset_s)


# ---------------------------------------------------------------------------------------------------------------------
# Duration flight (task 2.B3)
# ---------------------------------------------------------------------------------------------------------------------


def duration_flight(
    start_point: tuple[float, float],
    landing_point: tuple[float, float],
    *,
    takeoff_time: datetime.datetime,
    airborne_s: float,
    hold_before_s: float = 90.0,
    hold_after_s: float = 90.0,
    altitude=1000.0,
    interval_s: float = 1.0,
    sample_offset_s: float = 0.5,
) -> list[SimPosition]:
    """A flight that stands still at `start_point` for `hold_before_s`, takes off at `takeoff_time`, flies in a straight
    line at constant speed to `landing_point`, touches down `airborne_s` later and stands still for `hold_after_s`.

    The standstills are what a speed-based take-off and landing inference works from; the flight over a gate crosses
    it at the speed that follows from the distance and the airborne time."""
    projector = Projector(*start_point)
    landing = projector.project_point(*landing_point)
    end = (landing.projected_x, landing.projected_y)
    knots = [
        Knot(0.0, 0.0, -hold_before_s),
        Knot(0.0, 0.0, 0.0),
        Knot(end[0], end[1], airborne_s),
        Knot(end[0], end[1], airborne_s + hold_after_s),
    ]
    return sample_plan(Plan(knots, projector, takeoff_time), altitude, interval_s, sample_offset_s)


# ---------------------------------------------------------------------------------------------------------------------
# Measuring a generated track
# ---------------------------------------------------------------------------------------------------------------------


def gate_line_xy(
    waypoints: Sequence, index: int, half_width_m: float, projector: Projector
) -> tuple[tuple[float, float], tuple[float, float]]:
    """A gate line through waypoint `index`, perpendicular to the bisector of the legs, `half_width_m` each side.

    This is an independent re-derivation for checking the generated track, not the calculators' own gate line.
    """
    projected = [projector.project_point(w.latitude, w.longitude) for w in waypoints]
    directions = []
    if index > 0:
        directions.append(
            _unit(
                projected[index].projected_x - projected[index - 1].projected_x,
                projected[index].projected_y - projected[index - 1].projected_y,
            )
        )
    if index < len(waypoints) - 1:
        directions.append(
            _unit(
                projected[index + 1].projected_x - projected[index].projected_x,
                projected[index + 1].projected_y - projected[index].projected_y,
            )
        )
    forward = _unit(sum(d[0] for d in directions), sum(d[1] for d in directions))
    right = _right(forward)
    centre = (projected[index].projected_x, projected[index].projected_y)
    return (
        (centre[0] - right[0] * half_width_m, centre[1] - right[1] * half_width_m),
        (centre[0] + right[0] * half_width_m, centre[1] + right[1] * half_width_m),
    )


def line_crossings(
    positions: Sequence[SimPosition],
    line: tuple[tuple[float, float], tuple[float, float]],
    projector: Projector,
) -> list[tuple[datetime.datetime, int]]:
    """Where consecutive positions cross the finite `line` (metric frame): (interpolated time, direction).

    With a line from `gate_line_xy`, +1 means crossing in the direction of the route and -1 against it.
    """
    (x1, y1), (x2, y2) = line
    lx, ly = x2 - x1, y2 - y1

    def side(point):
        return lx * (point[1] - y1) - ly * (point[0] - x1)

    def xy(position):
        projected = projector.project_point(position.latitude, position.longitude)
        return projected.projected_x, projected.projected_y

    crossings = []
    previous = xy(positions[0])
    for before, after in zip(positions, positions[1:]):
        current = xy(after)
        side_before, side_after = side(previous), side(current)
        if side_before * side_after < 0:
            fraction = side_before / (side_before - side_after)
            point = (
                previous[0] + fraction * (current[0] - previous[0]),
                previous[1] + fraction * (current[1] - previous[1]),
            )
            along = ((point[0] - x1) * lx + (point[1] - y1) * ly) / (lx * lx + ly * ly)
            if 0.0 <= along <= 1.0:
                time = before.time + (after.time - before.time) * fraction
                crossings.append((time, 1 if side_after > 0 else -1))
        previous = current
    return crossings


@dataclass(frozen=True)
class Crossing:
    """One crossing of a gate line: when, in which direction (+1 along the route, -1 against it) and how many seconds
    after the gate's expected time (None for a gate without one)."""

    time: datetime.datetime
    direction: int
    error_s: Optional[float]


def gate_crossings(
    waypoints: Sequence,
    gate_times: dict,
    positions: Sequence[SimPosition],
    projector: Projector,
    gates: Optional[Iterable[str]] = None,
) -> dict[str, list[Crossing]]:
    """Where a track crosses the gate lines of `waypoints`, found from the geometry alone (independent of the
    calculators). Returns, per gate name, its crossings in time order; a gate never crossed has an empty list.
    The gate line is `gate_line_xy` through the waypoint, as wide as the waypoint says (`width` in nautical miles)."""
    wanted = set(gates) if gates is not None else None
    result: dict[str, list[Crossing]] = {}
    for index, waypoint_ in enumerate(waypoints):
        name = waypoint_.name
        if (wanted is not None and name not in wanted) or name not in gate_times:
            continue
        half_width = float(getattr(waypoint_, "width", 1.0) or 1.0) * NAUTICAL_MILE_IN_M / 2.0
        line = gate_line_xy(waypoints, index, half_width, projector)
        expected = gate_times.get(name)
        result[name] = [
            Crossing(time, direction, (time - expected).total_seconds() if expected else None)
            for time, direction in sorted(line_crossings(positions, line, projector))
        ]
    return result


# ---------------------------------------------------------------------------------------------------------------------
# Building a task the way the wizard does
# ---------------------------------------------------------------------------------------------------------------------


def _route_path_feature(points: Sequence[tuple[float, float]]) -> dict:
    return {
        "type": "Feature",
        "properties": {"featureType": "route_path"},
        "geometry": {"type": "LineString", "coordinates": [[lon, lat] for lat, lon in points]},
    }


def _route_waypoint_feature(
    sequence: int,
    name: str,
    point_type: str,
    point: tuple[float, float],
    width_m: float,
    timing: bool = True,
    **extra_properties,
) -> dict:
    """A route_waypoint feature with the properties the route editor saves."""
    return {
        "type": "Feature",
        "properties": {
            "id": f"wp-{sequence}",
            "name": name,
            "pointType": point_type,
            "featureType": "route_waypoint",
            "width": width_m,
            "isTiming": timing,
            "isPassing": True,
            "sequence": sequence,
            **extra_properties,
        },
        "geometry": {"type": "Point", "coordinates": [point[1], point[0]]},
    }


def precision_route_geojson(
    start: tuple[float, float] = (60.0, 11.0),
    legs: Sequence[tuple[float, float]] = ((90.0, 6000.0), (160.0, 5000.0), (90.0, 6000.0)),
    width_m: float = 1852.0,
    hidden_gates: Optional[dict[int, Sequence[float]]] = None,
    hidden_timing: bool = False,
    hidden_width_m: float = 300.0,
    untimed: Sequence[str] = (),
    unknown_legs: Optional[dict[str, Sequence[tuple[float, float]]]] = None,
) -> dict:
    """A precision-style EditableRoute: SP at `start`, then one waypoint per (bearing, metres) leg.

    Intermediate waypoints are turn points TP1..TPn, the last one is the finish point FP. Features have the shape the
    route editor saves (route_waypoint features with sequence numbers, plus the route_path line).

    `hidden_gates` puts hidden (secret) gates HG1, HG2, ... on the legs, in route order: it maps the number of a leg
    (0 is SP to TP1) to the fractions of that leg's length at which the gates lie. Hidden gates are not time gates
    unless `hidden_timing` is set. They are `hidden_width_m` wide: a narrow gate can be missed without a sharp turn.
    The waypoints named in `untimed` are not time gates. `unknown_legs` turns the named turn points into unknown-leg
    points (2.A5) and gives each its extension waypoints EXT1, EXT2, ...: (bearing, metres) steps from the point. The
    extension waypoints are not on the route, which is flown along the backbone.
    """
    points = [start]
    for bearing, distance in legs:
        points.append(project_position_lat_lon(points[-1], bearing, distance))
    waypoints = []  # (name, point type, point, timing, width)
    hidden_count = 0
    for index, point in enumerate(points):
        name, point_type = ("SP", "sp") if index == 0 else (f"TP{index}", "tp")
        if index == len(points) - 1:
            name, point_type = "FP", "fp"
        if name in (unknown_legs or {}):
            point_type = "ul"
        waypoints.append((name, point_type, point, name not in untimed, width_m))
        for fraction in sorted((hidden_gates or {}).get(index, ())):
            if index == len(points) - 1:
                raise ValueError("The finish point starts no leg")
            hidden_count += 1
            bearing, distance = legs[index]
            hidden_point = project_position_lat_lon(point, bearing, distance * fraction)
            waypoints.append((f"HG{hidden_count}", "secret", hidden_point, hidden_timing, hidden_width_m))
    features = [_route_path_feature([waypoint[2] for waypoint in waypoints])]
    extension_count = 0
    for sequence, (name, point_type, point, timing, width) in enumerate(waypoints):
        extra = {"unknownLegHeading": 90.0} if point_type == "ul" else {}
        features.append(_route_waypoint_feature(sequence, name, point_type, point, width, timing, **extra))
        previous = point
        for branch, (bearing, distance) in enumerate((unknown_legs or {}).get(name, ())):
            previous = project_position_lat_lon(previous, bearing, distance)
            extension_count += 1
            features.append(
                {
                    "type": "Feature",
                    "properties": {
                        "id": f"ext-{extension_count}",
                        "name": f"EXT{extension_count}",
                        "featureType": "dummy_branch_waypoint",
                        "triggerPointId": f"wp-{sequence}",
                        "branchSequence": branch,
                    },
                    "geometry": {"type": "Point", "coordinates": [previous[1], previous[0]]},
                }
            )
    return {"type": "FeatureCollection", "features": features}


def local_point(origin: tuple[float, float], along_m: float, across_m: float = 0.0) -> tuple[float, float]:
    """(lat, lon) `along_m` metres east of `origin` and `across_m` metres south of it (negative: north)."""
    point = project_position_lat_lon(origin, 90.0, along_m)
    return project_position_lat_lon(point, 180.0, across_m) if across_m else point


def catalogue_turnpoint_feature(name: str, point: tuple[float, float], score_value: Optional[float] = None) -> dict:
    """A free catalogue turn point (2.A3, 2.A6, 2.B2), optionally with its score value."""
    properties = {"id": f"cat-{name}", "name": name, "pointType": "tp", "featureType": "catalogue_turnpoint"}
    if score_value is not None:
        properties["scoreValue"] = score_value
    return {
        "type": "Feature",
        "properties": properties,
        "geometry": {"type": "Point", "coordinates": [point[1], point[0]]},
    }


def known_time_gate_feature(name: str, point: tuple[float, float], width_m: float = 1852.0) -> dict:
    """A standalone timed turn point (the compulsory gates of 2.A6 and 2.B2)."""
    return {
        "type": "Feature",
        "properties": {
            "id": f"ktg-{name}",
            "name": name,
            "pointType": "tp",
            "featureType": "known_time_gate",
            "width": width_m,
        },
        "geometry": {"type": "Point", "coordinates": [point[1], point[0]]},
    }


def contract_route_geojson(
    start: tuple[float, float] = (60.0, 11.0),
    mp_along_m: float = 9260.0,
    fp_along_m: float = 18520.0,
    catalogue: Optional[dict[str, tuple[float, float]]] = None,
    width_m: float = 1852.0,
) -> dict:
    """A 2.A3 route: SP, MP and FP on a line east from `start` (the backbone) and the free catalogue turn points,
    each given as (metres east of SP, metres south of the line)."""
    backbone = [
        ("SP", "sp", start),
        ("MP", "tp", local_point(start, mp_along_m)),
        ("FP", "fp", local_point(start, fp_along_m)),
    ]
    features = [_route_path_feature([point for _, _, point in backbone])]
    for sequence, (name, point_type, point) in enumerate(backbone):
        features.append(_route_waypoint_feature(sequence, name, point_type, point, width_m))
    for name, (along, across) in (catalogue or {}).items():
        features.append(catalogue_turnpoint_feature(name, local_point(start, along, across)))
    return {"type": "FeatureCollection", "features": features}


def hunt_route_geojson(
    start: tuple[float, float] = (60.0, 11.0),
    compulsory: Optional[dict[str, tuple[float, float]]] = None,
    catalogue: Optional[dict[str, tuple[float, float, Optional[float]]]] = None,
    width_m: float = 1852.0,
) -> dict:
    """A 2.A6 / 2.B2 route: no backbone, three standalone timed turn points (`compulsory`: name -> (metres east of
    `start`, metres south)) and free catalogue points (`catalogue`: name -> (east, south, score value))."""
    features = [
        known_time_gate_feature(name, local_point(start, along, across), width_m)
        for name, (along, across) in (compulsory or {}).items()
    ]
    for name, (along, across, value) in (catalogue or {}).items():
        features.append(catalogue_turnpoint_feature(name, local_point(start, along, across), value))
    return {"type": "FeatureCollection", "features": features}


def circle_marker_feature(feature_type: str, name: str, point: tuple[float, float], width_m: float = 1852.0) -> dict:
    """A 2.A7 circle marker. `feature_type` is circle_start_marker, circle_entry_marker, circle_center_marker or
    circle_exit_marker; the point type is derived from it as the route editor does."""
    point_type = feature_type.removesuffix("_marker").replace("circle_", "circle_")
    return {
        "type": "Feature",
        "properties": {
            "id": f"{point_type}-{name}",
            "name": name,
            "pointType": point_type,
            "featureType": feature_type,
            "width": width_m,
        },
        "geometry": {"type": "Point", "coordinates": [point[1], point[0]]},
    }


def circle_route_geojson(
    centre: tuple[float, float],
    start_m: tuple[float, float] = (-1000.0, 0.0),
    entry_m: tuple[float, float] = (500.0, 0.0),
    exit_m: tuple[float, float] = (0.0, -600.0),
) -> dict:
    """A 2.A7 route: the four markers SP, X (entry), CM and WP (exit). The marker positions are (metres east, metres
    north) of the circle centre `centre`."""

    def at(offset: tuple[float, float]) -> tuple[float, float]:
        return local_point(centre, offset[0], -offset[1])

    return {
        "type": "FeatureCollection",
        "features": [
            circle_marker_feature("circle_start_marker", "SP", at(start_m)),
            circle_marker_feature("circle_entry_marker", "X", at(entry_m)),
            circle_marker_feature("circle_center_marker", "CM", centre),
            circle_marker_feature("circle_exit_marker", "WP", at(exit_m)),
        ],
    }


def runway_gate_feature(
    kind: str, start: tuple[float, float], along_m: float, half_length_m: float = 150.0, name: Optional[str] = None
) -> dict:
    """A take-off ("takeoff") or landing ("landing") gate across the route east of `start`, `along_m` metres from it,
    `half_length_m` to each side, as the route editor saves it. Aircraft flying east cross it in the proper direction."""
    first, second = local_point(start, along_m, -half_length_m), local_point(start, along_m, half_length_m)
    return {
        "type": "Feature",
        "properties": {
            "id": f"{kind}-gate",
            "name": name or f"{kind.title()} 1",
            "gateType": kind,
            "featureType": f"{kind}_gate",
        },
        "geometry": {"type": "LineString", "coordinates": [[first[1], first[0]], [second[1], second[0]]]},
    }


def landing_area_feature(
    start: tuple[float, float], along_m: tuple[float, float], across_m: tuple[float, float], name: str = "Landing area"
) -> dict:
    """The landing area polygon of 2.B3 (the area between `along_m` metres east of `start` and `across_m` metres
    south of the line, as (from, to) pairs)."""
    corners = [
        local_point(start, along_m[0], across_m[0]),
        local_point(start, along_m[1], across_m[0]),
        local_point(start, along_m[1], across_m[1]),
        local_point(start, along_m[0], across_m[1]),
    ]
    ring = [[lon, lat] for lat, lon in corners]
    ring.append(ring[0])
    return {
        "type": "Feature",
        "properties": {
            "id": "landing-area",
            "name": name,
            "polygonType": "duration_landing_area",
            "featureType": "zone",
        },
        "geometry": {"type": "Polygon", "coordinates": [ring]},
    }


@dataclass
class SimulatedTask:
    """Everything `build_task` created."""

    contest: object
    editable_route: object
    route: object
    navigation_task: object
    scorecard: object
    contestant: object
    whole_second_gate_times: bool = False

    @property
    def effective_waypoints(self) -> list:
        from display.flight_order_and_maps.effective_route_rendering import get_effective_route_waypoints

        return get_effective_route_waypoints(self.navigation_task, contestant=self.contestant)

    @property
    def gate_times(self) -> dict:
        return self.contestant.gate_times

    @property
    def projector(self) -> Projector:
        return self.navigation_task.get_projector()

    def generate_track(self, deviations: Iterable[Deviation] = (), **options) -> list[SimPosition]:
        """A track over this task's effective waypoints and gate times, flown in the task's own projection."""
        options.setdefault("projector", self.projector)
        return generate_track(self.effective_waypoints, self.gate_times, deviations=deviations, **options)

    def run(self, positions: Sequence[SimPosition]) -> "ScoringResult":
        return run_flight(self.contestant, positions)

    def declare(self, declaration_payload: dict) -> "SimulatedTask":
        """The same pilot with a (new) declaration compiled, as the declaration page would save it."""
        from display.models import Contestant
        from display.services.contestant_task_compiler import ContestantTaskCompiler

        ContestantTaskCompiler(self.contestant).compile(declaration_payload=declaration_payload, force=True)
        contestant = Contestant.objects.get(pk=self.contestant.pk)
        if self.whole_second_gate_times:
            contestant = _round_compiled_gate_times(contestant)
        return replace(self, contestant=contestant)

    def crossings(self, positions: Sequence[SimPosition], gates: Optional[Iterable[str]] = None) -> dict:
        """Every crossing of the gate lines in `positions`, per gate name (see `gate_crossings`)."""
        return gate_crossings(self.effective_waypoints, self.gate_times, positions, self.projector, gates)


def _create_contestant(
    navigation_task,
    number: int,
    takeoff_time: datetime.datetime,
    declaration_payload: Optional[dict],
    air_speed: float,
    wind_speed: float,
    wind_direction: float,
    minutes_to_starting_point: int,
    adaptive_start: bool = False,
):
    """A compiled contestant on `navigation_task`. Must be called with the Traccar mocks in place."""
    from display.models import Aeroplane, Contestant, Crew, Person, Team
    from display.services.contestant_task_compiler import ContestantTaskCompiler

    # Persons need distinct e-mail addresses and aeroplanes distinct registrations, or a second task in one test fails.
    unique = uuid.uuid4().hex[:8]
    person = Person.objects.create(first_name="Sim", last_name=f"Pilot {number}", email=f"sim-{unique}@example.com")
    team = Team.objects.create(
        crew=Crew.objects.create(member1=person),
        aeroplane=Aeroplane.objects.create(registration=f"LN-{unique}"),
    )
    contestant = Contestant.objects.create(
        navigation_task=navigation_task,
        team=team,
        takeoff_time=takeoff_time,
        tracker_start_time=takeoff_time - datetime.timedelta(minutes=30),
        finished_by_time=takeoff_time + datetime.timedelta(hours=2),
        tracker_device_id=f"simulated-flight-{number}",
        contestant_number=number,
        minutes_to_starting_point=minutes_to_starting_point,
        air_speed=air_speed,
        wind_direction=wind_direction,
        wind_speed=wind_speed,
        adaptive_start=adaptive_start,
    )
    ContestantTaskCompiler(contestant).compile(declaration_payload=declaration_payload, force=True)
    contestant.refresh_from_db()
    return contestant


def _round_compiled_gate_times(contestant):
    """Round the compiled gate times to the nearest whole second, as gate times are published in a briefing. The
    calculated times carry fractions of a second, which makes the timing error of a crossing (measured to the whole
    second) ambiguous whenever a fraction is close to one half."""
    from display.models import Contestant

    config = contestant.contestanttaskconfiguration
    rounded = {}
    for name, value in (config.compiled_gate_times_payload or {}).items():
        time = datetime.datetime.fromisoformat(value) if isinstance(value, str) else value
        whole = time.replace(microsecond=0) + datetime.timedelta(seconds=1 if time.microsecond >= 500_000 else 0)
        rounded[name] = whole.isoformat()
    config.compiled_gate_times_payload = rounded
    config.save(update_fields=["compiled_gate_times_payload"])
    return Contestant.objects.get(pk=contestant.pk)


def build_task(
    route_geojson: dict,
    *,
    task_type: Optional[str] = None,
    task_subtype: Optional[str] = None,
    scorecard_shortcut: str = "FAI Precision no procedure turns",
    configure_scorecard: Optional[Callable] = None,
    declaration_payload: Optional[dict] = None,
    rounded_corners: Optional[bool] = None,
    corridor_width: Optional[float] = None,
    takeoff_time: datetime.datetime = datetime.datetime(2020, 8, 1, 8, 5, tzinfo=UTC),
    air_speed: float = 75,
    wind_speed: float = 0,
    wind_direction: float = 0,
    minutes_to_starting_point: int = 6,
    name: str = "Simulated task",
    whole_second_gate_times: bool = False,
    adaptive_start: bool = False,
) -> SimulatedTask:
    """Create a compiled contestant on a task the way the wizard does. Needs the test database.

    `route_geojson` is the EditableRoute feature collection. `configure_scorecard` may adjust the original scorecard
    (e.g. set config values) before the task is created; it is saved afterwards. `add_contestant` adds more pilots to
    the same task. `whole_second_gate_times` rounds the compiled gate times to whole seconds (also after `declare`).
    """
    from display.default_scorecards.create_scorecards import create_scorecards
    from display.models import Contest, EditableRoute, NavigationTask, Scorecard
    from display.utilities.task_types import PRECISION
    from utilities.mock_utilities import TraccarMock

    task_type = task_type or PRECISION
    with (
        patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock),
        patch("display.signals.get_traccar_instance", return_value=TraccarMock),
    ):
        create_scorecards()
        scorecard = Scorecard.get_originals().get(shortcut_name=scorecard_shortcut)
        if configure_scorecard:
            configure_scorecard(scorecard)
            scorecard.save(update_fields=["config"])
        editable_route = EditableRoute.objects.create(name=f"{name} route", route=route_geojson)
        route = editable_route.create_route(
            task_type, scorecard, rounded_corners, corridor_width, task_subtype=task_subtype
        )
        now = datetime.datetime.now(UTC)
        contest = Contest.objects.create(
            name=f"{name} contest {uuid.uuid4().hex[:8]}", start_time=now, finish_time=now, time_zone="Europe/Oslo"
        )
        task_arguments = {}
        if task_subtype:
            task_arguments["task_subtype"] = task_subtype
        navigation_task = NavigationTask.create(
            name=name,
            contest=contest,
            route=route,
            editable_route=editable_route,
            original_scorecard=scorecard,
            start_time=now,
            finish_time=now,
            **task_arguments,
        )
        contestant = _create_contestant(
            navigation_task,
            1,
            takeoff_time,
            declaration_payload,
            air_speed,
            wind_speed,
            wind_direction,
            minutes_to_starting_point,
            adaptive_start,
        )
        if whole_second_gate_times:
            contestant = _round_compiled_gate_times(contestant)
    return SimulatedTask(
        contest, editable_route, route, navigation_task, scorecard, contestant, whole_second_gate_times
    )


def add_contestant(
    task: SimulatedTask,
    *,
    declaration_payload: Optional[dict] = None,
    takeoff_time: Optional[datetime.datetime] = None,
    air_speed: float = 75,
    wind_speed: float = 0,
    wind_direction: float = 0,
    minutes_to_starting_point: int = 6,
) -> SimulatedTask:
    """Another pilot on the same task: a new compiled contestant (number 2, 3, ...) sharing the task's route and
    scorecard. The result is a SimulatedTask for that pilot, so it can generate tracks and run them."""
    from utilities.mock_utilities import TraccarMock

    number = task.navigation_task.contestant_set.count() + 1
    with (
        patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock),
        patch("display.signals.get_traccar_instance", return_value=TraccarMock),
    ):
        contestant = _create_contestant(
            task.navigation_task,
            number,
            takeoff_time or task.contestant.takeoff_time,
            declaration_payload,
            air_speed,
            wind_speed,
            wind_direction,
            minutes_to_starting_point,
        )
        if task.whole_second_gate_times:
            contestant = _round_compiled_gate_times(contestant)
    return replace(task, contestant=contestant)


# ---------------------------------------------------------------------------------------------------------------------
# Running a flight through the real calculators and score application
# ---------------------------------------------------------------------------------------------------------------------


@dataclass
class ScoringResult:
    """What a simulated flight produced."""

    messages: list[UpdateScoreMessage]
    score: float
    score_by_type: dict[str, float]
    gate_passing_times: dict[str, Optional[datetime.datetime]] = field(default_factory=dict)
    missed_gates: list[str] = field(default_factory=list)

    def messages_of_type(self, score_type: str) -> list[UpdateScoreMessage]:
        return [message for message in self.messages if message.score_type == score_type]

    def summary(self) -> list[tuple]:
        """The messages as plain tuples, for comparing two runs (messages hold Gate objects)."""
        return [
            (
                message.time,
                message.gate.name,
                message.score,
                message.message,
                message.score_type,
                message.annotation_type,
                message.planned,
                message.actual,
            )
            for message in self.messages
        ]


def make_score_applier(contestant) -> ContestantProcessor:
    """A bare ContestantProcessor (no Redis/Traccar/threads) that can apply score messages without side effects."""
    processor = object.__new__(ContestantProcessor)
    processor.contestant = contestant
    processor.scorecard = contestant.navigation_task.scorecard
    processor.accumulated_scores = ScoreAccumulator()
    processor.gate_scores = {}
    processor.suppress_side_effects = True
    processor.score = processor.scorecard.initial_score
    return processor


def run_flight(contestant, positions: Sequence[SimPosition], projector: Optional[Projector] = None) -> ScoringResult:
    """Feed `positions` through the contestant's calculators and apply every score message.

    Mirrors ContestantProcessor.run: calculate_score per position, finished_processing at the end (only when there
    were positions), with each emitted UpdateScoreMessage applied by update_score_from_thread in emission order.
    """
    projector = projector or contestant.navigation_task.get_projector()
    queue = Queue()
    orchestrator = calculator_factory(contestant, queue, live_processing=False, projector=projector)
    processor = make_score_applier(contestant)
    messages: list[UpdateScoreMessage] = []

    def apply_queued_messages():
        while not queue.empty():
            message = queue.get_nowait()
            processor.update_score_from_thread(message)
            messages.append(message)

    for position in positions:
        orchestrator.calculate_score(position.to_received_position(contestant))
        apply_queued_messages()
    if positions:
        orchestrator.finished_processing()
        apply_queued_messages()

    passing_times = {}
    missed = []
    for calculator in orchestrator.calculators:
        if isinstance(calculator, GateCalculator):
            for gate in calculator.gates:
                passing_times[gate.name] = gate.passing_time
                if gate.missed:
                    missed.append(gate.name)
    return ScoringResult(
        messages=messages,
        score=processor.score,
        score_by_type=dict(processor.accumulated_scores.related_score),
        gate_passing_times=passing_times,
        missed_gates=missed,
    )


def waypoint(name: str, latitude: float, longitude: float, width_nm: float = 1.0) -> SimpleNamespace:
    """A minimal waypoint for generating tracks without a database."""
    return SimpleNamespace(name=name, latitude=latitude, longitude=longitude, width=width_nm)
