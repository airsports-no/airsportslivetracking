import datetime
import json
from unittest.mock import patch

from django.contrib.auth.models import User, Permission
from django.contrib.auth import get_user_model

from django.urls import reverse
from guardian.shortcuts import assign_perm
from rest_framework import status
from rest_framework.test import APITestCase

from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
from display.models import Contest, NavigationTask, Contestant
from mock_utilities import TraccarMock

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
    "bearing_from_previous": 0

}


class TestCreateNavigationTask(APITestCase):
    def setUp(self):
        get_default_scorecard()
        self.NAVIGATION_TASK_DATA = {"name": "Task", "start_time": datetime.datetime.now(datetime.timezone.utc),
                                     "finish_time": datetime.datetime.now(datetime.timezone.utc), "route": {
                "waypoints": [],
                "takeoff_gates": [line],
                "landing_gates": [line],
                "name": "name"},
                                     "original_scorecard": get_default_scorecard().shortcut_name
                                     }
        self.user_owner = get_user_model().objects.create(email="withpermissions")
        permission = Permission.objects.get(codename="add_contest")
        self.user_owner.user_permissions.add(permission)
        self.user_without_permissions = get_user_model().objects.create(email="withoutpermissions")
        self.client.force_login(user=self.user_owner)
        result = self.client.post(reverse("contests-list"), data={"name": "TestContest", "is_public": False,
                                                                  "start_time": datetime.datetime.now(
                                                                      datetime.timezone.utc),
                                                                  "time_zone": "Europe/Oslo",
                                                                  "finish_time": datetime.datetime.now(
                                                                      datetime.timezone.utc)})
        print(result.json())
        self.contest_id = result.json()["id"]
        self.contest = Contest.objects.get(pk=self.contest_id)

    def test_create_navigation_task_without_login(self):
        self.client.logout()
        result = self.client.post(reverse("navigationtasks-list", kwargs={"contest_pk": self.contest_id}),
                                  data=self.NAVIGATION_TASK_DATA, format="json")
        print(result)
        self.assertEqual(result.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_navigation_task_without_privileges(self):
        self.client.force_login(user=self.user_without_permissions)
        result = self.client.post(reverse("navigationtasks-list", kwargs={"contest_pk": self.contest_id}),
                                  data=self.NAVIGATION_TASK_DATA, format="json")
        print(result)
        self.assertEqual(result.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_navigation_task_with_privileges(self):
        self.client.force_login(user=self.user_owner)
        result = self.client.post(reverse("navigationtasks-list", kwargs={"contest_pk": self.contest_id}),
                                  data=self.NAVIGATION_TASK_DATA, format="json")
        print(result)
        print(result.content)
        self.assertEqual(result.status_code, status.HTTP_201_CREATED)


class TestAccessNavigationTask(APITestCase):
    def setUp(self):
        self.NAVIGATION_TASK_DATA = {"name": "Task", "start_time": datetime.datetime.now(datetime.timezone.utc),
                                     "finish_time": datetime.datetime.now(datetime.timezone.utc), "route": {
                "waypoints": [],
                "takeoff_gates": [line],
                "landing_gates": [line],
                "name": "name"},
                                     "original_scorecard": get_default_scorecard().shortcut_name
                                     }

        get_default_scorecard()
        self.user_owner = get_user_model().objects.create(email="withpermissions")
        self.user_owner.user_permissions.add(
            Permission.objects.get(codename="add_contest"),
            Permission.objects.get(codename="view_contest"),
            Permission.objects.get(codename="change_contest"),
            Permission.objects.get(codename="delete_contest")
        )
        self.user_view_permissions = get_user_model().objects.create(email="view_permissions")
        self.user_view_permissions.user_permissions.add(
            Permission.objects.get(codename="view_contest"),
        )
        self.user_someone_else = get_user_model().objects.create(email="withoutpermissions")
        self.user_someone_else.user_permissions.add(
            Permission.objects.get(codename="view_contest"),
            Permission.objects.get(codename="add_contest"),
            Permission.objects.get(codename="change_contest"),
            Permission.objects.get(codename="delete_contest")
        )
        self.client.force_login(user=self.user_owner)
        result = self.client.post(reverse("contests-list"), data={"name": "TestContest", "is_public": False,
                                                                  "start_time": datetime.datetime.now(
                                                                      datetime.timezone.utc),
                                                                  "time_zone": "Europe/Oslo",
                                                                  "finish_time": datetime.datetime.now(
                                                                      datetime.timezone.utc)})
        print(result.json())
        self.contest_id = result.json()["id"]
        self.contest = Contest.objects.get(pk=self.contest_id)
        result = self.client.post(reverse("navigationtasks-list", kwargs={"contest_pk": self.contest_id}),
                                  data=self.NAVIGATION_TASK_DATA, format="json")
        print(result.content)
        self.navigation_task = NavigationTask.objects.get(pk=result.json()["id"])
        self.different_user_with_object_permissions = get_user_model().objects.create(email="objectpermissions")
        self.different_user_with_object_permissions.user_permissions.add(
            Permission.objects.get(codename="add_contest"),
            Permission.objects.get(codename="change_contest"),
            Permission.objects.get(codename="delete_contest")
        )
        assign_perm("add_contest", self.different_user_with_object_permissions, self.contest)
        assign_perm("view_contest", self.different_user_with_object_permissions, self.contest)
        assign_perm("change_contest", self.different_user_with_object_permissions, self.contest)
        assign_perm("delete_contest", self.different_user_with_object_permissions, self.contest)

    @patch("display.models.get_traccar_instance", return_value=TraccarMock)
    def test_delete_self_registration(self, p):
        self.generic_user = get_user_model().objects.create(email="name@domain.com")
        self.navigation_task.allow_self_management = True
        self.navigation_task.save()
        self.navigation_task.make_public()
        CONTESTANT_DATA = {
            "team": {
                "aeroplane": {
                    "registration": "LN-YDB2"
                },
                "crew": {
                    "member1": {
                        "first_name": "first_name",
                        "last_name": "last_name",
                        "email": "name@domain.com"
                    }
                },
                "country": "NO"
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
            "wind_direction": 0
        }
        result = self.client.post(reverse("contestants-list", kwargs={"contest_pk": self.contest_id,
                                                                      "navigationtask_pk": self.navigation_task.pk}),
                                  data=CONTESTANT_DATA, format="json")
        print("Contestant result: {}".format(result.content))
        self.contestant = Contestant.objects.get(pk=result.json()["id"])
        self.client.force_login(self.generic_user)
        result = self.client.delete(
            f"/api/v1/contests/{self.contest.pk}/navigationtasks/{self.navigation_task.pk}/contestant_self_registration/")
        self.assertEqual(result.status_code, status.HTTP_204_NO_CONTENT)

    def test_view_navigation_task_from_other_user_with_permissions(self):
        self.client.force_login(user=self.different_user_with_object_permissions)
        result = self.client.get(
            reverse("navigationtasks-detail", kwargs={'contest_pk': self.contest_id, 'pk': self.navigation_task.id}))
        print(result)
        print(result.json())
        self.assertEqual(result.status_code, status.HTTP_200_OK)

    def test_put_navigation_task_from_other_user_with_permissions(self):
        self.client.force_login(user=self.different_user_with_object_permissions)
        data = dict(self.NAVIGATION_TASK_DATA)
        data["name"] = "Putting a new name"

        result = self.client.put(
            reverse("navigationtasks-detail", kwargs={'contest_pk': self.contest_id, 'pk': self.navigation_task.id}),
            data=data, format="json")
        print(result)
        print(result.content)
        self.assertEqual(result.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_navigation_task_from_other_user_with_permissions(self):
        self.client.force_login(user=self.different_user_with_object_permissions)
        result = self.client.delete(
            reverse("navigationtasks-detail", kwargs={'contest_pk': self.contest_id, 'pk': self.navigation_task.id}))
        self.assertEqual(result.status_code, status.HTTP_204_NO_CONTENT)

    def test_put_navigation_task_without_login(self):
        self.client.logout()
        data = dict(self.NAVIGATION_TASK_DATA)
        data["name"] = "Putting a new name"

        result = self.client.put(
            reverse("navigationtasks-detail", kwargs={'contest_pk': self.contest_id, 'pk': self.navigation_task.id}),
            data=data, format="json")
        print(result)
        self.assertEqual(result.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_put_navigation_task_as_someone_else(self):
        self.client.force_login(user=self.user_someone_else)
        data = dict(self.NAVIGATION_TASK_DATA)
        data["name"] = "Putting a new name"

        result = self.client.put(
            reverse("navigationtasks-detail", kwargs={'contest_pk': self.contest_id, 'pk': self.navigation_task.id}),
            data=data, format="json")
        print(result)
        self.assertEqual(result.status_code, status.HTTP_403_FORBIDDEN)

    def test_put_navigation_task_as_creator(self):
        self.client.force_login(user=self.user_owner)
        data = dict(self.NAVIGATION_TASK_DATA)
        data["name"] = "Putting a new name"
        result = self.client.put(
            reverse("navigationtasks-detail", kwargs={'contest_pk': self.contest_id, 'pk': self.navigation_task.id}),
            data=data, format="json")
        print(result)
        print(result.content)
        self.assertEqual(result.status_code, status.HTTP_403_FORBIDDEN)

    def test_patch_navigation_task_without_login(self):
        self.client.logout()
        data = {"name": "Putting a new name"}

        result = self.client.patch(
            reverse("navigationtasks-detail", kwargs={'contest_pk': self.contest_id, 'pk': self.navigation_task.id}),
            data=data, format="json")
        print(result)
        self.assertEqual(result.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_patch_navigation_task_as_someone_else(self):
        self.client.force_login(user=self.user_someone_else)
        data = {"name": "Putting a new name"}
        result = self.client.patch(
            reverse("navigationtasks-detail", kwargs={'contest_pk': self.contest_id, 'pk': self.navigation_task.id}),
            data=data, format="json")
        print(result)
        self.assertEqual(result.status_code, status.HTTP_403_FORBIDDEN)

    def test_patch_navigation_task_as_creator(self):
        self.client.force_login(user=self.user_owner)
        data = {"name": "Putting a new name"}
        result = self.client.patch(
            reverse("navigationtasks-detail", kwargs={'contest_pk': self.contest_id, 'pk': self.navigation_task.id}),
            data=data, format="json")
        print(result)
        print(result.content)
        self.assertEqual(result.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_view_navigation_task_without_login(self):
        self.client.logout()
        result = self.client.get(
            reverse("navigationtasks-detail", kwargs={'contest_pk': self.contest_id, 'pk': self.navigation_task.id}))
        print(result)
        self.assertEqual(result.status_code, status.HTTP_404_NOT_FOUND)

    def test_view_navigation_task_as_someone_else(self):
        self.client.force_login(user=self.user_someone_else)
        result = self.client.get(
            reverse("navigationtasks-detail", kwargs={'contest_pk': self.contest_id, 'pk': self.navigation_task.id}))
        print(result)
        self.assertEqual(result.status_code, status.HTTP_404_NOT_FOUND)

    def test_view_navigation_task_as_creator(self):
        self.client.force_login(user=self.user_owner)
        result = self.client.get(
            reverse("navigationtasks-detail", kwargs={'contest_pk': self.contest_id, 'pk': self.navigation_task.id}))
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
            reverse("navigationtasks-detail", kwargs={'contest_pk': self.contest_id, 'pk': self.navigation_task.id}))
        print(result)
        self.assertEqual(result.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_delete_public_navigation_task_as_someone_else(self):
        self.client.force_login(user=self.user_someone_else)
        self.contest.is_public = True
        self.contest.save()
        self.navigation_task.is_public = True
        self.navigation_task.save()
        result = self.client.delete(
            reverse("navigationtasks-detail", kwargs={'contest_pk': self.contest_id, 'pk': self.navigation_task.id}))
        print(result)
        self.assertEqual(result.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_navigation_task_without_login(self):
        self.client.logout()
        result = self.client.delete(
            reverse("navigationtasks-detail", kwargs={'contest_pk': self.contest_id, 'pk': self.navigation_task.id}))
        print(result)
        self.assertEqual(result.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_delete_navigation_task_as_someone_else(self):
        self.client.force_login(user=self.user_someone_else)
        result = self.client.delete(
            reverse("navigationtasks-detail", kwargs={'contest_pk': self.contest_id, 'pk': self.navigation_task.id}))
        print(result)
        self.assertEqual(result.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_navigation_task_as_creator(self):
        self.client.force_login(user=self.user_owner)
        result = self.client.delete(
            reverse("navigationtasks-detail", kwargs={'contest_pk': self.contest_id, 'pk': self.navigation_task.id}))
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
        result = self.client.get(reverse("contests-detail", kwargs={'pk': self.contest_id}),
                                 data={"name": "TestContest2"})
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
            reverse("navigationtasks-detail", kwargs={'contest_pk': self.contest_id, 'pk': self.navigation_task.id}))
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
            reverse("navigationtasks-detail", kwargs={'contest_pk': self.contest_id, 'pk': self.navigation_task.id}))
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
            reverse("navigationtasks-detail", kwargs={'contest_pk': self.contest_id, 'pk': self.navigation_task.id}))

        print(result)
        self.assertEqual(result.status_code, status.HTTP_404_NOT_FOUND)

    def test_view_hidden_contest_public_navigation_task_navigation_task_without_login(self):
        self.contest.is_public = False
        self.contest.save()
        self.navigation_task.is_public = True
        self.navigation_task.save()
        self.client.logout()
        result = self.client.get(
            reverse("navigationtasks-detail", kwargs={'contest_pk': self.contest_id, 'pk': self.navigation_task.id}))
        print(result)
        self.assertEqual(result.status_code, status.HTTP_404_NOT_FOUND)

    def test_share_navigation_task(self):
        self.assertFalse(self.contest.is_public)
        self.assertFalse(self.contest.is_featured)
        self.client.force_login(user=self.user_owner)

        result = self.client.put(
            reverse("navigationtasks-share", kwargs={'contest_pk': self.contest_id, 'pk': self.navigation_task.id}),
            data={"visibility": "private"})
        self.assertEqual(result.status_code, status.HTTP_200_OK)
        self.navigation_task.refresh_from_db()
        self.contest.refresh_from_db()
        self.assertFalse(self.navigation_task.is_public)
        self.assertFalse(self.navigation_task.is_featured)
        self.assertFalse(self.contest.is_public)
        self.assertFalse(self.contest.is_featured)

        result = self.client.put(
            reverse("navigationtasks-share", kwargs={'contest_pk': self.contest_id, 'pk': self.navigation_task.id}),
            data={"visibility": "unlisted"})
        self.assertEqual(result.status_code, status.HTTP_200_OK)
        self.navigation_task.refresh_from_db()
        self.contest.refresh_from_db()
        self.assertTrue(self.navigation_task.is_public)
        self.assertFalse(self.navigation_task.is_featured)
        self.assertTrue(self.contest.is_public)
        self.assertFalse(self.contest.is_featured)

        result = self.client.put(
            reverse("navigationtasks-share", kwargs={'contest_pk': self.contest_id, 'pk': self.navigation_task.id}),
            data={"visibility": "public"})
        self.assertEqual(result.status_code, status.HTTP_200_OK)
        self.navigation_task.refresh_from_db()
        self.contest.refresh_from_db()
        self.assertTrue(self.navigation_task.is_public)
        self.assertTrue(self.navigation_task.is_featured)
        self.assertTrue(self.contest.is_public)
        self.assertTrue(self.contest.is_featured)

        result = self.client.put(
            reverse("navigationtasks-share", kwargs={'contest_pk': self.contest_id, 'pk': self.navigation_task.id}),
            data={"visibility": "private"})
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

        result = self.client.put(f"/api/v1/contests/{self.contest_id}/share/",
                                 data={"visibility": "private"})
        self.assertEqual(result.status_code, status.HTTP_200_OK)
        self.navigation_task.refresh_from_db()
        self.contest.refresh_from_db()
        self.assertFalse(self.navigation_task.is_public)
        self.assertFalse(self.navigation_task.is_featured)
        self.assertFalse(self.contest.is_public)
        self.assertFalse(self.contest.is_featured)

        result = self.client.put(
            f"/api/v1/contests/{self.contest_id}/share/",
            data={"visibility": "public"})
        self.contest.refresh_from_db()
        self.assertEqual(result.status_code, status.HTTP_200_OK)
        self.assertTrue(self.contest.is_public)
        self.assertTrue(self.contest.is_featured)

        result = self.client.put(
            reverse("navigationtasks-share", kwargs={'contest_pk': self.contest_id, 'pk': self.navigation_task.id}),
            data={"visibility": "public"})
        self.assertEqual(result.status_code, status.HTTP_200_OK)
        self.navigation_task.refresh_from_db()
        self.assertTrue(self.navigation_task.is_public)
        self.assertTrue(self.navigation_task.is_featured)

        result = self.client.put(
            f"/api/v1/contests/{self.contest_id}/share/",
            data={"visibility": "unlisted"})
        self.assertEqual(result.status_code, status.HTTP_200_OK)
        self.navigation_task.refresh_from_db()
        self.contest.refresh_from_db()
        self.assertTrue(self.navigation_task.is_public)
        self.assertFalse(self.navigation_task.is_featured)
        self.assertTrue(self.contest.is_public)
        self.assertFalse(self.contest.is_featured)

        result = self.client.put(
            f"/api/v1/contests/{self.contest_id}/share/",
            data={"visibility": "private"})
        self.assertEqual(result.status_code, status.HTTP_200_OK)
        self.navigation_task.refresh_from_db()
        self.contest.refresh_from_db()
        self.assertFalse(self.navigation_task.is_public)
        self.assertFalse(self.navigation_task.is_featured)
        self.assertFalse(self.contest.is_public)
        self.assertFalse(self.contest.is_featured)

    def test_modify_scorecard_as_owner(self):
        self.client.force_login(user=self.user_owner)
        scorecard_data = self.client.get(reverse("navigationtasks-scorecard", kwargs={'contest_pk': self.contest_id,
                                                                                      'pk': self.navigation_task.id})).json()
        self.assertEqual(200, scorecard_data["backtracking_penalty"])
        scorecard_data["backtracking_penalty"] = 1234
        scorecard_data["free_text"] = "asdf"
        scorecard_data.pop("task_type")
        gate = scorecard_data["gatescore_set"][1]
        self.assertEqual("fp", gate["gate_type"])
        self.assertEqual(2, gate["graceperiod_before"])
        gate["graceperiod_before"] = 4321
        result = self.client.put(reverse("navigationtasks-scorecard",
                                         kwargs={'contest_pk': self.contest_id, 'pk': self.navigation_task.id}),
                                 data=scorecard_data, format="json")
        self.assertEqual(result.status_code, status.HTTP_200_OK, result.content)
        self.navigation_task.scorecard.refresh_from_db()
        self.assertEqual(1234, self.navigation_task.scorecard.backtracking_penalty)
        self.assertEqual(4321, self.navigation_task.scorecard.gatescore_set.get(gate_type="fp").graceperiod_before)

    def test_anonymous_cannot_view_scorecard(self):
        self.client.logout()
        result = self.client.get(reverse("navigationtasks-scorecard", kwargs={'contest_pk': self.contest_id,
                                                                              'pk': self.navigation_task.id}))
        self.assertEqual(result.status_code, status.HTTP_401_UNAUTHORIZED, result.content)

