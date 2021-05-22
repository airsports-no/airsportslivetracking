import datetime
import glob
import os
import time
from collections import OrderedDict
from urllib.parse import urlencode

import gpxpy
import requests

from display.calculators.calculator_utilities import load_track_points_traccar_csv
from display.calculators.tests.utilities import load_traccar_track

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "live_tracking_map.settings")
    import django

    django.setup()

from display.convert_flightcontest_gpx import create_precision_route_from_csv
from traccar_facade import Traccar
from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
from display.models import Crew, Team, Contest, Aeroplane, NavigationTask, Route, Contestant, ContestantTrack, \
    TraccarCredentials, Person, ContestTeam, TRACCAR, Club, TRACKING_DEVICE, TRACKING_PILOT
from influx_facade import InfluxFacade

influx = InfluxFacade()
server = 'traccar:5055'

NUMBER_OF_CONTESTANTS = 50
TIME_OFFSET = datetime.timedelta(seconds=60)
tracks = {}


def create_contestant(index, start_time, navigation_task):
    person, _ = Person.objects.get_or_create(first_name=f"test_person_{index}", last_name=f"test_person_{index}",
                                             email=f"test_{index}@email.com")
    aircraft = Aeroplane.objects.get(registration="LN-YDB")
    club, _ = Club.objects.get_or_create(name="Kjeller Sportsflyklubb")
    crew, _ = Crew.objects.get_or_create(member1=person)
    team, _ = Team.objects.get_or_create(crew=crew, aeroplane=aircraft, club=club)
    return Contestant.objects.create(navigation_task=navigation_task, team=team,
                                     takeoff_time=start_time,
                                     finished_by_time=start_time + datetime.timedelta(hours=3),
                                     tracker_start_time=start_time - datetime.timedelta(minutes=3),
                                     contestant_number=index,
                                     minutes_to_starting_point=0,
                                     air_speed=70, tracking_device=TRACKING_PILOT,
                                     wind_direction=0, wind_speed=0)


def offset_times(track, offset):
    new_track = []
    for position in track:
        new_track.append((position[0] + offset, *position[1:]))
    return new_track


def load_data_traccar(tracks, offset=30, leadtime=0):
    def send(id, time, lat, lon, speed):
        params = (('id', id), ('timestamp', int(time)), ('lat', lat), ('lon', lon), ('speed', speed))
        requests.post("http://" + server + '/?' + urlencode(params))

    while True:
        remaining = False
        for tracking_id, positions in tracks.items():
            while len(positions) > 0 and positions[0][0] < datetime.datetime.now(datetime.timezone.utc):
                stamp, latitude, longitude = positions.pop(0)
                send(tracking_id, time.mktime(stamp.timetuple()), latitude, longitude, 0)
            remaining = remaining or len(positions) > 0


navigation_task = NavigationTask.objects.get(pk=314)
track = load_traccar_track("/data/tracks/espen_poker.csv")
actual_start_time = datetime.datetime.now(datetime.timezone.utc)
current_start_time = track[0][0]
start_difference = actual_start_time - current_start_time
current_offset = start_difference

for number in range(NUMBER_OF_CONTESTANTS):
    contestant_track = offset_times(track, start_difference + current_offset)
    contestant = create_contestant(number, contestant_track[0][0], navigation_task)
    tracks[contestant.team.crew.member1.simulator_tracking_id] = contestant_track
    current_offset += TIME_OFFSET
for item in tracks.values():
    print(item[0][0])
load_data_traccar(tracks, offset=60, leadtime=90)
