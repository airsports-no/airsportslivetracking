import datetime
import json
import logging
from typing import TYPE_CHECKING, Dict, List, Tuple, Optional

import dateutil
import pickle
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from redis import StrictRedis

from display.calculators.positions_and_gates import Position
from display.models import Contestant, ContestTeam, Task, TaskTest, MyUser, Team, ANOMALY
from display.serialisers import (
    ContestantTrackSerialiser,
    ContestTeamNestedSerialiser,
    TaskSerialiser,
    TaskTestSerialiser,
    ContestResultsDetailsSerialiser,
    TeamNestedSerialiser,
    TrackAnnotationSerialiser,
    ScoreLogEntrySerialiser,
    GateCumulativeScoreSerialiser,
    PlayingCardSerialiser, PositionSerialiser, GateScoreIfCrossedNowSerialiser, DangerLevelSerialiser,
)
from live_tracking_map.settings import REDIS_GLOBAL_POSITIONS_KEY, REDIS_HOST, REDIS_PORT, REDIS_PASSWORD

logger = logging.getLogger(__name__)


class DateTimeEncoder(json.JSONEncoder):
    """
    Helper class to correctly encode datetime objects to json.
    """

    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            encoded_object = obj.isoformat()
        else:
            encoded_object = json.JSONEncoder.default(self, obj)
        return encoded_object


def generate_contestant_data_block(
        contestant: "Contestant",
        positions: List = None,
        annotations: List = None,
        log_entries: List = None,
        latest_time: datetime.datetime = None,
        gate_scores: List = None,
        playing_cards: List = None,
        include_contestant_track: bool = False,
        gate_times: Dict = None,
        gate_score_if_crossed_now: Dict = None,
        danger_level: Dict = None
):
    if not hasattr(contestant, "contestanttrack"):
        include_contestant_track = False
    data = {
        "contestant_id": contestant.id,
        "positions": positions or [],
        "annotations": annotations,
        "score_log_entries": log_entries,
        "gate_scores": gate_scores,
        "playing_cards": playing_cards,
        "latest_time": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "gate_times": gate_times,
        "gate_score_if_crossed_now": gate_score_if_crossed_now,
        "danger_level": danger_level,
        "contestant_track": ContestantTrackSerialiser(contestant.contestanttrack).data
        if include_contestant_track
        else None,
    }
    if latest_time:
        data["progress"] = contestant.calculate_progress(latest_time)
    return data


