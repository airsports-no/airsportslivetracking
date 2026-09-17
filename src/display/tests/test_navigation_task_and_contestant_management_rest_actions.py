"""
Tests for NavigationTaskViewSet's remove_contestants/batch_update_contestants/
refresh_editable_route REST actions and ContestantViewSet.destroy's permission fix - all part of
migrating navigationtask_detail.html to the React SPA (Slice 0).
"""

import datetime
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from guardian.shortcuts import assign_perm
from rest_framework.test import APITestCase

from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
from display.models import Aeroplane, Contest, Contestant, Crew, EditableRoute, NavigationTask, Person, Route, Team
from utilities.mock_utilities import TraccarMock


@patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
@patch("display.signals.get_traccar_instance", return_value=TraccarMock)
class TestNavigationTaskAndContestantManagementRestActions(APITestCase):
    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, *args):
        self.contest = Contest.objects.create(
            name="Task Management Contest",
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1),
            location="60, 11",
        )
        self.route = Route.objects.create(name="Route")
        now = datetime.datetime.now(datetime.timezone.utc)
        self.navigation_task = NavigationTask.create(
            name="Task Management Task",
            original_scorecard=get_default_scorecard(),
            route=self.route,
            contest=self.contest,
            start_time=now,
            finish_time=now + datetime.timedelta(days=1),
        )
        self.manager = get_user_model().objects.create(email="task-mgmt-manager@example.com")
        assign_perm("view_contest", self.manager, self.contest)
        assign_perm("change_contest", self.manager, self.contest)
        self.client.force_login(user=self.manager)

    def _make_contestant(self, number, **overrides):
        now = datetime.datetime.now(datetime.timezone.utc)
        crew = Crew.objects.create(
            member1=Person.objects.create(
                first_name=f"P{number}", last_name="Mgmt", email=f"p{number}-mgmt@example.com"
            )
        )
        team = Team.objects.create(crew=crew, aeroplane=Aeroplane.objects.create(registration=f"LN-MG{number}"))
        defaults = dict(
            team=team,
            navigation_task=self.navigation_task,
            takeoff_time=now + datetime.timedelta(hours=1),
            finished_by_time=now + datetime.timedelta(hours=2),
            tracker_start_time=now + datetime.timedelta(minutes=30),
            tracker_device_id=f"task-mgmt-device-{number}",
            contestant_number=number,
        )
        defaults.update(overrides)
        return Contestant.objects.create(**defaults)

    def _url(self, action, viewset="navigationtasks", **extra_kwargs):
        kwargs = {"contest_pk": self.contest.pk, "pk": self.navigation_task.pk}
        kwargs.update(extra_kwargs)
        return reverse(f"{viewset}-{action}", kwargs=kwargs)

    def test_remove_contestants_deletes_all_and_reports_count(self, *args):
        self._make_contestant(1)
        self._make_contestant(2)
        response = self.client.post(self._url("remove-contestants"))
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.data["deleted"], 2)
        self.assertEqual(self.navigation_task.contestant_set.count(), 0)

    def test_remove_contestants_requires_change_contest_permission(self, *args):
        self._make_contestant(1)
        viewer = get_user_model().objects.create(email="task-mgmt-viewer@example.com")
        assign_perm("view_contest", viewer, self.contest)
        self.client.force_login(user=viewer)
        response = self.client.post(self._url("remove-contestants"))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.navigation_task.contestant_set.count(), 1)

    def test_batch_update_contestants_shifts_times_and_updates_wind(self, *args):
        c1 = self._make_contestant(1)
        c2 = self._make_contestant(2)
        original_takeoff = c1.takeoff_time

        response = self.client.post(
            self._url("batch-update-contestants"),
            {
                "contestant_ids": [c1.pk, c2.pk],
                "update_wind": True,
                "wind_speed": 12.5,
                "wind_direction": 270,
                "shift_times": True,
                "time_shift_minutes": 15,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.data["updated"], 2)
        c1.refresh_from_db()
        c2.refresh_from_db()
        self.assertEqual(c1.takeoff_time, original_takeoff + datetime.timedelta(minutes=15))
        self.assertEqual(c1.wind_speed, 12.5)
        self.assertEqual(c1.wind_direction, 270)

    @patch("display.viewsets.is_calculator_running", return_value=True)
    def test_batch_update_contestants_skips_currently_running_calculator(self, _mock_running, *args):
        c1 = self._make_contestant(1)
        original_takeoff = c1.takeoff_time

        response = self.client.post(
            self._url("batch-update-contestants"),
            {"contestant_ids": [c1.pk], "shift_times": True, "time_shift_minutes": 15},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.data["updated"], 0)
        c1.refresh_from_db()
        self.assertEqual(c1.takeoff_time, original_takeoff)

    def test_refresh_editable_route_succeeds(self, *args):
        with open("display/tests/NM.csv", "r") as file:
            editable_route, _ = EditableRoute.create_from_csv("Refresh test", file.readlines()[1:])
        self.navigation_task.editable_route = editable_route
        self.navigation_task.save(update_fields=["editable_route"])
        old_route_pk = self.navigation_task.route.pk

        response = self.client.post(self._url("refresh-editable-route"))

        self.assertEqual(response.status_code, 200, response.content)
        self.navigation_task.refresh_from_db()
        self.assertNotEqual(self.navigation_task.route.pk, old_route_pk)

    def test_refresh_editable_route_rejects_when_no_editable_route_linked(self, *args):
        response = self.client.post(self._url("refresh-editable-route"))
        self.assertEqual(response.status_code, 400)

    def test_refresh_editable_route_rejects_when_contestants_exist(self, *args):
        with open("display/tests/NM.csv", "r") as file:
            editable_route, _ = EditableRoute.create_from_csv("Refresh test 2", file.readlines()[1:])
        self.navigation_task.editable_route = editable_route
        self.navigation_task.save(update_fields=["editable_route"])
        self._make_contestant(1)

        response = self.client.post(self._url("refresh-editable-route"))

        self.assertEqual(response.status_code, 400)

    def test_destroy_contestant_succeeds_for_change_contest_only_manager(self, *args):
        # The classic ContestantDeleteView only required change_contest (not delete_contest) -
        # ContestantViewSet.destroy must match that, not the stricter delete_contest the base
        # ContestantNavigationTaskContestPermissions maps DELETE to (see get_permissions()).
        contestant = self._make_contestant(1)
        url = reverse(
            "contestants-detail",
            kwargs={"contest_pk": self.contest.pk, "navigationtask_pk": self.navigation_task.pk, "pk": contestant.pk},
        )
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 204, response.content)
        self.assertFalse(Contestant.objects.filter(pk=contestant.pk).exists())

    def test_destroy_contestant_requires_change_contest_permission(self, *args):
        contestant = self._make_contestant(1)
        viewer = get_user_model().objects.create(email="task-mgmt-destroy-viewer@example.com")
        assign_perm("view_contest", viewer, self.contest)
        self.client.force_login(user=viewer)
        url = reverse(
            "contestants-detail",
            kwargs={"contest_pk": self.contest.pk, "navigationtask_pk": self.navigation_task.pk, "pk": contestant.pk},
        )
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Contestant.objects.filter(pk=contestant.pk).exists())
