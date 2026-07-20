import datetime

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase

from display.models import Contest, Club, MyUser, AccessGrant, ClubManagerMembership, TokenType, UserTokenGrant, ContestTokenAssignment


class TestAccessControlModels(TestCase):
    def setUp(self):
        self.user = MyUser.objects.create(email="manager@example.com")
        self.club = Club.objects.create(name="Oslo Aero Club")
        self.contest = Contest.objects.create(
            name="Nordic Training Cup",
            time_zone="Europe/Oslo",
            start_time=datetime.datetime(2026, 1, 10, 9, 0, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 1, 10, 17, 0, tzinfo=datetime.timezone.utc),
            location="60.0,11.0",
            created_by=self.user,
            organizing_club=self.club,
        )

    def test_contest_can_store_creator_and_organizing_club(self):
        contest = Contest.objects.get(pk=self.contest.pk)

        self.assertEqual(self.user, contest.created_by)
        self.assertEqual(self.club, contest.organizing_club)

    def test_club_manager_membership_is_unique_per_user_and_club(self):
        ClubManagerMembership.objects.create(club=self.club, user=self.user)

        with self.assertRaises(IntegrityError):
            ClubManagerMembership.objects.create(club=self.club, user=self.user)

    def test_access_grant_requires_exactly_one_target(self):
        with self.assertRaises(ValidationError):
            AccessGrant(
                tier=AccessGrant.FREE,
                status=AccessGrant.ACTIVE,
                contestant_limit=10,
                task_limit=2,
            ).full_clean()

        with self.assertRaises(ValidationError):
            AccessGrant(
                club=self.club,
                contest=self.contest,
                tier=AccessGrant.ANNUAL_CLUB_PASS,
                status=AccessGrant.ACTIVE,
                contestant_limit=None,
                task_limit=None,
            ).full_clean()

    def test_access_grant_is_active_only_when_status_and_time_window_match(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        active_grant = AccessGrant.objects.create(
            club=self.club,
            tier=AccessGrant.SINGLE_EVENT,
            status=AccessGrant.ACTIVE,
            starts_at=now - datetime.timedelta(days=1),
            expires_at=now + datetime.timedelta(days=1),
            contestant_limit=None,
            task_limit=None,
        )
        expired_grant = AccessGrant.objects.create(
            contest=self.contest,
            tier=AccessGrant.ANNUAL_CLUB_PASS,
            status=AccessGrant.ACTIVE,
            starts_at=now - datetime.timedelta(days=3),
            expires_at=now - datetime.timedelta(days=1),
            contestant_limit=25,
            task_limit=3,
        )
        cancelled_grant = AccessGrant.objects.create(
            club=self.club,
            tier=AccessGrant.MANUAL_OVERRIDE,
            status=AccessGrant.CANCELLED,
            starts_at=now - datetime.timedelta(days=1),
            expires_at=now + datetime.timedelta(days=1),
            contestant_limit=50,
            task_limit=6,
        )

        self.assertEqual(AccessGrant.ANNUAL_CLUB_PASS, active_grant.tier)
        self.assertEqual(AccessGrant.SINGLE_EVENT, expired_grant.tier)
        self.assertEqual(AccessGrant.ANNUAL_CLUB_PASS, cancelled_grant.tier)
        self.assertTrue(active_grant.is_active)
        self.assertFalse(expired_grant.is_active)
        self.assertFalse(cancelled_grant.is_active)

    def test_new_access_models_expose_help_text(self):
        self.assertTrue(ClubManagerMembership._meta.get_field("club").help_text)
        self.assertTrue(TokenType._meta.get_field("description").help_text)
        self.assertTrue(UserTokenGrant._meta.get_field("token_type").help_text)
        self.assertTrue(ContestTokenAssignment._meta.get_field("token_grant").help_text)
        self.assertTrue(AccessGrant._meta.get_field("tier").help_text)
