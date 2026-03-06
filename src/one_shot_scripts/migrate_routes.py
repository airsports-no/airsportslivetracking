import os
import sys
import django
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

sys.path.append("/workspace/src")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "live_tracking_map.settings")
django.setup()

from display.models import NavigationTask
from display.utilities.navigation_task_type_definitions import (
    PRECISION,
    POKER,
    ANR_CORRIDOR,
    AIRSPORTS,
    AIRSPORT_CHALLENGE,
)
from display.utilities.coordinate_utilities import calculate_distance_lat_lon
from display.utilities.gate_definitions import FINISHPOINT


import json

WIDTHS_FILE = "inferred_corridor_widths.json"


def migrate():
    inferred_widths = {}
    if os.path.exists(WIDTHS_FILE):
        with open(WIDTHS_FILE, "r") as f:
            inferred_widths = json.load(f)
            print(f"Loaded {len(inferred_widths)} inferred widths from {WIDTHS_FILE}")

    tasks = NavigationTask.objects.filter(editable_route__isnull=False)
    count = tasks.count()
    print(f"Starting migration for {count} navigation tasks...")

    modified_count = 0
    for navigation_task in tasks:
        route = None
        try:
            if navigation_task.scorecard.calculator in (PRECISION, POKER):
                route = navigation_task.editable_route.create_precision_route(
                    navigation_task.route.use_procedure_turns, navigation_task.scorecard
                )
            elif navigation_task.scorecard.calculator == ANR_CORRIDOR:
                # Use inferred width if available, else fallback to current route width
                corridor_width = inferred_widths.get(str(navigation_task.id))
                if corridor_width is None:
                    corridor_width = navigation_task.route.corridor_width

                print(f"  Migrating ANR task {navigation_task.id} with width {corridor_width} NM")

                route = navigation_task.editable_route.create_anr_route(
                    navigation_task.route.rounded_corners,
                    corridor_width,
                    navigation_task.scorecard,
                )
            elif navigation_task.scorecard.calculator in (AIRSPORTS, AIRSPORT_CHALLENGE):
                route = navigation_task.editable_route.create_airsports_route(
                    navigation_task.route.rounded_corners, navigation_task.scorecard
                )

            if route:
                old_route = navigation_task.route
                navigation_task.route = route
                navigation_task.save()
                old_route.delete()
                modified_count += 1
                if navigation_task.scorecard.calculator != ANR_CORRIDOR:
                    print(f"  Migrated route for task id={navigation_task.id}")
        except Exception as e:
            print(f"Failed to migrate route for NavigationTask id={navigation_task.id}: {e}")

    print(f"Migration complete. Total tasks updated: {modified_count}")


if __name__ == "__main__":
    migrate()
