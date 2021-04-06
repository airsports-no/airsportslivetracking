import datetime
import logging
from plistlib import Dict
from typing import List, Union, Optional

import dateutil
from influxdb import InfluxDBClient
from influxdb.resultset import ResultSet

from display.models import Contestant
from websocket_channels import WebsocketFacade

host = "influx"
port = 8086
user = "airsport"
dbname = "airsport"
password = "notsecret"

logger = logging.getLogger(__name__)


class InfluxFacade:
    def __init__(self):
        self.client = InfluxDBClient(host, port, user, password, dbname)
        self.websocket_facade = WebsocketFacade()

    def generate_position_block_for_contestant(self, contestant: Contestant, position_data: Dict,
                                               device_time: datetime.datetime) -> Dict:
        return {
            "measurement": "device_position",
            "tags": {
                "contestant": contestant.pk,
                "navigation_task": contestant.navigation_task_id,
                "device_id": position_data["deviceId"]
            },
            "time": device_time.isoformat(),
            "fields": {
                "latitude": float(position_data["latitude"]),
                "longitude": float(position_data["longitude"]),
                "altitude": float(position_data["altitude"]),
                "battery_level": float(position_data["attributes"].get("batteryLevel", -1.0)),
                "speed": float(position_data["speed"]),
                "course": float(position_data["course"])
            }
        }

    def generate_position_data_for_contestant(self, contestant: Contestant, positions: List) -> List:
        data = []
        for position_data in positions:
            device_time = dateutil.parser.parse(position_data["deviceTime"])
            data.append(self.generate_position_block_for_contestant(contestant, position_data, device_time))
        return data

    def put_position_data_for_contestant(self, contestant: "Contestant", data: List):
        self.websocket_facade.transmit_navigation_task_position_data(contestant, data)
        self.client.write_points(data)

    def clear_data_for_contestant(self, contestant_id: int):
        self.client.delete_series(tags={"contestant": str(contestant_id)})

    def get_positions_for_contest(self, navigation_task_pk, from_time: Union[datetime.datetime, str]) -> ResultSet:
        if isinstance(from_time, datetime.datetime):
            from_time = from_time.isoformat()
        query = "select * from device_position where navigation_task=$navigation_task and time>$from_time;"
        bind_params = {'navigation_task': str(navigation_task_pk), 'from_time': from_time}
        response = self.client.query(query, bind_params=bind_params)
        return response

    def get_number_of_positions_in_database(self) -> int:
        query = "select count(*) from device_position;"
        response = self.client.query(query)
        return response

    def get_annotations_for_navigation_task(self, navigation_task_pk,
                                            from_time: Union[datetime.datetime, str]) -> ResultSet:
        if isinstance(from_time, datetime.datetime):
            from_time = from_time.isoformat()
        query = "select * from annotation where navigation_task=$navigation_task and time>$from_time;"
        bind_params = {'navigation_task': str(navigation_task_pk), 'from_time': from_time}
        response = self.client.query(query, bind_params=bind_params)
        return response

    def get_positions_for_contestant(self, contestant_pk, from_time: Union[datetime.datetime, str],
                                     limit: Optional[int] = None) -> ResultSet:
        if isinstance(from_time, datetime.datetime):
            from_time = from_time.isoformat()
        query = "select * from device_position where contestant=$contestant and time>$from_time"
        bind_params = {'contestant': str(contestant_pk), 'from_time': from_time}
        if limit is not None:
            query += " limit $limit"
            bind_params["limit"] = limit
        query += ";"
        response = self.client.query(query, bind_params=bind_params)
        return response

    def get_latest_position_for_contestant(self, contestant_pk) -> ResultSet:
        query = "select * from device_position where contestant=$contestant ORDER BY desc LIMIT 1"
        bind_params = {'contestant': str(contestant_pk)}
        query += ";"
        response = self.client.query(query, bind_params=bind_params)
        return response

    def get_annotations_for_contestant(self, contestant_pk, from_time: Union[datetime.datetime, str],
                                       until_time: Union[datetime.datetime, str]) -> ResultSet:
        if isinstance(from_time, datetime.datetime):
            from_time = from_time.isoformat()
        if isinstance(until_time, datetime.datetime):
            until_time = until_time.isoformat()
        query = "select * from annotation where contestant=$contestant and time>$from_time and time<=$until_time;"
        bind_params = {'contestant': str(contestant_pk), 'from_time': from_time, "until_time": until_time}
        response = self.client.query(query, bind_params=bind_params)
        return response

    def drop_database(self):
        self.client.drop_database(dbname)

    def create_database(self):
        self.client.create_database(dbname)
