import datetime
import time
from queue import Queue
from typing import TYPE_CHECKING
from urllib.parse import urlencode

import dateutil
from django.core.cache import cache

import requests
import gpxpy

from display.calculators.calculator_factory import calculator_factory
from influx_facade import InfluxFacade

if TYPE_CHECKING:
    from display.models import Contestant

server = "traccar:5055"


# server = 'localhost:5055'


def build_traccar_track(
    filename,
    today: datetime.datetime,
    start_index: int = 0,
    starting_time: datetime.datetime = None,
    leadtime_seconds: int = 0,
    time_offset: datetime.timedelta = datetime.timedelta(minutes=0),
):
    with open(filename, "r") as i:
        gpx = gpxpy.parse(i)
    positions = []
    lead = datetime.timedelta(seconds=leadtime_seconds)
    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points[start_index:]:
                now = today.replace(
                    hour=point.time.hour,
                    minute=point.time.minute,
                    second=point.time.second,
                    microsecond=point.time.microsecond,
                )
                now += time_offset
                if starting_time is None or now > starting_time - lead:
                    positions.append((now.astimezone(), point.latitude, point.longitude))
    return positions


def load_data_traccar(tracks, offset=30, leadtime=0, round_sleep=0.2):
    def send(id, time, lat, lon, speed):
        params = (("id", id), ("timestamp", int(time)), ("lat", lat), ("lon", lon), ("speed", speed))
        requests.post("http://" + server + "/?" + urlencode(params))

    next_times = {}
    index = 0
    for contestant_name, (positions, start_time) in tracks.items():
        next_times[contestant_name] = start_time - datetime.timedelta(seconds=index * offset + leadtime)
        index += 1
    count = 0
    time_step = 2
    first_round = True
    while True:
        remaining = False
        for contestant_name, (positions, start_time) in tracks.items():
            next_times[contestant_name] += datetime.timedelta(seconds=time_step)
            while len(positions) > 0 and positions[0][0] < next_times[contestant_name]:
                count += 1
                stamp, latitude, longitude = positions.pop(0)
                if not first_round:
                    send(contestant_name, time.mktime(stamp.timetuple()), latitude, longitude, 0)
            remaining = remaining or len(positions) > 0
        print(count)
        first_round = False
        time.sleep(round_sleep)
        if not remaining:
            break


def insert_gpx_file(contestant_object: "Contestant", file, influx: InfluxFacade):
    gpx = gpxpy.parse(file)
    positions = []
    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points:
                if point.time:
                    positions.append(
                        {
                            "deviceId": contestant_object.tracker_device_id,
                            "latitude": point.latitude,
                            "longitude": point.longitude,
                            "altitude": point.elevation if point.elevation else 0,
                            "attributes": {"batteryLevel": 1.0},
                            "speed": 0.0,
                            "course": 0.0,
                            "device_time": point.time,
                        }
                    )
    # generated_positions = influx.generate_position_data_for_contestant(contestant_object, positions)
    # influx.put_position_data_for_contestant(contestant_object, positions)
    q = Queue()
    for i in positions:
        q.put(i)
    q.put(None)
    calculator = calculator_factory(contestant_object, q, live_processing=False)
    calculator.run()
    while not q.empty():
        q.get_nowait()
