"""
The track pushed to the live map is the database's. The calculators hold several copies of a contestant's track and each
saves only the fields it changed, so a push from a copy that had not heard of the start line being crossed told the
browser the contestant was "not started" again, a moment after it had been promoted (seen with the scale test).
"""

import datetime
import json
from unittest.mock import patch

from django.test import TestCase

from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
from display.models import Aeroplane, Contest, Contestant, ContestantTrack, Crew, NavigationTask, Person, Route, Team
from utilities.mock_utilities import TraccarMock
from websocket_channels import WebsocketFacade


@patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
@patch("display.signals.get_traccar_instance", return_value=TraccarMock)
class TestBasicInformationPush(TestCase):
    def make_contestant(self, *args):
        now = datetime.datetime.now(datetime.timezone.utc)
        contest = Contest.objects.create(
            name="Push", start_time=now, finish_time=now + datetime.timedelta(days=1), location="60, 11"
        )
        task = NavigationTask.create(
            name="Push task",
            original_scorecard=get_default_scorecard(),
            route=Route.objects.create(name="Push route"),
            contest=contest,
            start_time=now,
            finish_time=now + datetime.timedelta(days=1),
        )
        crew = Crew.objects.create(member1=Person.objects.create(first_name="P", last_name="Push", email="p@push.example"))
        team = Team.objects.create(crew=crew, aeroplane=Aeroplane.objects.create(registration="LN-PUSH"))
        return Contestant.objects.create(
            team=team,
            navigation_task=task,
            takeoff_time=now + datetime.timedelta(hours=1),
            finished_by_time=now + datetime.timedelta(hours=2),
            tracker_start_time=now + datetime.timedelta(minutes=30),
            tracker_device_id="push-device",
            contestant_number=1,
        )

    def pushed(self, contestant):
        sent = []
        with patch.object(WebsocketFacade, "_safe_group_send", side_effect=lambda group, message: sent.append(message)):
            WebsocketFacade().transmit_basic_information(contestant)
        return json.loads(sent[0]["data"]["data"])["contestant_track"]

    def test_a_stale_copy_of_the_track_does_not_send_the_old_state(self, *args):
        contestant = self.make_contestant()
        stale = contestant.contestanttrack  # this copy has heard nothing of what happens next
        self.assertFalse(stale.passed_starting_gate)
        ContestantTrack.objects.filter(pk=stale.pk).update(passed_starting_gate=True, current_state="Started")

        track = self.pushed(contestant)

        self.assertTrue(track["passed_starting_gate"])
        self.assertEqual(track["current_state"], "Started")
        self.assertFalse(stale.passed_starting_gate)  # the copy itself is still behind: the push no longer depends on it
