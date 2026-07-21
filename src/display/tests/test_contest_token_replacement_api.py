from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from guardian.shortcuts import assign_perm
from rest_framework import status
from rest_framework.test import APITestCase

from display.models import Contest, TokenType, UserTokenGrant, ContestTokenAssignment


@patch("display.models.contestant.get_traccar_instance")
@patch("display.signals.get_traccar_instance")
class TestContestTokenReplacementApi(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create(email="replace-token@example.com")
        self.client.force_login(self.user)
        self.contest = Contest.objects.create(
            name="Replace Token Contest",
            time_zone="Europe/Oslo",
            start_time="2026-04-01T09:00:00+00:00",
            finish_time="2026-04-01T17:00:00+00:00",
            location="60.0,11.0",
            created_by=self.user,
        )
        assign_perm("view_contest", self.user, self.contest)
        assign_perm("change_contest", self.user, self.contest)
        self.small_type = TokenType.objects.create(name="Replace small", contestant_limit=10)
        self.large_type = TokenType.objects.create(name="Replace large", contestant_limit=50)
        self.small_grant = UserTokenGrant.objects.create(user=self.user, token_type=self.small_type, quantity_total=2)
        self.large_grant = UserTokenGrant.objects.create(user=self.user, token_type=self.large_type, quantity_total=2)
        ContestTokenAssignment.objects.create(contest=self.contest, token_grant=self.small_grant, token_type=self.small_type, assigned_by=self.user)
        self.small_grant.quantity_consumed = 1
        self.small_grant.save(update_fields=["quantity_consumed", "updated_at"])

    def test_replace_token_endpoint_consumes_new_token(self, *_args):
        url = reverse("contests-replace-token", kwargs={"pk": self.contest.id})
        response = self.client.post(url, {"token_grant_id": self.large_grant.id}, format="json")

        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.small_grant.refresh_from_db()
        self.large_grant.refresh_from_db()
        assignment = ContestTokenAssignment.objects.get(contest=self.contest)
        self.assertEqual(1, self.small_grant.quantity_consumed)
        self.assertEqual(1, self.large_grant.quantity_consumed)
        self.assertEqual(self.large_grant.id, assignment.token_grant_id)
