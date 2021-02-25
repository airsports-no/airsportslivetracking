import datetime

from django.contrib.auth.models import User, Permission
from django.contrib.auth import get_user_model

from django.urls import reverse
from guardian.shortcuts import assign_perm
from rest_framework import status
from rest_framework.test import APITestCase

from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
from display.models import Contest, NavigationTask

line = {
    "name": "land",
    "latitude": 0,
    "longitude": 0,
    "elevation": 0,
    "width": 1,
    "gate_line": [],
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
                "takeoff_gate": line,
                "landing_gate": line,
                "name": "name"},
                                "scorecard": get_default_scorecard().name
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
        self.assertEqual(result.status_code, status.HTTP_403_FORBIDDEN)

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
        "takeoff_gate": line,
        "landing_gate": line,
        "name": "name"},
                        "scorecard": get_default_scorecard().name
                        }

        get_default_scorecard()
        self.user_owner = get_user_model().objects.create(email="withpermissions")
        self.user_owner.user_permissions.add(
            Permission.objects.get(codename="add_contest"),
            Permission.objects.get(codename="view_contest"),
            Permission.objects.get(codename="change_contest"),
            Permission.objects.get(codename="delete_contest")
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

    def test_publish_navigation_task_as_other_user_with_permissions(self):
        self.client.force_login(user=self.different_user_with_object_permissions)
        result = self.client.put(
            reverse("navigationtasks-publish", kwargs={'contest_pk': self.contest_id, 'pk': self.navigation_task.id}))
        print(result)
        print(result.content)
        self.assertEqual(result.status_code, status.HTTP_200_OK)
        self.assertTrue(result.json()["is_public"])

    def test_put_navigation_task_without_login(self):
        self.client.logout()
        data = dict(self.NAVIGATION_TASK_DATA)
        data["name"] = "Putting a new name"

        result = self.client.put(
            reverse("navigationtasks-detail", kwargs={'contest_pk': self.contest_id, 'pk': self.navigation_task.id}),
            data=data, format="json")
        print(result)
        self.assertEqual(result.status_code, status.HTTP_403_FORBIDDEN)

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
        self.assertEqual(result.status_code, status.HTTP_403_FORBIDDEN)

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

    def test_publish_navigation_task_without_login(self):
        self.client.logout()
        result = self.client.put(
            reverse("navigationtasks-publish", kwargs={'contest_pk': self.contest_id, 'pk': self.navigation_task.id}))
        print(result)
        self.assertEqual(result.status_code, status.HTTP_403_FORBIDDEN)

    def test_publish_navigation_task_as_someone_else(self):
        self.client.force_login(user=self.user_someone_else)
        result = self.client.put(
            reverse("navigationtasks-publish", kwargs={'contest_pk': self.contest_id, 'pk': self.navigation_task.id}))
        print(result)
        self.assertEqual(result.status_code, status.HTTP_403_FORBIDDEN)

    def test_publish_navigation_task_as_creator(self):
        self.client.force_login(user=self.user_owner)
        result = self.client.put(
            reverse("navigationtasks-publish", kwargs={'contest_pk': self.contest_id, 'pk': self.navigation_task.id}))
        print(result)
        print(result.content)
        self.assertEqual(result.status_code, status.HTTP_200_OK)
        self.assertTrue(result.json()["is_public"])

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
        self.assertEqual(result.status_code, status.HTTP_403_FORBIDDEN)

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
        self.assertEqual(result.status_code, status.HTTP_403_FORBIDDEN)

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
        self.contest.save()
        self.navigation_task.is_public = True
        self.navigation_task.save()
        self.client.logout()
        result = self.client.get(reverse("contests-detail", kwargs={'pk': self.contest_id}),
                                 data={"name": "TestContest2"})
        print(result)
        self.assertEqual(result.status_code, status.HTTP_200_OK)

    def test_view_public_navigation_task_as_someone_else(self):
        self.contest.is_public = True
        self.contest.save()
        self.navigation_task.is_public = True
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
