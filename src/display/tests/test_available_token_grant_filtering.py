from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory

from display.models import Contest, TokenType, UserTokenGrant
from display.serialisers import ContestSerialiser


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
        active_type = TokenType.objects.create(name="Active token", contestant_limit=10, is_active=True)
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
