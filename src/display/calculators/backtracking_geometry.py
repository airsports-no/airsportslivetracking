"""
Where backtracking counts: FAI Section 10, 4.24.5, as geometry.

Backtracking is flying at an angle of more than 90 degrees to the intended flight direction for more than 5 seconds in
sequence, within a corridor defined by the width used to score gates in the task. The one exception is within a radius
around a turn point, defined by the distance from the centre of the turn point to the outermost intersection of the two
leg corridors. (For microlight tasks it is also rejoining the active track line at a point prior to the point where it
was left; that clause is not implemented, see BacktrackingAndProcedureTurnsCalculator.)

This module is the "where" of that definition and nothing else: whether the aircraft is inside the corridor of the active
leg and outside the turn point radius of either end of the leg. The bearing and the five seconds stay with the
calculator's state machine. Everything here is in the projected metric plane and has no dependencies on the models.
"""

import math
from dataclasses import dataclass
from typing import Optional, Sequence

from display.utilities.coordinate_utilities import euclidean_point_to_line_distance

# The radius at a very sharp turn grows without bound (the corridors of two legs that fold back on each other meet
# far from the turn point); it is limited to this many corridor half-widths.
MAXIMUM_RADIUS_IN_HALF_WIDTHS = 10.0


@dataclass(frozen=True)
class CorridorVertex:
    """A point of the route as the corridor sees it: where it is and the half-width (in metres) of the gate there."""

    x: float
    y: float
    half_width_m: float
    name: str = ""


@dataclass(frozen=True)
class CorridorLeg:
    """One leg of the route with its corridor and the turn point radii at both ends (all in metres)."""

    start: CorridorVertex
    end: CorridorVertex
    half_width_m: float
    start_radius_m: float
    end_radius_m: float


def turn_point_radius(half_width_m: float, interior_angle_deg: float) -> float:
    """
    The distance from the centre of a turn point to the outermost intersection of the corridors of the two legs that
    meet there, for corridors `half_width_m` to each side. `interior_angle_deg` is the angle between the two legs at the
    turn point (180 for a straight line, 90 for a right-angle turn). The outer corner of two corridors meeting at that
    angle lies half_width / sin(angle / 2) from the centre: the half-width itself on a straight line, 1.41 half-widths at
    a right angle.
    """
    sine = math.sin(math.radians(min(max(interior_angle_deg, 0.0), 180.0)) / 2.0)
    return half_width_m / max(sine, 1.0 / MAXIMUM_RADIUS_IN_HALF_WIDTHS)


def _interior_angle_deg(before: CorridorVertex, vertex: CorridorVertex, after: CorridorVertex) -> float:
    """The angle at `vertex` between the legs to `before` and to `after`, in degrees."""
    ax, ay = before.x - vertex.x, before.y - vertex.y
    bx, by = after.x - vertex.x, after.y - vertex.y
    lengths = math.hypot(ax, ay) * math.hypot(bx, by)
    if lengths == 0:
        return 180.0
    cosine = max(-1.0, min(1.0, (ax * bx + ay * by) / lengths))
    return math.degrees(math.acos(cosine))


def build_corridor_legs(vertices: Sequence[CorridorVertex]) -> list[CorridorLeg]:
    """
    The legs between consecutive vertices. The corridor of a leg is as wide as the gate it leaves (the width used to
    score gates), the turn point radius at a vertex follows from the angle between its two legs and the wider of the two
    corridors, and at the start and the end of the route (one leg only) it is the corridor's half-width.
    """
    legs = []
    for index in range(len(vertices) - 1):
        start, end = vertices[index], vertices[index + 1]
        start_radius = start.half_width_m
        if index > 0:
            before = vertices[index - 1]
            start_radius = turn_point_radius(
                max(start.half_width_m, before.half_width_m), _interior_angle_deg(before, start, end)
            )
        end_radius = end.half_width_m
        if index + 2 < len(vertices):
            after = vertices[index + 2]
            end_radius = turn_point_radius(
                max(end.half_width_m, start.half_width_m), _interior_angle_deg(start, end, after)
            )
        legs.append(CorridorLeg(start, end, start.half_width_m, start_radius, end_radius))
    return legs


def distance_to_leg(x: float, y: float, leg: CorridorLeg) -> float:
    """The distance from the point to the leg (the segment between its two ends)."""
    return euclidean_point_to_line_distance(leg.start.x, leg.start.y, leg.end.x, leg.end.y, x, y)


def is_inside_corridor(x: float, y: float, leg: CorridorLeg) -> bool:
    return distance_to_leg(x, y, leg) <= leg.half_width_m


def is_inside_turn_point_radius(x: float, y: float, leg: CorridorLeg) -> bool:
    """Within the turn point radius of either end of the leg."""
    return (
        math.hypot(x - leg.start.x, y - leg.start.y) <= leg.start_radius_m
        or math.hypot(x - leg.end.x, y - leg.end.y) <= leg.end_radius_m
    )


def backtracking_counts_here(x: float, y: float, leg: CorridorLeg) -> bool:
    """4.24.5: backtracking only counts inside the corridor of the active leg and outside the turn point radii."""
    return is_inside_corridor(x, y, leg) and not is_inside_turn_point_radius(x, y, leg)


def active_leg(x: float, y: float, legs: Sequence[CorridorLeg], first_leg_index: int = 0) -> Optional[CorridorLeg]:
    """The leg the point is on: the nearest of the legs from `first_leg_index` on (the earliest of equally near)."""
    best, best_distance = None, math.inf
    for leg in legs[first_leg_index:]:
        distance = distance_to_leg(x, y, leg)
        if distance < best_distance:
            best, best_distance = leg, distance
    return best
