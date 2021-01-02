import datetime
from typing import List, Dict, TYPE_CHECKING, Optional

import requests
from requests import Session

if TYPE_CHECKING:
    from display.models import TraccarCredentials


class Traccar:
    def __init__(self, protocol, address, token):
        self.protocol = protocol
        self.address = address
        self.token = token
        self.base = "{}://{}".format(self.protocol, self.address)
        self.session = self.get_authenticated_session()
        self.device_map = None

    @classmethod
    def create_from_configuration(cls, configuration: "TraccarCredentials") -> "Traccar":
        return cls(configuration.protocol, configuration.address, configuration.token)

    def get_authenticated_session(self) -> Session:
        session = requests.Session()
        string = self.base + "/api/session?token={}".format(self.token)
        response = session.get(string)
        if response.status_code != 200:
            raise Exception("Failed authenticating session: {}".format(response.text))
        return session

    def update_and_get_devices(self) -> List:
        return self.session.get(self.base + "/api/devices").json()

    def delete_device(self, device_id):
        response = self.session.delete(self.base + "/api/devices/{}".format(device_id))
        print(response)
        print(response.text)
        return response.status_code == 204

    def create_device(self, device_name, identifier):
        response = self.session.post(self.base + "/api/devices", json={"uniqueId": identifier, "name": device_name})
        print(response)
        print(response.text)
        if response.status_code == 200:
            return response.json()

    def get_device(self, identifier) -> Optional[Dict]:
        response = self.session.get(self.base + "/api/devices/?uniqueId={}".format(identifier))
        if response.status_code == 200:
            devices = response.json()
            try:
                return devices[0]
            except IndexError:
                return None
        return None

    def get_or_create_device(self, device_name, identifier) -> Dict:
        existing_device = self.get_device(identifier)
        if existing_device is None:
            return self.create_device(device_name, identifier)
        return existing_device

    def delete_all_devices(self):
        devices = self.update_and_get_devices()
        for item in devices:
            self.delete_device(item["id"])
        return devices

    def get_device_map(self) -> Dict:
        self.device_map = {item["id"]: item["name"] for item in self.update_and_get_devices()}
        return self.device_map
