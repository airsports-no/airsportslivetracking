from copy import deepcopy
from unittest.mock import patch

import datetime
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.urls import reverse
from guardian.shortcuts import assign_perm
from rest_framework import status
from rest_framework.test import APITestCase

from display.models import Contest, Person, Aeroplane, Crew, Team
from mock_utilities import TraccarMock

TEAM_DATA = {
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
}


@patch("display.models.get_traccar_instance", return_value=TraccarMock, autospec=True)
class TestTeamApi(APITestCase):
    @patch("display.models.get_traccar_instance", return_value=TraccarMock, autospec=True)
    def setUp(self, p):
        self.user_owner = get_user_model().objects.create(email="withpermissions")
        self.user_owner.user_permissions.add(Permission.objects.get(codename="add_contest"),
                                             Permission.objects.get(codename="view_contest"),
                                             Permission.objects.get(codename="change_contest"),
                                             Permission.objects.get(codename="delete_contest"))
        self.user_owner.refresh_from_db()
        self.user_without_permissions = get_user_model().objects.create(email="withoutpermissions")
        self.user_someone_else = get_user_model().objects.create(email="otherwithtpermissions")
        self.user_someone_else.user_permissions.add(Permission.objects.get(codename="add_contest"),
                                                    Permission.objects.get(codename="change_contest"),
                                                    Permission.objects.get(codename="view_contest"),
                                                    Permission.objects.get(codename="delete_contest"))

        self.client.force_login(user=self.user_owner)
        result = self.client.post(reverse("contests-list"),
                                  data={"name": "TestContest", "is_public": False, "time_zone": "Europe/Oslo",
                                        "start_time": datetime.datetime.now(datetime.timezone.utc),
                                        "finish_time": datetime.datetime.now(datetime.timezone.utc)})
        print(result.json())
        self.contest_id = result.json()["id"]
        self.contest = Contest.objects.get(pk=self.contest_id)
        self.different_user_with_object_permissions = get_user_model().objects.create(email="objectpermissions")
        self.different_user_with_object_permissions.user_permissions.add(Permission.objects.get(codename="add_contest"),
                                                                         Permission.objects.get(
                                                                             codename="change_contest"),
                                                                         Permission.objects.get(
                                                                             codename="delete_contest"))

        assign_perm("view_contest", self.different_user_with_object_permissions, self.contest)
        assign_perm("change_contest", self.different_user_with_object_permissions, self.contest)
        assign_perm("delete_contest", self.different_user_with_object_permissions, self.contest)

        aeroplane = Aeroplane.objects.create(registration="registration")
        crew = Crew.objects.create(member1=Person.objects.create(first_name="Mister", last_name="Pilot"))
        self.team = Team.objects.create(crew=crew, aeroplane=aeroplane)

    def test_fetch_team_list_without_login(self, p):
        self.client.logout()
        result = self.client.get(reverse("teams-list"))
        print(result)
        print(result.json())
        self.assertEqual(result.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_fetch_team_list_as_user_with_privileges(self, p):
        result = self.client.get(reverse("teams-list"))
        print(result)
        print(result.json())
        self.assertEqual(result.status_code, status.HTTP_200_OK)
        self.assertEqual(1, len(result.json()))

    def test_fetch_team_list_as_user_without_privileges(self, p):
        self.client.force_login(self.user_without_permissions)
        result = self.client.get(reverse("teams-list"))
        print(result)
        print(result.json())
        self.assertEqual(result.status_code, status.HTTP_403_FORBIDDEN)

    def test_post_team_with_privileges(self, p):
        result = self.client.post(reverse("teams-list"), TEAM_DATA, format="json")
        print(result)
        print(result.json())
        self.assertEqual(result.status_code, status.HTTP_201_CREATED)
        result = self.client.get(reverse("teams-list"))
        self.assertEqual(2, len(result.json()))

    def test_post_team_without_privileges(self, p):
        self.client.force_login(self.user_without_permissions)
        result = self.client.post(reverse("teams-list"), TEAM_DATA, format="json")
        print(result)
        print(result.json())
        self.assertEqual(result.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_specific_team_with_privileges(self, p):
        result = self.client.get(reverse("teams-detail", kwargs={"pk": self.team.pk}))
        print(result)
        print(result.json())
        self.assertEqual(result.status_code, status.HTTP_200_OK)

    def test_put_team_with_privileges(self, p):
        result = self.client.post(reverse("teams-list"), TEAM_DATA, format="json")
        self.assertEqual(result.status_code, status.HTTP_201_CREATED)
        modified = deepcopy(TEAM_DATA)
        modified["crew"] = {
            "member1": {
                "first_name": "first_name",
                "last_name": "last_name",
                "email": "name2@domain.com"
            }
        }
        result = self.client.put(reverse("teams-detail", kwargs={"pk": result.json()["id"]}), modified, format="json")
        print(result)
        print(result.json())
        self.assertEqual(result.status_code, status.HTTP_200_OK)
        self.assertEqual(result.json()["crew"]["member1"]["email"], "name2@domain.com")

    def test_patch_team_with_privileges(self, p):
        result = self.client.post(reverse("teams-list"), TEAM_DATA, format="json")
        self.assertEqual(result.status_code, status.HTTP_201_CREATED)
        modified = {"aeroplane": {"registration": "Different"}}
        result = self.client.patch(reverse("teams-detail", kwargs={"pk": result.json()["id"]}), modified, format="json")
        print(result)
        print(result.json())
        self.assertEqual(result.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_delete_team_with_privileges(self, p):
        result = self.client.delete()
        print(result)
        print(result.json())
        self.assertEqual(result.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_post_existing_team(self, p):
        result = self.client.post(reverse("teams-list"), TEAM_DATA, format="json")
        self.assertEqual(result.status_code, status.HTTP_201_CREATED)
        result = self.client.get(reverse("teams-list"))
        self.assertEqual(result.status_code, status.HTTP_200_OK)
        self.assertEqual(2, len(result.json()))
        result = self.client.post(reverse("teams-list"), TEAM_DATA, format="json")
        self.assertEqual(result.status_code, status.HTTP_201_CREATED)
        result = self.client.get(reverse("teams-list"))
        self.assertEqual(result.status_code, status.HTTP_200_OK)
        self.assertEqual(2, len(result.json()))
