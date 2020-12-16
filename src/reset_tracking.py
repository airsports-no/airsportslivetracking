import os


if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "live_tracking_map.settings")
    import django

    django.setup()

from traccar_facade import Traccar
from display.models import TraccarCredentials, ContestantTrack, Contestant
from influx_facade import InfluxFacade

configuration = TraccarCredentials.objects.get()

traccar = Traccar.create_from_configuration(configuration)

deleted = traccar.update_and_get_devices()
# Group ID = 1
for item in deleted:
    traccar.delete_device(item["id"])
    traccar.create_device(item["name"], item["uniqueId"])

influx = InfluxFacade()
print("Dropping database")
influx.drop_database()
print("Creating new database")
influx.create_database()
print("Deleting all tracks")
ContestantTrack.objects.all().delete()
for item in Contestant.objects.filter(contestanttrack__isnull=True):
    ContestantTrack.objects.create(contestant = item)
