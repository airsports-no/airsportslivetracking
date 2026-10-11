"""
Scoring of photo observations, emulating how they are marked on a paper map.

On a paper map the crew draws a line across the track at the point where they are when they see the
observation target. The judge compares where that line crosses the track with where the photo's
target is, projected onto the same track, and measures the distance on the printed map in millimetres.

We reproduce this by projecting both the crew's position at the time of the observation and the photo
target onto the route polyline (the track), taking the distance along the track between the two
projections, and converting it to millimetres with the map scale from the flight order configuration.

Everything in this module is pure geometry (no Django, no I/O) so it can be tested in isolation.
"""

from __future__ import annotations

import dataclasses
import math
from typing import Sequence

EARTH_RADIUS_M = 6371008.8

# Paper sizes in millimetres (width, height) in portrait orientation.
PAPER_SIZES_MM = {"A4": (210.0, 297.0), "A3": (297.0, 420.0)}
# Unprintable margin assumed when estimating the scale of a "fit page" map.
FIT_PAGE_MARGIN_MM = 10.0

# The paper-map rule: a mark is accepted when it is within this many millimetres of the target,
# measured along the track. Marks that are further out score a reduced fraction, see score_fraction().
FULL_SCORE_TOLERANCE_MM = 1.0
# Beyond the tolerance, up to this many mm the observation scores half. Set to the full tolerance to
# disable the half-score band.
HALF_SCORE_TOLERANCE_MM = 1.0
# An observation made further than this (in map millimetres) from the track is "out of track" and scores zero.
MAX_CROSS_TRACK_MM = 20.0


@dataclasses.dataclass(frozen=True)
class Projection:
    """The projection of a point onto a polyline."""

    latitude: float
    longitude: float
    # Distance in metres from the start of the polyline to the projected point, measured along the polyline
    distance_along_m: float
    # Perpendicular distance in metres from the original point to the polyline
    cross_track_m: float
    # Index of the polyline segment the point was projected onto (segment i runs from point i to point i+1)
    segment_index: int


@dataclasses.dataclass(frozen=True)
class PhotoObservationResult:
    scored: bool
    reason: str
    error_m: float | None = None
    error_mm: float | None = None
    score_fraction: float = 0.0
    metres_per_mm: float | None = None
    user_projection: Projection | None = None
    photo_projection: Projection | None = None


def metres_per_millimetre(scale_thousands: float) -> float:
    """1 mm on a 1:N map is N mm on the ground. FlightOrderConfiguration.map_scale stores N / 1000, so 1 mm is exactly map_scale metres."""
    return float(scale_thousands)


def estimate_fit_page_scale_thousands(
    points: Sequence[tuple[float, float]],
    document_size: str = "A4",
    landscape: bool = False,
) -> float | None:
    """
    Estimates the scale (in thousands, like FlightOrderConfiguration.map_scale) of a map that was
    generated with the "fit page" option, from the bounding box of the route points (latitude, longitude).
    """
    if len(points) < 2:
        return None
    width_mm, height_mm = PAPER_SIZES_MM.get(document_size, PAPER_SIZES_MM["A4"])
    if landscape:
        width_mm, height_mm = height_mm, width_mm
    width_mm -= 2 * FIT_PAGE_MARGIN_MM
    height_mm -= 2 * FIT_PAGE_MARGIN_MM
    reference_lat = sum(p[0] for p in points) / len(points)
    xs = []
    ys = []
    for lat, lon in points:
        x, y = _to_local_metres(lat, lon, reference_lat, 0.0)
        xs.append(x)
        ys.append(y)
    extent_x_m = max(xs) - min(xs)
    extent_y_m = max(ys) - min(ys)
    if extent_x_m == 0 and extent_y_m == 0:
        return None
    # Ground metres per paper millimetre needed to fit the extent on the page, orientation as is
    ratio = max(extent_x_m / width_mm, extent_y_m / height_mm)
    return ratio


def _to_local_metres(lat: float, lon: float, reference_lat: float, reference_lon: float) -> tuple[float, float]:
    x = math.radians(lon - reference_lon) * EARTH_RADIUS_M * math.cos(math.radians(reference_lat))
    y = math.radians(lat - reference_lat) * EARTH_RADIUS_M
    return x, y


def _from_local_metres(x: float, y: float, reference_lat: float, reference_lon: float) -> tuple[float, float]:
    lat = reference_lat + math.degrees(y / EARTH_RADIUS_M)
    lon = reference_lon + math.degrees(x / (EARTH_RADIUS_M * math.cos(math.radians(reference_lat))))
    return lat, lon


