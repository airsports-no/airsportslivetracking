import datetime
from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.contrib.auth import get_user_model

from django.urls import reverse
from guardian.shortcuts import assign_perm
from rest_framework import status
from rest_framework.test import APITestCase

from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
from display.models import Contest, NavigationTask, Contestant, EditableRoute
from utilities.mock_utilities import TraccarMock

line = {
    "name": "land",
    "latitude": 0,
    "longitude": 0,
    "elevation": 0,
    "width": 1,
    "gate_line": [[66, 66], [66.1, 66.1]],
    "end_curved": False,
    "is_procedure_turn": False,
    "time_check": True,
    "gate_check": True,
    "planning_test": True,
    "type": "TP",
    "distance_next": 0,
    "bearing_next": 0,
    "distance_previous": 0,
    "bearing_from_previous": 0,
}


class TestCreateNavigationTask(APITestCase):
    def setUp(self):
        get_default_scorecard()
        self.user_owner = get_user_model().objects.create(email="withpermissions")
        permission = Permission.objects.get(codename="add_contest")
        self.user_owner.user_permissions.add(permission)
        editable_route = EditableRoute.objects.create(name="test", route=EDITABLE_ROUTE_DATA)
        assign_perm("display.view_editableroute", self.user_owner, editable_route)
        assign_perm("display.change_editableroute", self.user_owner, editable_route)

        self.NAVIGATION_TASK_DATA = {
            "name": "Task",
            "start_time": datetime.datetime.now(datetime.timezone.utc),
            "finish_time": datetime.datetime.now(datetime.timezone.utc),
            "editable_route": editable_route.pk,
            "original_scorecard": get_default_scorecard().shortcut_name,
        }
        self.user_without_permissions = get_user_model().objects.create(email="withoutpermissions")
        self.client.force_login(user=self.user_owner)
        result = self.client.post(
            reverse("contests-list"),
            data={
                "name": "TestContest",
                "is_public": False,
                "start_time": datetime.datetime.now(datetime.timezone.utc),
                "time_zone": "Europe/Oslo",
                "finish_time": datetime.datetime.now(datetime.timezone.utc),
                "location": "60, 11",
            },
        )
        print(result.json())
        self.contest_id = result.json()["id"]
        self.contest = Contest.objects.get(pk=self.contest_id)

    def test_create_navigation_task_without_login(self):
        self.client.logout()
        result = self.client.post(
            reverse("navigationtasks-list", kwargs={"contest_pk": self.contest_id}),
            data=self.NAVIGATION_TASK_DATA,
            format="json",
        )
        print(result)
        self.assertEqual(result.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_navigation_task_without_privileges(self):
        self.client.force_login(user=self.user_without_permissions)
        result = self.client.post(
            reverse("navigationtasks-list", kwargs={"contest_pk": self.contest_id}),
            data=self.NAVIGATION_TASK_DATA,
            format="json",
        )
        print(result)
        self.assertEqual(result.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_navigation_task_with_privileges(self):
        self.client.force_login(user=self.user_owner)
        result = self.client.post(
            reverse("navigationtasks-list", kwargs={"contest_pk": self.contest_id}),
            data=self.NAVIGATION_TASK_DATA,
            format="json",
        )
        print(result)
        print(result.content)
        self.assertEqual(result.status_code, status.HTTP_201_CREATED)


EDITABLE_ROUTE_DATA = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {"featureType": "route_path"},
            "geometry": {
                "type": "LineString",
                "coordinates": [
                    [11, 60],
                    [11.1, 60.1],
                ],
            },
        },
        {
            "type": "Feature",
            "properties": {
                "id": "6900ce4c-11df-4edf-9a4f-770a57b00092",
                "name": "SP",
                "pointType": "sp",
                "featureType": "route_waypoint",
                "width": 1852,
                "isTiming": True,
                "isPassing": True,
                "sequence": 0,
            },
            "geometry": {"type": "Point", "coordinates": [11, 60]},
        },
        {
            "type": "Feature",
            "properties": {
                "id": "9d525739-b2db-424a-99b8-7c83d20a3e85",
                "name": "FP",
                "pointType": "fp",
                "featureType": "route_waypoint",
                "width": 1852,
                "isTiming": True,
                "isPassing": True,
                "sequence": 1,
            },
            "geometry": {"type": "Point", "coordinates": [11.1, 60.1]},
        },
    ],
}


