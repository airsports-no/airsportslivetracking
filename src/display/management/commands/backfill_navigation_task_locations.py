import time

from django.core.management.base import BaseCommand

from display.models import NavigationTask


class Command(BaseCommand):
    help = (
        "Backfill the cached reverse-geocode (_nominatim) for every NavigationTask that doesn't "
        "have one yet, so country-based statistics (display.services.admin_system_stats."
        "get_country_stats) don't keep showing them as 'Unknown' forever - they otherwise only "
        "ever resolve lazily, on whichever admin happens to load that one task's detail page. "
        "Hits the external Nominatim service, rate-limited to 1 request/second by its usage "
        "policy - a management command run deliberately (and resumable: already-geocoded tasks "
        "are always skipped) rather than a data migration, which would run automatically on "
        "every deploy and has no business making slow external network calls."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only report how many tasks would be processed, without contacting Nominatim.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Process at most this many tasks (for a cautious first batch).",
        )
        parser.add_argument(
            "--delay",
            type=float,
            default=1.1,
            help="Seconds to wait between requests. Nominatim's usage policy caps at 1/second.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        limit = options["limit"]
        delay = options["delay"]

        # _nominatim is a pickled blob column, not reliably filterable at the DB level (this
        # mirrors how admin_system_stats.get_country_stats and the legacy
        # statistics_utilities.get_system_statistics both read it - fetch and check in Python
        # instead of trying to query into the pickle). NavigationTask count is in the low
        # thousands, so iterating all of them is cheap.
        candidates = []
        skipped_no_location = 0
        for task in NavigationTask.objects.select_related("route").order_by("pk"):
            if task._nominatim:
                continue
            if task.route.get_location() is None:
                skipped_no_location += 1
            else:
                candidates.append(task)

        if limit is not None:
            candidates = candidates[:limit]

        limit_note = " (capped by --limit; more may remain)" if limit is not None else ""
        self.stdout.write(
            f"{len(candidates)} navigation task(s) to resolve{limit_note}. {skipped_no_location} more have no "
            "cached geocode but also no route location to resolve from (e.g. a 2.A6 Turnpoint hunt/2.A7 Circle "
            "route with no waypoints or takeoff/landing gates) - permanently unresolvable this way."
        )
        if dry_run:
            return

        resolved = 0
        failed = 0
        for index, task in enumerate(candidates, start=1):
            try:
                task._geo_reference()
            except Exception as exc:
                failed += 1
                self.stderr.write(self.style.ERROR(f"[{index}/{len(candidates)}] task {task.pk} ({task}): {exc}"))
                continue

            task.refresh_from_db(fields=["_nominatim"])
            if task._nominatim:
                resolved += 1
                country = task._nominatim.get("address", {}).get("country", "?")
                self.stdout.write(f"[{index}/{len(candidates)}] task {task.pk} ({task}) -> {country}")
            else:
                failed += 1
                self.stdout.write(
                    self.style.WARNING(f"[{index}/{len(candidates)}] task {task.pk} ({task}): lookup returned nothing")
                )

            if index < len(candidates):
                time.sleep(delay)

        self.stdout.write(self.style.SUCCESS(f"Done: {resolved} resolved, {failed} failed."))
