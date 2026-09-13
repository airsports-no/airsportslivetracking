"""
Coverage for ContestSerialiser.club_access_grants/club_manager_memberships - ported from the
classic contest_detail view's context (views.py ContestDetailView.get_context_data) as part of
folding that page into the SPA contest dashboard.
"""

import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from display.models import AccessGrant, Club, ClubManagerMembership, Contest


class TestContestClubAccessSerialisation(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(email="club-access-owner@example.com", password="secret")
        self.club = Club.objects.create(name="Club access test club")
        self.contest = Contest.objects.create(
            name="Club access contest",
            time_zone="Europe/Oslo",
            start_time=datetime.datetime(2026, 10, 1, 9, 0, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 10, 1, 17, 0, tzinfo=datetime.timezone.utc),
            location="60.0,11.0",
            organizing_club=self.club,
        )
        self.contest.initialise(self.owner)
        self.client = APIClient()
        self.client.force_authenticate(self.owner)
        self.detail_url = f"/api/v1/contests/{self.contest.pk}/"

    def test_no_organizing_club_means_empty_lists(self):
        contest = Contest.objects.create(
            name="No club contest",
            time_zone="Europe/Oslo",
            start_time=datetime.datetime(2026, 10, 1, 9, 0, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 10, 1, 17, 0, tzinfo=datetime.timezone.utc),
            location="60.0,11.0",
        )
        contest.initialise(self.owner)

        response = self.client.get(f"/api/v1/contests/{contest.pk}/")

        self.assertEqual(response.data["club_access_grants"], [])
        self.assertEqual(response.data["club_manager_memberships"], [])

    def test_active_club_access_grant_is_listed(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        AccessGrant.objects.create(
            club=self.club,
            tier=AccessGrant.ANNUAL_CLUB_PASS,
            status=AccessGrant.ACTIVE,
            starts_at=now - datetime.timedelta(days=1),
            expires_at=now + datetime.timedelta(days=1),
            contestant_limit=42,
        )

        response = self.client.get(self.detail_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.assertEqual(len(response.data["club_access_grants"]), 1)
        self.assertEqual(response.data["club_access_grants"][0]["contestant_limit"], 42)

    def test_club_manager_memberships_only_visible_to_someone_who_can_manage_the_contest(self):
        manager = get_user_model().objects.create_user(email="club-access-manager@example.com", password="secret")
        ClubManagerMembership.objects.create(club=self.club, user=manager, role=ClubManagerMembership.MANAGER, is_active=True)

        owner_response = self.client.get(self.detail_url)
        self.assertEqual(len(owner_response.data["club_manager_memberships"]), 1)
        self.assertEqual(owner_response.data["club_manager_memberships"][0]["email"], manager.email)

        outsider = get_user_model().objects.create_user(email="club-access-outsider@example.com", password="secret")
        self.contest.make_public()
        self.client.force_authenticate(outsider)
        outsider_response = self.client.get(self.detail_url)
        self.assertEqual(outsider_response.data["club_manager_memberships"], [])
