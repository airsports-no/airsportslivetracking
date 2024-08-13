import datetime
import glob
import os
import sys
import time
from collections import OrderedDict
from unittest.mock import patch


if __name__ == "__main__":
    sys.path.append("../")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "live_tracking_map.settings")
    import django

    django.setup()

from traccar_facade import Traccar
from playback_tools.playback import build_traccar_track, load_data_traccar
from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
from display.models import (
    Crew,
    Team,
    Contest,
    Aeroplane,
    NavigationTask,
    Route,
    Contestant,
    ContestantTrack,
    Person,
    ContestTeam,
    TRACCAR,
    Club,
    TRACKING_DEVICE,
    EditableRoute,
)

maximum_index = 0
tracks = {}

contestants = {
    "Hans-Inge": (datetime.datetime(2020, 8, 1, 9, 50), 85, 2),
    # "Steinar": (datetime.datetime(2020, 8, 1, 9, 55), 80, 2),
    "Anders": (datetime.datetime(2020, 8, 1, 10, 0), 75, 6),
    "Frank-Olaf": (datetime.datetime(2020, 8, 1, 10, 5), 75, 6),
    "Jørgen": (datetime.datetime(2020, 8, 1, 10, 55), 75, 1),
    "Niklas": (datetime.datetime(2020, 8, 1, 9, 0), 75, 1),
    "Helge": (datetime.datetime(2020, 8, 1, 12, 55), 75, 1),
    # "Arild": (datetime.datetime(2020, 8, 1, 10, 10), 70, 6),
    "Bjørn": (datetime.datetime(2020, 8, 1, 9, 15), 70, 6),
    # "Espen": (datetime.datetime(2020, 8, 1, 11, 10), 70, 6),
    "Håkon": (datetime.datetime(2020, 8, 1, 11, 15), 70, 1),
    "Hedvig": (datetime.datetime(2020, 8, 1, 13, 5), 70, 2),
    "Jorge": (datetime.datetime(2020, 8, 1, 9, 10), 70, 1),
    "Kenneth": (datetime.datetime(2020, 8, 1, 9, 5), 70, 1),
    "Magnus": (datetime.datetime(2020, 8, 1, 11, 5), 70, 2),
    "Odin": (datetime.datetime(2020, 8, 1, 9, 20), 70, 1),
    "Ola": (datetime.datetime(2020, 8, 1, 13, 0), 70, 1),
    "Ole": (datetime.datetime(2020, 8, 1, 10, 25), 70, 1),
    "Stian": (datetime.datetime(2020, 8, 1, 13, 10), 70, 2),
    "Tim": (datetime.datetime(2020, 8, 1, 11, 0), 70, 2),
    "Tommy": (datetime.datetime(2020, 8, 1, 13, 15), 70, 1),
    "TorHelge": (datetime.datetime(2020, 8, 1, 12, 40), 70, 2),
}


traccar = Traccar.create_from_configuration()

devices = traccar.update_and_get_devices()
# Group ID = 1

for item in devices:
    if item["uniqueId"] in contestants.keys():
        traccar.delete_device(item["id"])
        traccar.create_device(item["name"], item["uniqueId"])
name = "Demo contest"
scorecard = get_default_scorecard()
original_contest = Contest.objects.filter(name=name).first()
if original_contest:
    original_contest.delete()
aeroplane, _ = Aeroplane.objects.get_or_create(registration="LN-YDB")
today = datetime.datetime.now(datetime.timezone.utc)
tomorrow = today + datetime.timedelta(days=1)
contest_start_time = today.replace(hour=0).astimezone()
contest_finish_time = tomorrow.astimezone()
contest = Contest.objects.create(
    name=name,
    is_public=True,
    start_time=contest_start_time,
    finish_time=contest_finish_time,
    time_zone="Europe/Oslo",
    location="60, 11",
)
with open("/data/NM.csv", "r") as file:
    with patch(
        "display.models.EditableRoute._create_route_and_thumbnail",
        lambda name, r: EditableRoute.objects.create(name=name, route=r),
    ):
        editable_route, _ = EditableRoute.create_from_csv("NM 2020", file.readlines()[1:])
        route = editable_route.create_precision_route(True, scorecard)

navigation_task = NavigationTask.create(
    name=name,
    contest=contest,
    route=route,
    original_scorecard=scorecard,
    start_time=contest_start_time,
    finish_time=contest_finish_time,
    is_public=True,
)
print(f"Created navigation task {navigation_task.pk}")
time.sleep(10)
contestant_map = {}
tracks = OrderedDict()
now = datetime.datetime.now(datetime.timezone.utc)
for index, file in enumerate(glob.glob("/data/tracks/*.gpx")[:-1]):
    print(file)
    contestant = os.path.splitext(os.path.basename(file))[0]
    if contestant in contestants:
        print(contestant)
        if contestant == "Frank-Olaf":
            member1, _ = Person.objects.get_or_create(
                first_name="Frank Olaf", last_name="Sem-Jacobsen", email="frankose@ifi.uio.no"
            )
            member2, _ = Person.objects.get_or_create(
                first_name="Espen", last_name="Grønstad", email="espengronstad@gmail.com"
            )
            crew, _ = Crew.objects.get_or_create(member1=member1, member2=member2)
        else:
            person = Person.objects.filter(first_name=contestant, last_name="Pilot").first()
            if not person:
                person = Person.objects.create(
                    first_name=contestant, last_name="Pilot", email=f"bogus{index}@domain.com"
                )
            crew = Crew.objects.filter(member1=person).first()
            if not crew:
                crew = Crew.objects.create(member1=person)

        team, _ = Team.objects.get_or_create(
            crew=crew, aeroplane=aeroplane, club=Club.objects.get_or_create(name="Kjeller Sportsflyklubb")[0]
        )
        start_time, speed, _ = contestants[contestant]
        ContestTeam.objects.get_or_create(
            team=team,
            contest=contest,
            defaults={"air_speed": speed, "tracking_service": TRACCAR, "tracker_device_id": contestant},
        )
        start_time = start_time - datetime.timedelta(hours=2)
        start_time = start_time.astimezone()
        start_time = today.replace(
            hour=start_time.hour, minute=start_time.minute, second=start_time.second, tzinfo=start_time.tzinfo
        )
        start_time_offset = now - start_time

        start_time += start_time_offset

        minutes_starting = 6
        # start_time = start_time.replace(tzinfo=datetime.timezone.utc)
        contestant_object = Contestant(
            navigation_task=navigation_task,
            route=navigation_task.route,
            team=team,
            takeoff_time=start_time,
            finished_by_time=start_time + datetime.timedelta(hours=3),
            tracker_start_time=start_time - datetime.timedelta(minutes=3),
            tracker_device_id=contestant,
            contestant_number=index,
            minutes_to_starting_point=minutes_starting,
            air_speed=speed,
            tracking_device=TRACKING_DEVICE,
            wind_direction=165,
            wind_speed=8,
        )
        print(contestant_object.pk)
        contestant_map[contestant] = contestant_object
        print(f"{contestant_object} {start_time}")
        # with open(file, "r") as i:
        #     insert_gpx_file(contestant_object, i, influx)

        tracks[contestant] = (
            build_traccar_track(file, today, start_index=0, time_offset=start_time_offset),
            contestant_object.absolute_gate_times.get("SP"),
        )
tracks = OrderedDict(sorted(tracks.items(), key=lambda item: contestants[item[0]][1], reverse=True))
print("Sleeping for 10 seconds")
time.sleep(10)
load_data_traccar(tracks, offset=300, leadtime=90, round_sleep=0.8, contestant_map=contestant_map)
