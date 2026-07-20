from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.urls import reverse
from guardian.shortcuts import assign_perm
from rest_framework import status
from rest_framework.test import APITestCase

from display.models import Contest, Club, TokenType, UserTokenGrant


class TestContestDetailCaching(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create(email="cache-user@example.com")
        self.user.user_permissions.add(Permission.objects.get(codename="view_contest"))
        self.club = Club.objects.create(name="Cache Club")
        self.contest = Contest.objects.create(
            name="Cache Contest",
            time_zone="Europe/Oslo",
            start_time="2026-10-01T09:00:00+00:00",
            finish_time="2026-10-01T17:00:00+00:00",
            location="60.0,11.0",
            organizing_club=self.club,
            is_public=True,
            is_featured=True,
        )
        assign_perm("view_contest", self.user, self.contest)
        token_type = TokenType.objects.create(name="Cache token", contestant_limit=10, task_limit=1)
        UserTokenGrant.objects.create(user=self.user, token_type=token_type, quantity_total=1)

    def test_public_contest_detail_with_authenticated_user_is_private_cache(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("contests-detail", kwargs={"pk": self.contest.id}))

        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual("private, no-cache", response["Cache-Control"])
