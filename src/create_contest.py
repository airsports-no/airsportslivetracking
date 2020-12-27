import glob
import os
from datetime import datetime, timedelta, timezone

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "live_tracking_map.settings")
    import django

    django.setup()
from display.models import Team, Aeroplane, NavigationTask, Route, Contestant

NavigationTask.objects.all().delete()
aeroplane = Aeroplane.objects.first()
now = datetime.now(timezone.utc).astimezone()
navigation_task = NavigationTask.objects.create(name="Test navigation_task",
                                                route=Route.objects.get(name="NM 2020"), server_address="home.kolaf.net:8082",
                                                server_token="FydcKTi7Lnat5wHhMGTCs0ykEpNAAOdj",
                                                start_time=now, finish_time=now + timedelta(hours=2))

for index, file in enumerate(glob.glob("../data/tracks/*.kml")):
    contestant_name = os.path.splitext(os.path.basename(file))[0]
    team, _ = Team.objects.get_or_create(pilot=contestant_name, navigator="", aeroplane=aeroplane)
    contestant = Contestant.objects.create(navigation_task=navigation_task, team=team, takeoff_time=now,
                                           finished_by_time=now + timedelta(hours=2),
                                           tracker_device_id=contestant_name, contestant_number=index)
print(navigation_task.pk)
# for contestant in Contestant.objects.filter(contest__pk = 7):
#     contestant.takeoff_time = contestant.navigation_task.start_time
#     contestant.finished_by_time = contestant.navigation_task.finish_time
