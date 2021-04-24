import datetime
from unittest.mock import patch

from django.contrib.auth.models import User, Permission
from django.contrib.auth import get_user_model

from django.urls import reverse
from guardian.shortcuts import assign_perm, get_objects_for_user
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase, APIClient

from display.models import Contest, Team, Aeroplane, Crew, Person, ContestTeam
from mock_utilities import TraccarMock


class TestCreateContest(APITestCase):
    def setUp(self):
        self.user_with_permissions = get_user_model().objects.create(email="withpermissions")
        permission = Permission.objects.get(codename="add_contest")
        self.user_with_permissions.user_permissions.add(permission)
        self.user_without_permissions = get_user_model().objects.create(email="withoutpermissions")
        self.base_url = reverse("contests-list")

    def test_create_contest_without_login(self):
        result = self.client.post(self.base_url, data={"name": "TestContest",
                                                       "start_time": datetime.datetime.now(datetime.timezone.utc),
                                                       "finish_time": datetime.datetime.now(datetime.timezone.utc)})
        print(result)
        self.assertEqual(result.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_contest_without_privileges(self):
        self.client.force_login(user=self.user_without_permissions)
        result = self.client.post(self.base_url, data={"name": "TestContest",
                                                       "start_time": datetime.datetime.now(datetime.timezone.utc),
                                                       "finish_time": datetime.datetime.now(datetime.timezone.utc)})
        print(result)
        self.assertEqual(result.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_contest_with_privileges(self):
        self.client.force_login(user=self.user_with_permissions)
        result = self.client.post(self.base_url,
                                  data={"name": "TestContest", "is_public": False, "time_zone": "Europe/Oslo",
                                        "start_time": datetime.datetime.now(datetime.timezone.utc),
                                        "finish_time": datetime.datetime.now(datetime.timezone.utc)})
        print(result)
        print(result.content)
        self.assertEqual(result.status_code, status.HTTP_201_CREATED)


@patch("display.models.get_traccar_instance", return_value=TraccarMock)
class TestAccessContest(APITestCase):
    def setUp(self):
        self.user_owner = get_user_model().objects.create(email="withpermissions")
        self.user_owner.user_permissions.add(Permission.objects.get(codename="add_contest"),
                                             Permission.objects.get(codename="view_contest"),
                                             Permission.objects.get(codename="change_contest"),
                                             Permission.objects.get(codename="delete_contest"))
        self.user_owner.refresh_from_db()
        self.user_someone_else = get_user_model().objects.create(email="withoutpermissions")
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

    def test_get_objects_for_user(self, p):
        contests = get_objects_for_user(self.user_owner, "display.view_contest", accept_global_perms=False)
        self.assertEqual(1, contests.count())
        contests = get_objects_for_user(self.user_someone_else, "display.view_contest", accept_global_perms=False)
        self.assertEqual(0, contests.count())

    def test_list_contests_as_someone_else(self, p):
        self.client.force_login(user=self.user_someone_else)
        result = self.client.get(reverse("contests-list"))
        print(result)
        print(result.json())
        self.assertEqual(result.status_code, status.HTTP_200_OK)
        self.assertEqual(0, len(result.json()))

    def test_list_contests_as_owner(self, p):
        self.client.force_login(user=self.user_owner)
        result = self.client.get(reverse("contests-list"))
        print(result)
        print(result.json())
        self.assertEqual(result.status_code, status.HTTP_200_OK)
        self.assertEqual(1, len(result.json()))

    def test_view_contest_from_other_user_with_permissions(self, patch):
        self.client.force_login(user=self.different_user_with_object_permissions)
        result = self.client.get(reverse("contests-detail", kwargs={'pk': self.contest_id}))
        print(result)
        print(result.json())
        self.assertEqual(result.status_code, status.HTTP_200_OK)
        self.assertEqual("TestContest", result.json()["name"])

    def test_put_contestant_from_other_user_with_permissions(self, patch):
        self.client.force_login(user=self.different_user_with_object_permissions)
        result = self.client.put(reverse("contests-detail", kwargs={'pk': self.contest_id}),
                                 data={"name": "TestContest2", "time_zone": "Europe/Oslo",
                                       "start_time": datetime.datetime.now(datetime.timezone.utc),
                                       "finish_time": datetime.datetime.now(datetime.timezone.utc)})
        print(result)
        print(result.content)
        self.assertEqual(result.status_code, status.HTTP_200_OK)
        self.assertEqual("TestContest2", result.json()["name"])

    def test_patch_contestant_from_other_user_with_permissions(self, patch):
        self.client.force_login(user=self.different_user_with_object_permissions)
        data = {"is_public": True}
        result = self.client.patch(reverse("contests-detail", kwargs={'pk': self.contest_id}),
                                   data=data)
        print(result)
        print(result.content)
        self.assertEqual(result.status_code, status.HTTP_200_OK)
        self.assertTrue(result.json()["is_public"])

    def test_delete_contestant_from_other_user_with_permissions(self, patch):
        self.client.force_login(user=self.different_user_with_object_permissions)
        result = self.client.delete(reverse("contests-detail", kwargs={'pk': self.contest_id}))
        self.assertEqual(result.status_code, status.HTTP_204_NO_CONTENT)

    def test_modify_contest_without_login(self, patch):
        self.client.logout()
        result = self.client.put(reverse("contests-detail", kwargs={'pk': self.contest_id}),
                                 data={"name": "TestContest2"})
        print(result)
        self.assertEqual(result.status_code, status.HTTP_403_FORBIDDEN)

    def test_modify_contest_as_someone_else(self, patch):
        self.client.force_login(user=self.user_someone_else)
        result = self.client.put(reverse("contests-detail", kwargs={'pk': self.contest_id}),
                                 data={"name": "TestContest2",
                                       "start_time": datetime.datetime.now(datetime.timezone.utc),
                                       "finish_time": datetime.datetime.now(datetime.timezone.utc)})
        print(result)
        self.assertEqual(result.status_code, status.HTTP_404_NOT_FOUND)

    def test_modify_contest_as_creator(self, patch):
        self.client.force_login(user=self.user_owner)
        result = self.client.put(reverse("contests-detail", kwargs={'pk': self.contest_id}),
                                 data={"name": "TestContest2", "time_zone": "Europe/Oslo",
                                       "start_time": datetime.datetime.now(datetime.timezone.utc),
                                       "finish_time": datetime.datetime.now(datetime.timezone.utc)})
        print(result)
        print(result.content)
        self.assertEqual(result.status_code, status.HTTP_200_OK)
        self.assertEqual("TestContest2", result.json()["name"])

    def test_view_contest_as_someone_else(self, patch):
        self.client.force_login(user=self.user_someone_else)
        result = self.client.get(reverse("contests-detail", kwargs={'pk': self.contest_id}),
                                 data={"name": "TestContest2"})
        print(result)
        self.assertEqual(result.status_code, status.HTTP_404_NOT_FOUND)

    def test_view_contest_as_creator(self, patch):
        self.client.force_login(user=self.user_owner)
        result = self.client.get(reverse("contests-detail", kwargs={'pk': self.contest_id}), time_zone="Europe/Oslo",
                                 data={"name": "TestContest2"})
        print(result)
        print(result.content)
        self.assertEqual(result.status_code, status.HTTP_200_OK)

    def test_delete_public_contest_without_login(self, patch):
        self.client.logout()
        self.contest.is_public = True
        self.contest.save()
        result = self.client.delete(reverse("contests-detail", kwargs={'pk': self.contest_id}))
        print(result)
        self.assertEqual(result.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_contest_without_login(self, patch):
        self.client.logout()
        result = self.client.delete(reverse("contests-detail", kwargs={'pk': self.contest_id}))
        print(result)
        self.assertEqual(result.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_contest_as_someone_else(self, patch):
        self.client.force_login(user=self.user_someone_else)
        result = self.client.delete(reverse("contests-detail", kwargs={'pk': self.contest_id}))
        print(result)
        self.assertEqual(result.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_contest_as_creator(self, patch):
        self.client.force_login(user=self.user_owner)
        result = self.client.delete(reverse("contests-detail", kwargs={'pk': self.contest_id}))
        print(result)
        print(result.content)
        self.assertEqual(result.status_code, status.HTTP_204_NO_CONTENT)

    def test_view_public_contest_without_login(self, patch):
        self.contest.is_public = True
        self.contest.is_featured = True
        self.contest.save()
        self.client.logout()
        result = self.client.get(reverse("contests-detail", kwargs={'pk': self.contest_id}),
                                 data={"name": "TestContest2"})
        print(result)
        self.assertEqual(result.status_code, status.HTTP_200_OK)

    def test_view_public_contest_as_someone_else(self, patch):
        self.contest.is_public = True
        self.contest.is_featured = True
        self.contest.save()
        self.client.force_login(user=self.user_someone_else)
        result = self.client.get(reverse("contests-detail", kwargs={'pk': self.contest_id}),
                                 data={"name": "TestContest2"})
        print(result)
        self.assertEqual(result.status_code, status.HTTP_200_OK)

    def test_view_public_contest_as_creator(self, patch):
        self.contest.is_public = True
        self.contest.save()
        self.client.force_login(user=self.user_owner)
        result = self.client.get(reverse("contests-detail", kwargs={'pk': self.contest_id}),
                                 data={"name": "TestContest2"})
        print(result)
        print(result.content)
        self.assertEqual(result.status_code, status.HTTP_200_OK)

    def test_remove_team_from_contest_without_login(self, patch):
        team = Team.objects.create(crew=Crew.objects.create(
            member1=Person.objects.create(first_name="first", last_name="last", email="someone@somewhere.com")),
            aeroplane=Aeroplane.objects.create(registration="registration"))
        ContestTeam.objects.create(team=team, contest=self.contest)
        self.client.logout()
        result = self.client.get(reverse("remove_team", kwargs={'contest_pk': self.contest_id, "team_pk": team.pk}))
        print(result)
        self.assertEqual(result.status_code, status.HTTP_302_FOUND)

    def test_remove_team_from_contest_as_someone_else(self, patch):
        team = Team.objects.create(crew=Crew.objects.create(
            member1=Person.objects.create(first_name="first", last_name="last", email="someone@somewhere.com")),
            aeroplane=Aeroplane.objects.create(registration="registration"))
        ContestTeam.objects.create(team=team, contest=self.contest)
        self.client.force_login(user=self.user_someone_else)
        result = self.client.get(reverse("remove_team", kwargs={'contest_pk': self.contest_id, "team_pk": team.pk}))
        print(result)
        self.assertEqual(result.status_code, status.HTTP_302_FOUND)

    def test_remove_team_from_contest_as_creator(self, patch):
        team = Team.objects.create(crew=Crew.objects.create(
            member1=Person.objects.create(first_name="first", last_name="last", email="someone@somewhere.com")),
            aeroplane=Aeroplane.objects.create(registration="registration"))
        ContestTeam.objects.create(team=team, contest=self.contest)
        self.client.force_login(user=self.user_owner)
        result = self.client.get(reverse("remove_team", kwargs={'contest_pk': self.contest_id, "team_pk": team.pk}))
        print(result)
        self.assertEqual(result.status_code, status.HTTP_302_FOUND)


class TestTokenAuthentication(APITestCase):

    def setUp(self):
        self.user = get_user_model().objects.create(email="user")
        self.user.user_permissions.add(Permission.objects.get(codename="add_contest"),
                                       Permission.objects.get(codename="change_contest"))
        self.token = Token.objects.create(user=self.user)

    def test_post_contest(self):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION='Token {}'.format(self.token.key))
        result = client.post(reverse("contests-list"),
                             data={"name": "My test contest",
                                   "start_time": datetime.datetime.now(datetime.timezone.utc),
                                   "time_zone": "Europe/Oslo",
                                   "finish_time": datetime.datetime.now(datetime.timezone.utc)}, format="json"
                             )

        self.assertEqual(result.status_code, status.HTTP_201_CREATED)
