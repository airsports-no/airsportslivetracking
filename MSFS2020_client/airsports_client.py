import datetime
import time
from urllib.parse import urlencode

from SimConnect import *
import requests

TRACKING_ID = "0x2nXGmVbQ7s5hJ3Y49xATolpSOf"


def send(id, time, lat, lon, speed, altitude):
    params = (
        ('id', id), ('timestamp', int(time)), ('lat', lat), ('lon', lon), ('speed', speed), ('altitude', altitude))
    print(f"Posting position: {params}")
    response = requests.post("https://traccar.airsports.no/?" + urlencode(params))
    print(response.status_code)
    print(response.text)


def run():
    failed = True
    while failed:
        failed = False
        try:
            # Create SimConnect link
            sm = SimConnect()
        except ConnectionError:
            print("Failed connecting")
            return
            # failed = True
    print("Got link")
    # Note the default _time is 2000 to be refreshed every 2 seconds
    aq = AircraftRequests(sm, _time=2000)
    print("Created aircraft requests")

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


if __name__ == "__main__":
    run()
