from unittest.mock import Mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.urls import reverse
from guardian.shortcuts import assign_perm
from rest_framework import status
from rest_framework.test import APITestCase

from display.models import Aeroplane, Club, Contest, Crew, Team

AJAX_HEADER = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}


class TestAutoCompleteAeroplane(APITestCase):
    def setUp(self):
        Aeroplane.objects.create(registration="registration")
        self.user_without_permissions = get_user_model().objects.create(email="test_without_permissions")
        self.user = get_user_model().objects.create(email="test")
        permission = Permission.objects.get(codename="add_contest")
        self.user.user_permissions.add(permission)

    def test_search_without_add_contest_permission_still_allowed(self):
        # Any authenticated user may search - this is used by the self-service
        # RegisterTeamWizard, which most organisers reach via a per-contest
        # guardian change_contest grant, not the site-wide add_contest permission.
        self.client.force_login(self.user_without_permissions)
        result = self.client.post(
            "/display/api/aeroplane/autocomplete/registration/",
            data={"request": 1, "search": "reg"},
            format="json",
            **AJAX_HEADER,
        )
        self.assertEqual(status.HTTP_200_OK, result.status_code)

    def test_search_not_logged_in(self):
        result = self.client.post(
            "/display/api/aeroplane/autocomplete/registration/", data={"request": 1, "search": "reg"}, format="json"
        )
        self.assertEqual(status.HTTP_401_UNAUTHORIZED, result.status_code)

    def test_search(self):
        self.client.force_login(self.user)
        result = self.client.post(
            "/display/api/aeroplane/autocomplete/registration/",
            data={
                "request": 1,
                "search": "reg",
            },
            format="json",
            **AJAX_HEADER,
        )
        self.assertEqual(status.HTTP_200_OK, result.status_code)
        self.assertListEqual(["registration"], result.json())

    def test_fetch(self):
        self.client.force_login(self.user)
        result = self.client.post(
            "/display/api/aeroplane/autocomplete/registration/",
            data={
                "request": 2,
                "search": "registration",
            },
            format="json",
            **AJAX_HEADER,
        )
        self.assertEqual(status.HTTP_200_OK, result.status_code)
        result = result.json()
        self.assertEqual(1, len(result))
        self.assertEqual("registration", result[0]["registration"])


class TestAutoCompleteClub(APITestCase):
    def setUp(self):
        Club.objects.create(name="name")
        self.user_without_permissions = get_user_model().objects.create(email="test_without_permissions")
        self.user = get_user_model().objects.create(email="test")
        permission = Permission.objects.get(codename="add_contest")
        self.user.user_permissions.add(permission)

    def test_search_without_add_contest_permission_still_allowed(self):
        self.client.force_login(self.user_without_permissions)
        result = self.client.post(
            "/display/api/club/autocomplete/name/",
            data={"request": 1, "search": "nam"},
            format="json",
            **AJAX_HEADER,
        )
        self.assertEqual(status.HTTP_200_OK, result.status_code)

    def test_search_not_logged_in(self):
        result = self.client.post(
            "/display/api/club/autocomplete/name/", data={"request": 1, "search": "nam"}, format="json"
        )
        self.assertEqual(status.HTTP_401_UNAUTHORIZED, result.status_code)

    def test_search(self):
        self.client.force_login(self.user)
        result = self.client.post(
            "/display/api/club/autocomplete/name/",
            data={
                "request": 1,
                "search": "nam",
            },
            format="json",
            **AJAX_HEADER,
        )
        self.assertEqual(status.HTTP_200_OK, result.status_code)
        self.assertListEqual([{"label": "name ()", "value": "name"}], result.json())

    def test_fetch(self):
        self.client.force_login(self.user)
        result = self.client.post(
            "/display/api/club/autocomplete/name/",
            data={
                "request": 2,
                "search": "name",
            },
            format="json",
            **AJAX_HEADER,
        )
        self.assertEqual(status.HTTP_200_OK, result.status_code)
        response = result.json()[0]
        del response["id"]
        self.assertDictEqual(
            {"country": "", "country_flag_url": None, "logo": None, "name": "name", "manager_memberships": []}, response
        )


TraccarMock = Mock()
TraccarMock.get_or_create_device.return_value = ({}, False)
