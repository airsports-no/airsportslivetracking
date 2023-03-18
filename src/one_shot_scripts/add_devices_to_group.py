import os


if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "live_tracking_map.settings")
    import django

    django.setup()

from traccar_facade import Traccar

traccar = Traccar.create_from_configuration()

devices = traccar.update_and_get_devices()
# Group ID = 1
for item in devices:
    print(item)
    if traccar.add_device_to_shared_group(item["id"]):
        print("Success")
    else:
        print("Failure")
