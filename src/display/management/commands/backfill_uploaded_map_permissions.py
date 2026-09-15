from django.core.management.base import BaseCommand
from django.db import transaction
from guardian.shortcuts import assign_perm, get_users_with_perms

from display.models.user_uploaded_map import UserUploadedMap

PERMISSIONS = (
    "view_useruploadedmap",
    "change_useruploadedmap",
    "delete_useruploadedmap",
    "add_useruploadedmap",
)


class Command(BaseCommand):
    help = (
        "Backfill guardian object permissions for uploaded maps whose owner has none - these "
        "maps were created through a path that skipped UserUploadedMapCreate.form_valid()'s "
        "assign_perm calls (e.g. Django admin's bare GuardedModelAdmin registration before it "
        "gained its own save_model override), leaving them permanently invisible to their own "
        "owner regardless of geographic bounds or contest access."
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
            help="Reassign permissions even when the owner already has some of them.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be updated without writing to the database.",
        )

    def handle(self, *args, **options):
        map_ids = options.get("map_ids") or []
        force = options["force"]
        dry_run = options["dry_run"]

        queryset = UserUploadedMap.objects.filter(unprotected=False).order_by("pk")
        if map_ids:
            queryset = queryset.filter(pk__in=map_ids)

        processed = 0
        updated = 0
        skipped = 0

        for uploaded_map in queryset:
            if not force and get_users_with_perms(uploaded_map).exists():
                skipped += 1
                continue

            processed += 1
            self.stdout.write(
                f"map {uploaded_map.pk} ({uploaded_map.name}) -> granting {', '.join(PERMISSIONS)} to "
                f"{uploaded_map.user.email}"
            )
            if dry_run:
                continue

            with transaction.atomic():
                for permission in PERMISSIONS:
                    assign_perm(permission, uploaded_map.user, uploaded_map)
            updated += 1

        summary = f"processed={processed} updated={updated} skipped_already_has_perms={skipped}" + (
            " dry-run=1" if dry_run else ""
        )
        self.stdout.write(self.style.SUCCESS(summary))
