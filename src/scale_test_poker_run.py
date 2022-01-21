import datetime
import os
import time
from urllib.parse import urlencode

import requests

from display.calculators.tests.utilities import load_traccar_track
from traccar_facade import Traccar

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "live_tracking_map.settings")
    import django

    django.setup()

from display.models import Crew, Team, Contest, Aeroplane, NavigationTask, Route, Contestant, ContestantTrack, \
    TraccarCredentials, Person, ContestTeam, TRACCAR, Club, TRACKING_DEVICE, TRACKING_PILOT

import os
TRACCAR_HOST = os.environ.get("TRACCAR_HOST", "traccar")
server = f"{TRACCAR_HOST}:5055"

NUMBER_OF_CONTESTANTS = 50
TIME_OFFSET = datetime.timedelta(seconds=20)
tracks = {}


configuration = TraccarCredentials.objects.get()

traccar = Traccar.create_from_configuration(configuration)

traccar.get_device_map()

def create_contestant(index, start_time, navigation_task):
    person, _ = Person.objects.get_or_create(first_name=f"test_person_{index}", last_name=f"test_person_{index}",
                                             email=f"test_{index}@email.com")
    traccar.delete_device(traccar.unique_id_map.get(person.app_tracking_id))
    traccar.create_device(person.first_name, person.app_tracking_id)
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

    remaining = True
    count = 0
    while remaining:
        count += 1
        remaining = False
        start = time.time()
        for tracking_id, positions in tracks.items():
            while len(positions) > 0 and positions[0][0] < datetime.datetime.now(datetime.timezone.utc):
                stamp, latitude, longitude = positions.pop(0)
                send(tracking_id, time.mktime(stamp.timetuple()), latitude, longitude, 0)
            remaining = remaining or len(positions) > 0
        finish = time.time()
        duration = finish - start
        if duration < 1:
            time.sleep(1 - duration)
        if count%10==0:
            print(f"Cycle duration: {finish - start:.02f}")


navigation_task = NavigationTask.get(pk=314)
navigation_task.contestant_set.all().delete()
track = load_traccar_track("/data/tracks/espen_poker.csv")
actual_start_time = datetime.datetime.now(datetime.timezone.utc)
current_start_time = track[0][0]
print(f"actual_start_time {actual_start_time}")
print(f"current_start_time {current_start_time}")
start_difference = actual_start_time - current_start_time
print(f"start_difference {start_difference}")

current_offset = datetime.timedelta()
print(f"current_offset {current_offset}")

for number in range(NUMBER_OF_CONTESTANTS):
    contestant_track = offset_times(track, start_difference + current_offset)
    contestant = create_contestant(number, contestant_track[0][0], navigation_task)
    tracks[contestant.team.crew.member1.simulator_tracking_id] = contestant_track
    current_offset += TIME_OFFSET
for item in tracks.values():
    print(item[0][0])
load_data_traccar(tracks, offset=60)
