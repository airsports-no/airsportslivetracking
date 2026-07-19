import datetime

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from display.models import (
    Contest,
    ContestTokenAssignment,
    TokenType,
    UserTokenGrant,
)
from display.services.token_assignment import assign_token_to_contest


class TestTokenAssignment(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create(email="token-owner@example.com")
        self.contest = Contest.objects.create(
            name="Token Contest",
            time_zone="Europe/Oslo",
            start_time=datetime.datetime(2026, 6, 1, 9, 0, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 6, 1, 17, 0, tzinfo=datetime.timezone.utc),
            location="60.0,11.0",
            created_by=self.user,
        )
        self.token_type = TokenType.objects.create(
            name="Club event 25/3",
            contestant_limit=25,
            task_limit=3,
        )

    def test_user_token_grant_reports_remaining_quantity(self):
        grant = UserTokenGrant.objects.create(
            user=self.user,
            token_type=self.token_type,
            quantity_total=5,
            quantity_consumed=2,
        )

        self.assertEqual(3, grant.quantity_remaining)
        self.assertTrue(grant.has_available_tokens)

    def test_assign_token_to_contest_consumes_one_token_and_links_assignment(self):
        grant = UserTokenGrant.objects.create(
            user=self.user,
            token_type=self.token_type,
            quantity_total=2,
            quantity_consumed=0,
        )

        assignment = assign_token_to_contest(self.contest, self.user, grant.id)
        grant.refresh_from_db()

        self.assertEqual(1, grant.quantity_consumed)
        self.assertEqual(1, grant.quantity_remaining)
        self.assertEqual(self.contest, assignment.contest)
        self.assertEqual(grant, assignment.token_grant)
        self.assertEqual(self.token_type, assignment.token_type)
        self.assertEqual(ContestTokenAssignment.objects.get(contest=self.contest), assignment)

    def test_assign_token_to_contest_rejects_exhausted_grant(self):
        grant = UserTokenGrant.objects.create(
            user=self.user,
            token_type=self.token_type,
            quantity_total=1,
            quantity_consumed=1,
        )

        with self.assertRaises(ValidationError):
            assign_token_to_contest(self.contest, self.user, grant.id)

    def test_assign_token_to_contest_rejects_other_users_grant(self):
        other_user = get_user_model().objects.create(email="other@example.com")
        grant = UserTokenGrant.objects.create(
            user=other_user,
            token_type=self.token_type,
            quantity_total=1,
            quantity_consumed=0,
        )

        with self.assertRaises(ValidationError):
            assign_token_to_contest(self.contest, self.user, grant.id)
