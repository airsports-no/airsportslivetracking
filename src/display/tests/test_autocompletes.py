from unittest.mock import patch, Mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.urls import reverse
from guardian.shortcuts import assign_perm
from rest_framework import status
from rest_framework.test import APITestCase

from display.models import Aeroplane, Club, Person, Contest, Crew, Team

AJAX_HEADER = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}


class TestAutoCompleteAeroplane(APITestCase):
    def setUp(self):
        Aeroplane.objects.create(registration="registration")
        self.user_without_permissions = get_user_model().objects.create_and_push(email="test_without_permissions")
        self.user = get_user_model().objects.create_and_push(email="test")
        permission = Permission.objects.get(codename="add_contest")
        self.user.user_permissions.add(permission)

    def test_search_without_permission(self):
        self.client.force_login(self.user_without_permissions)
        result = self.client.post("/display/aeroplane/autocomplete/registration/", data={
            "request": 1,
            "search": "reg"
        }, format="json")
        self.assertEqual(status.HTTP_403_FORBIDDEN, result.status_code)

    def test_search_not_logged_in(self):
        self.client.force_login(self.user_without_permissions)
        result = self.client.post("/display/aeroplane/autocomplete/registration/", data={
            "request": 1,
            "search": "reg"
        }, format="json")
        self.assertEqual(status.HTTP_403_FORBIDDEN, result.status_code)

    def test_search(self):
        self.client.force_login(self.user)
        result = self.client.post("/display/aeroplane/autocomplete/registration/", data={
            "request": 1,
            "search": "reg",
        }, format="json", **AJAX_HEADER)
        self.assertEqual(status.HTTP_200_OK, result.status_code)
        self.assertListEqual(["registration"], result.json())

    def test_fetch(self):
        self.client.force_login(self.user)
        result = self.client.post("/display/aeroplane/autocomplete/registration/", data={
            "request": 2,
            "search": "registration",
        }, format="json", **AJAX_HEADER)
        self.assertEqual(status.HTTP_200_OK, result.status_code)
        result = result.json()
        self.assertEqual(1, len(result))
        self.assertEqual("registration", result[0]["registration"])


class TestAutoCompleteClub(APITestCase):
    def setUp(self):
        Club.objects.create(name="name")
        self.user_without_permissions = get_user_model().objects.create_and_push(email="test_without_permissions")
        self.user = get_user_model().objects.create_and_push(email="test")
        permission = Permission.objects.get(codename="add_contest")
        self.user.user_permissions.add(permission)

    def test_search_without_permission(self):
        self.client.force_login(self.user_without_permissions)
        result = self.client.post("/display/club/autocomplete/name/", data={
            "request": 1,
            "search": "nam"
        }, format="json")
        self.assertEqual(status.HTTP_403_FORBIDDEN, result.status_code)

    def test_search_not_logged_in(self):
        self.client.force_login(self.user_without_permissions)
        result = self.client.post("/display/club/autocomplete/name/", data={
            "request": 1,
            "search": "nam"
        }, format="json")
        self.assertEqual(status.HTTP_403_FORBIDDEN, result.status_code)

    def test_search(self):
        self.client.force_login(self.user)
        result = self.client.post("/display/club/autocomplete/name/", data={
            "request": 1,
            "search": "nam",
        }, format="json", **AJAX_HEADER)
        self.assertEqual(status.HTTP_200_OK, result.status_code)
        self.assertListEqual([{'label': 'name ()', 'value': 'name'}], result.json())

    def test_fetch(self):
        self.client.force_login(self.user)
        result = self.client.post("/display/club/autocomplete/name/", data={
            "request": 2,
            "search": "name",
        }, format="json", **AJAX_HEADER)
        self.assertEqual(status.HTTP_200_OK, result.status_code)
        self.assertDictEqual({'country': '', 'country_flag_url': None, 'id': 1, 'logo': None, 'name': 'name'},
                             result.json()[0])


TraccarMock = Mock()
TraccarMock.get_or_create_device.return_value = ({}, False)


