import datetime
import json
import logging
import pickle
from typing import List, Optional, Dict, Any, TYPE_CHECKING

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from redis import StrictRedis

if TYPE_CHECKING:
    from display.models import (
        Contestant,
        ContestantReceivedPosition,
        ScoreLogEntry,
        TrackAnnotation,
        GateCumulativeScore,
        ContestantTrack,
        Contest,
        MyUser,
    )

REDIS_HOST = getattr(settings, "REDIS_HOST", "localhost")
REDIS_PORT = getattr(settings, "REDIS_PORT", 6379)
REDIS_GLOBAL_POSITIONS_KEY = getattr(settings, "REDIS_GLOBAL_POSITIONS_KEY", "global_positions")

ANOMALY = "anomaly"


class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime.date, datetime.datetime)):
            return obj.isoformat()
        else:
            return super().default(obj)


def serialize_score_log_entry(entry: "ScoreLogEntry") -> dict:
    return {
        "id": entry.id,
        "time": entry.time,
        "contestant": entry.contestant_id,
        "gate": entry.gate,
        "message": entry.message,
        "string": entry.string,
        "points": entry.points,
        "planned": entry.planned,
        "actual": entry.actual,
        "offset_string": entry.offset_string,
        "times_string": entry.times_string,
        "type": entry.type,
    }


def serialize_track_annotation(annotation: "TrackAnnotation") -> dict:
    return {
        "id": annotation.id,
        "time": annotation.time,
        "contestant": annotation.contestant_id,
        "gate": annotation.gate,
        "type": annotation.type,
        "message": annotation.message,
        "latitude": annotation.latitude,
        "longitude": annotation.longitude,
        "gate_type": annotation.gate_type,
        "score_log_entry": annotation.score_log_entry_id,
    }


def serialize_gate_cumulative_score(gs: "GateCumulativeScore") -> dict:
    return {
        "id": gs.id,
        "gate": gs.gate,
        "contestant": gs.contestant_id,
        "points": gs.points,
    }


def serialize_contestant_track(ct: "ContestantTrack") -> dict:
    return {
        "id": ct.id,
        "contestant": ct.contestant_id,
        "score": ct.score,
        "current_state": ct.current_state,
        "current_leg": ct.current_leg,
        "last_gate": ct.last_gate,
        "last_gate_time_offset": ct.last_gate_time_offset,
        "passed_starting_gate": ct.passed_starting_gate,
        "passed_finish_gate": ct.passed_finish_gate,
        "calculator_finished": ct.calculator_finished,
        "calculator_started": ct.calculator_started,
    }


def serialize_position(p: "ContestantReceivedPosition") -> dict:
    return {
        "latitude": p.latitude,
        "longitude": p.longitude,
        "altitude": p.altitude,
        "time": p.time,
        "progress": p.progress,
        "device_id": p.device_id,
        "course": p.course,
        "position_id": p.position_id,
        "interpolated": p.interpolated,
    }


def serialize_playing_card(pc: "PlayingCard") -> dict:
    return {
        "id": pc.id,
        "contestant": pc.contestant_id,
        "gate": pc.gate,
        "card_type": pc.card_type,
        "card_value": pc.card_value,
        "card_suit": pc.card_suit,
        "card_string": pc.card_string,
    }


def serialize_person(p: "Person") -> dict:
    return {
        "id": p.id,
        "first_name": p.first_name,
        "last_name": p.last_name,
    }


def serialize_crew(c: "Crew") -> dict:
    return {
        "id": c.id,
        "member1": serialize_person(c.member1),
        "member2": serialize_person(c.member2) if c.member2 else None,
    }


def serialize_aeroplane(a: "Aeroplane") -> dict:
    return {
        "id": a.id,
        "registration": a.registration,
        "colour": a.colour,
        "type": a.type,
        "picture": a.picture.url if a.picture else None,
    }


def serialize_club(c: "Club") -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "country": str(c.country),
        "country_flag_url": c.country_flag_url,
        "logo": c.logo.url if c.logo else None,
    }


def serialize_team(t: "Team") -> dict:
    return {
        "id": t.id,
        "name": str(t),
        "aeroplane": serialize_aeroplane(t.aeroplane),
        "crew": serialize_crew(t.crew),
        "club": serialize_club(t.club) if t.club else None,
        "country": str(t.country),
        "country_flag_url": t.country_flag_url,
        "logo": t.logo.url if t.logo else None,
    }


