"""
Regression coverage for the "create a contest, then assign an event token to it" sequence that
RouteToTaskWizard used to perform atomically in one done() (see the wizard->SPA migration plan).
The React replacement (NavigationTaskCreationFlow's ContestCreationStep) deliberately does this as
two separate API calls instead - POST contests-list, then POST contests-detail/assign_token - so a
token-assignment failure leaves a real, usable contest behind rather than rolling everything back.
This pins down that each of those two endpoints, and the combination, still behaves correctly -
`assign_token` itself had no dedicated test coverage before (it was only ever exercised indirectly
through the wizard).
"""

import datetime

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from display.default_scorecards.create_scorecards import create_scorecards
from display.models import Contest, ContestTokenAssignment, TokenType, UserTokenGrant


class TestContestCreationApi(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(email="contest-creation@example.com", password="secret")
        contest_creator, _ = Group.objects.get_or_create(name="ContestCreator")
        self.user.groups.add(contest_creator)
        self.user.user_permissions.add(Permission.objects.get(codename="add_contest"))
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_creates_contest_and_derives_country_from_location(self):
        response = self.client.post(
            "/api/v1/contests/",
            {
                "name": "API-created contest",
                "time_zone": "Europe/Oslo",
                "location": "60.0,11.0",
                "start_time": "2026-10-01T09:00:00Z",
                "finish_time": "2026-10-01T17:00:00Z",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)
        contest = Contest.objects.get(pk=response.json()["id"])
        # Unlike RouteToTaskWizard.done()'s contest_creation branch (which passed a stray
        # country_code key straight into Contest.objects.create(**contest_data), raising
        # TypeError - see the migration plan's "real bugs fixed" list), the API derives this
        # correctly via ContestSerialiser.validate().
        self.assertEqual(contest.country, "NO")
        self.assertEqual(contest.created_by, self.user)
        self.assertTrue(self.user.has_perm("display.change_contest", contest))

    def test_creator_gets_full_permissions_via_initialise(self):
        response = self.client.post(
            "/api/v1/contests/",
            {
                "name": "Permissions contest",
                "time_zone": "UTC",
                "location": "60.0,11.0",
                "start_time": "2026-10-01T09:00:00Z",
                "finish_time": "2026-10-01T17:00:00Z",
            },
            format="json",
        )
        contest = Contest.objects.get(pk=response.json()["id"])
        for perm in ("view_contest", "change_contest", "delete_contest", "add_contest"):
            self.assertTrue(self.user.has_perm(f"display.{perm}", contest), perm)


class TestAssignTokenApi(TestCase):
    def setUp(self):
        create_scorecards()
        self.user = get_user_model().objects.create_user(email="assign-token@example.com", password="secret")
        contest_creator, _ = Group.objects.get_or_create(name="ContestCreator")
        self.user.groups.add(contest_creator)
        self.user.user_permissions.add(Permission.objects.get(codename="add_contest"))
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.contest = Contest.objects.create(
            name="Token assignment contest",
            time_zone="Europe/Oslo",
            start_time=datetime.datetime(2026, 10, 1, 9, 0, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 10, 1, 17, 0, tzinfo=datetime.timezone.utc),
            location="60.0,11.0",
        )
        self.contest.initialise(self.user)
        self.token_type = TokenType.objects.create(name="API token", contestant_limit=25)
        self.token_grant = UserTokenGrant.objects.create(user=self.user, token_type=self.token_type, quantity_total=2)

    def test_assigns_token_and_increments_consumed_quantity(self):
        response = self.client.post(
            f"/api/v1/contests/{self.contest.pk}/assign_token/",
            {"token_grant_id": self.token_grant.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.assertTrue(
            ContestTokenAssignment.objects.filter(contest=self.contest, token_grant=self.token_grant).exists()
        )
        self.token_grant.refresh_from_db()
        self.assertEqual(self.token_grant.quantity_consumed, 1)

    def test_rejects_a_token_grant_belonging_to_another_user(self):
        other_user = get_user_model().objects.create_user(email="not-the-owner@example.com", password="secret")
        others_grant = UserTokenGrant.objects.create(user=other_user, token_type=self.token_type, quantity_total=1)

        response = self.client.post(
            f"/api/v1/contests/{self.contest.pk}/assign_token/",
            {"token_grant_id": others_grant.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.content)
        self.assertFalse(ContestTokenAssignment.objects.filter(contest=self.contest).exists())

    def test_full_create_contest_assign_token_create_navigation_task_sequence(self):
        # The real end-to-end replacement for RouteToTaskWizard's inline-contest-creation branch:
        # three separate API calls rather than one atomic wizard done().
        create_response = self.client.post(
            "/api/v1/contests/",
            {
                "name": "Full sequence contest",
                "time_zone": "Europe/Oslo",
                "location": "60.0,11.0",
                "start_time": "2026-10-01T09:00:00Z",
                "finish_time": "2026-10-01T17:00:00Z",
            },
            format="json",
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED, create_response.content)
        new_contest_id = create_response.json()["id"]

        # A fresh grant, since self.token_grant was already assigned to self.contest in setUp's
        # spirit - use a new one to keep this test independent of the others.
        fresh_grant = UserTokenGrant.objects.create(user=self.user, token_type=self.token_type, quantity_total=1)
        assign_response = self.client.post(
            f"/api/v1/contests/{new_contest_id}/assign_token/",
            {"token_grant_id": fresh_grant.pk},
            format="json",
        )
        self.assertEqual(assign_response.status_code, status.HTTP_200_OK, assign_response.content)

        self.assertTrue(Contest.objects.filter(pk=new_contest_id).exists())
        fresh_grant.refresh_from_db()
        self.assertEqual(fresh_grant.quantity_consumed, 1)