class TestAutoCompletePersonFirstName(APITestCase):
    @patch("display.models.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, p):
        Person.objects.create(first_name="first_name", last_name="last_name", email="mail@address.com",
                              phone="+471234678")
        self.user_without_permissions = get_user_model().objects.create_and_push(email="test_without_permissions")
        self.user = get_user_model().objects.create_and_push(email="test")
        permission = Permission.objects.get(codename="add_contest")
        self.user.user_permissions.add(permission)

    def test_search_without_permission(self):
        self.client.force_login(self.user_without_permissions)
        result = self.client.post("/display/contestant/autocomplete/firstname/", data={
            "request": 1,
            "search": "nam"
        }, format="json")
        self.assertEqual(status.HTTP_403_FORBIDDEN, result.status_code)

    def test_search_not_logged_in(self):
        self.client.force_login(self.user_without_permissions)
        result = self.client.post("/display/contestant/autocomplete/firstname/", data={
            "request": 1,
            "search": "first"
        }, format="json")
        self.assertEqual(status.HTTP_403_FORBIDDEN, result.status_code)

    def test_search(self):
        self.client.force_login(self.user)
        result = self.client.post("/display/contestant/autocomplete/firstname/", data={
            "request": 1,
            "search": "first",
        }, format="json", **AJAX_HEADER)
        self.assertEqual(status.HTTP_200_OK, result.status_code)
        self.assertListEqual([{'label': 'first_name last_name', 'value': 'first_name'}], result.json())

    def test_search_fail(self):
        self.client.force_login(self.user)
        result = self.client.post("/display/contestant/autocomplete/firstname/", data={
            "request": 1,
            "search": "different",
        }, format="json", **AJAX_HEADER)
        self.assertEqual(status.HTTP_200_OK, result.status_code)
        self.assertListEqual([], result.json())

    def test_fetch(self):
        self.client.force_login(self.user)
        result = self.client.post("/display/contestant/autocomplete/firstname/", data={
            "request": 2,
            "search": "first_name",
        }, format="json", **AJAX_HEADER)
        self.assertEqual(status.HTTP_200_OK, result.status_code)
        result = result.json()
        self.assertEqual(1, len(result))
        result = result[0]
        self.assertEqual("first_name", result["first_name"])
        self.assertEqual("last_name", result["last_name"])


class TestAutoCompletePersonLastname(APITestCase):
    @patch("display.models.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, p):
        Person.objects.create(first_name="first_name", last_name="last_name", email="mail@address.com",
                              phone="+471234678")
        self.user_without_permissions = get_user_model().objects.create_and_push(email="test_without_permissions")
        self.user = get_user_model().objects.create_and_push(email="test")
        permission = Permission.objects.get(codename="add_contest")
        self.user.user_permissions.add(permission)

    def test_search_without_permission(self):
        self.client.force_login(self.user_without_permissions)
        result = self.client.post("/display/contestant/autocomplete/lastname/", data={
            "request": 1,
            "search": "nam"
        }, format="json")
        self.assertEqual(status.HTTP_403_FORBIDDEN, result.status_code)

    def test_search_not_logged_in(self):
        self.client.force_login(self.user_without_permissions)
        result = self.client.post("/display/contestant/autocomplete/lastname/", data={
            "request": 1,
            "search": "last"
        }, format="json")
        self.assertEqual(status.HTTP_403_FORBIDDEN, result.status_code)

    def test_search(self):
        self.client.force_login(self.user)
        result = self.client.post("/display/contestant/autocomplete/lastname/", data={
            "request": 1,
            "search": "last",
        }, format="json", **AJAX_HEADER)
        self.assertEqual(status.HTTP_200_OK, result.status_code)
        self.assertListEqual([{'label': 'first_name last_name', 'value': 'last_name'}], result.json())

    def test_search_fail(self):
        self.client.force_login(self.user)
        result = self.client.post("/display/contestant/autocomplete/lastname/", data={
            "request": 1,
            "search": "different",
        }, format="json", **AJAX_HEADER)
        self.assertEqual(status.HTTP_200_OK, result.status_code)
        self.assertListEqual([], result.json())

    def test_fetch(self):
        self.client.force_login(self.user)
        result = self.client.post("/display/contestant/autocomplete/lastname/", data={
            "request": 2,
            "search": "last_name",
        }, format="json", **AJAX_HEADER)
        self.assertEqual(status.HTTP_200_OK, result.status_code)
        result = result.json()
        self.assertEqual(1, len(result))
        result = result[0]
        self.assertEqual("first_name", result["first_name"])
        self.assertEqual("last_name", result["last_name"])


class TestAutoCompletePersonPhone(APITestCase):
    @patch("display.models.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, p):
        Person.objects.create(first_name="first_name", last_name="last_name", email="mail@address.com",
                              phone="+471234678")
        self.user_without_permissions = get_user_model().objects.create_and_push(email="test_without_permissions")
        self.user = get_user_model().objects.create_and_push(email="test")
        permission = Permission.objects.get(codename="add_contest")
        self.user.user_permissions.add(permission)

    def test_search_without_permission(self):
        self.client.force_login(self.user_without_permissions)
        result = self.client.post("/display/contestant/autocomplete/phone/", data={
            "request": 1,
            "search": "123"
        }, format="json")
        self.assertEqual(status.HTTP_403_FORBIDDEN, result.status_code)

    def test_search_not_logged_in(self):
        self.client.force_login(self.user_without_permissions)
        result = self.client.post("/display/contestant/autocomplete/phone/", data={
            "request": 1,
            "search": "123"
        }, format="json")
        self.assertEqual(status.HTTP_403_FORBIDDEN, result.status_code)

    def test_search(self):
        self.client.force_login(self.user)
        result = self.client.post("/display/contestant/autocomplete/phone/", data={
            "request": 1,
            "search": "123",
        }, format="json", **AJAX_HEADER)
        self.assertEqual(status.HTTP_200_OK, result.status_code)
        self.assertListEqual(['+471234678'], result.json())

    def test_search_fail(self):
        self.client.force_login(self.user)
        result = self.client.post("/display/contestant/autocomplete/phone/", data={
            "request": 1,
            "search": "321",
        }, format="json", **AJAX_HEADER)
        self.assertEqual(status.HTTP_200_OK, result.status_code)
        self.assertListEqual([], result.json())

    def test_fetch(self):
        self.client.force_login(self.user)
        result = self.client.post("/display/contestant/autocomplete/phone/", data={
            "request": 2,
            "search": "+471234678",
        }, format="json", **AJAX_HEADER)
        self.assertEqual(status.HTTP_200_OK, result.status_code)
        result = result.json()
        self.assertEqual(1, len(result))
        result = result[0]
        self.assertEqual("first_name", result["first_name"])
        self.assertEqual("last_name", result["last_name"])


class TestAutoCompletePersonEmail(APITestCase):
    @patch("display.models.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, p):
        Person.objects.create(first_name="first_name", last_name="last_name", email="mail@address.com",
                              phone="+471234678")
        self.user_without_permissions = get_user_model().objects.create_and_push(email="test_without_permissions")
        self.user = get_user_model().objects.create_and_push(email="test")
        permission = Permission.objects.get(codename="add_contest")
        self.user.user_permissions.add(permission)

    def test_search_without_permission(self):
        self.client.force_login(self.user_without_permissions)
        result = self.client.post("/display/contestant/autocomplete/email/", data={
            "request": 1,
            "search": "mail"
        }, format="json")
        self.assertEqual(status.HTTP_403_FORBIDDEN, result.status_code)

    def test_search_not_logged_in(self):
        self.client.force_login(self.user_without_permissions)
        result = self.client.post("/display/contestant/autocomplete/email/", data={
            "request": 1,
            "search": "mail"
        }, format="json")
        self.assertEqual(status.HTTP_403_FORBIDDEN, result.status_code)

    def test_search(self):
        self.client.force_login(self.user)
        result = self.client.post("/display/contestant/autocomplete/email/", data={
            "request": 1,
            "search": "mail",
        }, format="json", **AJAX_HEADER)
        self.assertEqual(status.HTTP_200_OK, result.status_code)
        self.assertListEqual(['mail@address.com'], result.json())

    def test_search_fail(self):
        self.client.force_login(self.user)
        result = self.client.post("/display/contestant/autocomplete/email/", data={
            "request": 1,
            "search": "321",
        }, format="json", **AJAX_HEADER)
        self.assertEqual(status.HTTP_200_OK, result.status_code)
        self.assertListEqual([], result.json())

    def test_fetch(self):
        self.client.force_login(self.user)
        result = self.client.post("/display/contestant/autocomplete/email/", data={
            "request": 2,
            "search": "mail@address.com",
        }, format="json", **AJAX_HEADER)
        self.assertEqual(status.HTTP_200_OK, result.status_code)
        result = result.json()
        self.assertEqual(1, len(result))
        result = result[0]
        self.assertEqual("first_name", result["first_name"])
        self.assertEqual("last_name", result["last_name"])


class TestAutoCompletePersonId(APITestCase):
    @patch("display.models.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, p):
        self.person = Person.objects.create(first_name="first_name", last_name="last_name", email="mail@address.com",
                              phone="+471234678")
        self.user_without_permissions = get_user_model().objects.create_and_push(email="test_without_permissions")
        self.user = get_user_model().objects.create_and_push(email="test")
        permission = Permission.objects.get(codename="add_contest")
        self.user.user_permissions.add(permission)

    def test_search_without_permission(self):
        self.client.force_login(self.user_without_permissions)
        result = self.client.post("/display/contestant/autocomplete/id/", data={
            "request": 1,
            "search": self.person.pk,
        }, format="json")
        self.assertEqual(status.HTTP_403_FORBIDDEN, result.status_code)

    def test_search_not_logged_in(self):
        self.client.force_login(self.user_without_permissions)
        result = self.client.post("/display/contestant/autocomplete/id/", data={
            "request": 1,
            "search": self.person.pk,
        }, format="json")
        self.assertEqual(status.HTTP_403_FORBIDDEN, result.status_code)

    def test_search(self):
        self.client.force_login(self.user)
        result = self.client.post("/display/contestant/autocomplete/id/", data={
            "request": 1,
            "search": self.person.pk,
        }, format="json", **AJAX_HEADER)
        self.assertEqual(status.HTTP_200_OK, result.status_code)
        self.assertListEqual(['+471234678'], result.json())

    def test_search_fail(self):
        self.client.force_login(self.user)
        result = self.client.post("/display/contestant/autocomplete/id/", data={
            "request": 1,
            "search": -321,
        }, format="json", **AJAX_HEADER)
        self.assertEqual(status.HTTP_200_OK, result.status_code)
        self.assertListEqual([], result.json())

    def test_fetch(self):
        self.client.force_login(self.user)
        result = self.client.post("/display/contestant/autocomplete/id/", data={
            "request": 2,
            "search": self.person.pk,
        }, format="json", **AJAX_HEADER)
        self.assertEqual(status.HTTP_200_OK, result.status_code)
        result = result.json()
        self.assertEqual(1, len(result))
        result = result[0]
        self.assertEqual("first_name", result["first_name"])
        self.assertEqual("last_name", result["last_name"])
