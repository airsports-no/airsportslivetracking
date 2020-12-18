import datetime

from django.contrib.auth.models import User, Permission
from django.urls import reverse
from guardian.shortcuts import assign_perm
from rest_framework import status
from rest_framework.test import APITestCase

from display.default_scorecards.create_scorecards import create_scorecards
from display.models import Contest, NavigationTask, Contestant

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

NAVIGATION_TASK_DATA = {"name": "Task", "start_time": datetime.datetime.utcnow(),
                        "finish_time": datetime.datetime.utcnow(), "route": {
        "waypoints": [],
        "takeoff_gate": line,
        "landing_gate": line,
        "name": "name"
    }}

CONTESTANT_DATA = {
    "team": {
        "aeroplane": {
            "registration": "LN-YDB"
        },
        "crew": {
            "pilot": "Mr pilot"
        },
        "nation": "Norway"
    },
    "gate_times": [],
    "scorecard": "FAI Precision 2020",
    "takeoff_time": datetime.datetime.utcnow(),
    "minutes_to_starting_point": 5,
    "finished_by_time": datetime.datetime.utcnow(),
    "air_speed": 70,
    "contestant_number": 1,
    "traccar_device_name": "tracker",
    "tracker_start_time": datetime.datetime.utcnow(),
    "wind_speed": 10,
    "wind_direction": 0
}


