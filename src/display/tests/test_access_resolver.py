import datetime

from django.test import TestCase, override_settings

from display.models import Contest, Club, MyUser, AccessGrant, ClubManagerMembership
from display.services.access_resolver import resolve_contest_access


@override_settings(
    DEFAULT_FREE_CONTESTANT_LIMIT=None,
    ACCESS_ENFORCEMENT_MODE="audit",
)
class TestAccessResolver(TestCase):
    def setUp(self):
        self.user = MyUser.objects.create(email="organizer@example.com")
        self.club = Club.objects.create(name="Resolver Club")
        self.contest = Contest.objects.create(
            name="Resolver Contest",
            time_zone="Europe/Oslo",
            start_time=datetime.datetime(2026, 2, 1, 9, 0, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 2, 1, 17, 0, tzinfo=datetime.timezone.utc),
            location="60.0,11.0",
            created_by=self.user,
            organizing_club=self.club,
        )

    def test_returns_free_defaults_when_no_active_grant_exists(self):
        resolution = resolve_contest_access(self.contest)

        self.assertEqual("free", resolution.tier_code)
        self.assertEqual("free_defaults", resolution.source_type)
        self.assertIsNone(resolution.contestant_limit)
        self.assertEqual("audit", resolution.enforcement_mode)

    def test_contest_level_grant_takes_precedence_over_club_grant(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        ClubManagerMembership.objects.create(club=self.club, user=self.user, is_active=True)
        AccessGrant.objects.create(
            club=self.club,
            tier=AccessGrant.ANNUAL_CLUB_PASS,
            status=AccessGrant.ACTIVE,
            starts_at=now - datetime.timedelta(days=1),
            expires_at=now + datetime.timedelta(days=1),
            contestant_limit=None,
        )
        contest_grant = AccessGrant.objects.create(
            contest=self.contest,
            tier=AccessGrant.SINGLE_EVENT,
            status=AccessGrant.ACTIVE,
            starts_at=now - datetime.timedelta(days=1),
            expires_at=now + datetime.timedelta(days=1),
            contestant_limit=25,
        )

        resolution = resolve_contest_access(self.contest)

        self.assertEqual("single_event", resolution.tier_code)
        self.assertEqual("contest_override", resolution.source_type)
        self.assertEqual(contest_grant.id, resolution.source_id)
        self.assertIsNone(resolution.contestant_limit)
        self.assertEqual(25, resolution.package_contestant_limit)
        self.assertTrue(resolution.contestant_limit_uses_free_default)

    def test_club_level_grant_applies_from_organizing_club_without_creator_membership_check(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        AccessGrant.objects.create(
            club=self.club,
            tier=AccessGrant.ANNUAL_CLUB_PASS,
            status=AccessGrant.ACTIVE,
            starts_at=now - datetime.timedelta(days=1),
            expires_at=now + datetime.timedelta(days=1),
            contestant_limit=None,
        )

        resolution = resolve_contest_access(self.contest)

        self.assertEqual("annual_club_pass", resolution.tier_code)
        self.assertEqual("club_pass", resolution.source_type)

    def test_club_level_grant_applies_for_owner_role(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        AccessGrant.objects.create(
            club=self.club,
            tier=AccessGrant.ANNUAL_CLUB_PASS,
            status=AccessGrant.ACTIVE,
            starts_at=now - datetime.timedelta(days=1),
            expires_at=now + datetime.timedelta(days=1),
            contestant_limit=15,
        )
        ClubManagerMembership.objects.create(club=self.club, user=self.user, is_active=True, role=ClubManagerMembership.OWNER)

        resolution = resolve_contest_access(self.contest)

        self.assertEqual("annual_club_pass", resolution.tier_code)
        self.assertEqual("club_pass", resolution.source_type)
        self.assertIsNone(resolution.contestant_limit)
        self.assertEqual(15, resolution.package_contestant_limit)
        self.assertTrue(resolution.contestant_limit_uses_free_default)

    @override_settings(DEFAULT_FREE_CONTESTANT_LIMIT=20)
    def test_more_advantageous_free_limits_override_stricter_club_package(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        AccessGrant.objects.create(
            club=self.club,
            status=AccessGrant.ACTIVE,
            starts_at=now - datetime.timedelta(days=1),
            expires_at=now + datetime.timedelta(days=1),
            contestant_limit=10,
        )
        ClubManagerMembership.objects.create(club=self.club, user=self.user, is_active=True, role=ClubManagerMembership.OWNER)

        resolution = resolve_contest_access(self.contest)

        self.assertEqual("annual_club_pass", resolution.tier_code)
        self.assertEqual("club_pass", resolution.source_type)
        self.assertEqual(20, resolution.contestant_limit)
        self.assertEqual(10, resolution.package_contestant_limit)
        self.assertTrue(resolution.contestant_limit_uses_free_default)
