"""
Repair EditableRoute rows identified by `find_swapped_routes` as having
lat/lon swapped in their stored GeoJSON FeatureCollection (issue #65).

For each supplied route id, swaps every [x, y] coordinate pair in every
feature's geometry to [y, x]. Writes a JSON backup of the original route
field before saving, so the change can be reverted manually if needed.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from display.management.commands.find_swapped_routes import (
    Command as FindSwappedRoutesCommand,
)
from display.management.commands.find_swapped_routes import (
    contest_for_route,
    has_any_invalid_lat,
    route_bbox_centroid,
)
from display.models import EditableRoute


SUPPORTED_GEOMETRY_TYPES = {"Point", "LineString", "Polygon"}


def _swap_pair(pair: list) -> list:
    if not pair or len(pair) < 2:
        return pair
    return [pair[1], pair[0], *pair[2:]]


def swap_geometry_coordinates(geometry: dict) -> None:
    """Mutate geometry in place so every coordinate pair is swapped."""
    gtype = geometry.get("type")
    if gtype == "Point":
        geometry["coordinates"] = _swap_pair(geometry.get("coordinates", []))
    elif gtype == "LineString":
        geometry["coordinates"] = [_swap_pair(p) for p in geometry.get("coordinates", [])]
    elif gtype == "Polygon":
        geometry["coordinates"] = [
            [_swap_pair(p) for p in ring] for ring in geometry.get("coordinates", [])
        ]
    else:
        raise ValueError(f"Unsupported geometry type: {gtype!r}")


def swap_route_coordinates(route: dict) -> dict:
    """Return a shallow-copied route with every feature geometry coord-swapped."""
    new_route = {"type": route.get("type", "FeatureCollection"), "features": []}
    for feature in route.get("features", []) or []:
        new_feature = dict(feature)
        geom = dict(feature.get("geometry") or {})
        swap_geometry_coordinates(geom)
        new_feature["geometry"] = geom
        new_route["features"].append(new_feature)
    return new_route


class Command(BaseCommand):
    help = (
        "Swap lat/lon in the stored GeoJSON for one or more EditableRoute rows, "
        "as a repair for routes whose coordinates were left inverted by the "
        "0120 route-editor data migration. See issue #65."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "route_ids",
            nargs="+",
            type=int,
            help="EditableRoute ids to repair.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be changed without saving.",
        )
        parser.add_argument(
            "--backup-dir",
            default="route_swap_backups",
            help="Directory where pre-fix route JSON is written. Default: ./route_swap_backups",
        )
        parser.add_argument(
            "--threshold-km",
            type=float,
            default=500.0,
            help="Same meaning as find_swapped_routes --threshold-km - used to re-verify each "
            "route is still SUSPICIOUS immediately before swapping it. Default: 500 km.",
        )
        parser.add_argument(
            "--improvement-ratio",
            type=float,
            default=5.0,
            help="Same meaning as find_swapped_routes --improvement-ratio. Default: 5.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Swap anyway even if the route no longer classifies as SUSPICIOUS. A route "
            "list gathered earlier (or with different thresholds) can be stale by the time "
            "this runs - --force skips that safety check.",
        )

    def handle(self, *args, **opts):
        dry_run: bool = opts["dry_run"]
        backup_dir = Path(opts["backup_dir"])
        route_ids: list[int] = opts["route_ids"]
        threshold_km: float = opts["threshold_km"]
        improvement_ratio: float = opts["improvement_ratio"]
        force: bool = opts["force"]

        if threshold_km < 0:
            raise CommandError("--threshold-km must be non-negative")
        if improvement_ratio < 1:
            raise CommandError(
                "--improvement-ratio must be at least 1 - below 1 it makes the SUSPICIOUS check "
                "easier to satisfy (swapped_dist * ratio < dist), so it could reclassify a "
                "correctly-ordered route as SUSPICIOUS and swap it without --force."
            )

        if not dry_run:
            backup_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

        for rid in route_ids:
            try:
                route = EditableRoute.objects.get(id=rid)
            except EditableRoute.DoesNotExist:
                raise CommandError(f"EditableRoute {rid} not found")

            original = route.route or {}

            if not force:
                centroid = route_bbox_centroid(original)
                ref = contest_for_route(route)
                invalid_lat = has_any_invalid_lat(original)
                verdict, _dist, _swapped_dist = FindSwappedRoutesCommand._classify(
                    centroid, ref, threshold_km, improvement_ratio, invalid_lat
                )
                if verdict != "SUSPICIOUS":
                    self.stderr.write(
                        self.style.ERROR(
                            f"Route {rid}: currently classifies as {verdict}, not SUSPICIOUS - "
                            f"refusing to swap it (a repair applied to a route that's actually "
                            f"fine would invert it). Pass --force to override."
                        )
                    )
                    continue

            try:
                swapped = swap_route_coordinates(original)
            except ValueError as e:
                self.stderr.write(self.style.ERROR(f"Route {rid}: {e} — skipping"))
                continue

            sample_before = self._first_coord(original)
            sample_after = self._first_coord(swapped)
            self.stdout.write(
                f"Route {rid} ({route.name}): "
                f"first coord {sample_before} -> {sample_after}"
            )

            if dry_run:
                continue

            backup_path = backup_dir / f"editable_route_{rid}_{timestamp}.json"
            with backup_path.open("w", encoding="utf-8") as f:
                json.dump(original, f, indent=2, default=str)
            self.stdout.write(f"  backup: {backup_path}")

            try:
                route.route = swapped
                route.save(update_fields=["route"])
                route.refresh_from_db()
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  saved (waypoints={route.number_of_waypoints}, "
                        f"route_length={route.route_length:.0f})"
                    )
                )
            except ValueError as e:
                self.stderr.write(
                    self.style.ERROR(f"  Error saving or calculating stats for route {rid}: {e}")
                )
            except Exception as e:
                self.stderr.write(
                    self.style.ERROR(f"  Unexpected error for route {rid}: {e}")
                )

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run — no changes saved."))

    @staticmethod
    def _first_coord(route: dict):
        for feature in route.get("features", []) or []:
            geom = feature.get("geometry") or {}
            coords = geom.get("coordinates")
            if not coords:
                continue
            if geom.get("type") == "Point":
                return coords
            if geom.get("type") == "LineString" and coords:
                return coords[0]
            if geom.get("type") == "Polygon" and coords and coords[0]:
                return coords[0][0]
        return None
