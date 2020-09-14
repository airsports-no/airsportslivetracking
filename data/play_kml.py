import datetime
import time
from urllib.parse import urlencode

import requests
from fastkml import kml

id = '123456789012345'
server = '192.168.1.2:5055'

with open("Frank-Olaf.kml", "r") as input_kml:
    document = input_kml.read()

kml_document = kml.KML()
kml_document.from_string(document)
document = list(kml_document.features())[0]
placemark = list(list(document.features())[0].features())[0]
geometry = placemark.geometry
positions = list(zip(*geometry.xy))
print(len(positions))


def send(time, lat, lon, speed):
    params = (('id', id), ('timestamp', int(time)), ('lat', lat), ('lon', lon), ('speed', speed))
    requests.post("http://" + server + '/?' + urlencode(params))


for longitude, latitude in positions[1400:]:
    send(time.mktime(datetime.datetime.now().timetuple()), latitude, longitude, 0)
    time.sleep(0.5)
