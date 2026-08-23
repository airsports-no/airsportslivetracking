from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from guardian.shortcuts import assign_perm
from rest_framework import status
from rest_framework.test import APITestCase

from display.models import (
    Contest,
    ContestTeam,
    Crew,
    Person,
    Team,
    Aeroplane,
    TokenType,
    UserTokenGrant,
    ContestTokenAssignment,
)
from utilities.mock_utilities import TraccarMock


@patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
@patch("display.signals.get_traccar_instance", return_value=TraccarMock)
class TestContestTokenAssignmentApi(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create(email="owner@example.com")
        self.client.force_login(self.user)
        self.contest = Contest.objects.create(
            name="Token API Contest",
            time_zone="Europe/Oslo",
            start_time="2026-04-01T09:00:00+00:00",
            finish_time="2026-04-01T17:00:00+00:00",
            location="60.0,11.0",
            created_by=self.user,
        )
        self.token_type = TokenType.objects.create(
            name="Token 20/2",
            contestant_limit=20,
        )
        self.token_grant = UserTokenGrant.objects.create(
            user=self.user,
            token_type=self.token_type,
            quantity_total=2,
            quantity_consumed=0,
        )
        assign_perm("view_contest", self.user, self.contest)
        assign_perm("change_contest", self.user, self.contest)

    def test_assign_token_to_contest_endpoint_consumes_token(self, *_args):
        url = reverse("contests-assign-token", kwargs={"pk": self.contest.id})
        response = self.client.post(url, {"token_grant_id": self.token_grant.id}, format="json")

        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.token_grant.refresh_from_db()
        self.assertEqual(1, self.token_grant.quantity_consumed)
        self.assertTrue(ContestTokenAssignment.objects.filter(contest=self.contest).exists())
        self.assertEqual(self.token_type.id, response.data["token_type"])

    def test_assign_token_to_contest_endpoint_rejects_other_users_token(self, *_args):
        other_user = get_user_model().objects.create(email="other@example.com")
        other_grant = UserTokenGrant.objects.create(
            user=other_user,
            token_type=self.token_type,
            quantity_total=1,
            quantity_consumed=0,
        )
        url = reverse("contests-assign-token", kwargs={"pk": self.contest.id})
        response = self.client.post(url, {"token_grant_id": other_grant.id}, format="json")

        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    @patch("display.viewsets.assert_can_register_team")
    def test_existing_capacity_integration_no_longer_runs_at_signup(self, mock_guard, *_args):
        person = Person.objects.create(first_name="Pilot", last_name="One", email=self.user.email)
        team = Team.objects.create(
            crew=Crew.objects.create(member1=person),
            aeroplane=Aeroplane.objects.create(registration="LN-INT"),
        )
        ContestTeam.objects.create(contest=self.contest, team=team)
        self.contest.make_public()
        url = reverse("contests-signup", kwargs={"pk": self.contest.id})
        self.client.post(
            url,
            {
                "club_name": "Club",
                "aircraft_registration": "LN-NEW",
                "pilot_id": person.id,
                "airspeed": 70,
                "copilot_id": None,
            },
            format="json",
        )

        mock_guard.assert_not_called()