class WebsocketFacade:
    def __init__(self):
        self.channel_layer = get_channel_layer()
        self.redis = StrictRedis(REDIS_HOST, REDIS_PORT, password=REDIS_PASSWORD)

    def transmit_annotations(self, contestant: "Contestant"):
        group_key = "tracking_{}".format(contestant.navigation_task.pk)
        annotation_data = TrackAnnotationSerialiser(contestant.trackannotation_set.all(), many=True).data
        channel_data = generate_contestant_data_block(contestant, annotations=annotation_data)
        async_to_sync(self.channel_layer.group_send)(
            group_key, {"type": "tracking.data", "data": json.dumps(channel_data, cls=DateTimeEncoder)}
        )

    def transmit_score_log_entry(self, contestant: "Contestant"):
        group_key = "tracking_{}".format(contestant.navigation_task.pk)
        # Only push anomalous score logs to the GUI. Everything will be visible as annotations or on the contestant
        # table administration page.
        log_entries = ScoreLogEntrySerialiser(contestant.scorelogentry_set.filter(type=ANOMALY), many=True).data
        channel_data = generate_contestant_data_block(contestant, log_entries=log_entries)
        async_to_sync(self.channel_layer.group_send)(
            group_key, {"type": "tracking.data", "data": json.dumps(channel_data, cls=DateTimeEncoder)}
        )

    def transmit_gate_score_entry(self, contestant: "Contestant"):
        group_key = "tracking_{}".format(contestant.navigation_task.pk)
        gate_scores = GateCumulativeScoreSerialiser(contestant.gatecumulativescore_set.all(), many=True).data
        channel_data = generate_contestant_data_block(contestant, gate_scores=gate_scores)
        async_to_sync(self.channel_layer.group_send)(
            group_key, {"type": "tracking.data", "data": json.dumps(channel_data, cls=DateTimeEncoder)}
        )

    def transmit_playing_cards(self, contestant: "Contestant"):
        group_key = "tracking_{}".format(contestant.navigation_task.pk)
        playing_cards = PlayingCardSerialiser(contestant.playingcard_set.all(), many=True).data
        channel_data = generate_contestant_data_block(contestant, playing_cards=playing_cards)
        async_to_sync(self.channel_layer.group_send)(
            group_key, {"type": "tracking.data", "data": json.dumps(channel_data, cls=DateTimeEncoder)}
        )

    def transmit_basic_information(self, contestant: "Contestant"):
        group_key = "tracking_{}".format(contestant.navigation_task.pk)
        channel_data = generate_contestant_data_block(contestant, include_contestant_track=True)
        async_to_sync(self.channel_layer.group_send)(
            group_key, {"type": "tracking.data", "data": json.dumps(channel_data, cls=DateTimeEncoder)}
        )

    def transmit_navigation_task_position_data(self, contestant: "Contestant", positions: List["Position"]):
        if len(positions) == 0:
            return
        position_data = PositionSerialiser(positions, many=True).data
        channel_data = generate_contestant_data_block(
            contestant,
            positions=position_data,
            latest_time=positions[-1].time,
        )
        group_key = "tracking_{}".format(contestant.navigation_task.pk)
        # for position in positions:
        #     logger.debug(f"Transmitting position ID {position.position_id} for device ID {position.device_id}")

        async_to_sync(self.channel_layer.group_send)(
            group_key, {"type": "tracking.data", "data": json.dumps(channel_data, cls=DateTimeEncoder)}
        )

    def transmit_gate_score_if_crossed_now(self, contestant: "Contestant", waypoint_name: str, seconds: float,
                                           final: bool, missed: bool):
        channel_data = generate_contestant_data_block(contestant,
                                                      gate_score_if_crossed_now=GateScoreIfCrossedNowSerialiser(
                                                          {"seconds": seconds, "final": final, "missed": missed,
                                                           "waypoint_name": waypoint_name}).data)
        group_key = "tracking_{}".format(contestant.navigation_task.pk)
        async_to_sync(self.channel_layer.group_send)(
            group_key, {"type": "tracking.data", "data": json.dumps(channel_data, cls=DateTimeEncoder)}
        )

    def transmit_danger_estimate_and_accumulated_penalty(self, contestant: "Contestant", danger_level: float,
                                                         accumulated_score: 0):
        channel_data = generate_contestant_data_block(contestant,
                                                      danger_level=DangerLevelSerialiser(
                                                          {"danger_level": danger_level,
                                                           "accumulated_score": accumulated_score}).data)
        group_key = "tracking_{}".format(contestant.navigation_task.pk)
        async_to_sync(self.channel_layer.group_send)(
            group_key, {"type": "tracking.data", "data": json.dumps(channel_data, cls=DateTimeEncoder)}
        )

    def transmit_airsports_position_data(self, global_tracking_name: str,
                                         position_data: Dict,
                                         device_time: datetime.datetime,
                                         navigation_task_id: Optional[int], ):
        data = {
            "name": global_tracking_name,
            "time": device_time,
            "latitude": float(position_data["latitude"]),
            "longitude": float(position_data["longitude"]),
            "altitude": float(position_data["altitude"]) * 3.28084,  # feet
            "speed": float(position_data["speed"]),  # knots
            "course": float(position_data["course"]),
            "navigation_task_id": navigation_task_id,
            "traffic_source": "airsports",
        }
        s = json.dumps(data, cls=DateTimeEncoder)
        container = {
            "type": "tracking.data",
            "data": s,
        }
        async_to_sync(self.channel_layer.group_send)("tracking_airsports", container)

    def transmit_global_position_data(
            self,
            global_tracking_name: str,
            person: Optional[Dict],
            position_data: Dict,
            device_time: datetime.datetime,
            navigation_task_id: Optional[int],
    ):
        data = {
            "name": global_tracking_name,
            "time": device_time,
            "person": person,
            "deviceId": position_data["deviceId"],
            "latitude": float(position_data["latitude"]),
            "longitude": float(position_data["longitude"]),
            "altitude": float(position_data["altitude"]),
            "baro_altitude": float(position_data["altitude"]),
            "battery_level": float(position_data["attributes"].get("batteryLevel", -1.0)),
            "speed": float(position_data["speed"]),
            "course": float(position_data["course"]),
            "navigation_task_id": navigation_task_id,
            "traffic_source": "internal",
        }
        s = json.dumps(data, cls=DateTimeEncoder)
        container = {
            "type": "tracking.data",
            "data": s,
            "latitude": float(position_data["latitude"]),
            "longitude": float(position_data["longitude"]),
        }
        device_id = data["deviceId"]
        # existing = self.redis.hget(REDIS_GLOBAL_POSITIONS_KEY, device_id)
        # if existing:
        #     existing = pickle.loads(existing)
        #     if existing["time"] >= data["time"]:
        #         return
        self.redis.hset(REDIS_GLOBAL_POSITIONS_KEY, key=device_id, value=pickle.dumps(data))
        async_to_sync(self.channel_layer.group_send)("tracking_global", container)

    async def transmit_external_global_position_data(
            self,
            device_id: str,
            name: str,
            time_stamp: datetime,
            latitude,
            longitude,
            altitude,
            baro_altitude,
            speed,
            course,
            traffic_source: str,
            raw_data: Optional[Dict] = None,
            aircraft_type: int = 9,
    ):
        data = {
            "name": name,
            "time": time_stamp,
            "person": None,
            "deviceId": device_id,
            "latitude": latitude,
            "longitude": longitude,
            "altitude": altitude,
            "baro_altitude": baro_altitude,
            "battery_level": -1,
            "speed": speed,
            "course": course,
            "navigation_task_id": None,
            "traffic_source": traffic_source,
            "raw_data": raw_data,
            "aircraft_type": aircraft_type,
        }
        s = json.dumps(data, cls=DateTimeEncoder)
        container = {"type": "tracking.data", "data": s, "latitude": latitude, "longitude": longitude}
        existing = self.redis.hget(REDIS_GLOBAL_POSITIONS_KEY, device_id)
        if existing:
            existing = pickle.loads(existing)
            if existing["time"] >= data["time"]:
                return
        self.redis.hset(REDIS_GLOBAL_POSITIONS_KEY, key=device_id, value=pickle.dumps(data))
        await self.channel_layer.group_send("tracking_global", container)

    def contest_results_channel_name(self, contest: "Contest") -> str:
        return "contestresults_{}".format(contest.pk)

    def transmit_teams(self, contest: "Contest"):
        teams = Team.objects.filter(contestteam__contest=contest)
        serialiser = TeamNestedSerialiser(teams, many=True)
        data = {
            "type": "contestresults",
            "content": {"type": "contest.teams", "teams": serialiser.data},
        }
        async_to_sync(self.channel_layer.group_send)(self.contest_results_channel_name(contest), data)

    def transmit_tasks(self, contest: "Contest"):
        tasks = Task.objects.filter(contest=contest)
        data = {
            "type": "contestresults",
            "content": {
                "type": "contest.tasks",
                "tasks": TaskSerialiser(tasks, many=True).data,
            },
        }
        async_to_sync(self.channel_layer.group_send)(self.contest_results_channel_name(contest), data)

    def transmit_tests(self, contest: "Contest"):
        tests = TaskTest.objects.filter(task__contest=contest)
        data = {
            "type": "contestresults",
            "content": {
                "type": "contest.tests",
                "tests": TaskTestSerialiser(tests, many=True).data,
            },
        }
        async_to_sync(self.channel_layer.group_send)(self.contest_results_channel_name(contest), data)

    def transmit_contest_results(self, user: Optional["MyUser"], contest: "Contest"):
        contest.permission_change_contest = (
            user.has_perm("display.change_contest", contest) if user is not None else False
        )
        serialiser = ContestResultsDetailsSerialiser(contest)

        data = {
            "type": "contestresults",
            "content": {"type": "contest.results", "results": serialiser.data},
        }
        async_to_sync(self.channel_layer.group_send)(self.contest_results_channel_name(contest), data)