def serialize_contestant(c: "Contestant") -> dict:
    return {
        "id": c.id,
        "contest_id": c.navigation_task.contest_id,
        "name": str(c),
        "contestant_number": c.contestant_number,
        "tracker_device_id": c.tracker_device_id,
        "team": serialize_team(c.team),
        "track_version": c.track_version,
        "live_processing": getattr(c, "live_processing", True),
        "takeoff_time": c.takeoff_time,
        "finished_by_time": c.finished_by_time,
        "adaptive_start": c.adaptive_start,
        "gate_times": c.gate_times,
        "has_crossed_starting_line": c.has_crossed_starting_line,
    }


def generate_contestant_data_block(
    contestant: "Contestant",
    positions: List = None,
    annotations: List = None,
    log_entries: List = None,
    latest_time: datetime.datetime = None,
    gate_scores: List = None,
    playing_cards: List = None,
    contestant_track_data: dict = None,
    gate_times: Dict = None,
    gate_distance_and_estimate: Dict = None,
    danger_level: Dict = None,
):
    data = {"contestant_id": contestant.id}
    data["positions"] = positions or []
    if annotations is not None:
        data["annotations"] = annotations
    if log_entries is not None:
        data["score_log_entries"] = log_entries
    if gate_scores is not None:
        data["gate_scores"] = gate_scores
    if playing_cards is not None:
        data["playing_cards"] = playing_cards
    if gate_times is not None:
        data["gate_times"] = gate_times
    elif contestant.adaptive_start:
        data["gate_times"] = contestant.gate_times
    if gate_distance_and_estimate is not None:
        data["gate_distance_and_estimate"] = gate_distance_and_estimate
    if danger_level is not None:
        data["danger_level"] = danger_level
    if contestant_track_data is not None:
        data["contestant_track"] = contestant_track_data
    if latest_time:
        data["progress"] = contestant.calculate_progress(latest_time)
    return data


