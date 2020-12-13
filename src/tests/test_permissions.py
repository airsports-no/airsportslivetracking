from django.contrib.auth.models import User, Permission
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from display.models import Contest


class TestCreateContest(APITestCase):
    def setUp(self):
        self.user_with_permissions = User.objects.create(username="withpermissions")
        permission = Permission.objects.get(codename="add_contest")
        self.user_with_permissions.user_permissions.add(permission)
        self.user_without_permissions = User.objects.create(username="withoutpermissions")
        self.base_url = reverse("contests-list")

    def test_create_contest_without_login(self):
        result = self.client.post(self.base_url, data={"name": "TestContest"})
        print(result)
        self.assertEqual(result.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_contest_without_privileges(self):
        self.client.force_login(user=self.user_without_permissions)
        result = self.client.post(self.base_url, data={"name": "TestContest"})
        print(result)
        self.assertEqual(result.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_contest_with_privileges(self):
        self.client.force_login(user=self.user_with_permissions)
        result = self.client.post(self.base_url, data={"name": "TestContest", "is_public": False})
        print(result)
        print(result.content)
        self.assertEqual(result.status_code, status.HTTP_201_CREATED)


class TestAccessContest(APITestCase):
    def setUp(self):
        self.user_owner = User.objects.create(username="withpermissions")
        permission = Permission.objects.get(codename="add_contest")
        self.user_owner.user_permissions.add(permission)
        self.user_owner.refresh_from_db()
        self.user_someone_else = User.objects.create(username="withoutpermissions")
        self.client.force_login(user=self.user_owner)
        result = self.client.post(reverse("contests-list"), data={"name": "TestContest", "is_public": False})
        print(result.json())
        self.contest_id = result.json()["id"]
        self.contest = Contest.objects.get(pk=self.contest_id)

    def test_modify_contest_without_login(self):
        self.client.logout()
        result = self.client.put(reverse("contests-detail", kwargs={'pk': self.contest_id}),
                                 data={"name": "TestContest2"})
        print(result)
        self.assertEqual(result.status_code, status.HTTP_404_NOT_FOUND)

    def test_modify_contest_as_someone_else(self):
        self.client.force_login(user=self.user_someone_else)
        result = self.client.put(reverse("contests-detail", kwargs={'pk': self.contest_id}),
                                 data={"name": "TestContest2"})
        print(result)
        self.assertEqual(result.status_code, status.HTTP_404_NOT_FOUND)

    def test_modify_contest_as_creator(self):
        self.client.force_login(user=self.user_owner)
        result = self.client.put(reverse("contests-detail", kwargs={'pk': self.contest_id}),
                                 data={"name": "TestContest2"})
        print(result)
        print(result.content)
        self.assertEqual(result.status_code, status.HTTP_200_OK)

    def test_publish_contest_without_login(self):
        self.client.logout()
        result = self.client.put(reverse("contests-publish", kwargs={'pk': self.contest_id}))
        print(result)
        self.assertEqual(result.status_code, status.HTTP_404_NOT_FOUND)

    def test_publish_contest_as_someone_else(self):
        self.client.force_login(user=self.user_someone_else)
        result = self.client.put(reverse("contests-publish", kwargs={'pk': self.contest_id}))
        print(result)
        self.assertEqual(result.status_code, status.HTTP_404_NOT_FOUND)

    def test_publish_contest_as_creator(self):
        self.client.force_login(user=self.user_owner)
        result = self.client.put(reverse("contests-publish", kwargs={'pk': self.contest_id}))
        print(result)
        print(result.content)
        self.assertEqual(result.status_code, status.HTTP_200_OK)

    def test_view_contest_without_login(self):
        self.client.logout()
        result = self.client.get(reverse("contests-detail", kwargs={'pk': self.contest_id}),
                                 data={"name": "TestContest2"})
        print(result)
        self.assertEqual(result.status_code, status.HTTP_404_NOT_FOUND)

    def test_view_contest_as_someone_else(self):
        self.client.force_login(user=self.user_someone_else)
        result = self.client.get(reverse("contests-detail", kwargs={'pk': self.contest_id}),
                                 data={"name": "TestContest2"})
        print(result)
        self.assertEqual(result.status_code, status.HTTP_404_NOT_FOUND)

    def test_view_contest_as_creator(self):
        self.client.force_login(user=self.user_owner)
        result = self.client.get(reverse("contests-detail", kwargs={'pk': self.contest_id}),
                                 data={"name": "TestContest2"})
        print(result)
        print(result.content)
        self.assertEqual(result.status_code, status.HTTP_200_OK)

    def test_view_public_contest_without_login(self):
        self.contest.is_public = True
        self.contest.save()
        self.client.logout()
        result = self.client.get(reverse("contests-detail", kwargs={'pk': self.contest_id}),
                                 data={"name": "TestContest2"})
        print(result)
        self.assertEqual(result.status_code, status.HTTP_200_OK)

    def test_view_public_contest_as_someone_else(self):
        self.contest.is_public = True
        self.contest.save()
        self.client.force_login(user=self.user_someone_else)
        result = self.client.get(reverse("contests-detail", kwargs={'pk': self.contest_id}),
                                 data={"name": "TestContest2"})
        print(result)
        self.assertEqual(result.status_code, status.HTTP_200_OK)

    def test_view_public_contest_as_creator(self):
        self.contest.is_public = True
        self.contest.save()
        self.client.force_login(user=self.user_owner)
        result = self.client.get(reverse("contests-detail", kwargs={'pk': self.contest_id}),
                                 data={"name": "TestContest2"})
        print(result)
        print(result.content)
        self.assertEqual(result.status_code, status.HTTP_200_OK)
