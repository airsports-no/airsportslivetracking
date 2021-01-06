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

from display.convert_flightcontest_gpx import create_route_from_csv
from playback_tools import build_traccar_track, load_data_traccar, insert_gpx_file
from traccar_facade import Traccar
from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
from display.models import Crew, Team, Contest, Aeroplane, NavigationTask, Route, Contestant, ContestantTrack, \
    TraccarCredentials, Person, ContestTeam, TRACCAR, Club
from influx_facade import InfluxFacade

influx = InfluxFacade()

maximum_index = 0
tracks = {}

contestants = {
    "Anders": (datetime.datetime(2020, 8, 1, 10, 0), 75, 6),
    # "Arild": (datetime.datetime(2020, 8, 1, 10, 10), 70, 6),
    "Bjørn": (datetime.datetime(2020, 8, 1, 9, 15), 70, 6),
    # "Espen": (datetime.datetime(2020, 8, 1, 11, 10), 70, 6),
    "Frank-Olaf": (datetime.datetime(2020, 8, 1, 10, 5), 75, 6),
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

configuration = TraccarCredentials.objects.get()

traccar = Traccar.create_from_configuration(configuration)

deleted = traccar.update_and_get_devices()
# Group ID = 1
for item in deleted:
    traccar.delete_device(item["id"])
    traccar.create_device(item["name"], item["uniqueId"])

scorecard = get_default_scorecard()
original_contest = Contest.objects.filter(name="NM 2020").first()
if original_contest:
    for contestant in Contestant.objects.filter(navigation_task__contest=original_contest):
        influx.clear_data_for_contestant(contestant.pk)

    original_contest.delete()
aeroplane, _ = Aeroplane.objects.get_or_create(registration="LN-YDB")
contest_start_time = datetime.datetime(2020, 8, 1, 6, 0, 0).astimezone()
contest_finish_time = datetime.datetime(2020, 8, 1, 16, 0, 0).astimezone()
contest = Contest.objects.create(name="NM 2020", is_public=True, start_time=contest_start_time,
                                 finish_time=contest_finish_time)
with open("/data/NM.csv", "r") as file:
    route = create_route_from_csv("NM 2020", file.readlines()[1:], True)

navigation_task = NavigationTask.objects.create(name="NM 2020 ", contest=contest,
                                                route=route,
                                                scorecard=scorecard,
                                                start_time=contest_start_time, finish_time=contest_finish_time,
                                                is_public=True)

tracks = {}
for index, file in enumerate(glob.glob("../data/tracks/*.gpx")):
    print(file)
    contestant = os.path.splitext(os.path.basename(file))[0]
    if contestant in contestants:
        print(contestant)
        if contestant == "Frank-Olaf":
            member1, _ = Person.objects.get_or_create(first_name="Frank Olaf", last_name="Sem-Jacobsen")
            member2, _ = Person.objects.get_or_create(first_name="Espen", last_name="Grønstad")
            crew, _ = Crew.objects.get_or_create(member1=member1, member2=member2)
        else:
            person = Person.objects.filter(first_name=contestant, last_name="Pilot").first()
            if not person:
                person = Person.objects.create(first_name=contestant, last_name="Pilot")
            crew, _ = Crew.objects.get_or_create(
                member1=person)

        team, _ = Team.objects.get_or_create(crew=crew, aeroplane=aeroplane,
                                             club=Club.objects.get(name="Kjeller Sportsflyklubb"))
        start_time, speed, _ = contestants[contestant]
        ContestTeam.objects.get_or_create(team=team, contest=contest,
                                          defaults={"air_speed": speed, "tracking_service": TRACCAR,
                                                    "tracker_device_id": contestant})
        start_time = start_time - datetime.timedelta(hours=2)
        start_time = start_time.astimezone()
        minutes_starting = 6
        # start_time = start_time.replace(tzinfo=datetime.timezone.utc)
        contestant_object = Contestant.objects.create(navigation_task=navigation_task, team=team,
                                                      takeoff_time=start_time,
                                                      finished_by_time=start_time + datetime.timedelta(hours=2),
                                                      tracker_start_time=start_time - datetime.timedelta(minutes=30),
                                                      tracker_device_id=contestant, contestant_number=index,
                                                      minutes_to_starting_point=minutes_starting,
                                                      air_speed=speed,
                                                      wind_direction=165, wind_speed=8)
        print(navigation_task.pk)
        # with open(file, "r") as i:
        #     insert_gpx_file(contestant_object, i, influx)

        tracks[contestant] = build_traccar_track(file)
print("Sleeping for 10 seconds")
time.sleep(10)
load_data_traccar(tracks)
