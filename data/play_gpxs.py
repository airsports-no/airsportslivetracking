import datetime
import glob
import os
import time
from urllib.parse import urlencode

import dateutil
import gpxpy
import requests
from fastkml import kml

server = '192.168.1.2:5055'

maximum_index = 0
tracks = {}
for file in glob.glob("tracks/*.gpx"):
    contestant = os.path.splitext(os.path.basename(file))[0]
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


# print(tracks)
# print(maximum_index)
# count = 0
# for index in range(0, maximum_index, 4):
#     for contestant_name, positions in tracks.items():
#         if len(positions) > index:
#             count += 1
#             stamp, latitude, longitude = positions[index]
#             stamp = stamp.astimezone()
#             send(contestant_name, time.mktime(stamp.timetuple()), latitude, longitude, 0)
#             # print(stamp)
#     print(count)
#     time.sleep(0.5)
