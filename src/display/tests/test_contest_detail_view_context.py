from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from guardian.shortcuts import assign_perm

from display.models import Contest, Club, AccessGrant, ClubManagerMembership, TokenType, UserTokenGrant


class TestContestDetailViewContext(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create(email="detail-user@example.com")
        self.user.user_permissions.add(Permission.objects.get(codename="view_contest"))
        self.change_user = get_user_model().objects.create(email="detail-change@example.com")
        self.change_user.user_permissions.add(
            Permission.objects.get(codename="view_contest"),
            Permission.objects.get(codename="change_contest"),
        )
        self.club = Club.objects.create(name="Detail Club")
        ClubManagerMembership.objects.create(club=self.club, user=self.change_user, role=ClubManagerMembership.OWNER, is_active=True)
        self.contest = Contest.objects.create(
            name="Detail Contest",
            time_zone="Europe/Oslo",
            start_time="2026-10-01T09:00:00+00:00",
            finish_time="2026-10-01T17:00:00+00:00",
            location="60.0,11.0",
            created_by=self.change_user,
            organizing_club=self.club,
        )
        assign_perm("view_contest", self.user, self.contest)
        assign_perm("view_contest", self.change_user, self.contest)
        assign_perm("change_contest", self.change_user, self.contest)
        self.grant = AccessGrant.objects.create(
            club=self.club,
            status=AccessGrant.ACTIVE,
            contestant_limit=10,
        )
        self.token_type = TokenType.objects.create(name="Detail token", contestant_limit=8)
        self.token_grant = UserTokenGrant.objects.create(user=self.change_user, token_type=self.token_type, quantity_total=2)

    def test_view_permission_gets_read_only_access_context(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("contest_details", kwargs={"pk": self.contest.id}))

        self.assertEqual(200, response.status_code)
        self.assertContains(response, "Access & Limits")
        self.assertContains(response, "Annual club pass")
        self.assertContains(response, "club_pass")
        self.assertContains(response, "Free-tier fallback improved the effective limits")
        self.assertContains(response, "Contestants")
        self.assertNotContains(response, ">Tasks<", html=False)
        self.assertNotContains(response, "Token Management")
        self.assertNotContains(response, "Club managers")

    def test_change_permission_gets_management_context(self):
        self.client.force_login(self.change_user)
        response = self.client.get(reverse("contest_details", kwargs={"pk": self.contest.id}))

        self.assertEqual(200, response.status_code)
        self.assertContains(response, "Access & Limits")
        self.assertContains(response, "Annual club pass")
        self.assertContains(response, "club_pass")
        self.assertContains(response, "Token Management")
        self.assertContains(response, "No token is currently assigned to this contest.")
        self.assertContains(response, self.change_user.email)
        self.assertContains(response, "Assign token")
        self.assertContains(response, "Contestants")
        self.assertNotContains(response, ">Tasks<", html=False)
