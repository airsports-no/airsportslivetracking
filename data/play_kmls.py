import datetime
import glob
import os
import time
from urllib.parse import urlencode

import requests
from fastkml import kml

server = '192.168.1.2:5055'

maximum_index = 0
tracks = {}
for file in glob.glob("tracks/*.kml"):
    contestant = os.path.splitext(os.path.basename(file))[0]
    with open(file, "r") as input_kml:
        document = input_kml.read()
    kml_document = kml.KML()
    kml_document.from_string(document)
    document = list(kml_document.features())[0]
    placemark = list(list(document.features())[0].features())[0]
    geometry = placemark.geometry
    positions = list(zip(*geometry.xy))
    tracks[contestant] = positions
    maximum_index = max(maximum_index, len(positions))
    print(len(positions))


def send(id, time, lat, lon, speed):
    params = (('id', id), ('timestamp', int(time)), ('lat', lat), ('lon', lon), ('speed', speed))
    requests.post("http://" + server + '/?' + urlencode(params))


print(tracks)
print(maximum_index)
for index in range(0, maximum_index, 10):
    for contestant_name, positions in tracks.items():
        if len(positions) > index:
            longitude, latitude = positions[index]
            send(contestant_name, time.mktime(datetime.datetime.now().timetuple()), latitude, longitude, 0)
    time.sleep(0.5)
