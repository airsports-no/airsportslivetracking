import datetime
from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
from display.models import Contest, NavigationTask, Route
from display.waypoint import Waypoint
from utilities.mock_utilities import TraccarMock


def waypoint(name, latitude, longitude):
    w = Waypoint(name)
    w.latitude = latitude
    w.longitude = longitude
    w.gate_line = [[latitude + 0.001, longitude], [latitude - 0.001, longitude]]
    w.bearing_next = -1
    return w


class TestNavigationTaskDetailPk(TestCase):
    """The results page builds the "Replay track" link from task.pk: the detail must send pk, not only id."""

    def setUp(self):
        for target in ("display.models.contestant.get_traccar_instance", "display.signals.get_traccar_instance"):
            patcher = patch(target, return_value=TraccarMock)
            patcher.start()
            self.addCleanup(patcher.stop)
        now = datetime.datetime.now(datetime.timezone.utc)
        self.contest = Contest.objects.create(
            name="Cup", start_time=now, finish_time=now + datetime.timedelta(days=2), is_public=True
        )
        self.task = NavigationTask.create(
            name="Task",
            original_scorecard=get_default_scorecard(),
            start_time=now,
            finish_time=now + datetime.timedelta(days=1),
            route=Route.objects.create(
                name="Route", waypoints=[waypoint("SP", 59.97, 11.2), waypoint("TP1", 59.97, 11.4)]
            ),
            contest=self.contest,
            is_public=True,
        )

    def test_the_task_detail_has_pk_as_well_as_id(self):
        response = APIClient().get(f"/api/v1/contests/{self.contest.pk}/navigationtasks/{self.task.pk}/")

        self.assertEqual(200, response.status_code, response.content)
        data = response.json()
        self.assertEqual(self.task.pk, data["pk"])
        self.assertEqual(self.task.pk, data["id"])
