from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from display.models import Contest, TokenType, UserTokenGrant, ContestTokenAssignment, Club, ClubManagerMembership, AccessGrant
from display.services.access_resolver import resolve_contest_access


class TestContestCreateWithToken(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create(email="creator-token@example.com")
        self.user.user_permissions.add(Permission.objects.get(codename="add_contest"))
        self.client.force_login(self.user)
        self.token_type = TokenType.objects.create(name="Create token", contestant_limit=30)
        self.token_grant = UserTokenGrant.objects.create(user=self.user, token_type=self.token_type, quantity_total=2)

    def test_create_contest_can_assign_initial_token(self):
        response = self.client.post(
            reverse("contest_create"),
            data={
                "name": "ContestWithToken",
                "time_zone": "Europe/Oslo",
                "start_time": "2026-10-01T09:00",
                "finish_time": "2026-10-01T17:00",
                "location": "60, 11",
                "initial_token_grant": self.token_grant.id,
                "summary_score_sorting_direction": "asc",
                "autosum_scores": True,
            },
            follow=False,
        )

        self.assertEqual(status.HTTP_302_FOUND, response.status_code)
        contest = Contest.objects.get(name="ContestWithToken")
        self.token_grant.refresh_from_db()
        self.assertTrue(ContestTokenAssignment.objects.filter(contest=contest, token_grant=self.token_grant).exists())
        self.assertEqual(1, self.token_grant.quantity_consumed)

    def test_create_contest_persists_creator_and_applies_club_access_grant(self):
        club = Club.objects.create(name="Create Club")
        ClubManagerMembership.objects.create(club=club, user=self.user, role=ClubManagerMembership.MANAGER, is_active=True)
        AccessGrant.objects.create(
            club=club,
            status=AccessGrant.ACTIVE,
            contestant_limit=12,
        )

        response = self.client.post(
            reverse("contest_create"),
            data={
                "name": "ContestWithClubGrant",
                "time_zone": "Europe/Oslo",
                "start_time": "2026-10-02T09:00",
                "finish_time": "2026-10-02T17:00",
                "location": "60, 11",
                "organizing_club": club.id,
                "summary_score_sorting_direction": "asc",
                "autosum_scores": True,
            },
            follow=False,
        )

        self.assertEqual(status.HTTP_302_FOUND, response.status_code)
        contest = Contest.objects.get(name="ContestWithClubGrant")
        self.assertEqual(self.user, contest.created_by)
        self.assertEqual(club, contest.organizing_club)
        resolution = resolve_contest_access(contest)
        self.assertEqual(AccessGrant.ANNUAL_CLUB_PASS, resolution.tier_code)
        self.assertEqual("club_pass", resolution.source_type)
        self.assertIsNone(resolution.contestant_limit)
        self.assertEqual(12, resolution.package_contestant_limit)
        self.assertTrue(resolution.contestant_limit_uses_free_default)
