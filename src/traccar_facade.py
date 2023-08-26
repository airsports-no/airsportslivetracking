import datetime
import logging
import time
from typing import List, Dict, TYPE_CHECKING, Optional, Tuple

import requests
from requests import Session

from live_tracking_map.settings import (
    TRACCAR_PROTOCOL,
    TRACCAR_HOST,
    TRACCAR_PASSWORD,
    TRACCAR_USERNAME,
    TRACCAR_PORT,
)

if TYPE_CHECKING:
    from display.models import Contestant

logger = logging.getLogger(__name__)

SESSION_LIFETIME = 3600


class Traccar:
    def __init__(self, protocol, address, username, password):
        self.protocol = protocol
        self.address = address
        self.username = username
        self.password = password
        self.base = "{}://{}".format(self.protocol, self.address)
        self.last_session_time = None
        self._session = None
        self.device_map = {}
        self.unique_id_map = {}

    @classmethod
    def create_from_configuration(cls) -> "Traccar":
        return cls(
            TRACCAR_PROTOCOL,
            f"{TRACCAR_HOST}:{TRACCAR_PORT}",
            TRACCAR_USERNAME,
            TRACCAR_PASSWORD,
        )

    @property
    def session(self) -> Session:
        if not self._session or time.time() - SESSION_LIFETIME > self.last_session_time:
            if self._session:
                try:
                    self._session.close()
                except:
                    logger.exception(f"Failed closing traccar session {self._session}")
            self._session = self.get_authenticated_session()
        return self._session

    def get_authenticated_session(self) -> Session:
        session = requests.Session()
        response = session.post(
            self.base + "/api/session",
            data={"email": self.username, "password": self.password},
        )
        # response = session.get(string)
        if response.status_code != 200:
            raise Exception("Failed authenticating session: {}".format(response.text))
        logger.info("Successfully connected to Traccar")
        self.last_session_time = time.time()
        return session

    def get_positions_for_device_id(
        self,
        device_id: int,
        start_time: datetime.datetime,
        finish_time: datetime.datetime,
    ) -> List[Dict]:
        """
         {
        "id": 4565767,
        "attributes":
        {
            "batteryLevel": 53.0,
            "distance": 80.05,
            "totalDistance": 355900.28,
            "motion": true
        },
        "deviceId": 11942,
        "type": null,
        "protocol": "osmand",
        "serverTime": "2021-09-17T10:56:54.000+00:00",
        "deviceTime": "2021-09-17T10:55:03.000+00:00",
        "fixTime": "2021-09-17T10:55:03.000+00:00",
        "outdated": false,
        "valid": true,
        "latitude": 52.82202,
        "longitude": 8.7318365,
        "altitude": 455.001,
        "speed": 77.2231,
        "course": 214.099,
        "address": null,
        "accuracy": 5.599999904632568,
        "network": null
        }
        """
        response = self.session.get(
            self.base + "/api/positions",
            params={
                "deviceId": device_id,
                "from": start_time.isoformat(),
                "to": finish_time.isoformat(),
            },
        )
        logger.debug(f"Fetching data from traccar: {response.url}")
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Failed fetching positions for device {device_id}, {response.text}")
            return []

    def get_device_ids_for_contestant(self, contestant: "Contestant") -> List[int]:
        devices = []
        for name in contestant.get_tracker_ids() + contestant.get_simulator_tracker_ids():
            try:
                devices.append(self.unique_id_map[name])
            except KeyError:
                self.get_device_map()
                try:
                    devices.append(self.unique_id_map[name])
                except KeyError:
                    logger.error(f"Failed to find device ID for unique ID {name}")
        return devices

    def update_and_get_devices(self) -> Optional[List]:
        response = self.session.get(self.base + "/api/devices")
        try:
            return response.json()
        except:
            logger.exception(f"Failed fetching device list {response.status_code}: {response.text}")
            return None

    def delete_device(self, device_id):
        response = self.session.delete(self.base + "/api/devices/{}".format(device_id))
        # print(response)
        # print(response.text)
        return response.status_code == 204

    def get_groups(self) -> List[Dict]:
        response = self.session.get(self.base + "/api/groups")
        if response.status_code == 200:
            return response.json()

    def create_group(self, group_name) -> Dict:
        response = self.session.post(self.base + "/api/groups", json={"name": group_name})
        if response.status_code == 200:
            return response.json()

    def get_shared_group_id(self):
        groups = self.get_groups()
        for group in groups:
            if group["name"] == "GlobalDevices":
                return group["id"]
        return self.create_group("GlobalDevices")["id"]

    def create_device(self, device_name, identifier):
        response = self.session.post(
            self.base + "/api/devices",
            json={
                "uniqueId": identifier,
                "name": device_name,
                "groupId": self.get_shared_group_id(),
            },
        )
        # print(response)
        # print(response.text)
        if response.status_code == 200:
            return response.json()

    def add_device_to_shared_group(self, deviceId):
        response = self.session.put(
            self.base + f"/api/devices/{deviceId}/",
            json={"groupId": self.get_shared_group_id(), "id": deviceId},
        )
        if response.status_code == 200:
            return True

    def get_device(self, identifier) -> Optional[Dict]:
        response = self.session.get(self.base + "/api/devices/?uniqueId={}".format(identifier))
        if response.status_code == 200:
            devices = response.json()
            try:
                return devices[0]
            except IndexError:
                return None
        return None

    def update_device_name(self, device_name: str, identifier: str) -> bool:
        existing_device = self.get_device(identifier)
        logger.debug(f" Found existing device {existing_device}")
        if existing_device is None:
            logger.warning("Failed fetching assumed to be existing device {}".format(identifier))
            return False
        key = existing_device["id"]
        response = self.session.put(
            self.base + f"/api/devices/{key}/",
            json={"name": device_name, "id": key, "uniqueId": identifier},
        )
        if response.status_code != 200:
            logger.error(f"Failed updating device name because of: {response.status_code} {response.text}")
            return False
        logger.debug(f"Updated device name for {identifier} to {device_name}")
        return True

    def get_or_create_device(self, device_name, identifier) -> Tuple[Dict, bool]:
        existing_device = self.get_device(identifier)
        if existing_device is None:
            return self.create_device(device_name, identifier), True
        return existing_device, False

    def delete_all_devices(self):
        if devices := self.update_and_get_devices():
            for item in devices:
                self.delete_device(item["id"])
        return devices

    def get_device_map(self) -> Dict:
        if dmap := self.update_and_get_devices():
            self.device_map = {item["id"]: item["uniqueId"] for item in dmap}
        self.unique_id_map = {value: key for key, value in self.device_map.items()}
        return self.device_map
