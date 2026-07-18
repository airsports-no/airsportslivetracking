from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from display.models.user_uploaded_map import UserUploadedMap


class Command(BaseCommand):
    help = (
        "Reconcile UserUploadedMap rows with storage-backed uploaded files. "
        "Can report, backfill missing published_relative_path/service metadata, and identify orphan files."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--storage-prefix",
            default="user_uploaded_maps",
            help="Storage prefix to inspect for uploaded mbtiles files.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Maximum number of database rows to inspect.",
        )
        parser.add_argument(
            "--after-id",
            type=int,
            default=None,
            help="Only inspect rows with pk greater than this value.",
        )
        parser.add_argument(
            "--backfill-metadata",
            action="store_true",
            help="Backfill published_relative_path and published_service_key when missing.",
        )
        parser.add_argument(
            "--list-orphan-files",
            action="store_true",
            help="List files found in storage that are not referenced by any UserUploadedMap row.",
        )
        parser.add_argument(
            "--delete-orphan-files",
            action="store_true",
            help="Delete files found in storage that are not referenced by any UserUploadedMap row.",
        )
        parser.add_argument(
            "--execute",
            action="store_true",
            help="Actually apply metadata updates and/or orphan-file deletions. Without this flag the command is dry-run only.",
        )

    def handle(self, *args, **options):
        storage_prefix = options["storage_prefix"].rstrip("/")
        limit = options["limit"]
        after_id = options["after_id"]
        backfill_metadata = options["backfill_metadata"]
        list_orphan_files = options["list_orphan_files"]
        delete_orphan_files = options["delete_orphan_files"]
        execute = options["execute"]

        queryset = UserUploadedMap.objects.all().order_by("pk")
        if after_id is not None:
            queryset = queryset.filter(pk__gt=after_id)
        if limit is not None:
            queryset = queryset[:limit]

        inspected = 0
        metadata_updates = 0
        missing_map_file = 0
        missing_published_relative_path = 0
        missing_storage_file = 0

        referenced_paths = set()
        for uploaded_map in queryset:
            inspected += 1
            try:
                map_file_name = getattr(uploaded_map.map_file, "name", "") or ""
                published_relative_path = uploaded_map.published_relative_path or ""
                expected_relative_path = map_file_name or published_relative_path or uploaded_map.default_published_relative_path

                if map_file_name:
                    referenced_paths.add(map_file_name)
                if published_relative_path:
                    referenced_paths.add(published_relative_path)
                if expected_relative_path:
                    referenced_paths.add(expected_relative_path)

                if not map_file_name:
                    missing_map_file += 1
                    self.stdout.write(self.style.WARNING(f"map {uploaded_map.pk}: missing map_file"))

                if not published_relative_path:
                    missing_published_relative_path += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f"map {uploaded_map.pk}: missing published_relative_path; expected {expected_relative_path!r}"
                        )
                    )

                if expected_relative_path and not uploaded_map.map_file.storage.exists(expected_relative_path):
                    missing_storage_file += 1
                    self.stdout.write(
                        self.style.ERROR(
                            f"map {uploaded_map.pk}: storage file missing for {expected_relative_path!r}"
                        )
                    )

                if backfill_metadata:
                    fields_to_update = []
                    if not uploaded_map.published_relative_path and expected_relative_path:
                        uploaded_map.published_relative_path = expected_relative_path
                        fields_to_update.append("published_relative_path")
                    if not uploaded_map.published_service_key:
                        uploaded_map.published_service_key = uploaded_map.default_service_key
                        fields_to_update.append("published_service_key")
                    if fields_to_update:
                        self.stdout.write(
                            f"map {uploaded_map.pk}: would backfill {fields_to_update} -> "
                            f"relative_path={uploaded_map.published_relative_path!r}, service_key={uploaded_map.published_service_key!r}"
                        )
                        if execute:
                            with transaction.atomic():
                                uploaded_map.save(update_fields=fields_to_update)
                            metadata_updates += 1
            finally:
                uploaded_map.clear_local_file_path()

        orphan_files = []
        if list_orphan_files or delete_orphan_files:
            storage = UserUploadedMap._meta.get_field("map_file").storage
            _, files = storage.listdir(storage_prefix)
            for filename in files:
                relative_path = f"{storage_prefix}/{filename}"
                if relative_path not in referenced_paths:
                    orphan_files.append(relative_path)
                    self.stdout.write(self.style.WARNING(f"orphan file: {relative_path}"))
            if delete_orphan_files and execute:
                for relative_path in orphan_files:
                    storage.delete(relative_path)
                    self.stdout.write(self.style.SUCCESS(f"deleted orphan file: {relative_path}"))

        self.stdout.write(
            self.style.SUCCESS(
                f"summary: inspected={inspected} metadata_updates={metadata_updates} "
                f"missing_map_file={missing_map_file} missing_published_relative_path={missing_published_relative_path} "
                f"missing_storage_file={missing_storage_file} orphan_files={len(orphan_files)} dry_run={0 if execute else 1}"
            )
        )
