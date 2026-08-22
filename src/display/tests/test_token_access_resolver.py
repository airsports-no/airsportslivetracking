import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from display.models import Contest, ContestTokenAssignment, TokenType, UserTokenGrant
from display.services.access_resolver import resolve_contest_access


@override_settings(
    DEFAULT_FREE_CONTESTANT_LIMIT=None,
    ACCESS_ENFORCEMENT_MODE="audit",
)
class TestTokenAccessResolver(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create(email="resolver-token@example.com")
        self.contest = Contest.objects.create(
            name="Token Resolver Contest",
            time_zone="Europe/Oslo",
            start_time=datetime.datetime(2026, 7, 1, 9, 0, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 7, 1, 17, 0, tzinfo=datetime.timezone.utc),
            location="60.0,11.0",
            created_by=self.user,
        )
        self.token_type = TokenType.objects.create(
            name="Small token",
            contestant_limit=12,
        )
        self.token_grant = UserTokenGrant.objects.create(
            user=self.user,
            token_type=self.token_type,
            quantity_total=4,
            quantity_consumed=1,
        )

    def test_token_assignment_takes_precedence_in_access_resolution(self):
        ContestTokenAssignment.objects.create(
            contest=self.contest,
            token_grant=self.token_grant,
            token_type=self.token_type,
        )

        resolution = resolve_contest_access(self.contest)

        self.assertEqual("token", resolution.tier_code)
        self.assertEqual("contest_token", resolution.source_type)
        self.assertIsNone(resolution.contestant_limit)
        self.assertEqual(12, resolution.package_contestant_limit)
        self.assertTrue(resolution.contestant_limit_uses_free_default)
        self.assertEqual(self.token_grant.id, resolution.token_grant_id)
        self.assertEqual(self.token_type.id, resolution.token_type_id)
