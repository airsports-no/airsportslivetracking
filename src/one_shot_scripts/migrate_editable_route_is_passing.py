import os
import sys
import django

# Setup Django
sys.path.append("/workspace/src")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "live_tracking_map.settings")
django.setup()

from display.models import EditableRoute

def migrate():
    routes = EditableRoute.objects.all()
    count = routes.count()
    print(f"Starting migration for {count} editable routes...")
    
    modified_count = 0
    for editable_route in routes:
        route_data = editable_route.route
        if not isinstance(route_data, dict) or "features" not in route_data:
            continue
            
        modified = False
        for feature in route_data.get("features", []):
            props = feature.get("properties", {})
            if props.get("featureType") == "route_waypoint":
                # Sync isPassing with isTiming. Default to True if missing.
                is_timing = props.get("isTiming", True)
                props["isPassing"] = is_timing
                modified = True
        
        if modified:
            editable_route.route = route_data
            editable_route.save(update_fields=["route"])
            modified_count += 1
            if modified_count % 10 == 0:
                print(f"Processed {modified_count} modified routes...")

    print(f"Migration complete. Total modified: {modified_count}")

if __name__ == "__main__":
    migrate()
