import datetime

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from display.models import Contest, ContestTokenAssignment, TokenType, UserTokenGrant
from display.services.token_assignment import assign_token_to_contest, replace_token_for_contest


class TestTokenAssignmentLifecycle(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create(email="token-lifecycle@example.com")
        self.contest = Contest.objects.create(
            name="Lifecycle Contest",
            time_zone="Europe/Oslo",
            start_time=datetime.datetime(2026, 9, 1, 9, 0, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 9, 1, 17, 0, tzinfo=datetime.timezone.utc),
            location="60.0,11.0",
            created_by=self.user,
        )
        self.token_type_small = TokenType.objects.create(name="Small token", contestant_limit=10)
        self.token_type_large = TokenType.objects.create(name="Large token", contestant_limit=40)
        self.small_grant = UserTokenGrant.objects.create(user=self.user, token_type=self.token_type_small, quantity_total=2)
        self.large_grant = UserTokenGrant.objects.create(user=self.user, token_type=self.token_type_large, quantity_total=2)

    def test_replacing_token_burns_new_token_without_restoring_old_one(self):
        first_assignment = assign_token_to_contest(self.contest, self.user, self.small_grant.id)
        replacement = replace_token_for_contest(self.contest, self.user, self.large_grant.id)
        self.small_grant.refresh_from_db()
        self.large_grant.refresh_from_db()

        self.assertEqual(1, self.small_grant.quantity_consumed)
        self.assertEqual(1, self.large_grant.quantity_consumed)
        self.assertNotEqual(first_assignment.token_type_id, replacement.token_type_id)
        self.assertEqual(replacement.id, ContestTokenAssignment.objects.get(contest=self.contest).id)

    def test_replacing_token_resets_lifecycle_for_fresh_activation_window(self):
        first_assignment = assign_token_to_contest(self.contest, self.user, self.small_grant.id)
        first_assignment.activated_at = datetime.datetime(2026, 9, 1, 9, 0, tzinfo=datetime.timezone.utc)
        first_assignment.expires_at = datetime.datetime(2026, 9, 15, 9, 0, tzinfo=datetime.timezone.utc)
        first_assignment.save(update_fields=["activated_at", "expires_at"])

        replacement = replace_token_for_contest(self.contest, self.user, self.large_grant.id)

        self.assertIsNone(replacement.activated_at)
        self.assertIsNone(replacement.expires_at)

    def test_cannot_reassign_with_same_grant(self):
        assign_token_to_contest(self.contest, self.user, self.small_grant.id)

        with self.assertRaises(ValidationError):
            replace_token_for_contest(self.contest, self.user, self.small_grant.id)

    def test_deleting_contest_does_not_restore_consumed_token(self):
        assign_token_to_contest(self.contest, self.user, self.small_grant.id)
        self.contest.delete()
        self.small_grant.refresh_from_db()

        self.assertEqual(1, self.small_grant.quantity_consumed)
        self.assertEqual(1, self.small_grant.quantity_remaining)
