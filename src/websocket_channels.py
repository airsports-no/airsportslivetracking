import datetime
from typing import TYPE_CHECKING, Dict, List, Tuple, Optional

import dateutil
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from display.models import Contestant, ContestTeam, Task, TaskTest, MyUser, Team
from display.serialisers import ContestantTrackSerialiser, ContestTeamNestedSerialiser, TaskSerialiser, \
    TaskTestSerialiser, ContestResultsDetailsSerialiser, TeamNestedSerialiser, TrackAnnotationSerialiser, \
    ScoreLogEntrySerialiser, GateCumulativeScoreSerialiser, PlayingCardSerialiser


def generate_contestant_data_block(contestant: "Contestant", positions: List = None, annotations: List = None,
                                   log_entries: List = None, latest_time: datetime.datetime = None,
                                   gate_scores: List = None, playing_cards: List = None,
                                   include_contestant_track: bool = False):
    data = {
        "contestant_id": contestant.id,
        "positions": positions or [],
        "annotations": annotations or [],
        "score_log_entries": log_entries,
        "gate_scores": gate_scores,
        "playing_cards": playing_cards,
        "latest_time": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }
    if latest_time:
        data["progress"] = contestant.calculate_progress(latest_time)
    return data


class WebsocketFacade:
    def __init__(self):
        self.channel_layer = get_channel_layer()

    def transmit_annotations(self, contestant: "Contestant"):
        group_key = "tracking_{}".format(contestant.navigation_task.pk)
        annotation_data = TrackAnnotationSerialiser(contestant.trackannotation_set.all(), many = True).data
        channel_data = generate_contestant_data_block(contestant, annotations=[annotation_data])
        async_to_sync(self.channel_layer.group_send)(
            group_key,
            {"type": "tracking.data", "data": channel_data}
        )

    def transmit_score_log_entry(self, contestant: "Contestant"):
        group_key = "tracking_{}".format(contestant.navigation_task.pk)
        log_entries = ScoreLogEntrySerialiser(contestant.scorelogentry_set.all(), many=True).data
        channel_data = generate_contestant_data_block(contestant, log_entries=log_entries)
        async_to_sync(self.channel_layer.group_send)(
            group_key,
            {"type": "tracking.data", "data": channel_data}
        )

    def transmit_gate_score_entry(self, contestant: "Contestant"):
        group_key = "tracking_{}".format(contestant.navigation_task.pk)
        gate_scores = GateCumulativeScoreSerialiser(contestant.gatecumulativescore_set.all(), many=True).data
        channel_data = generate_contestant_data_block(contestant, gate_scores=gate_scores)
        async_to_sync(self.channel_layer.group_send)(
            group_key,
            {"type": "tracking.data", "data": channel_data}
        )

    def transmit_playing_cards(self, contestant: "Contestant"):
        group_key = "tracking_{}".format(contestant.navigation_task.pk)
        playing_cards = PlayingCardSerialiser(contestant.playingcard_set.all(), many=True).data
        channel_data = generate_contestant_data_block(contestant, playing_cards=playing_cards)
        async_to_sync(self.channel_layer.group_send)(
            group_key,
            {"type": "tracking.data", "data": channel_data}
        )

    def transmit_basic_information(self, contestant: "Contestant"):
        group_key = "tracking_{}".format(contestant.navigation_task.pk)
        channel_data = generate_contestant_data_block(contestant, include_contestant_track=True)
        async_to_sync(self.channel_layer.group_send)(
            group_key,
            {"type": "tracking.data", "data": channel_data}
        )

    def transmit_navigation_task_position_data(self, contestant: "Contestant", data: List[Dict]):
        if len(data) == 0:
            return
        position_data = []
        for item in data:
            position_data.append({
                "latitude": item["fields"]["latitude"],
                "longitude": item["fields"]["longitude"],
                "speed": item["fields"]["speed"],
                "course": item["fields"]["course"],
                "altitude": item["fields"]["altitude"],
                "time": item["time"]
            })
        channel_data = generate_contestant_data_block(contestant, positions=position_data,
                                                      latest_time=dateutil.parser.parse(position_data[-1]["time"]))
        group_key = "tracking_{}".format(contestant.navigation_task.pk)
        async_to_sync(self.channel_layer.group_send)(
            group_key,
            {"type": "tracking.data", "data": channel_data}
        )

    def transmit_global_position_data(self, global_tracking_name: str, person: Optional[str], position_data: Dict,
                                      device_time: datetime.datetime, navigation_task_id: Optional[int]) -> Dict:
        data = {
            "type": "tracking.data",
            "data": {
                "name": global_tracking_name,
                "time": device_time.isoformat(),
                "person": person,
                "deviceId": position_data["deviceId"],
                "latitude": float(position_data["latitude"]),
                "longitude": float(position_data["longitude"]),
                "altitude": float(position_data["altitude"]),
                "battery_level": float(position_data["attributes"].get("batteryLevel", -1.0)),
                "speed": float(position_data["speed"]),
                "course": float(position_data["course"]),
                "navigation_task_id": navigation_task_id
            }
        }
        async_to_sync(self.channel_layer.group_send)(
            "tracking_global", data
        )
        return data

    def contest_results_channel_name(self, contest: "Contest") -> str:
        return "contestresults_{}".format(contest.pk)

    def transmit_teams(self, contest: "Contest"):
        teams = Team.objects.filter(contestteam__contest=contest)
        serialiser = TeamNestedSerialiser(teams, many=True)
        data = {
            "type": "contestresults",
            "content": {
                "type": "contest.teams",
                "teams": serialiser.data
            }
        }
        async_to_sync(self.channel_layer.group_send)(
            self.contest_results_channel_name(contest), data
        )

    def transmit_tasks(self, contest: "Contest"):
        tasks = Task.objects.filter(contest=contest)
        data = {
            "type": "contestresults",
            "content": {
                "type": "contest.tasks",
                "tasks": TaskSerialiser(tasks, many=True).data
            }
        }
        async_to_sync(self.channel_layer.group_send)(
            self.contest_results_channel_name(contest), data
        )

    def transmit_tests(self, contest: "Contest"):
        tests = TaskTest.objects.filter(task__contest=contest)
        data = {
            "type": "contestresults",
            "content": {
                "type": "contest.tests",
                "tests": TaskTestSerialiser(tests, many=True).data
            }
        }
        async_to_sync(self.channel_layer.group_send)(
            self.contest_results_channel_name(contest), data
        )

    def transmit_contest_results(self, user: Optional["MyUser"], contest: "Contest"):
        contest.permission_change_contest = user.has_perm("display.change_contest",
                                                          contest) if user is not None else False
        serialiser = ContestResultsDetailsSerialiser(contest)

        data = {
            "type": "contestresults",
            "content": {
                "type": "contest.results",
                "results": serialiser.data
            }
        }
        async_to_sync(self.channel_layer.group_send)(
            self.contest_results_channel_name(contest), data
        )
