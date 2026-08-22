from django.contrib.auth import get_user_model
from django.test import TestCase
from django.core.exceptions import ValidationError

from display.models import AccessGrant, Club, Contest, TokenType, UserTokenGrant, ClubManagerMembership


class TestAuditFieldAutofillModels(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create(email="audit-user@example.com")
        self.club = Club.objects.create(name="Audit Club")
        self.contest = Contest.objects.create(
            name="Audit Contest",
            time_zone="Europe/Oslo",
            start_time="2026-10-01T09:00:00+00:00",
            finish_time="2026-10-01T17:00:00+00:00",
            location="60.0,11.0",
            created_by=self.user,
        )
        self.token_type = TokenType.objects.create(name="Audit token", contestant_limit=10)

    def test_access_grant_audit_fields_can_be_set_programmatically(self):
        grant = AccessGrant.objects.create(
            club=self.club,
            tier=AccessGrant.ANNUAL_CLUB_PASS,
            status=AccessGrant.ACTIVE,
            created_by=self.user,
            updated_by=self.user,
        )
        self.assertEqual(self.user, grant.created_by)
        self.assertEqual(self.user, grant.updated_by)

    def test_club_manager_membership_audit_fields_can_be_set_programmatically(self):
        membership = ClubManagerMembership.objects.create(
            club=self.club,
            user=self.user,
            role=ClubManagerMembership.OWNER,
            created_by=self.user,
            updated_by=self.user,
        )
        self.assertEqual(self.user, membership.created_by)
        self.assertEqual(self.user, membership.updated_by)

    def test_club_manager_membership_cannot_deactivate_last_active_owner(self):
        membership = ClubManagerMembership.objects.create(
            club=self.club,
            user=self.user,
            role=ClubManagerMembership.OWNER,
            is_active=True,
        )
        membership.is_active = False

        with self.assertRaises(ValidationError):
            membership.full_clean()
