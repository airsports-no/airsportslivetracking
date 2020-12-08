# coding: utf-8
import datetime
import glob
import os

from traccar_facade import Traccar

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "live_tracking_map.settings")
    import django

    django.setup()
from display.models import Team, Aeroplane, Contest, Track, Contestant, Scorecard, TraccarCredentials
from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard

configuration = TraccarCredentials.objects.get()
traccar = Traccar.create_from_configuration(configuration)

Contest.objects.all().delete()
aeroplane = Aeroplane.objects.first()
contest_start_time = datetime.datetime(2020, 8, 1, 6, 0, 0).astimezone()
contest_finish_time = datetime.datetime(2020, 8, 1, 16, 0, 0).astimezone()
contest = Contest.objects.create(name="NM contest",
                                 track=Track.objects.get(name="NM 2020"),
                                 start_time=contest_start_time, finish_time=contest_finish_time, wind_direction=165,
                                 wind_speed=8)
contestants = {
    "Anders": (datetime.datetime(2020, 8, 1, 10, 0), 75, 1),
    "Arild": (datetime.datetime(2020, 8, 1, 10, 10), 70, 1),
    "Bjørn": (datetime.datetime(2020, 8, 1, 9, 15), 70, 1),
    "Espen": (datetime.datetime(2020, 8, 1, 11, 10), 70, 1),
    "Frank-Olaf": (datetime.datetime(2020, 8, 1, 10, 5), 75, 1),
    "Håkon": (datetime.datetime(2020, 8, 1, 11, 15), 70, 1),
    "Hans-Inge": (datetime.datetime(2020, 8, 1, 9, 50), 85, 2),
    "Hedvig": (datetime.datetime(2020, 8, 1, 13, 5), 70, 2),
    "Helge": (datetime.datetime(2020, 8, 1, 12, 55), 75, 1),
    "Jorge": (datetime.datetime(2020, 8, 1, 9, 10), 70, 1),
    "Jørgen": (datetime.datetime(2020, 8, 1, 10, 55), 75, 1),
    "Kenneth": (datetime.datetime(2020, 8, 1, 9, 5), 70, 1),
    "Magnus": (datetime.datetime(2020, 8, 1, 11, 5), 70, 2),
    "Niklas": (datetime.datetime(2020, 8, 1, 9, 0), 75, 1),
    "Odin": (datetime.datetime(2020, 8, 1, 9, 20), 70, 1),
    "Ola": (datetime.datetime(2020, 8, 1, 13, 0), 70, 1),
    "Ole": (datetime.datetime(2020, 8, 1, 10, 25), 70, 1),
    "Steinar": (datetime.datetime(2020, 8, 1, 9, 55), 80, 2),
    "Stian": (datetime.datetime(2020, 8, 1, 13, 10), 70, 2),
    "Tim": (datetime.datetime(2020, 8, 1, 11, 0), 70, 2),
    "Tommy": (datetime.datetime(2020, 8, 1, 13, 15), 70, 1),
    "TorHelge": (datetime.datetime(2020, 8, 1, 12, 40), 70, 2)
}
traccar.delete_all_devices()
for item in contestants.keys():
    traccar.create_device(item, item)

scorecard=get_default_scorecard()

for index, file in enumerate(glob.glob("../data/tracks/*.kml")):
    contestant_name = os.path.splitext(os.path.basename(file))[0]
    team, _ = Team.objects.get_or_create(pilot=contestant_name, navigator="", aeroplane=aeroplane)
    start_time, speed, contestant_class = contestants[contestant_name]
    print(contestant_name)
    print(start_time)
    start_time = start_time - datetime.timedelta(hours=2)
    start_time = start_time.astimezone()
    print(start_time)
    # if contestant_class == 1:
    #     scorecard = class_one_scorecard
    # else:
    #     scorecard = class_two_scorecard
    contestant = Contestant.objects.create(contest=contest, team=team, takeoff_time=start_time,
                                           finished_by_time=start_time + datetime.timedelta(hours=2),
                                           traccar_device_name=contestant_name, contestant_number=index,
                                           scorecard=scorecard, minutes_to_starting_point=6, air_speed=speed)
print(contest.pk)
# for contestant in Contestant.objects.filter(contest__pk = 7):
#     contestant.takeoff_time = contestant.contest.start_time
#     contestant.finished_by_time = contestant.contest.finish_time
