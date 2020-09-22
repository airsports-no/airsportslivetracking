import os
from datetime import datetime

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "live_tracking_map.settings")
    import django

    django.setup()
from influx_facade import InfluxFacade

influx = InfluxFacade()
for item in influx.get_annotations_for_contest(15, datetime(2020, 9, 21, 0).astimezone()).get_points(tags = {"contestant":"220"}):
    print(item)
