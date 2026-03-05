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


def migrate():
    tasks = NavigationTask.objects.filter(pk=3111)
    count = tasks.count()
    print(f"Starting migration for {count} navigation tasks...")

    modified_count = 0
    for navigation_task in tasks:
        if navigation_task.editable_route is None:
            continue
        route = None
        try:
            if navigation_task.scorecard.calculator in (PRECISION, POKER):
                route = navigation_task.editable_route.create_precision_route(
                    navigation_task.route.use_procedure_turns, navigation_task.scorecard
                )
            elif navigation_task.scorecard.calculator == ANR_CORRIDOR:
                corridor_width = navigation_task.route.corridor_width

                # # Find finish point gate length to infer corridor width
                # for waypoint in navigation_task.route.waypoints:
                #     if waypoint.type == FINISHPOINT:
                #         if len(waypoint.gate_line) == 2:
                #             dist_m = calculate_distance_lat_lon(waypoint.gate_line[0], waypoint.gate_line[1])
                #             inferred_width = round(dist_m / 1852.0, 1)
                #             if abs(inferred_width - corridor_width) > 0.001 or navigation_task.pk == 3111:
                #                 print(
                #                     f"    Inferred corridor width {inferred_width:.4f} NM from finish gate (stored: {corridor_width:.4f} NM) for task id={navigation_task.id}"
                #                 )
                #                 corridor_width = inferred_width
                #         break

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
                print(f"  Migrated route for task id={navigation_task.id}")
        except Exception as e:
            print(f"Failed to migrate route for NavigationTask id={navigation_task.id}: {e}")

    print(f"Migration complete. Total tasks updated: {modified_count}")


if __name__ == "__main__":
    migrate()
