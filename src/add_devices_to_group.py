import os


if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "live_tracking_map.settings")
    import django

    django.setup()

from display.models import TraccarCredentials
from traccar_facade import Traccar

configuration = TraccarCredentials.objects.get()
traccar = Traccar.create_from_configuration(configuration)

devices = traccar.update_and_get_devices()
# Group ID = 1
for item in devices:
    print(item)
    traccar.add_device_to_shared_group(item["id"])
