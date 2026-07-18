from django.core.management.base import BaseCommand
from django.db import transaction

from display.models.user_uploaded_map import UserUploadedMap


class Command(BaseCommand):
    help = (
        "Backfill bounds metadata for uploaded MBTiles maps by opening each map file, "
        "computing bounds, and writing minimum/maximum longitude/latitude."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--map-id",
            type=int,
            action="append",
            dest="map_ids",
            help="Only process the specified UserUploadedMap id. Repeat to process multiple ids.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Recompute bounds even when the row already has all four bound values.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be updated without writing to the database.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Maximum number of rows to process.",
        )

    def handle(self, *args, **options):
        map_ids = options.get("map_ids") or []
        force = options["force"]
        dry_run = options["dry_run"]
        limit = options["limit"]

        queryset = UserUploadedMap.objects.all().order_by("pk")
        if map_ids:
            queryset = queryset.filter(pk__in=map_ids)
        if not force:
            queryset = queryset.filter(
                minimum_longitude__isnull=True,
                minimum_latitude__isnull=True,
                maximum_longitude__isnull=True,
                maximum_latitude__isnull=True,
            )
        if limit is not None:
            queryset = queryset[:limit]

        processed = 0
        updated = 0
        skipped = 0
        failed = 0

        for uploaded_map in queryset:
            processed += 1

            if not force and uploaded_map.bounds:
                skipped += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"skip map {uploaded_map.pk} ({uploaded_map.name}): bounds already present"
                    )
                )
                continue

            try:
                minimum_longitude, minimum_latitude, maximum_longitude, maximum_latitude = uploaded_map.get_bounds()
            except Exception as exc:
                failed += 1
                self.stderr.write(
                    self.style.ERROR(
                        f"fail map {uploaded_map.pk} ({uploaded_map.name}): {exc}"
                    )
                )
                continue

            self.stdout.write(
                f"map {uploaded_map.pk} ({uploaded_map.name}) -> "
                f"west={minimum_longitude}, south={minimum_latitude}, east={maximum_longitude}, north={maximum_latitude}"
            )

            if dry_run:
                continue

            uploaded_map.minimum_longitude = minimum_longitude
            uploaded_map.minimum_latitude = minimum_latitude
            uploaded_map.maximum_longitude = maximum_longitude
            uploaded_map.maximum_latitude = maximum_latitude
            with transaction.atomic():
                uploaded_map.save(
                    update_fields=[
                        "minimum_longitude",
                        "minimum_latitude",
                        "maximum_longitude",
                        "maximum_latitude",
                    ]
                )
            updated += 1

        summary = (
            f"processed={processed} updated={updated} skipped={skipped} failed={failed}"
            + (" dry-run=1" if dry_run else "")
        )
        self.stdout.write(self.style.SUCCESS(summary))
