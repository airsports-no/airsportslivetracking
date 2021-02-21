import datetime
import time
from urllib.parse import urlencode

import requests
from SimConnect import *

TRACKING_ID = ""

# Create SimConnect link
sm = SimConnect()
print("Got link")
# Note the default _time is 2000 to be refreshed every 2 seconds
aq = AircraftRequests(sm, _time=2000)
print("Created aircraft requests")

def send(id, time, lat, lon, speed):
    params = (('id', id), ('timestamp', int(time)), ('lat', lat), ('lon', lon), ('speed', speed))
    print(f"Posting position: {params}")
    response=requests.post("https://traccar.airsports.no/?" + urlencode(params))
    print(response.status_code)
    print(response.text)


while True:
    latitude = aq.get("PLANE_LATITUDE")
    longitude = aq.get("PLANE_LONGITUDE")
    now = datetime.datetime.now().replace(tzinfo=datetime.timezone.utc)
    print(now)
    send(TRACKING_ID, time.mktime(now.timetuple()), latitude, longitude, 0)
    time.sleep(2)