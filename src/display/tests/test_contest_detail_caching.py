from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.urls import reverse
from guardian.shortcuts import assign_perm
from rest_framework import status
from rest_framework.test import APITestCase

from display.models import Contest, Club, TokenType, UserTokenGrant, ContestTokenAssignment, ClubManagerMembership, AccessGrant


class TestContestDetailCaching(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create(email="cache-user@example.com")
        self.user.user_permissions.add(Permission.objects.get(codename="view_contest"))
        self.change_user = get_user_model().objects.create(email="cache-change@example.com")
        self.change_user.user_permissions.add(Permission.objects.get(codename="view_contest"))
        self.club = Club.objects.create(name="Cache Club")
        ClubManagerMembership.objects.create(club=self.club, user=self.change_user, role=ClubManagerMembership.OWNER, is_active=True)
        self.contest = Contest.objects.create(
            name="Cache Contest",
            time_zone="Europe/Oslo",
            start_time="2026-10-01T09:00:00+00:00",
            finish_time="2026-10-01T17:00:00+00:00",
            location="60.0,11.0",
            organizing_club=self.club,
            created_by=self.change_user,
            is_public=True,
            is_featured=True,
        )
        assign_perm("view_contest", self.user, self.contest)
        assign_perm("view_contest", self.change_user, self.contest)
        assign_perm("change_contest", self.change_user, self.contest)
        self.token_type = TokenType.objects.create(name="Cache token", contestant_limit=10, task_limit=1)
        self.token_grant = UserTokenGrant.objects.create(user=self.change_user, token_type=self.token_type, quantity_total=1)
        AccessGrant.objects.create(club=self.club, status=AccessGrant.ACTIVE, contestant_limit=10, task_limit=2)

    def test_public_contest_detail_with_authenticated_user_is_private_cache(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("contests-detail", kwargs={"pk": self.contest.id}))

        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual("private, no-cache", response["Cache-Control"])

    def test_token_assignment_changes_contest_detail_etag(self):
        self.client.force_login(self.change_user)
        detail_url = reverse("contests-detail", kwargs={"pk": self.contest.id})
        first = self.client.get(detail_url)
        first_etag = first["ETag"]

        assign_url = reverse("contests-assign-token", kwargs={"pk": self.contest.id})
        assign_response = self.client.post(assign_url, {"token_grant_id": self.token_grant.id}, format="json")
        self.assertEqual(status.HTTP_200_OK, assign_response.status_code)

        second = self.client.get(detail_url, HTTP_IF_NONE_MATCH=first_etag)
        self.assertEqual(status.HTTP_200_OK, second.status_code)
        self.assertNotEqual(first_etag, second["ETag"])
