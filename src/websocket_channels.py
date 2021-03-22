import datetime
from typing import TYPE_CHECKING, Dict, List, Tuple, Optional

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from display.models import Contestant, ContestTeam, Task, TaskTest, MyUser, Team
from display.serialisers import ContestantTrackSerialiser, ContestTeamNestedSerialiser, TaskSerialiser, \
    TaskTestSerialiser, ContestResultsDetailsSerialiser, TeamNestedSerialiser


class WebsocketFacade:
    def __init__(self):
        self.channel_layer = get_channel_layer()

    def transmit_annotations(self, contestant: "Contestant", timestamp: datetime.datetime, latitude: float,
                             longitude: float,
                             message: str, annotation_type: str):
        group_key = "tracking_{}".format(contestant.navigation_task.pk)
        annotation = {
            "contestant": contestant.pk,
            "navigation_task": contestant.navigation_task_id,
            "annotation_number": contestant.annotation_index,
            "time": timestamp.isoformat(),
            "latitude": latitude,
            "longitude": longitude,
            "message": message,
            "type": annotation_type
        }
        channel_data = {
            "contestant_id": contestant.pk,
            "positions": [],
            "annotations": [annotation],
            "latest_time": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "contestant_track": ContestantTrackSerialiser(contestant.contestanttrack).data

        }
        async_to_sync(self.channel_layer.group_send)(
            group_key,
            {"type": "tracking.data", "data": channel_data}
        )

    def transmit_basic_information(self, contestant: "Contestant"):
        group_key = "tracking_{}".format(contestant.navigation_task.pk)
        channel_data = {
            "contestant_id": contestant.pk,
            "positions": [],
            "annotations": [],
            "latest_time": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "contestant_track": ContestantTrackSerialiser(contestant.contestanttrack).data

        }
        async_to_sync(self.channel_layer.group_send)(
            group_key,
            {"type": "tracking.data", "data": channel_data}
        )

    def transmit_navigation_task_position_data(self, contestant: "Contestant", data: List[Dict], route_progress: float):
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
        channel_data = {
            "contestant_id": contestant.pk,
            "positions": position_data,
            "annotations": [],
            "progress": route_progress,
            "latest_time": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "contestant_track": ContestantTrackSerialiser(contestant.contestanttrack).data

        }
        group_key = "tracking_{}".format(contestant.navigation_task.pk)
        async_to_sync(self.channel_layer.group_send)(
            group_key,
            {"type": "tracking.data", "data": channel_data}
        )

    def transmit_global_position_data(self, global_tracking_name: str, position_data: Dict,
                                      device_time: datetime.datetime, navigation_task_id: Optional[int]) -> Dict:
        data = {
            "type": "tracking.data",
            "data": {
                "name": global_tracking_name,
                "time": device_time.isoformat(),
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
        contest.permission_change_contest = user.has_perm("display.change_contest", contest) if user is not None else False
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
