import datetime
import glob
import os
import time
from urllib.parse import urlencode

import gpxpy
import requests

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "live_tracking_map.settings")
    import django

    django.setup()

from display.convert_flightcontest_gpx import create_precision_route_from_gpx
from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
from display.models import Crew, Team, Contest, Aeroplane, NavigationTask, Route, Contestant, ContestantTrack, Person, \
    ContestTeam, TRACCAR
from display.calculators.calculator_factory import calculator_factory
from playback_tools import insert_gpx_file


server = 'traccar:5055'
# server = 'localhost:5055'

maximum_index = 0
tracks = {}

contestants = {
    "2017_101": (datetime.datetime(2015, 1, 1, 7, 30), 80, 8),
    "2017_102": (datetime.datetime(2015, 1, 1, 7, 33), 70, 9),
    "2017_103": (datetime.datetime(2015, 1, 1, 7, 36), 70, 9),
    "2017_104": (datetime.datetime(2015, 1, 1, 7, 39), 70, 9),
    "2017_105": (datetime.datetime(2015, 1, 1, 7, 42), 70, 9),
    "2017_106": (datetime.datetime(2015, 1, 1, 7, 45), 70, 9),
    "2017_107": (datetime.datetime(2015, 1, 1, 7, 48), 70, 9),
    "2017_108": (datetime.datetime(2015, 1, 1, 7, 51), 70, 9),
    "2017_109": (datetime.datetime(2015, 1, 1, 7, 54), 70, 9),
    "2017_110": (datetime.datetime(2015, 1, 1, 7, 57), 70, 9),
    "2017_111": (datetime.datetime(2015, 1, 1, 8, 00), 70, 9),
    "2017_112": (datetime.datetime(2015, 1, 1, 8, 3), 70, 9),
    "2017_113": (datetime.datetime(2015, 1, 1, 8, 6), 70, 9),
    "2017_114": (datetime.datetime(2015, 1, 1, 8, 9), 70, 9),
    "2017_115": (datetime.datetime(2015, 1, 1, 8, 12), 70, 9),
    "2017_116": (datetime.datetime(2015, 1, 1, 8, 15), 70, 9),
    "2017_117": (datetime.datetime(2015, 1, 1, 8, 18), 70, 9),
    "2017_118": (datetime.datetime(2015, 1, 1, 8, 21), 70, 9),
    "2017_119": (datetime.datetime(2015, 1, 1, 8, 24), 70, 9),
    "2017_120": (datetime.datetime(2015, 1, 1, 8, 27), 70, 9),
    "2017_121": (datetime.datetime(2015, 1, 1, 8, 30), 70, 9),
    "2017_122": (datetime.datetime(2015, 1, 1, 8, 33), 70, 9),
    "2017_124": (datetime.datetime(2015, 1, 1, 8, 39), 70, 9),

}
scorecard = get_default_scorecard()

Contest.objects.filter(name="WPFC 2017").delete()
aeroplane = Aeroplane.objects.first()
contest_start_time = datetime.datetime(2014, 8, 1, 6, 0, 0).astimezone()
contest_finish_time = datetime.datetime(2014, 8, 1, 16, 0, 0).astimezone()
contest = Contest.objects.create(name="WPFC 2017", is_public=True, start_time=contest_start_time,
                                 finish_time=contest_finish_time)
with open("../data/demo_contests/2017_WPFC/Route-1-Blue.gpx", "r") as file:
    route = create_precision_route_from_gpx(file, True)
navigation_task = NavigationTask.create(name="Route-1-Blue ", contest=contest,
                                                route=route, original_scorecard=scorecard,
                                                start_time=contest_start_time, finish_time=contest_finish_time,
                                                is_public=True)

implemented = ["2017_{}".format(number) for number in range(101, 125)]
for file in glob.glob("../data/demo_contests/2017_WPFC/*_Results_*.gpx"):
    print(file)
    base = os.path.splitext(os.path.basename(file))[0]
    number = int(base.split("_")[0])
    contestant = "2017_{}".format(number)
    print(contestant)
    if contestant not in implemented:
        continue

    crew, _ = Crew.objects.get_or_create(
        member1=Person.objects.get_or_create(first_name=contestant, last_name="Pilot")[0])
    team, _ = Team.objects.get_or_create(crew=crew, aeroplane=aeroplane)
    start_time, speed, minutes_starting = contestants[contestant]
    ContestTeam.objects.get_or_create(team=team, contest=contest,
                                      defaults={"air_speed": speed, "tracking_service": TRACCAR,
                                                "tracker_device_id": contestant})
    print(start_time)
    start_time = start_time.replace(tzinfo=datetime.timezone.utc)
    contestant_object = Contestant.objects.create(navigation_task=navigation_task, team=team, takeoff_time=start_time,
                                                  finished_by_time=start_time + datetime.timedelta(hours=2),
                                                  tracker_start_time=start_time - datetime.timedelta(minutes=30),
                                                  tracker_device_id=contestant, contestant_number=number,
                                                  minutes_to_starting_point=minutes_starting,
                                                  air_speed=speed,
                                                  wind_direction=160, wind_speed=18)
    print(navigation_task.pk)
