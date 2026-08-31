import re
from pathlib import Path

from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand
from django.db import transaction

from display.models.user_uploaded_map import UserUploadedMap


LOG_PATH_RE = re.compile(r'/tilesets-user/([^"\s]+\.mbtiles)')


class Command(BaseCommand):
    help = (
        "Find uploaded MBTiles files from mbtileserver error output, show matching "
        "UserUploadedMap rows, and optionally delete the DB rows and/or storage files."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "items",
            nargs="*",
            help=(
                "Filenames like 'AF-tile1.mbtiles' or raw log lines containing "
                "/tilesets-user/<file>.mbtiles"
            ),
        )
        parser.add_argument(
            "--from-log-file",
            dest="from_log_file",
            help="Path to a text file containing mbtileserver log lines.",
        )
        parser.add_argument(
            "--delete-objects",
            action="store_true",
            help="Delete matching UserUploadedMap database rows. Neither this nor --delete-files "
            "given means report-only, even with --execute.",
        )
        parser.add_argument(
            "--delete-files",
            action="store_true",
            help="Delete matching storage files (default_storage) for offending filenames. "
            "Neither this nor --delete-objects given means report-only, even with --execute.",
        )
        parser.add_argument(
            "--execute",
            action="store_true",
            help="Actually perform deletions. Without this flag the command is dry-run only.",
        )

    def _extract_filenames(self, raw_items):
        filenames = []
        for raw in raw_items:
            match = LOG_PATH_RE.search(raw)
            if match:
                filenames.append(match.group(1))
                continue
            candidate = Path(raw).name
            if candidate.endswith(".mbtiles"):
                filenames.append(candidate)
        return filenames

    def handle(self, *args, **options):
        raw_items = list(options["items"])
        if options.get("from_log_file"):
            raw_items.extend(Path(options["from_log_file"]).read_text().splitlines())

        filenames = sorted(set(self._extract_filenames(raw_items)))
        if not filenames:
            self.stdout.write(self.style.WARNING("No .mbtiles filenames found."))
            return

        delete_objects = options["delete_objects"]
        delete_files = options["delete_files"]
        execute = options["execute"]

        matched_object_ids = set()
        files_deleted = 0
        objects_deleted = 0
        missing_files = 0

        for filename in filenames:
            self.stdout.write(self.style.MIGRATE_HEADING(f"\n=== {filename} ==="))
            # Require a path-separator boundary immediately before the filename (every stored
            # path carries the "user_uploaded_maps/" upload_to prefix) - a bare __endswith=filename
            # also matches a longer user-chosen name like "my-map.mbtiles" against "map.mbtiles".
            boundary_suffix = f"/{filename}"
            queryset = UserUploadedMap.objects.filter(
                map_file__endswith=boundary_suffix
            ) | UserUploadedMap.objects.filter(published_relative_path__endswith=boundary_suffix)
            queryset = queryset.distinct().order_by("pk")

            if queryset.exists():
                for obj in queryset:
                    matched_object_ids.add(obj.pk)
                    self.stdout.write(
                        f"object id={obj.pk} name={obj.name!r} status={obj.processing_status} "
                        f"map_file={obj.map_file!s} published_relative_path={obj.published_relative_path!r}"
                    )
            else:
                self.stdout.write("no matching UserUploadedMap rows")

            relative_candidates = [f"user_uploaded_maps/{filename}"]
            existing_relatives = [rel for rel in relative_candidates if default_storage.exists(rel)]
            if existing_relatives:
                for rel in existing_relatives:
                    self.stdout.write(f"storage file exists: {rel}")
            else:
                missing_files += 1
                self.stdout.write("storage file not found via default_storage")

            if execute and delete_files:
                for rel in existing_relatives:
                    default_storage.delete(rel)
                    files_deleted += 1
                    self.stdout.write(self.style.SUCCESS(f"deleted storage file: {rel}"))

        if execute and delete_objects:
            delete_qs = UserUploadedMap.objects.filter(pk__in=matched_object_ids).order_by("pk")
            with transaction.atomic():
                for obj in delete_qs:
                    obj.delete()
                    objects_deleted += 1
                    self.stdout.write(self.style.SUCCESS(f"deleted object id={obj.pk}"))

        self.stdout.write(
            self.style.SUCCESS(
                f"summary: filenames={len(filenames)} matched_objects={len(matched_object_ids)} "
                f"files_deleted={files_deleted} objects_deleted={objects_deleted} "
                f"dry_run={0 if execute else 1} missing_files={missing_files}"
            )
        )
