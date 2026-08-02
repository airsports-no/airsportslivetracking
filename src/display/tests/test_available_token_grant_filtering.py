from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory

from display.models import Contest, TokenType, UserTokenGrant, Club, ClubManagerMembership, AccessGrant
from display.serialisers import ContestSerialiser
from display.services.task_type_visibility import can_user_see_cima_task_types, get_visible_task_type_groups_for_user
from display.utilities.task_type_group_definitions import CIMA_TASK_TYPE_GROUP


class TestAvailableTokenGrantFiltering(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create(email="token-filter@example.com")
        self.contest = Contest.objects.create(
            name="Filter Contest",
            time_zone="Europe/Oslo",
            start_time="2026-10-01T09:00:00+00:00",
            finish_time="2026-10-01T17:00:00+00:00",
            location="60.0,11.0",
            created_by=self.user,
        )
        active_type = TokenType.objects.create(name="Active token", contestant_limit=10, is_active=True, task_type_groups=[CIMA_TASK_TYPE_GROUP])
        inactive_type = TokenType.objects.create(name="Inactive token", contestant_limit=10, is_active=False)
        UserTokenGrant.objects.create(user=self.user, token_type=active_type, quantity_total=2, quantity_consumed=0)
        UserTokenGrant.objects.create(user=self.user, token_type=active_type, quantity_total=1, quantity_consumed=1)
        UserTokenGrant.objects.create(user=self.user, token_type=inactive_type, quantity_total=2, quantity_consumed=0)
        self.request = APIRequestFactory().get("/")
        self.request.user = self.user

    def test_serializer_only_returns_active_grants_with_remaining_tokens(self):
        data = ContestSerialiser(self.contest, context={"request": self.request}).data

        self.assertEqual(1, len(data["available_token_grants"]))
        self.assertEqual("Active token", data["available_token_grants"][0]["token_type_name"])
        self.assertEqual([CIMA_TASK_TYPE_GROUP], data["available_token_grants"][0]["task_type_groups"])


@override_settings(GATE_CIMA_TASK_VISIBILITY=True, DEFAULT_FREE_TASK_TYPE_GROUPS=["legacy"])
class TestTaskTypeVisibility(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create(email="visible-cima@example.com")
        self.club = Club.objects.create(name="Visibility Club")

    def test_default_free_groups_hide_cima_without_entitlement(self):
        self.assertFalse(can_user_see_cima_task_types(self.user))
        self.assertEqual(["legacy"], get_visible_task_type_groups_for_user(self.user))

    def test_token_with_remaining_quantity_exposes_cima(self):
        token_type = TokenType.objects.create(name="Visible CIMA token", contestant_limit=10, task_type_groups=[CIMA_TASK_TYPE_GROUP])
        UserTokenGrant.objects.create(user=self.user, token_type=token_type, quantity_total=1, quantity_consumed=0)

        self.assertTrue(can_user_see_cima_task_types(self.user))
        self.assertIn(CIMA_TASK_TYPE_GROUP, get_visible_task_type_groups_for_user(self.user))

    def test_club_pass_exposes_cima_for_active_member(self):
        ClubManagerMembership.objects.create(club=self.club, user=self.user, role=ClubManagerMembership.OWNER, is_active=True)
        AccessGrant.objects.create(club=self.club, status=AccessGrant.ACTIVE, contestant_limit=None, task_type_groups=[CIMA_TASK_TYPE_GROUP])

        self.assertTrue(can_user_see_cima_task_types(self.user))
        self.assertIn(CIMA_TASK_TYPE_GROUP, get_visible_task_type_groups_for_user(self.user))
