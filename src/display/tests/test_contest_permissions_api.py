"""
Coverage for ContestViewSet.permissions/permission_detail and the contest_permissions service -
slice 0 of the plan to fold the classic contest-admin pages (list_contest_permissions,
add_user_contest_permissions, change_user_contest_permissions, delete_user_contest_permissions in
views.py) into the SPA contest page. Ports the assertions those classic views' behaviour depends
on: self-removal guard, permission-level mapping, add-by-email and add-by-id.
"""

import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from display.models import Contest


def _make_contest(owner, name="Permissions API contest"):
    contest = Contest.objects.create(
        name=name,
        time_zone="Europe/Oslo",
        start_time=datetime.datetime(2026, 10, 1, 9, 0, tzinfo=datetime.timezone.utc),
        finish_time=datetime.datetime(2026, 10, 1, 17, 0, tzinfo=datetime.timezone.utc),
        location="60.0,11.0",
    )
    contest.initialise(owner)
    return contest


class TestContestPermissionsApi(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(email="perm-owner@example.com", password="secret")
        self.contest = _make_contest(self.owner)
        self.other_user = get_user_model().objects.create_user(email="perm-other@example.com", password="secret")
        self.client = APIClient()
        self.client.force_authenticate(self.owner)
        self.list_url = f"/api/v1/contests/{self.contest.pk}/permissions/"

    def _detail_url(self, user_pk):
        return f"/api/v1/contests/{self.contest.pk}/permissions/{user_pk}/"

    def test_list_starts_with_just_the_creator(self):
        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.assertEqual(
            [{"user_id": self.owner.pk, "email": self.owner.email, "level": "delete"}],
            response.data,
        )

    def test_add_by_email(self):
        response = self.client.post(self.list_url, {"identifier": self.other_user.email, "level": "view"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)
        emails_and_levels = {(row["email"], row["level"]) for row in self.client.get(self.list_url).data}
        self.assertIn((self.other_user.email, "view"), emails_and_levels)

    def test_add_by_id(self):
        response = self.client.post(self.list_url, {"identifier": str(self.other_user.pk), "level": "change"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)
        emails_and_levels = {(row["email"], row["level"]) for row in self.client.get(self.list_url).data}
        self.assertIn((self.other_user.email, "change"), emails_and_levels)

    def test_add_with_unknown_identifier_is_rejected(self):
        response = self.client.post(self.list_url, {"identifier": "nobody@example.com", "level": "view"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_change_level(self):
        self.client.post(self.list_url, {"identifier": self.other_user.email, "level": "view"}, format="json")

        response = self.client.put(self._detail_url(self.other_user.pk), {"level": "delete"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        emails_and_levels = {(row["email"], row["level"]) for row in self.client.get(self.list_url).data}
        self.assertIn((self.other_user.email, "delete"), emails_and_levels)

    def test_remove(self):
        self.client.post(self.list_url, {"identifier": self.other_user.email, "level": "view"}, format="json")

        response = self.client.delete(self._detail_url(self.other_user.pk))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        emails = {row["email"] for row in self.client.get(self.list_url).data}
        self.assertNotIn(self.other_user.email, emails)

    def test_self_removal_is_rejected(self):
        # Never lets the acting user lock themselves out of the contest they're managing.
        response = self.client.delete(self._detail_url(self.owner.pk))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        emails = {row["email"] for row in self.client.get(self.list_url).data}
        self.assertIn(self.owner.email, emails)

    def test_non_editor_gets_404_not_403(self):
        # Same get_queryset scoping behavior already established for every other ContestViewSet
        # action: a user with no view_contest on a non-public contest never learns it exists.
        self.client.force_authenticate(self.other_user)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_get_on_permission_detail_is_rejected(self):
        # Ported from the classic delete_user_contest_permissions view's CSRF regression test
        # (a plain GET view with no CSRF protection was a one-click permission-revocation vector)
        # - DRF only registers put/delete for this action, so GET is method-not-allowed by
        # construction rather than needing an explicit guard.
        self.client.post(self.list_url, {"identifier": self.other_user.email, "level": "view"}, format="json")

        response = self.client.get(self._detail_url(self.other_user.pk))

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
