import time
from typing import TYPE_CHECKING
from urllib.parse import urlencode
from django.core.cache import cache

import requests
import gpxpy

from display.calculators.calculator_factory import calculator_factory

if TYPE_CHECKING:
    from display.models import Contestant

server = 'traccar:5055'


# server = 'localhost:5055'


def build_traccar_track(filename):
    with open(filename, "r") as i:
        gpx = gpxpy.parse(i)
    positions = []
    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points:
                positions.append((point.time, point.latitude, point.longitude))
    return positions


def load_data_traccar(tracks):
    def send(id, time, lat, lon, speed):
        params = (('id', id), ('timestamp', int(time)), ('lat', lat), ('lon', lon), ('speed', speed))
        requests.post("http://" + server + '/?' + urlencode(params))

    maximum_index = max([len(item) for item in tracks.values()])
    count = 0
    for index in range(0, maximum_index, 4):
        for contestant_name, positions in tracks.items():
            if len(positions) > index:
                count += 1
                stamp, latitude, longitude = positions[index]
                stamp = stamp.astimezone()
                send(contestant_name, time.mktime(stamp.timetuple()), latitude, longitude, 0)
                # print(stamp)
        print(count)
        time.sleep(0.5)


def insert_gpx_file(contestant_object: "Contestant", file, influx):
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
    influx.put_data(generated_positions)
    calculator = calculator_factory(contestant_object, influx, live_processing=False)
    calculator.start()
    new_positions = []
    for position in generated_positions:
        data = position["fields"]
        data["time"] = position["time"]
        new_positions.append(data)
    new_positions.append(None)
    calculator.add_positions(new_positions)
    calculator.join()
    from display.models import CONTESTANT_CACHE_KEY
    key = "{}.{}.*".format(CONTESTANT_CACHE_KEY, contestant_object.pk)
    # logger.info("Clearing cache for {}".format(contestant))
    cache.delete_pattern(key)
