import os


if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "live_tracking_map.settings")
    import django

    django.setup()

from traccar_facade import Traccar
from influx_facade import InfluxFacade

traccar = Traccar()
deleted = traccar.delete_all_devices()
for item in deleted:
    traccar.create_device(item)

influx = InfluxFacade()
influx.drop_database()
influx.create_database()
