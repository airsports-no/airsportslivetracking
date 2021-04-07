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

server = 'traccar:5055'


# server = 'localhost:5055'


def build_traccar_track(filename, today: datetime.datetime, start_index: int = 0,
                        time_offset: datetime.timedelta = datetime.timedelta(minutes=0)):
    with open(filename, "r") as i:
        gpx = gpxpy.parse(i)
    positions = []
    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points[start_index:]:
                now = today.replace(hour=point.time.hour, minute=point.time.minute, second=point.time.second,
                                    microsecond=point.time.microsecond)
                now += time_offset
                positions.append((now, point.latitude, point.longitude))
    return positions


def load_data_traccar(tracks):
    def send(id, time, lat, lon, speed):
        params = (('id', id), ('timestamp', int(time)), ('lat', lat), ('lon', lon), ('speed', speed))
        requests.post("http://" + server + '/?' + urlencode(params))

    maximum_index = max([len(item) for item in tracks.values()])
    count = 0
    for index in range(0, maximum_index, 1):
        for contestant_name, positions in tracks.items():
            if len(positions) > index:
                count += 1
                stamp, latitude, longitude = positions[index]
                stamp = stamp.astimezone()
                send(contestant_name, time.mktime(stamp.timetuple()), latitude, longitude, 0)
                # print(stamp)
        print(count)
        time.sleep(0.1)


def insert_gpx_file(contestant_object: "Contestant", file, influx: InfluxFacade):
    gpx = gpxpy.parse(file)
    positions = []
    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points:
                positions.append({
                    "deviceId": contestant_object.tracker_device_id,
                    "latitude": point.latitude,
                    "longitude": point.longitude,
                    "altitude": point.elevation if point.elevation else 0,
                    "attributes": {"batteryLevel": 1.0},
                    "speed": 0.0,
                    "course": 0.0,
                    "deviceTime": point.time.isoformat()
                })
    generated_positions = influx.generate_position_data_for_contestant(contestant_object, positions)
    influx.put_position_data_for_contestant(contestant_object, generated_positions)
    q = Queue()
    for i in generated_positions:
        q.put(i)
    q.put(None)
    calculator = calculator_factory(contestant_object, q, live_processing=False)
    calculator.run()
    while not q.empty():
        q.get_nowait()

