from datetime import datetime
import time
from urllib.parse import urlencode

import requests
server = "traccarclient.airsports.no"

def send(id, time, lat, lon, speed):
    params = (("id", id), ("timestamp", int(time)), ("lat", lat), ("lon", lon), ("speed", speed))
    response = requests.post("https://" + server + "/?" + urlencode(params))
    print(response.status_code)
    print(response.text)

send("wnRJiibMlfUD5QciSLFn5GQECbr6", time.mktime(datetime.now().timetuple()), 60, 11, 5)