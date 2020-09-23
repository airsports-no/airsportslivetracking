import os
from datetime import datetime

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "live_tracking_map.settings")
    import django

    django.setup()
from influx_facade import InfluxFacade

influx = InfluxFacade()
for item in influx.get_positions_for_contestant(901, datetime(2020, 8, 1, 0).astimezone()).get_points():
    print(item)
