import datetime
from urllib.parse import urlencode

import requests

server = "traccar.airsports.no"


def send(id, timestamp, lat, lon, speed):
    params = (
        ("id", id),
        ("timestamp", int(timestamp)),
        ("lat", lat),
        ("lon", lon),
        ("speed", speed),
    )
    response = requests.post("https://" + server + "/?" + urlencode(params))
    print(response.status_code)
    print(response.text)


# stamp = datetime.datetime(2022, 5, 16, tzinfo=datetime.timezone.utc)
stamp = datetime.datetime.now(datetime.timezone.utc)
print(stamp)
send("Z8gTiLd32Vt0NGcB7pef5WUeUIfc", stamp.timestamp(), 60, 11, 0)
