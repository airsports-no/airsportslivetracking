import datetime
import time
from urllib.parse import urlencode

import requests
from SimConnect import *

TRACKING_ID = "0x2nXGmVbQ7s5hJ3Y49xATolpSOf"

# Create SimConnect link
sm = SimConnect()
print("Got link")
# Note the default _time is 2000 to be refreshed every 2 seconds
aq = AircraftRequests(sm, _time=2000)
print("Created aircraft requests")


def send(id, time, lat, lon, speed, altitude):
    params = (
    ('id', id), ('timestamp', int(time)), ('lat', lat), ('lon', lon), ('speed', speed), ('altitude', altitude))
    print(f"Posting position: {params}")
    response = requests.post("https://traccar.airsports.no/?" + urlencode(params))
    print(response.status_code)
    print(response.text)


while True:
    altitude = aq.get("PLANE_ALTITUDE")
    latitude = aq.get("PLANE_LATITUDE")
    longitude = aq.get("PLANE_LONGITUDE")
    velocity = aq.get("GROUND_VELOCITY")
    now = datetime.datetime.now().replace(tzinfo=datetime.timezone.utc)
    print(now)
    if longitude != 0 and latitude != 0:
        send(TRACKING_ID, time.mktime(now.timetuple()), latitude, longitude, velocity, altitude)
    time.sleep(2)
