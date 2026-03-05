import os
import sys
import django
import json
import logging

# Setup Django
sys.path.append("/workspace/src")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "live_tracking_map.settings")
django.setup()

from display.models import NavigationTask
from display.utilities.navigation_task_type_definitions import ANR_CORRIDOR
from display.utilities.coordinate_utilities import calculate_distance_lat_lon
from display.utilities.gate_definitions import FINISHPOINT

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

OUTPUT_FILE = "inferred_corridor_widths.json"

def generate():
    tasks = NavigationTask.objects.all()
    widths = {}
    
    print(f"Analyzing {tasks.count()} tasks for inferred widths...")
    
    for task in tasks:
        if task.scorecard.calculator == ANR_CORRIDOR:
            # Default to stored width
            width = task.route.corridor_width
            
            # Try to infer from finish point gate
            for waypoint in task.route.waypoints:
                if waypoint.type == FINISHPOINT:
                    if len(waypoint.gate_line) == 2:
                        dist_m = calculate_distance_lat_lon(waypoint.gate_line[0], waypoint.gate_line[1])
                        # Round to 1 decimal place as requested previously
                        inferred_width = round(dist_m / 1852.0, 1)
                        if abs(inferred_width - width) > 0.001:
                            print(f"  Task {task.id}: Inferred {inferred_width} NM (stored {width} NM)")
                        width = inferred_width
                    break
            
            widths[str(task.id)] = width

    with open(OUTPUT_FILE, "w") as f:
        json.dump(widths, f, indent=2)
    
    print(f"Generated {len(widths)} entries in {OUTPUT_FILE}")

if __name__ == "__main__":
    generate()
