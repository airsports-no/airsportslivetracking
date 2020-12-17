import time
from urllib.parse import urlencode

import requests
import gpxpy

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
