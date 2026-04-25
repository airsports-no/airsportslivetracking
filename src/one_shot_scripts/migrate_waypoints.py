import os
import sys
import django

# Set up Django environment
sys.path.append('/src')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'live_tracking_map.settings')
django.setup()

from display.models.route import Route
from display.waypoint import Waypoint

def migrate_waypoint(old_wp):
    """
    Creates a new Waypoint object and copies all attributes from the old one.
    This ensures that the pickled object reflects the current Waypoint class structure.
    """
    if old_wp is None:
        return None
    
    if not hasattr(old_wp, '__dict__') or not hasattr(old_wp, 'name'):
        print(f"  Warning: Expected Waypoint object, got {type(old_wp)}")
        return old_wp # Return as is if it's not a Waypoint-like object
    
    new_wp = Waypoint(old_wp.name)
    # Copy all dictionary attributes to handle any field
    for key, value in old_wp.__dict__.items():
        setattr(new_wp, key, value)
    
    return new_wp

def run():
    routes = Route.objects.all()
    count = routes.count()
    print(f"Starting migration for {count} routes...")
    
    for i, route in enumerate(routes):
        try:
            modified = False
            
            # Migrate waypoints
            if route.waypoints:
                new_waypoints = [migrate_waypoint(wp) for wp in route.waypoints]
                route.waypoints = new_waypoints
                modified = True
            
            # Migrate takeoff_gates
            if route.takeoff_gates:
                new_takeoff = [migrate_waypoint(wp) for wp in route.takeoff_gates]
                route.takeoff_gates = new_takeoff
                modified = True
                
            # Migrate landing_gates
            if route.landing_gates:
                new_landing = [migrate_waypoint(wp) for wp in route.landing_gates]
                route.landing_gates = new_landing
                modified = True
            
            if modified:
                route.save()
            
            if (i + 1) % 10 == 0 or (i + 1) == count:
                print(f"Processed {i + 1}/{count} routes...")
                
        except Exception as e:
            print(f"Error processing route {route.id} ({route.name}): {e}")

    print("Migration completed.")

if __name__ == "__main__":
    run()
