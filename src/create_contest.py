import glob
import os
from datetime import datetime, timedelta, timezone

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "live_tracking_map.settings")
    import django

    django.setup()
from display.models import Team, Aeroplane, Contest, Track, Contestant

aeroplane = Aeroplane.objects.first()
now = datetime.now(timezone.utc).astimezone()
contest = Contest.objects.create(name="Test contest",
                                 track=Track.objects.get(name="NM 2020"), server_address="home.kolaf.net:8082",
                                 server_token="FydcKTi7Lnat5wHhMGTCs0ykEpNAAOdj",
                                 start_time=now, finish_time=now + timedelta(hours=2))

for index, file in enumerate(glob.glob("../data/tracks/*.kml")):
    print(index)
    contestant_name = os.path.splitext(os.path.basename(file))[0]
    team, _ = Team.objects.get_or_create(pilot=contestant_name, navigator="", aeroplane=aeroplane)
    contestant = Contestant.objects.create(contest=contest, team=team, takeoff_time=now,
                                           finished_by_time=now + timedelta(hours=2),
                                           traccar_device_name=contestant_name, contestant_number=index)
print(contest.pk)
# for contestant in Contestant.objects.filter(contest__pk = 7):
#     contestant.takeoff_time = contestant.contest.start_time
#     contestant.finished_by_time = contestant.contest.finish_time
