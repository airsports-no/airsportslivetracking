import datetime
from typing import List, Dict

import requests
from requests import Session

from secret_configuration import TRACCAR_ADDRESS, TOKEN, PROTOCOL


class Traccar:
    def __init__(self):
        self.base = "{}://{}".format(PROTOCOL, TRACCAR_ADDRESS)
        self.session = self.get_authenticated_session()

    def get_authenticated_session(self) -> Session:
        session = requests.Session()
        string = self.base + "/api/session?token={}".format(TOKEN)
        response = session.get(string)
        if response.status_code != 200:
            raise Exception("Failed authenticating session: {}".format(response.text))
        return session

    def get_devices(self) -> List:
        return self.session.get(self.base + "/api/devices").json()

    def get_device_map(self) -> Dict:
        return {item["id"]: item["name"] for item in self.get_devices()}
