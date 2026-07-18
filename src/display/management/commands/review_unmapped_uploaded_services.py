from pathlib import Path
from urllib.parse import urlparse

from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand

from display.flight_order_and_maps.map_plotter_shared_utilities import service_key_from_uploaded_relative_path
from display.flight_order_and_maps.mbtiles_facade import get_available_maps
from display.models.user_uploaded_map import UserUploadedMap


class Command(BaseCommand):
    help = (
        "List mbtiles services/files under the uploaded storage root that are not mapped to any "
        "UserUploadedMap object, and optionally delete the orphaned storage files."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--storage-prefix",
            default="user_uploaded_maps",
            help="Storage prefix to inspect for uploaded mbtiles files.",
        )
        parser.add_argument(
            "--delete-files",
            action="store_true",
            help="Delete orphaned storage files that are offered by mbtiles but not mapped to any UserUploadedMap.",
        )
        parser.add_argument(
            "--execute",
            action="store_true",
            help="Actually perform deletions. Without this flag the command is dry-run only.",
        )

    def handle(self, *args, **options):
        storage_prefix = options["storage_prefix"].rstrip("/")
        delete_files = options["delete_files"]
        execute = options["execute"]

        mapped_relative_paths = {
            uploaded_map.published_relative_path
            for uploaded_map in UserUploadedMap.objects.exclude(published_relative_path="")
            if uploaded_map.published_relative_path
        }
        mapped_service_keys = {
            service_key_from_uploaded_relative_path(relative_path)
            for relative_path in mapped_relative_paths
        }

        services = get_available_maps() or []
        service_keys = set()
        for service in services:
            url = service.get("url", "")
            if not url:
                continue
            path = urlparse(url).path.rstrip("/")
            if not path.startswith("/services/"):
                continue
            service_keys.add(Path(path).name)

        _, files = default_storage.listdir(storage_prefix)
        orphan_files = []
        for filename in files:
            if not filename.endswith(".mbtiles"):
                continue
            relative_path = f"{storage_prefix}/{filename}"
            service_key = Path(filename).stem
            if relative_path in mapped_relative_paths:
                continue
            if service_key not in service_keys:
                continue
            orphan_files.append((relative_path, service_key))
            self.stdout.write(self.style.WARNING(f"orphan service file: {relative_path} (service={service_key})"))

        deleted = 0
        if delete_files and execute:
            for relative_path, service_key in orphan_files:
                default_storage.delete(relative_path)
                deleted += 1
                self.stdout.write(self.style.SUCCESS(f"deleted orphan service file: {relative_path} (service={service_key})"))

        self.stdout.write(
            self.style.SUCCESS(
                f"summary: services_seen={len(service_keys)} mapped_paths={len(mapped_relative_paths)} orphan_service_files={len(orphan_files)} deleted={deleted} dry_run={0 if execute else 1}"
            )
        )