class TestCreateNavigationTask(APITestCase):
    def setUp(self):
        create_scorecards()
        self.user_owner = User.objects.create(username="withpermissions")
        permission = Permission.objects.get(codename="add_contest")
        self.user_owner.user_permissions.add(permission)
        self.user_without_permissions = User.objects.create(username="withoutpermissions")
        self.client.force_login(user=self.user_owner)
        result = self.client.post(reverse("contests-list"), data={"name": "TestContest", "is_public": False})
        print(result.json())
        self.contest_id = result.json()["id"]
        self.contest = Contest.objects.get(pk=self.contest_id)
        result = self.client.post(reverse("navigationtasks-list", kwargs={"contest_pk": self.contest_id}),
                                  data=NAVIGATION_TASK_DATA, format="json")
        print(result.content)
        self.navigation_task = NavigationTask.objects.get(pk=result.json()["id"])

    def test_create_contestant_without_login(self):
        self.client.logout()
        result = self.client.post(reverse("contestants-list", kwargs={"contest_pk": self.contest_id,
                                                                      "navigationtask_pk": self.navigation_task.pk}),
                                  data=CONTESTANT_DATA, format="json")
        print(result)
        self.assertEqual(result.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_navigation_task_without_privileges(self):
        self.client.force_login(user=self.user_without_permissions)
        result = self.client.post(reverse("contestants-list", kwargs={"contest_pk": self.contest_id,
                                                                      "navigationtask_pk": self.navigation_task.pk}),
                                  data=CONTESTANT_DATA, format="json")
        print(result)
        self.assertEqual(result.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_navigation_task_with_privileges(self):
        self.client.force_login(user=self.user_owner)
        result = self.client.post(reverse("contestants-list", kwargs={"contest_pk": self.contest_id,
                                                                      "navigationtask_pk": self.navigation_task.pk}),
                                  data=CONTESTANT_DATA, format="json")

        print(result)
        print(result.content)
        self.assertEqual(result.status_code, status.HTTP_200_OK)


class TestAccessNavigationTask(APITestCase):
    def setUp(self):
        create_scorecards()
        self.user_owner = User.objects.create(username="withpermissions")
        self.user_owner.user_permissions.add(
            Permission.objects.get(codename="add_contest"),
            Permission.objects.get(codename="change_contest"),
            Permission.objects.get(codename="delete_contest")
        )
        self.user_someone_else = User.objects.create(username="withoutpermissions")
        self.user_someone_else.user_permissions.add(
            Permission.objects.get(codename="add_contest"),
            Permission.objects.get(codename="change_contest"),
            Permission.objects.get(codename="delete_contest")
        )

        self.client.force_login(user=self.user_owner)
        result = self.client.post(reverse("contests-list"), data={"name": "TestContest", "is_public": False})
        print(result.json())
        self.contest_id = result.json()["id"]
        self.contest = Contest.objects.get(pk=self.contest_id)
        result = self.client.post(reverse("navigationtasks-list", kwargs={"contest_pk": self.contest_id}),
                                  data=NAVIGATION_TASK_DATA, format="json")
        print(result.content)
        self.navigation_task = NavigationTask.objects.get(pk=result.json()["id"])
        result = self.client.post(reverse("contestants-list", kwargs={"contest_pk": self.contest_id,
                                                                      "navigationtask_pk": self.navigation_task.pk}),
                                  data=CONTESTANT_DATA, format="json")
        self.contestant = Contestant.objects.get(pk=result.json()["id"])
        self.different_user_with_object_permissions = User.objects.create(username="objectpermissions")
        self.different_user_with_object_permissions.user_permissions.add(
            Permission.objects.get(codename="add_contest"),
            Permission.objects.get(codename="change_contest"),
            Permission.objects.get(codename="delete_contest")
        )
        assign_perm("view_contest", self.different_user_with_object_permissions, self.contest)
        assign_perm("change_contest", self.different_user_with_object_permissions, self.contest)
        assign_perm("delete_contest", self.different_user_with_object_permissions, self.contest)

    def test_view_contestant_from_other_user_with_permissions(self):
        self.client.force_login(user=self.different_user_with_object_permissions)
        url = reverse("contestants-detail",
                      kwargs={'contest_pk': self.contest_id, 'navigationtask_pk': self.navigation_task.id,
                              "pk": self.contestant.pk})
        result = self.client.get(url)
        print(result)
        print(result.json())
        self.assertEqual(result.status_code, status.HTTP_200_OK)
        self.assertEqual(10, result.json()["wind_speed"])

    def test_put_contestant_from_other_user_with_permissions(self):
        self.client.force_login(user=self.different_user_with_object_permissions)
        data = dict(CONTESTANT_DATA)
        data["wind_speed"] = 30
        url = reverse("contestants-detail",
                      kwargs={'contest_pk': self.contest_id, 'navigationtask_pk': self.navigation_task.id,
                              "pk": self.contestant.pk})
        result = self.client.put(url,
                                 data=data, format="json")
        print(result)
        print(result.content)
        self.assertEqual(result.status_code, status.HTTP_200_OK)
        self.assertEqual(30, result.json()["wind_speed"])

    def test_patch_contestant_from_other_user_with_permissions(self):
        self.client.force_login(user=self.different_user_with_object_permissions)
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

    def test_delete_contestant_from_other_user_with_permissions(self):
        self.client.force_login(user=self.different_user_with_object_permissions)
        url = reverse("contestants-detail",
                      kwargs={'contest_pk': self.contest_id, 'navigationtask_pk': self.navigation_task.id,
                              "pk": self.contestant.pk})
        result = self.client.delete(url)
        self.assertEqual(result.status_code, status.HTTP_204_NO_CONTENT)

    def test_put_contestant_without_login(self):
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

    def test_put_ncontestant_as_someone_else(self):
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

    def test_put_contestant_as_creator(self):
        self.client.force_login(user=self.user_owner)
        data = dict(CONTESTANT_DATA)
        data["wind_speed"] = 30
        url = reverse("contestants-detail",
                      kwargs={'contest_pk': self.contest_id, 'navigationtask_pk': self.navigation_task.id,
                              "pk": self.contestant.pk})
        result = self.client.put(url,
                                 data=data, format="json")
        print(result)
        print(result.content)
        self.assertEqual(result.status_code, status.HTTP_200_OK)
        self.assertEqual(30, result.json()["wind_speed"])

    def test_patch_contestant_without_login(self):
        self.client.logout()
        data = {"wind_speed": 30}
        url = reverse("contestants-detail",
                      kwargs={'contest_pk': self.contest_id, 'navigationtask_pk': self.navigation_task.id,
                              "pk": self.contestant.pk})
        result = self.client.patch(url,
                                   data=data, format="json")
        print(result)
        self.assertEqual(result.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_patch_contestant_as_someone_else(self):
        self.client.force_login(user=self.user_someone_else)
        data = {"wind_speed": 30}
        url = reverse("contestants-detail",
                      kwargs={'contest_pk': self.contest_id, 'navigationtask_pk': self.navigation_task.id,
                              "pk": self.contestant.pk})
        result = self.client.patch(url,
                                   data=data, format="json")
        print(result)
        self.assertEqual(result.status_code, status.HTTP_403_FORBIDDEN)

    def test_patch_contestant_as_creator(self):
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

    def test_view_contestant_without_login(self):
        self.client.logout()
        url = reverse("contestants-detail",
                      kwargs={'contest_pk': self.contest_id, 'navigationtask_pk': self.navigation_task.id,
                              "pk": self.contestant.pk})

        result = self.client.get(url)
        print(result)
        self.assertEqual(result.status_code, status.HTTP_404_NOT_FOUND)

    def test_view_contestant_as_someone_else(self):
        self.client.force_login(user=self.user_someone_else)
        url = reverse("contestants-detail",
                      kwargs={'contest_pk': self.contest_id, 'navigationtask_pk': self.navigation_task.id,
                              "pk": self.contestant.pk})
        result = self.client.get(url)
        print(result)
        self.assertEqual(result.status_code, status.HTTP_403_FORBIDDEN)

    def test_view_contestant_as_creator(self):
        self.client.force_login(user=self.user_owner)
        url = reverse("contestants-detail",
                      kwargs={'contest_pk': self.contest_id, 'navigationtask_pk': self.navigation_task.id,
                              "pk": self.contestant.pk})
        result = self.client.get(url)
        print(result)
        print(result.content)
        self.assertEqual(result.status_code, status.HTTP_200_OK)

    def test_delete_public_contestant_without_login(self):
        self.client.logout()
        self.contest.is_public = True
        self.contest.save()
        self.navigation_task.is_public = True
        self.navigation_task.save()

        url = reverse("contestants-detail",
                      kwargs={'contest_pk': self.contest_id, 'navigationtask_pk': self.navigation_task.id,
                              "pk": self.contestant.pk})

        result = self.client.delete(url)
        print(result)
        self.assertEqual(result.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_delete_public_contestant_as_someone_else(self):
        self.contest.is_public = True
        self.contest.save()
        self.navigation_task.is_public = True
        self.navigation_task.save()
        self.client.force_login(user=self.user_someone_else)
        url = reverse("contestants-detail",
                      kwargs={'contest_pk': self.contest_id, 'navigationtask_pk': self.navigation_task.id,
                              "pk": self.contestant.pk})

        result = self.client.delete(url)
        print(result)
        self.assertEqual(result.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_contestant_without_login(self):
        self.client.logout()
        url = reverse("contestants-detail",
                      kwargs={'contest_pk': self.contest_id, 'navigationtask_pk': self.navigation_task.id,
                              "pk": self.contestant.pk})

        result = self.client.delete(url)
        print(result)
        self.assertEqual(result.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_delete_contestant_as_someone_else(self):
        self.client.force_login(user=self.user_someone_else)
        url = reverse("contestants-detail",
                      kwargs={'contest_pk': self.contest_id, 'navigationtask_pk': self.navigation_task.id,
                              "pk": self.contestant.pk})
        result = self.client.delete(url)
        print(result)
        self.assertEqual(result.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_contestant_as_creator(self):
        self.client.force_login(user=self.user_owner)
        url = reverse("contestants-detail",
                      kwargs={'contest_pk': self.contest_id, 'navigationtask_pk': self.navigation_task.id,
                              "pk": self.contestant.pk})
        result = self.client.delete(url)
        print(result)
        print(result.content)
        self.assertEqual(result.status_code, status.HTTP_204_NO_CONTENT)

    def test_view_public_contestant_without_login(self):
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

    def test_view_public_contestant_as_someone_else(self):
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

    def test_view_publiccontestant_as_creator(self):
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

    def test_view_public_contest_hidden_navigation_task_contestant_without_login(self):
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

    def test_view_hidden_contest_public_navigation_task_contestant_without_login(self):
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

    def test_view_public_contest_hidden_navigation_task_contestant_without_privileges(self):
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
        self.assertEqual(result.status_code, status.HTTP_403_FORBIDDEN)

    def test_view_hidden_contest_public_navigation_task_contestant_without_privileges(self):
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
        self.assertEqual(result.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_contestant_track_public_contest_public_navigation_task_without_login(self):
        self.contest.is_public = True
        self.contest.save()
        self.navigation_task.is_public = True
        self.navigation_task.save()
        self.client.logout()
        url = reverse("contestants-track",
                      kwargs={'contest_pk': self.contest_id, 'navigationtask_pk': self.navigation_task.id,
                              "pk": self.contestant.pk})
        self.assertTrue("/track" in url)
        result = self.client.get(url)
        print(result.json())
        self.assertEqual(result.status_code, status.HTTP_200_OK)
        self.assertEqual(result.json()["track"], [])

    def test_get_contestant_track_hidden_contest_public_navigation_task_without_login(self):
        self.contest.is_public = False
        self.contest.save()
        self.navigation_task.is_public = True
        self.navigation_task.save()
        self.client.logout()
        url = reverse("contestants-track",
                      kwargs={'contest_pk': self.contest_id, 'navigationtask_pk': self.navigation_task.id,
                              "pk": self.contestant.pk})
        result = self.client.get(url)
        print(result)
        self.assertEqual(result.status_code, status.HTTP_404_NOT_FOUND)

    def test_get_contestant_track_public_contest_hidden_navigation_task_without_login(self):
        self.contest.is_public = True
        self.contest.save()
        self.navigation_task.is_public = False
        self.navigation_task.save()
        self.client.logout()
        url = reverse("contestants-track",
                      kwargs={'contest_pk': self.contest_id, 'navigationtask_pk': self.navigation_task.id,
                              "pk": self.contestant.pk})
        result = self.client.get(url)
        print(result)
        self.assertEqual(result.status_code, status.HTTP_404_NOT_FOUND)

    def test_get_contestant_track_public_contest_public_navigation_task_without_privileges(self):
        self.contest.is_public = True
        self.contest.save()
        self.navigation_task.is_public = True
        self.navigation_task.save()
        self.client.force_login(self.user_someone_else)
        url = reverse("contestants-track",
                      kwargs={'contest_pk': self.contest_id, 'navigationtask_pk': self.navigation_task.id,
                              "pk": self.contestant.pk})
        result = self.client.get(url)
        print(result)
        self.assertEqual(result.status_code, status.HTTP_200_OK)

    def test_get_contestant_track_hidden_contest_public_navigation_task_without_privileges(self):
        self.contest.is_public = False
        self.contest.save()
        self.navigation_task.is_public = True
        self.navigation_task.save()
        self.client.force_login(self.user_someone_else)
        url = reverse("contestants-track",
                      kwargs={'contest_pk': self.contest_id, 'navigationtask_pk': self.navigation_task.id,
                              "pk": self.contestant.pk})
        result = self.client.get(url)
        print(result)
        self.assertEqual(result.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_contestant_track_public_contest_hidden_navigation_task_without_provisions(self):
        self.contest.is_public = True
        self.contest.save()
        self.navigation_task.is_public = False
        self.navigation_task.save()
        self.client.force_login(self.user_someone_else)
        url = reverse("contestants-track",
                      kwargs={'contest_pk': self.contest_id, 'navigationtask_pk': self.navigation_task.id,
                              "pk": self.contestant.pk})
        result = self.client.get(url)
        print(result)
        self.assertEqual(result.status_code, status.HTTP_403_FORBIDDEN)


    def test_get_contestant_track_frontend_public_contest_public_navigation_task_without_privileges(self):
        self.contest.is_public = True
        self.contest.save()
        self.navigation_task.is_public = True
        self.navigation_task.save()
        self.client.force_login(self.user_someone_else)
        url = reverse("contestants-track-frontend",
                      kwargs={'contest_pk': self.contest_id, 'navigationtask_pk': self.navigation_task.id,
                              "pk": self.contestant.pk})
        result = self.client.get(url)
        print(result)
        self.assertEqual(result.status_code, status.HTTP_200_OK)

    def test_get_contestant_track_frontend_hidden_contest_public_navigation_task_without_privileges(self):
        self.contest.is_public = False
        self.contest.save()
        self.navigation_task.is_public = True
        self.navigation_task.save()
        self.client.force_login(self.user_someone_else)
        url = reverse("contestants-track-frontend",
                      kwargs={'contest_pk': self.contest_id, 'navigationtask_pk': self.navigation_task.id,
                              "pk": self.contestant.pk})
        result = self.client.get(url)
        print(result)
        self.assertEqual(result.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_contestant_track_frontend_public_contest_hidden_navigation_task_without_provisions(self):
        self.contest.is_public = True
        self.contest.save()
        self.navigation_task.is_public = False
        self.navigation_task.save()
        self.client.force_login(self.user_someone_else)
        url = reverse("contestants-track-frontend",
                      kwargs={'contest_pk': self.contest_id, 'navigationtask_pk': self.navigation_task.id,
                              "pk": self.contestant.pk})
        result = self.client.get(url)
        print(result)
        self.assertEqual(result.status_code, status.HTTP_403_FORBIDDEN)
