import glob
import os
import time
from urllib.parse import urlencode

import gpxpy
import requests

server = 'traccar:5055'
# server = 'localhost:5055'

maximum_index = 0
tracks = {}
implemented = ["2017_101"]
for file in glob.glob("demo_contests/2017_WPFC/*_Results_*.gpx"):
    print(file)
    base = os.path.splitext(os.path.basename(file))[0]
    contestant = "2017_{}".format(base.split("_")[0])
    print(contestant)
    if contestant not in implemented:
        continue
    with open(file, "r") as i:
        gpx = gpxpy.parse(i)
    positions = []
    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points:
                positions.append((point.time, point.latitude, point.longitude))
    tracks[contestant] = positions
    maximum_index = max(maximum_index, len(positions))
    print(contestant)
    print(len(positions))
print(len(tracks))

def send(id, time, lat, lon, speed):
    params = (('id', id), ('timestamp', int(time)), ('lat', lat), ('lon', lon), ('speed', speed))
    requests.post("http://" + server + '/?' + urlencode(params))


print(maximum_index)
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
