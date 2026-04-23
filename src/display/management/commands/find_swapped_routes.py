"""
Find EditableRoute rows whose coordinates appear to be stored with lat/lon
swapped, most likely due to the partial migration 0120_auto_20251228_2126
(see issue #65).

Strategy: for each route, find the linked Contest (via NavigationTask) and
compare the route's bounding-box centroid to the contest location. If the
centroid is far from the contest and becomes much closer when all route
coordinates are swapped, flag the route as SUSPICIOUS.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from django.core.management.base import BaseCommand

from display.models import Contest, EditableRoute, NavigationTask
from display.utilities.coordinate_utilities import calculate_distance_lat_lon


@dataclass
class ContestRef:
    contest_id: int
    name: str
    latitude: Optional[float]
    longitude: Optional[float]
    country: Optional[str]


def _iter_coord_pairs(geometry: dict) -> Iterable[list]:
    """Yield every [x, y] pair in a GeoJSON geometry (Point/LineString/Polygon)."""
    gtype = geometry.get("type")
    coords = geometry.get("coordinates")
    if coords is None:
        return
    if gtype == "Point":
        yield coords
    elif gtype == "LineString":
        yield from coords
    elif gtype == "Polygon":
        for ring in coords:
            yield from ring
    else:
        return


def route_bbox_centroid(route: dict) -> Optional[tuple[float, float]]:
    """Return (lon, lat) centroid of bbox over all feature coordinates."""
    lons: list[float] = []
    lats: list[float] = []
    for feature in route.get("features", []) or []:
        geom = feature.get("geometry") or {}
        for pair in _iter_coord_pairs(geom):
            if not pair or len(pair) < 2:
                continue
            lon, lat = pair[0], pair[1]
            lons.append(lon)
            lats.append(lat)
    if not lons:
        return None
    return (
        (min(lons) + max(lons)) / 2.0,
        (min(lats) + max(lats)) / 2.0,
    )


def contest_for_route(route: EditableRoute) -> Optional[ContestRef]:
    """Find the first Contest linked to this route via NavigationTask."""
    nav = (
        NavigationTask.objects.filter(editable_route=route)
        .select_related("contest")
        .first()
    )
    if not nav or not nav.contest:
        return None
    c: Contest = nav.contest
    lat = getattr(c, "latitude", None)
    lon = getattr(c, "longitude", None)
    try:
        lat = float(lat) if lat is not None else None
        lon = float(lon) if lon is not None else None
    except (TypeError, ValueError):
        lat = lon = None
    country = str(c.country) if getattr(c, "country", None) else None
    return ContestRef(contest_id=c.id, name=c.name, latitude=lat, longitude=lon, country=country)


def km_between(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Distance in km between two (lon, lat) points."""
    a_lat_lon = (a[1], a[0])
    b_lat_lon = (b[1], b[0])
    return calculate_distance_lat_lon(a_lat_lon, b_lat_lon) / 1000.0


class Command(BaseCommand):
    help = (
        "Identify EditableRoute rows whose coordinates appear to have lat/lon "
        "swapped by comparing route bbox centroid to the linked Contest location."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--threshold-km",
            type=float,
            default=500.0,
            help="Flag a route if its centroid is farther than this from the contest "
                 "AND swapping coordinates brings it much closer. Default: 500 km.",
        )
        parser.add_argument(
            "--improvement-ratio",
            type=float,
            default=5.0,
            help="Require swapped distance to be at least this many times smaller "
                 "than original distance. Default: 5.",
        )
        parser.add_argument(
            "--route-id",
            type=int,
            action="append",
            default=None,
            help="Limit check to given route id(s). May be repeated.",
        )
        parser.add_argument(
            "--show-all",
            action="store_true",
            help="Also print non-suspicious routes (OK, UNLINKED, NO_LOCATION).",
        )

    def handle(self, *args, **opts):
        threshold_km: float = opts["threshold_km"]
        ratio: float = opts["improvement_ratio"]
        route_ids = opts.get("route_id")
        show_all: bool = opts["show_all"]

        qs = EditableRoute.objects.all().order_by("id")
        if route_ids:
            qs = qs.filter(id__in=route_ids)

        suspicious: list[int] = []
        header = "id\tverdict\tdist_km\tswapped_km\tcontest_id\tcontest_name\troute_name"
        self.stdout.write(header)

        for route in qs:
            centroid = route_bbox_centroid(route.route or {})
            ref = contest_for_route(route)

            verdict, dist, swapped_dist = self._classify(
                centroid, ref, threshold_km, ratio
            )
            if verdict == "SUSPICIOUS":
                suspicious.append(route.id)

            if verdict == "SUSPICIOUS" or show_all:
                contest_id = ref.contest_id if ref else ""
                contest_name = ref.name if ref else ""
                self.stdout.write(
                    f"{route.id}\t{verdict}\t"
                    f"{self._fmt(dist)}\t{self._fmt(swapped_dist)}\t"
                    f"{contest_id}\t{contest_name}\t{route.name}"
                )

        self.stdout.write("")
        self.stdout.write(f"Suspicious route ids: {suspicious}")
        self.stdout.write(
            f"To repair: python manage.py fix_swapped_route "
            + " ".join(str(i) for i in suspicious)
        )

    @staticmethod
    def _fmt(v) -> str:
        return f"{v:.0f}" if isinstance(v, (int, float)) else ""

    @staticmethod
    def _classify(
        centroid: Optional[tuple[float, float]],
        ref: Optional[ContestRef],
        threshold_km: float,
        ratio: float,
    ) -> tuple[str, Optional[float], Optional[float]]:
        if centroid is None:
            return "EMPTY_ROUTE", None, None
        if ref is None:
            return "UNLINKED", None, None
        if ref.latitude is None or ref.longitude is None:
            return "NO_LOCATION", None, None

        contest_point = (ref.longitude, ref.latitude)
        dist = km_between(centroid, contest_point)
        swapped = (centroid[1], centroid[0])
        swapped_dist = km_between(swapped, contest_point)

        if dist > threshold_km and swapped_dist * ratio < dist:
            return "SUSPICIOUS", dist, swapped_dist
        return "OK", dist, swapped_dist