class WebsocketFacade:
    def __init__(self):
        self.channel_layer = get_channel_layer()
        self.redis = StrictRedis(REDIS_HOST, REDIS_PORT)

    def transmit_annotations(self, contestant: "Contestant"):
        group_key = "tracking_{}".format(contestant.navigation_task.pk)
        annotation_data = [serialize_track_annotation(a) for a in contestant.trackannotation_set.all()]
        channel_data = generate_contestant_data_block(contestant, annotations=annotation_data)
        async_to_sync(self.channel_layer.group_send)(
            group_key,
            {
                "type": "tracking.data",
                "data": {"type": "annotations", "data": json.dumps(channel_data, cls=DateTimeEncoder)},
            },
        )

    def transmit_score_log_entry(self, contestant: "Contestant"):
        group_key = "tracking_{}".format(contestant.navigation_task.pk)
        log_entries = [serialize_score_log_entry(e) for e in contestant.scorelogentry_set.filter(type=ANOMALY)]
        channel_data = generate_contestant_data_block(contestant, log_entries=log_entries)
        async_to_sync(self.channel_layer.group_send)(
            group_key,
            {
                "type": "tracking.data",
                "data": {"type": "score_log", "data": json.dumps(channel_data, cls=DateTimeEncoder)},
            },
        )

    def transmit_gate_score_entry(self, contestant: "Contestant"):
        group_key = "tracking_{}".format(contestant.navigation_task.pk)
        gate_scores = [serialize_gate_cumulative_score(gs) for gs in contestant.gatecumulativescore_set.all()]
        channel_data = generate_contestant_data_block(contestant, gate_scores=gate_scores)
        async_to_sync(self.channel_layer.group_send)(
            group_key,
            {
                "type": "tracking.data",
                "data": {"type": "gate_score", "data": json.dumps(channel_data, cls=DateTimeEncoder)},
            },
        )

    def transmit_playing_cards(self, contestant: "Contestant"):
        group_key = "tracking_{}".format(contestant.navigation_task.pk)
        playing_cards = [serialize_playing_card(pc) for pc in contestant.playingcard_set.all()]
        channel_data = generate_contestant_data_block(contestant, playing_cards=playing_cards)
        async_to_sync(self.channel_layer.group_send)(
            group_key,
            {
                "type": "tracking.data",
                "data": {"type": "playing_cards", "data": json.dumps(channel_data, cls=DateTimeEncoder)},
            },
        )

    def transmit_basic_information(self, contestant: "Contestant"):
        group_key = "tracking_{}".format(contestant.navigation_task.pk)
        channel_data = generate_contestant_data_block(
            contestant, contestant_track_data=serialize_contestant_track(contestant.contestanttrack)
        )
        async_to_sync(self.channel_layer.group_send)(
            group_key,
            {
                "type": "tracking.data",
                "data": {"type": "basic_information", "data": json.dumps(channel_data, cls=DateTimeEncoder)},
            },
        )

    def transmit_contestant(self, contestant: "Contestant"):
        group_key = "tracking_{}".format(contestant.navigation_task.pk)
        channel_data = serialize_contestant(contestant)
        async_to_sync(self.channel_layer.group_send)(
            group_key,
            {
                "type": "tracking.data",
                "data": {"type": "contestant", "data": json.dumps(channel_data, cls=DateTimeEncoder)},
            },
        )

    def transmit_delete_contestant(self, contestant: "Contestant"):
        group_key = "tracking_{}".format(contestant.navigation_task.pk)
        channel_data = {"contestant_id": contestant.pk}
        async_to_sync(self.channel_layer.group_send)(
            group_key,
            {
                "type": "tracking.data",
                "data": {"type": "contestant_delete", "data": json.dumps(channel_data, cls=DateTimeEncoder)},
            },
        )

    def transmit_navigation_task_position_data(
        self, contestant: "Contestant", positions: List["ContestantReceivedPosition"]
    ):
        if len(positions) == 0:
            return
        position_data = [serialize_position(p) for p in positions]
        channel_data = generate_contestant_data_block(
            contestant,
            positions=position_data,
            latest_time=positions[-1].time,
        )
        group_key = "tracking_{}".format(contestant.navigation_task.pk)
        async_to_sync(self.channel_layer.group_send)(
            group_key,
            {
                "type": "tracking.data",
                "data": {"type": "position_data", "data": json.dumps(channel_data, cls=DateTimeEncoder)},
            },
        )

    def transmit_seconds_to_crossing_time_and_crossing_estimate(
        self,
        contestant: "Contestant",
        waypoint_name: str,
        seconds_to_planned_crossing: float,
        crossing_offset_estimate: float,
        score: float,
        final: bool,
        missed: bool,
    ):
        channel_data = generate_contestant_data_block(
            contestant,
            gate_distance_and_estimate={
                "seconds_to_planned_crossing": seconds_to_planned_crossing,
                "estimated_crossing_offset": crossing_offset_estimate,
                "estimated_score": score,
                "final": final,
                "missed": missed,
                "waypoint_name": waypoint_name,
            },
        )
        group_key = "tracking_{}".format(contestant.navigation_task.pk)
        async_to_sync(self.channel_layer.group_send)(
            group_key,
            {
                "type": "tracking.data",
                "data": {"type": "crossing_time", "data": json.dumps(channel_data, cls=DateTimeEncoder)},
            },
        )

    def transmit_danger_estimate_and_accumulated_penalty(
        self, contestant: "Contestant", danger_level: float, accumulated_score: float
    ):
        channel_data = generate_contestant_data_block(
            contestant,
            danger_level={"danger_level": danger_level, "accumulated_score": accumulated_score},
        )
        group_key = "tracking_{}".format(contestant.navigation_task.pk)
        async_to_sync(self.channel_layer.group_send)(
            group_key,
            {
                "type": "tracking.data",
                "data": {"type": "danger_level", "data": json.dumps(channel_data, cls=DateTimeEncoder)},
            },
        )

    def transmit_airsports_position_data(
        self,
        global_tracking_name: str,
        position_data: Dict,
        device_time: datetime.datetime,
        navigation_task_id: Optional[int],
    ):
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
        from display.models import Team
        from display.serialisers import TeamNestedSerialiser

        teams = Team.objects.filter(contestteam__contest=contest)
        serialiser = TeamNestedSerialiser(teams, many=True)
        data = {
            "type": "contestresults",
            "content": {"type": "contest.teams", "teams": serialiser.data},
        }
        async_to_sync(self.channel_layer.group_send)(self.contest_results_channel_name(contest), data)

    def transmit_tasks(self, contest: "Contest"):
        from display.models import Task
        from display.serialisers import TaskSerialiser

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
        from display.models import TaskTest
        from display.serialisers import TaskTestSerialiser

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
        from display.serialisers import ContestResultsDetailsSerialiser

        # Check permissions safely
        if user is not None:
            contest.permission_change_contest = user.has_perm("display.change_contest", contest)
        else:
            contest.permission_change_contest = False

        serialiser = ContestResultsDetailsSerialiser(contest)

        data = {
            "type": "contestresults",
            "content": {"type": "contest.results", "results": serialiser.data},
        }
        async_to_sync(self.channel_layer.group_send)(self.contest_results_channel_name(contest), data)
