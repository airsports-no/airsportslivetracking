from django.core.management.base import BaseCommand

from display.flight_order_and_maps.effective_route_rendering import get_effective_route_waypoints
from display.models import Contestant
from display.utilities.gate_definitions import CIRCLE_CENTER

# Mirrors gate_calculator.py's create_gates(): these waypoint types are never actually crossed as
# a gate, so the first waypoint NOT in this set (and not on a curved segment) is the same one
# create_gates() treats as gates[0] / the starting line.
NON_CROSSABLE_WAYPOINT_TYPES = ("dummy", "to", "ldg", CIRCLE_CENTER)


class Command(BaseCommand):
    help = (
        "Backfill ContestantTrack.passed_starting_gate for contestants tracked before the "
        "orchestrator fix that started setting it (StartingLinePassedEvent handling in "
        "display.calculators.orchestrator.Orchestrator.handle_event) - every row from before "
        "that fix stays permanently False otherwise, since nothing else derives it "
        "retroactively (unlike passed_finish_gate, which was already being set correctly). "
        "Derives it the same way live tracking does: True iff the contestant has a recorded "
        "ActualGateTime for their route's first real gate."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only report how many rows would change, without writing anything.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        checked = 0
        updated = 0
        skipped_no_gate = 0

        candidates = (
            Contestant.objects.filter(contestanttrack__passed_starting_gate=False)
            .select_related("contestanttrack", "navigation_task", "contestanttaskconfiguration")
            .order_by("pk")
        )
        for contestant in candidates:
            checked += 1
            waypoints = get_effective_route_waypoints(
                contestant.navigation_task, contestant=contestant, include_contestant_declarations=True
            )
            starting_waypoint = next(
                (
                    waypoint
                    for waypoint in waypoints
                    if waypoint.type not in NON_CROSSABLE_WAYPOINT_TYPES and not getattr(waypoint, "on_curved_segment", False)
                ),
                None,
            )
            if starting_waypoint is None:
                # e.g. a 2.B3 Duration task, authored as just takeoff/landing gates with no
                # route waypoints at all - gate_calculator.create_gates() has nothing to cross
                # either, so there's no "starting gate" event to backfill.
                skipped_no_gate += 1
                continue
            if contestant.actualgatetime_set.filter(gate=starting_waypoint.name).exists():
                updated += 1
                if not dry_run:
                    contestant.contestanttrack.passed_starting_gate = True
                    contestant.contestanttrack.save(update_fields=["passed_starting_gate"])

        prefix = "Would update" if dry_run else "Updated"
        self.stdout.write(
            self.style.SUCCESS(
                f"Checked {checked} contestant(s) with passed_starting_gate=False. {prefix} {updated}. "
                f"{skipped_no_gate} had no crossable starting gate (nothing to backfill)."
            )
        )