class TestAccessNavigationTask(APITestCase):
    def setUp(self):
        get_default_scorecard()
        self.user_owner = get_user_model().objects.create(email="withpermissions")
        self.user_owner.user_permissions.add(
            Permission.objects.get(codename="add_contest"),
            Permission.objects.get(codename="view_contest"),
            Permission.objects.get(codename="change_contest"),
            Permission.objects.get(codename="delete_contest"),
        )
        editable_route = EditableRoute.objects.create(name="test", route=EDITABLE_ROUTE_DATA)
        assign_perm("display.view_editableroute", self.user_owner, editable_route)
        assign_perm("display.change_editableroute", self.user_owner, editable_route)

        self.NAVIGATION_TASK_DATA = {
            "name": "Task",
            "start_time": datetime.datetime.now(datetime.timezone.utc),
            "finish_time": datetime.datetime.now(datetime.timezone.utc),
            "original_scorecard": get_default_scorecard().shortcut_name,
            "editable_route": editable_route.pk,
        }
        self.user_view_permissions = get_user_model().objects.create(email="view_permissions")
        self.user_view_permissions.user_permissions.add(
            Permission.objects.get(codename="view_contest"),
        )
        self.user_someone_else = get_user_model().objects.create(email="withoutpermissions")
        self.user_someone_else.user_permissions.add(
            Permission.objects.get(codename="view_contest"),
            Permission.objects.get(codename="add_contest"),
            Permission.objects.get(codename="change_contest"),
            Permission.objects.get(codename="delete_contest"),
        )
        self.client.force_login(user=self.user_owner)
        result = self.client.post(
            reverse("contests-list"),
            data={
                "name": "TestContest",
                "is_public": False,
                "start_time": datetime.datetime.now(datetime.timezone.utc),
                "time_zone": "Europe/Oslo",
                "finish_time": datetime.datetime.now(datetime.timezone.utc),
                "location": "60, 11",
            },
        )
        print(result.json())
        self.contest_id = result.json()["id"]
        self.contest = Contest.objects.get(pk=self.contest_id)
        result = self.client.post(
            reverse("navigationtasks-list", kwargs={"contest_pk": self.contest_id}),
            data=self.NAVIGATION_TASK_DATA,
            format="json",
        )
        print(result.content)
        self.navigation_task = NavigationTask.objects.get(pk=result.json()["id"])
        self.different_user_with_object_permissions = get_user_model().objects.create(email="objectpermissions")
        self.different_user_with_object_permissions.user_permissions.add(
            Permission.objects.get(codename="add_contest"),
            Permission.objects.get(codename="change_contest"),
            Permission.objects.get(codename="delete_contest"),
        )
        assign_perm("add_contest", self.different_user_with_object_permissions, self.contest)
        assign_perm("view_contest", self.different_user_with_object_permissions, self.contest)
        assign_perm("change_contest", self.different_user_with_object_permissions, self.contest)
        assign_perm("delete_contest", self.different_user_with_object_permissions, self.contest)

    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    def test_delete_self_registration(self, *args):
        self.generic_user = get_user_model().objects.create(email="name@domain.com")
        self.navigation_task.allow_self_management = True
        self.navigation_task.save()
        self.navigation_task.make_public()
        CONTESTANT_DATA = {
            "team": {
                "aeroplane": {"registration": "LN-YDB2"},
                "crew": {"member1": {"first_name": "first_name", "last_name": "last_name", "email": "name@domain.com"}},
                "country": "NO",
            },
            "gate_times": {},
            "takeoff_time": datetime.datetime.now(datetime.timezone.utc),
            "minutes_to_starting_point": 5,
            "finished_by_time": datetime.datetime.now(datetime.timezone.utc),
            "air_speed": 70,
            "contestant_number": 1,
            "tracker_device_id": "tracker",
            "tracker_start_time": datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1),
            "wind_speed": 10,
            "wind_direction": 0,
        }
        result = self.client.post(
            reverse(
                "contestants-create-with-team",
                kwargs={"contest_pk": self.contest_id, "navigationtask_pk": self.navigation_task.pk},
            ),
            data=CONTESTANT_DATA,
            format="json",
        )
        print("Contestant result: {}".format(result.content))
        self.contestant = Contestant.objects.get(pk=result.json()["id"])
        self.client.force_login(self.generic_user)
        result = self.client.delete(
            f"/api/v1/contests/{self.contest.pk}/navigationtasks/{self.navigation_task.pk}/delete_self_managed_contestant/{self.contestant.pk}/"
        )
        self.assertEqual(result.status_code, status.HTTP_204_NO_CONTENT)

    def test_view_navigation_task_from_other_user_with_permissions(self):
        self.client.force_login(user=self.different_user_with_object_permissions)
        result = self.client.get(
            reverse("navigationtasks-detail", kwargs={"contest_pk": self.contest_id, "pk": self.navigation_task.id})
        )
        print(result)
        print(result.json())
        self.assertEqual(result.status_code, status.HTTP_200_OK)

    def test_put_navigation_task_from_other_user_with_permissions(self):
        self.client.force_login(user=self.different_user_with_object_permissions)
        data = dict(self.NAVIGATION_TASK_DATA)
        data["name"] = "Putting a new name"

        result = self.client.put(
            reverse("navigationtasks-detail", kwargs={"contest_pk": self.contest_id, "pk": self.navigation_task.id}),
            data=data,
            format="json",
        )
        print(result)
        print(result.content)
        self.assertEqual(result.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_navigation_task_from_other_user_with_permissions(self):
        self.client.force_login(user=self.different_user_with_object_permissions)
        result = self.client.delete(
            reverse("navigationtasks-detail", kwargs={"contest_pk": self.contest_id, "pk": self.navigation_task.id})
        )
        self.assertEqual(result.status_code, status.HTTP_204_NO_CONTENT)

    def test_put_navigation_task_without_login(self):
        self.client.logout()
        data = dict(self.NAVIGATION_TASK_DATA)
        data["name"] = "Putting a new name"

        result = self.client.put(
            reverse("navigationtasks-detail", kwargs={"contest_pk": self.contest_id, "pk": self.navigation_task.id}),
            data=data,
            format="json",
        )
        print(result)
        self.assertEqual(result.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_put_navigation_task_as_someone_else(self):
        self.client.force_login(user=self.user_someone_else)
        data = dict(self.NAVIGATION_TASK_DATA)
        data["name"] = "Putting a new name"

        result = self.client.put(
            reverse("navigationtasks-detail", kwargs={"contest_pk": self.contest_id, "pk": self.navigation_task.id}),
            data=data,
            format="json",
        )
        print(result)
        self.assertEqual(result.status_code, status.HTTP_403_FORBIDDEN)

    def test_put_navigation_task_as_creator(self):
        self.client.force_login(user=self.user_owner)
        data = dict(self.NAVIGATION_TASK_DATA)
        data["name"] = "Putting a new name"
        result = self.client.put(
            reverse("navigationtasks-detail", kwargs={"contest_pk": self.contest_id, "pk": self.navigation_task.id}),
            data=data,
            format="json",
        )
        print(result)
        print(result.content)
        self.assertEqual(result.status_code, status.HTTP_403_FORBIDDEN)

    def test_patch_navigation_task_without_login(self):
        self.client.logout()
        data = {"name": "Putting a new name"}

        result = self.client.patch(
            reverse("navigationtasks-detail", kwargs={"contest_pk": self.contest_id, "pk": self.navigation_task.id}),
            data=data,
            format="json",
        )
        print(result)
        self.assertEqual(result.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_patch_navigation_task_as_someone_else(self):
        self.client.force_login(user=self.user_someone_else)
        data = {"name": "Putting a new name"}
        result = self.client.patch(
            reverse("navigationtasks-detail", kwargs={"contest_pk": self.contest_id, "pk": self.navigation_task.id}),
            data=data,
            format="json",
        )
        print(result)
        self.assertEqual(result.status_code, status.HTTP_403_FORBIDDEN)

    def test_patch_navigation_task_as_creator(self):
        self.client.force_login(user=self.user_owner)
        data = {"name": "Putting a new name"}
        result = self.client.patch(
            reverse("navigationtasks-detail", kwargs={"contest_pk": self.contest_id, "pk": self.navigation_task.id}),
            data=data,
            format="json",
        )
        print(result)
        print(result.content)
        self.assertEqual(result.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_view_navigation_task_without_login(self):
        self.client.logout()
        result = self.client.get(
            reverse("navigationtasks-detail", kwargs={"contest_pk": self.contest_id, "pk": self.navigation_task.id})
        )
        print(result)
        self.assertEqual(result.status_code, status.HTTP_404_NOT_FOUND)

    def test_view_navigation_task_as_someone_else(self):
        self.client.force_login(user=self.user_someone_else)
        result = self.client.get(
            reverse("navigationtasks-detail", kwargs={"contest_pk": self.contest_id, "pk": self.navigation_task.id})
        )
        print(result)
        self.assertEqual(result.status_code, status.HTTP_404_NOT_FOUND)

    def test_view_navigation_task_as_creator(self):
        self.client.force_login(user=self.user_owner)
        result = self.client.get(
            reverse("navigationtasks-detail", kwargs={"contest_pk": self.contest_id, "pk": self.navigation_task.id})
        )
        print(result)
        print(result.content)
        self.assertEqual(result.status_code, status.HTTP_200_OK)

    def test_delete_public_navigation_task_without_login(self):
        self.contest.is_public = True
        self.contest.save()
        self.navigation_task.is_public = True
        self.navigation_task.save()
        self.client.logout()
        result = self.client.delete(
            reverse("navigationtasks-detail", kwargs={"contest_pk": self.contest_id, "pk": self.navigation_task.id})
        )
        print(result)
        self.assertEqual(result.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_delete_public_navigation_task_as_someone_else(self):
        self.client.force_login(user=self.user_someone_else)
        self.contest.is_public = True
        self.contest.save()
        self.navigation_task.is_public = True
        self.navigation_task.save()
        result = self.client.delete(
            reverse("navigationtasks-detail", kwargs={"contest_pk": self.contest_id, "pk": self.navigation_task.id})
        )
        print(result)
        self.assertEqual(result.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_navigation_task_without_login(self):
        self.client.logout()
        result = self.client.delete(
            reverse("navigationtasks-detail", kwargs={"contest_pk": self.contest_id, "pk": self.navigation_task.id})
        )
        print(result)
        self.assertEqual(result.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_delete_navigation_task_as_someone_else(self):
        self.client.force_login(user=self.user_someone_else)
        result = self.client.delete(
            reverse("navigationtasks-detail", kwargs={"contest_pk": self.contest_id, "pk": self.navigation_task.id})
        )
        print(result)
        self.assertEqual(result.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_navigation_task_as_creator(self):
        self.client.force_login(user=self.user_owner)
        result = self.client.delete(
            reverse("navigationtasks-detail", kwargs={"contest_pk": self.contest_id, "pk": self.navigation_task.id})
        )
        print(result)
        print(result.content)
        self.assertEqual(result.status_code, status.HTTP_204_NO_CONTENT)

    def test_view_public_navigation_task_without_login(self):
        self.contest.is_public = True
        self.contest.is_featured = True
        self.contest.save()
        self.navigation_task.is_public = True
        self.navigation_task.is_featured = True
        self.navigation_task.save()
        self.client.logout()
        result = self.client.get(
            reverse("contests-detail", kwargs={"pk": self.contest_id}), data={"name": "TestContest2"}
        )
        print(result)
        self.assertEqual(result.status_code, status.HTTP_200_OK)

    def test_view_public_navigation_task_as_someone_else(self):
        self.contest.is_public = True
        self.contest.is_featured = True
        self.contest.save()
        self.navigation_task.is_public = True
        self.navigation_task.is_featured = True
        self.navigation_task.save()
        self.client.logout()
        self.client.force_login(user=self.user_someone_else)
        result = self.client.get(
            reverse("navigationtasks-detail", kwargs={"contest_pk": self.contest_id, "pk": self.navigation_task.id})
        )
        print(result)
        self.assertEqual(result.status_code, status.HTTP_200_OK)

    def test_view_public_navigation_task_as_creator(self):
        self.contest.is_public = True
        self.contest.save()
        self.navigation_task.is_public = True
        self.navigation_task.save()
        self.client.logout()
        self.client.force_login(user=self.user_owner)
        result = self.client.get(
            reverse("navigationtasks-detail", kwargs={"contest_pk": self.contest_id, "pk": self.navigation_task.id})
        )
        print(result)
        print(result.content)
        self.assertEqual(result.status_code, status.HTTP_200_OK)

    def test_view_public_contest_hidden_navigation_task_navigation_task_without_login(self):
        self.contest.is_public = True
        self.contest.save()
        self.navigation_task.is_public = False
        self.navigation_task.save()
        self.client.logout()
        result = self.client.get(
            reverse("navigationtasks-detail", kwargs={"contest_pk": self.contest_id, "pk": self.navigation_task.id})
        )

        print(result)
        self.assertEqual(result.status_code, status.HTTP_404_NOT_FOUND)

    def test_view_hidden_contest_public_navigation_task_navigation_task_without_login(self):
        self.contest.is_public = False
        self.contest.save()
        self.navigation_task.is_public = True
        self.navigation_task.save()
        self.client.logout()
        result = self.client.get(
            reverse("navigationtasks-detail", kwargs={"contest_pk": self.contest_id, "pk": self.navigation_task.id})
        )
        print(result)
        self.assertEqual(result.status_code, status.HTTP_404_NOT_FOUND)

    def test_share_navigation_task(self):
        self.assertFalse(self.contest.is_public)
        self.assertFalse(self.contest.is_featured)
        self.client.force_login(user=self.user_owner)

        result = self.client.put(
            reverse("navigationtasks-share", kwargs={"contest_pk": self.contest_id, "pk": self.navigation_task.id}),
            data={"visibility": "private"},
        )
        self.assertEqual(result.status_code, status.HTTP_200_OK)
        self.navigation_task.refresh_from_db()
        self.contest.refresh_from_db()
        self.assertFalse(self.navigation_task.is_public)
        self.assertFalse(self.navigation_task.is_featured)
        self.assertFalse(self.contest.is_public)
        self.assertFalse(self.contest.is_featured)

        result = self.client.put(
            reverse("navigationtasks-share", kwargs={"contest_pk": self.contest_id, "pk": self.navigation_task.id}),
            data={"visibility": "unlisted"},
        )
        self.assertEqual(result.status_code, status.HTTP_200_OK)
        self.navigation_task.refresh_from_db()
        self.contest.refresh_from_db()
        self.assertTrue(self.navigation_task.is_public)
        self.assertFalse(self.navigation_task.is_featured)
        self.assertTrue(self.contest.is_public)
        self.assertFalse(self.contest.is_featured)

        result = self.client.put(
            reverse("navigationtasks-share", kwargs={"contest_pk": self.contest_id, "pk": self.navigation_task.id}),
            data={"visibility": "public"},
        )
        self.assertEqual(result.status_code, status.HTTP_200_OK)
        self.navigation_task.refresh_from_db()
        self.contest.refresh_from_db()
        self.assertTrue(self.navigation_task.is_public)
        self.assertTrue(self.navigation_task.is_featured)
        self.assertTrue(self.contest.is_public)
        self.assertTrue(self.contest.is_featured)

        result = self.client.put(
            reverse("navigationtasks-share", kwargs={"contest_pk": self.contest_id, "pk": self.navigation_task.id}),
            data={"visibility": "private"},
        )
        self.assertEqual(result.status_code, status.HTTP_200_OK)
        self.navigation_task.refresh_from_db()
        self.contest.refresh_from_db()
        self.assertFalse(self.navigation_task.is_public)
        self.assertFalse(self.navigation_task.is_featured)
        self.assertTrue(self.contest.is_public)
        self.assertTrue(self.contest.is_featured)

    def test_share_contest(self):
        self.assertFalse(self.contest.is_public)
        self.assertFalse(self.contest.is_featured)
        self.client.force_login(user=self.user_owner)

        result = self.client.put(f"/api/v1/contests/{self.contest_id}/share/", data={"visibility": "private"})
        self.assertEqual(result.status_code, status.HTTP_200_OK)
        self.navigation_task.refresh_from_db()
        self.contest.refresh_from_db()
        self.assertFalse(self.navigation_task.is_public)
        self.assertFalse(self.navigation_task.is_featured)
        self.assertFalse(self.contest.is_public)
        self.assertFalse(self.contest.is_featured)

        result = self.client.put(f"/api/v1/contests/{self.contest_id}/share/", data={"visibility": "public"})
        self.contest.refresh_from_db()
        self.assertEqual(result.status_code, status.HTTP_200_OK)
        self.assertTrue(self.contest.is_public)
        self.assertTrue(self.contest.is_featured)

        result = self.client.put(
            reverse("navigationtasks-share", kwargs={"contest_pk": self.contest_id, "pk": self.navigation_task.id}),
            data={"visibility": "public"},
        )
        self.assertEqual(result.status_code, status.HTTP_200_OK)
        self.navigation_task.refresh_from_db()
        self.assertTrue(self.navigation_task.is_public)
        self.assertTrue(self.navigation_task.is_featured)

        result = self.client.put(f"/api/v1/contests/{self.contest_id}/share/", data={"visibility": "unlisted"})
        self.assertEqual(result.status_code, status.HTTP_200_OK)
        self.navigation_task.refresh_from_db()
        self.contest.refresh_from_db()
        self.assertTrue(self.navigation_task.is_public)
        self.assertFalse(self.navigation_task.is_featured)
        self.assertTrue(self.contest.is_public)
        self.assertFalse(self.contest.is_featured)

        result = self.client.put(f"/api/v1/contests/{self.contest_id}/share/", data={"visibility": "private"})
        self.assertEqual(result.status_code, status.HTTP_200_OK)
        self.navigation_task.refresh_from_db()
        self.contest.refresh_from_db()
        self.assertFalse(self.navigation_task.is_public)
        self.assertFalse(self.navigation_task.is_featured)
        self.assertFalse(self.contest.is_public)
        self.assertFalse(self.contest.is_featured)

    def test_modify_scorecard_as_owner(self):
        self.client.force_login(user=self.user_owner)
        scorecard_data = self.client.get(
            reverse("navigationtasks-scorecard", kwargs={"contest_pk": self.contest_id, "pk": self.navigation_task.id})
        ).json()
        self.assertEqual(200, scorecard_data["backtracking_penalty"])
        scorecard_data["backtracking_penalty"] = 1234
        scorecard_data["free_text"] = "asdf"
        scorecard_data.pop("task_type")
        gate = scorecard_data["gatescore_set"][1]
        self.assertEqual("fp", gate["gate_type"])
        self.assertEqual(2, gate["graceperiod_before"])
        gate["graceperiod_before"] = 4321
        result = self.client.put(
            reverse("navigationtasks-scorecard", kwargs={"contest_pk": self.contest_id, "pk": self.navigation_task.id}),
            data=scorecard_data,
            format="json",
        )
        self.assertEqual(result.status_code, status.HTTP_200_OK, result.content)
        self.navigation_task.scorecard.refresh_from_db()
        self.assertEqual(1234, self.navigation_task.scorecard.backtracking_penalty)
        self.assertEqual(4321, self.navigation_task.scorecard.get_gate_scorecard("fp").graceperiod_before)

    def test_anonymous_cannot_view_scorecard(self):
        self.client.logout()
        result = self.client.get(
            reverse("navigationtasks-scorecard", kwargs={"contest_pk": self.contest_id, "pk": self.navigation_task.id})
        )
        self.assertEqual(result.status_code, status.HTTP_401_UNAUTHORIZED, result.content)

    def test_scorecard_response_includes_applicable_gate_types_and_original_scorecard(self):
        # Scorecard Phase 3: the new React scorecard editor needs to know which gate types
        # matter for this specific task (services/scorecard_gate_applicability.py) and what
        # the task's standard/original scorecard looks like (to diff against and build
        # "reset this field" payloads) - both are merged into the scorecard action's response
        # rather than requiring a second request.
        self.client.force_login(user=self.user_owner)
        scorecard_data = self.client.get(
            reverse("navigationtasks-scorecard", kwargs={"contest_pk": self.contest_id, "pk": self.navigation_task.id})
        ).json()
        self.assertIn("applicable_gate_types", scorecard_data)
        self.assertIsInstance(scorecard_data["applicable_gate_types"], list)
        self.assertGreater(len(scorecard_data["applicable_gate_types"]), 0)
        # dummy is never applicable to any task - see scorecard_gate_applicability.py
        self.assertNotIn("dummy", scorecard_data["applicable_gate_types"])
        self.assertIn("applicable_scalar_groups", scorecard_data)
        self.assertIsInstance(scorecard_data["applicable_scalar_groups"], list)
        # this fixture's task is a precision task - Corridor/ANR route/Duration/Circle/Speed
        # keeping are never applicable to it, see scorecard_gate_applicability.py
        for irrelevant_group in ("Corridor", "ANR route", "Duration", "Circle", "Speed keeping"):
            self.assertNotIn(irrelevant_group, scorecard_data["applicable_scalar_groups"])
        self.assertIsNotNone(scorecard_data["original_scorecard"])
        self.assertEqual(
            get_default_scorecard().backtracking_penalty,
            scorecard_data["original_scorecard"]["backtracking_penalty"],
        )

    def test_scorecard_response_exposes_visible_fields_for_curation_not_hiding(self):
        # visible_fields used to only exist to decide what the legacy Django form even
        # rendered (a hard filter that made some scorecards' organizer pages show nothing at
        # all) - now exposed read-only so the new editor can use it as a grouping hint while
        # still showing every field.
        self.client.force_login(user=self.user_owner)
        scorecard_data = self.client.get(
            reverse("navigationtasks-scorecard", kwargs={"contest_pk": self.contest_id, "pk": self.navigation_task.id})
        ).json()
        self.assertIn("visible_fields", scorecard_data)
        self.assertIsInstance(scorecard_data["visible_fields"], list)
        for gate in scorecard_data["gatescore_set"]:
            self.assertIn("visible_fields", gate)
            self.assertIsInstance(gate["visible_fields"], list)

    def test_reset_scorecard_action_restores_original_values(self):
        self.client.force_login(user=self.user_owner)
        self.navigation_task.scorecard.backtracking_penalty = 999999
        self.navigation_task.scorecard.save()

        result = self.client.post(
            reverse(
                "navigationtasks-reset-scorecard",
                kwargs={"contest_pk": self.contest_id, "pk": self.navigation_task.id},
            )
        )
        self.assertEqual(result.status_code, status.HTTP_200_OK, result.content)
        self.assertEqual(get_default_scorecard().backtracking_penalty, result.json()["backtracking_penalty"])
        self.navigation_task.refresh_from_db()
        self.assertEqual(
            get_default_scorecard().backtracking_penalty, self.navigation_task.scorecard.backtracking_penalty
        )

    def test_reset_scorecard_requires_change_permission(self):
        self.client.force_login(user=self.user_view_permissions)
        assign_perm("view_contest", self.user_view_permissions, self.contest)
        result = self.client.post(
            reverse(
                "navigationtasks-reset-scorecard",
                kwargs={"contest_pk": self.contest_id, "pk": self.navigation_task.id},
            )
        )
        self.assertEqual(result.status_code, status.HTTP_403_FORBIDDEN, result.content)

    def test_scorecard_put_without_gatescore_set_key_does_not_400(self):
        # Regression test (PR #753 review): gatescore_set used to be a required nested field,
        # so a scalar-only PUT that omits the key entirely failed validation even though
        # nothing about a gate score was being changed. The React scorecard editor happens to
        # always send an (possibly empty) gatescore_set list, so this never surfaced there -
        # but any other PUT caller sending a genuinely scalar-only body would 400.
        self.client.force_login(user=self.user_owner)
        result = self.client.put(
            reverse("navigationtasks-scorecard", kwargs={"contest_pk": self.contest_id, "pk": self.navigation_task.id}),
            data={"backtracking_penalty": 4242},
            format="json",
        )
        self.assertEqual(result.status_code, status.HTTP_200_OK, result.content)
        self.navigation_task.scorecard.refresh_from_db()
        self.assertEqual(4242, self.navigation_task.scorecard.backtracking_penalty)
