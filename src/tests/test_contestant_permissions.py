import datetime
from unittest.mock import patch

from django.contrib.auth.models import User, Permission
from django.contrib.auth import get_user_model

from django.urls import reverse
from guardian.shortcuts import assign_perm
from rest_framework import status
from rest_framework.test import APITestCase

from display.default_scorecards.create_scorecards import create_scorecards
from display.models import Contest, NavigationTask, Contestant
from mock_utilities import TraccarMock

line = {
    "name": "land",
    "latitude": 0,
    "longitude": 0,
    "elevation": 0,
    "width": 1,
    "gate_line": [[66,66],[66.1,66.1]],
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

NAVIGATION_TASK_DATA = {"name": "Task", "start_time": datetime.datetime.now(datetime.timezone.utc),
                        "finish_time": datetime.datetime.now(datetime.timezone.utc), "route": {
        "waypoints": [],
        "takeoff_gate": line,
        "landing_gate": line,
        "name": "name"
    },
                        "scorecard": "FAI Precision 2020"
                        }

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


@patch("display.models.get_traccar_instance", return_value=TraccarMock)
class TestCreateNavigationTask(APITestCase):
    def setUp(self):
        create_scorecards()
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
        result = self.client.post(reverse("navigationtasks-list", kwargs={"contest_pk": self.contest_id}),
                                  data=NAVIGATION_TASK_DATA, format="json")
        print(result.content)
        self.navigation_task = NavigationTask.objects.get(pk=result.json()["id"])

    def test_create_contestant_without_login(self, patch):
        self.client.logout()
        result = self.client.post(reverse("contestants-list", kwargs={"contest_pk": self.contest_id,
                                                                      "navigationtask_pk": self.navigation_task.pk}),
                                  data=CONTESTANT_DATA, format="json")
        print(result)
        self.assertEqual(result.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_navigation_task_without_privileges(self, patch):
        self.client.force_login(user=self.user_without_permissions)
        result = self.client.post(reverse("contestants-list", kwargs={"contest_pk": self.contest_id,
                                                                      "navigationtask_pk": self.navigation_task.pk}),
                                  data=CONTESTANT_DATA, format="json")
        print(result)
        self.assertEqual(result.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_navigation_task_with_privileges(self, patch):
        self.client.force_login(user=self.user_owner)
        result = self.client.post(reverse("contestants-list", kwargs={"contest_pk": self.contest_id,
                                                                      "navigationtask_pk": self.navigation_task.pk}),
                                  data=CONTESTANT_DATA, format="json")

        print(result)
        print(result.content)
        self.assertEqual(result.status_code, status.HTTP_200_OK)


@patch("display.models.get_traccar_instance", return_value=TraccarMock)
class TestAccessNavigationTask(APITestCase):
    @patch("display.models.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, patch):
        create_scorecards()
        self.user_owner = get_user_model().objects.create(email="withpermissions")
        self.user_owner.user_permissions.add(
            Permission.objects.get(codename="add_contest"),
            Permission.objects.get(codename="view_contest"),
            Permission.objects.get(codename="change_contest"),
            Permission.objects.get(codename="delete_contest")
        )
        self.user_someone_else = get_user_model().objects.create(email="withoutpermissions")
        self.user_someone_else.user_permissions.add(
            Permission.objects.get(codename="add_contest"),
            Permission.objects.get(codename="view_contest"),
            Permission.objects.get(codename="change_contest"),
            Permission.objects.get(codename="delete_contest")
        )

        self.client.force_login(user=self.user_owner)
        result = self.client.post(reverse("contests-list"),
                                  data={"name": "TestContest", "is_public": False, "time_zone": "Europe/Oslo",
                                        "start_time": datetime.datetime.now(
                                            datetime.timezone.utc),
                                        "finish_time": datetime.datetime.now(
                                            datetime.timezone.utc)})
        print(result.json())
        self.contest_id = result.json()["id"]
        self.contest = Contest.objects.get(pk=self.contest_id)
        result = self.client.post(reverse("navigationtasks-list", kwargs={"contest_pk": self.contest_id}),
                                  data=NAVIGATION_TASK_DATA, format="json")
        print("Navigation task result: {}".format(result.content))
        self.navigation_task = NavigationTask.objects.get(pk=result.json()["id"])
        result = self.client.post(reverse("contestants-list", kwargs={"contest_pk": self.contest_id,
                                                                      "navigationtask_pk": self.navigation_task.pk}),
                                  data=CONTESTANT_DATA, format="json")
        print("Contestant result: {}".format(result.content))
        self.contestant = Contestant.objects.get(pk=result.json()["id"])
        self.different_user_with_object_permissions = get_user_model().objects.create(email="objectpermissions")
        self.different_user_with_object_permissions.user_permissions.add(
            Permission.objects.get(codename="add_contest"),
            Permission.objects.get(codename="change_contest"),
            Permission.objects.get(codename="delete_contest")
        )
        assign_perm("view_contest", self.different_user_with_object_permissions, self.contest)
        assign_perm("change_contest", self.different_user_with_object_permissions, self.contest)
        assign_perm("delete_contest", self.different_user_with_object_permissions, self.contest)

    def test_view_contestant_from_other_user_with_permissions(self, patch):
        self.client.force_login(user=self.different_user_with_object_permissions)
        url = reverse("contestants-detail",
                      kwargs={'contest_pk': self.contest_id, 'navigationtask_pk': self.navigation_task.id,
                              "pk": self.contestant.pk})
        result = self.client.get(url)
        print(result)
        print(result.json())
        self.assertEqual(result.status_code, status.HTTP_200_OK)
        self.assertEqual(10, result.json()["wind_speed"])

    def test_put_contestant_from_other_user_with_permissions(self, patch):
        self.client.force_login(user=self.different_user_with_object_permissions)
        data = dict(CONTESTANT_DATA)
        data["wind_speed"] = 30
        data["team"]["crew"]["member1"]["email"] = "putotheruser@domain.com"
        url = reverse("contestants-detail",
                      kwargs={'contest_pk': self.contest_id, 'navigationtask_pk': self.navigation_task.id,
                              "pk": self.contestant.pk})
        result = self.client.put(url,
                                 data=data, format="json")
        print(result)
        print(result.content)
        self.assertEqual(result.status_code, status.HTTP_200_OK)
        self.assertEqual(30, result.json()["wind_speed"])

    def test_patch_contestant_from_other_user_with_permissions(self, patch):
        self.client.force_login(user=self.different_user_with_object_permissions)
        data = {"wind_speed": 30}
        url = reverse("contestants-detail",
                      kwargs={'contest_pk': self.contest_id, 'navigationtask_pk': self.navigation_task.id,
                              "pk": self.contestant.pk})
        result = self.client.patch(url,
                                   data=data, format="json")
        patch.asserCalled()
        print(result)
        print(result.content)
        self.assertEqual(result.status_code, status.HTTP_200_OK)
        self.assertEqual(30, result.json()["wind_speed"])

    def test_delete_contestant_from_other_user_with_permissions(self, patch):
        self.client.force_login(user=self.different_user_with_object_permissions)
        url = reverse("contestants-detail",
                      kwargs={'contest_pk': self.contest_id, 'navigationtask_pk': self.navigation_task.id,
                              "pk": self.contestant.pk})
        result = self.client.delete()
        self.assertEqual(result.status_code, status.HTTP_204_NO_CONTENT)

    def test_put_contestant_without_login(self, patch):
        self.client.logout()
        data = dict(CONTESTANT_DATA)
        data["wind_speed"] = 30
        result = self.client.put(
            reverse("contestants-detail",
                    kwargs={'contest_pk': self.contest_id, 'navigationtask_pk': self.navigation_task.id,
                            "pk": self.contestant.pk}),
            data=data, format="json")
        print(result)
        self.assertEqual(result.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_put_ncontestant_as_someone_else(self, patch):
        self.client.force_login(user=self.user_someone_else)
        data = dict(CONTESTANT_DATA)
        data["wind_speed"] = 30
        result = self.client.put(
            reverse("contestants-detail",
                    kwargs={'contest_pk': self.contest_id, 'navigationtask_pk': self.navigation_task.id,
                            "pk": self.contestant.pk}),
            data=data, format="json")
        print(result)
        self.assertEqual(result.status_code, status.HTTP_403_FORBIDDEN)

    def test_put_contestant_as_creator(self, patch):
        self.client.force_login(user=self.user_owner)
        data = dict(CONTESTANT_DATA)
        data["wind_speed"] = 30
        data["team"]["crew"]["member1"]["email"] = "putCreator@domain.com"
        url = reverse("contestants-detail",
                      kwargs={'contest_pk': self.contest_id, 'navigationtask_pk': self.navigation_task.id,
                              "pk": self.contestant.pk})
        result = self.client.put(url,
                                 data=data, format="json")
        print(result)
        print(result.content)
        self.assertEqual(result.status_code, status.HTTP_200_OK)
        self.assertEqual(30, result.json()["wind_speed"])

    def test_patch_contestant_without_login(self, patch):
        self.client.logout()
        data = {"wind_speed": 30}
        url = reverse("contestants-detail",
                      kwargs={'contest_pk': self.contest_id, 'navigationtask_pk': self.navigation_task.id,
                              "pk": self.contestant.pk})
        result = self.client.patch(url,
                                   data=data, format="json")
        print(result)
        self.assertEqual(result.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_patch_contestant_as_someone_else(self, patch):
        self.client.force_login(user=self.user_someone_else)
        data = {"wind_speed": 30}
        url = reverse("contestants-detail",
                      kwargs={'contest_pk': self.contest_id, 'navigationtask_pk': self.navigation_task.id,
                              "pk": self.contestant.pk})
        result = self.client.patch(url,
                                   data=data, format="json")
        print(result)
        self.assertEqual(result.status_code, status.HTTP_403_FORBIDDEN)

    def test_patch_contestant_as_creator(self, patch):
        self.client.force_login(user=self.user_owner)
        data = {"wind_speed": 30}
        url = reverse("contestants-detail",
                      kwargs={'contest_pk': self.contest_id, 'navigationtask_pk': self.navigation_task.id,
                              "pk": self.contestant.pk})
        result = self.client.patch(url,
                                   data=data, format="json")
        print(result)
        print(result.content)
        self.assertEqual(result.status_code, status.HTTP_200_OK)
        self.assertEqual(30, result.json()["wind_speed"])

    def test_view_contestant_without_login(self, patch):
        self.client.logout()
        url = reverse("contestants-detail",
                      kwargs={'contest_pk': self.contest_id, 'navigationtask_pk': self.navigation_task.id,
                              "pk": self.contestant.pk})

        result = self.client.get(url)
        print(result)
        self.assertEqual(result.status_code, status.HTTP_404_NOT_FOUND)

    def test_view_contestant_as_someone_else(self, patch):
        self.client.force_login(user=self.user_someone_else)
        url = reverse("contestants-detail",
                      kwargs={'contest_pk': self.contest_id, 'navigationtask_pk': self.navigation_task.id,
                              "pk": self.contestant.pk})
        result = self.client.get(url)
        print(result)
        self.assertEqual(result.status_code, status.HTTP_404_NOT_FOUND)

    def test_view_contestant_as_creator(self, patch):
        self.client.force_login(user=self.user_owner)
        url = reverse("contestants-detail",
                      kwargs={'contest_pk': self.contest_id, 'navigationtask_pk': self.navigation_task.id,
                              "pk": self.contestant.pk})
        result = self.client.get(url)
        print(result)
        print(result.content)
        self.assertEqual(result.status_code, status.HTTP_200_OK)

    def test_delete_public_contestant_without_login(self, patch):
        self.client.logout()
        self.contest.is_public = True
        self.contest.save()
        self.navigation_task.is_public = True
        self.navigation_task.save()

        url = reverse("contestants-detail",
                      kwargs={'contest_pk': self.contest_id, 'navigationtask_pk': self.navigation_task.id,
                              "pk": self.contestant.pk})

        result = self.client.delete()
        print(result)
        self.assertEqual(result.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_delete_public_contestant_as_someone_else(self, patch):
        self.contest.is_public = True
        self.contest.save()
        self.navigation_task.is_public = True
        self.navigation_task.save()
        self.client.force_login(user=self.user_someone_else)
        url = reverse("contestants-detail",
                      kwargs={'contest_pk': self.contest_id, 'navigationtask_pk': self.navigation_task.id,
                              "pk": self.contestant.pk})

        result = self.client.delete()
        print(result)
        self.assertEqual(result.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_contestant_without_login(self, patch):
        self.client.logout()
        url = reverse("contestants-detail",
                      kwargs={'contest_pk': self.contest_id, 'navigationtask_pk': self.navigation_task.id,
                              "pk": self.contestant.pk})

        result = self.client.delete()
        print(result)
        self.assertEqual(result.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_delete_contestant_as_someone_else(self, patch):
        self.client.force_login(user=self.user_someone_else)
        url = reverse("contestants-detail",
                      kwargs={'contest_pk': self.contest_id, 'navigationtask_pk': self.navigation_task.id,
                              "pk": self.contestant.pk})
        result = self.client.delete()
        print(result)
        self.assertEqual(result.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_contestant_as_creator(self, patch):
        self.client.force_login(user=self.user_owner)
        url = reverse("contestants-detail",
                      kwargs={'contest_pk': self.contest_id, 'navigationtask_pk': self.navigation_task.id,
                              "pk": self.contestant.pk})
        result = self.client.delete()
        print(result)
        print(result.content)
        self.assertEqual(result.status_code, status.HTTP_204_NO_CONTENT)

    def test_view_public_contestant_without_login(self, patch):
        self.contest.is_public = True
        self.contest.save()
        self.navigation_task.is_public = True
        self.navigation_task.save()
        self.client.logout()
        url = reverse("contestants-detail",
                      kwargs={'contest_pk': self.contest_id, 'navigationtask_pk': self.navigation_task.id,
                              "pk": self.contestant.pk})
        result = self.client.get(url)
        print(result)
        self.assertEqual(result.status_code, status.HTTP_200_OK)

    def test_view_public_contestant_as_someone_else(self, patch):
        self.contest.is_public = True
        self.contest.save()
        self.navigation_task.is_public = True
        self.navigation_task.save()
        self.client.logout()
        self.client.force_login(user=self.user_someone_else)
        url = reverse("contestants-detail",
                      kwargs={'contest_pk': self.contest_id, 'navigationtask_pk': self.navigation_task.id,
                              "pk": self.contestant.pk})
        result = self.client.get(url)
        print(result)
        self.assertEqual(result.status_code, status.HTTP_200_OK)

    def test_view_publiccontestant_as_creator(self, patch):
        self.contest.is_public = True
        self.contest.save()
        self.navigation_task.is_public = True
        self.navigation_task.save()
        self.client.logout()
        self.client.force_login(user=self.user_owner)
        url = reverse("contestants-detail",
                      kwargs={'contest_pk': self.contest_id, 'navigationtask_pk': self.navigation_task.id,
                              "pk": self.contestant.pk})
        result = self.client.get(url)
        print(result)
        print(result.content)
        self.assertEqual(result.status_code, status.HTTP_200_OK)

    def test_view_public_contest_hidden_navigation_task_contestant_without_login(self, patch):
        self.contest.is_public = True
        self.contest.save()
        self.navigation_task.is_public = False
        self.navigation_task.save()
        self.client.logout()
        url = reverse("contestants-detail",
                      kwargs={'contest_pk': self.contest_id, 'navigationtask_pk': self.navigation_task.id,
                              "pk": self.contestant.pk})
        result = self.client.get(url)
        print(result)
        self.assertEqual(result.status_code, status.HTTP_404_NOT_FOUND)

    def test_view_hidden_contest_public_navigation_task_contestant_without_login(self, patch):
        self.contest.is_public = False
        self.contest.save()
        self.navigation_task.is_public = True
        self.navigation_task.save()
        self.client.logout()
        url = reverse("contestants-detail",
                      kwargs={'contest_pk': self.contest_id, 'navigationtask_pk': self.navigation_task.id,
                              "pk": self.contestant.pk})
        result = self.client.get(url)
        print(result)
        self.assertEqual(result.status_code, status.HTTP_404_NOT_FOUND)

    def test_view_public_contest_hidden_navigation_task_contestant_without_privileges(self, patch):
        self.contest.is_public = True
        self.contest.save()
        self.navigation_task.is_public = False
        self.navigation_task.save()
        self.client.force_login(self.user_someone_else)
        url = reverse("contestants-detail",
                      kwargs={'contest_pk': self.contest_id, 'navigationtask_pk': self.navigation_task.id,
                              "pk": self.contestant.pk})
        result = self.client.get(url)
        print(result)
        self.assertEqual(result.status_code, status.HTTP_404_NOT_FOUND)

    def test_view_hidden_contest_public_navigation_task_contestant_without_privileges(self, patch):
        self.contest.is_public = False
        self.contest.save()
        self.navigation_task.is_public = True
        self.navigation_task.save()
        self.client.force_login(self.user_someone_else)
        url = reverse("contestants-detail",
                      kwargs={'contest_pk': self.contest_id, 'navigationtask_pk': self.navigation_task.id,
                              "pk": self.contestant.pk})
        result = self.client.get(url)
        print(result)
        self.assertEqual(result.status_code, status.HTTP_404_NOT_FOUND)