def project_onto_polyline(
    latitude: float,
    longitude: float,
    polyline: Sequence[tuple[float, float]],
    segment_range: tuple[int, int] | None = None,
) -> Projection | None:
    """
    Projects a point onto the closest position on the polyline (a sequence of (latitude, longitude)).
    The distance along the polyline is always measured from its first point. Use segment_range
    (inclusive start, exclusive end segment indices) to restrict the candidate segments.
    """
    if len(polyline) < 2:
        return None
    # The frame is anchored on the polyline, not the query point, so that distances along the polyline
    # are identical regardless of which point is being projected.
    reference_lat = sum(lat for lat, _ in polyline) / len(polyline)
    reference_lon = polyline[0][1]
    query_x, query_y = _to_local_metres(latitude, longitude, reference_lat, reference_lon)
    local = [_to_local_metres(lat, lon, reference_lat, reference_lon) for lat, lon in polyline]
    cumulative = [0.0]
    for (x0, y0), (x1, y1) in zip(local, local[1:]):
        cumulative.append(cumulative[-1] + math.hypot(x1 - x0, y1 - y0))
    start, end = segment_range if segment_range else (0, len(local) - 1)
    best: Projection | None = None
    for i in range(max(start, 0), min(end, len(local) - 1)):
        (x0, y0), (x1, y1) = local[i], local[i + 1]
        dx, dy = x1 - x0, y1 - y0
        length_squared = dx * dx + dy * dy
        t = (
            0.0
            if length_squared == 0
            else max(0.0, min(1.0, ((query_x - x0) * dx + (query_y - y0) * dy) / length_squared))
        )
        px, py = x0 + t * dx, y0 + t * dy
        cross_track = math.hypot(px - query_x, py - query_y)
        if best is None or cross_track < best.cross_track_m:
            lat, lon = _from_local_metres(px, py, reference_lat, reference_lon)
            best = Projection(
                latitude=lat,
                longitude=lon,
                distance_along_m=cumulative[i] + t * math.sqrt(length_squared),
                cross_track_m=cross_track,
                segment_index=i,
            )
    return best


def score_fraction(error_mm: float, full_tolerance_mm: float, half_tolerance_mm: float) -> float:
    if error_mm <= full_tolerance_mm:
        return 1.0
    if error_mm <= half_tolerance_mm:
        return 0.5
    return 0.0


def calculate_photo_observation(
    *,
    user_latitude: float,
    user_longitude: float,
    photo_latitude: float,
    photo_longitude: float,
    polyline: Sequence[tuple[float, float]],
    metres_per_mm: float | None,
    full_tolerance_mm: float = FULL_SCORE_TOLERANCE_MM,
    half_tolerance_mm: float = HALF_SCORE_TOLERANCE_MM,
    max_cross_track_mm: float = MAX_CROSS_TRACK_MM,
) -> PhotoObservationResult:
    """
    Scores one observation. polyline is the track the crew is following, as (latitude, longitude) pairs.
    metres_per_mm is the ground distance covered by one millimetre on the printed map.
    """
    if metres_per_mm is None or metres_per_mm <= 0:
        return PhotoObservationResult(scored=False, reason="map_scale_unknown")
    photo_projection = project_onto_polyline(photo_latitude, photo_longitude, polyline)
    if photo_projection is None:
        return PhotoObservationResult(scored=False, reason="no_route")
    # Look for the crew on the leg the photo belongs to and its immediate neighbours, so that an
    # unrelated part of a looping route running alongside the photo does not capture the position.
    segment_range = (photo_projection.segment_index - 1, photo_projection.segment_index + 2)
    user_projection = project_onto_polyline(user_latitude, user_longitude, polyline, segment_range)
    if user_projection is None:
        return PhotoObservationResult(scored=False, reason="no_route", photo_projection=photo_projection)
    error_m = abs(user_projection.distance_along_m - photo_projection.distance_along_m)
    error_mm = error_m / metres_per_mm
    if user_projection.cross_track_m / metres_per_mm > max_cross_track_mm:
        return PhotoObservationResult(
            scored=True,
            reason="out_of_track",
            error_m=error_m,
            error_mm=error_mm,
            score_fraction=0.0,
            metres_per_mm=metres_per_mm,
            user_projection=user_projection,
            photo_projection=photo_projection,
        )
    return PhotoObservationResult(
        scored=True,
        reason="ok",
        error_m=error_m,
        error_mm=error_mm,
        score_fraction=score_fraction(error_mm, full_tolerance_mm, half_tolerance_mm),
        metres_per_mm=metres_per_mm,
        user_projection=user_projection,
        photo_projection=photo_projection,
    )
