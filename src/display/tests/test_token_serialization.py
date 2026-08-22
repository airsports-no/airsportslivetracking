import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory

from display.models import Contest, TokenType, UserTokenGrant
from display.serialisers import ContestSerialiser
from display.utilities.task_type_group_definitions import CIMA_TASK_TYPE_GROUP


class TestTokenSerialization(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create(email="serializer-token@example.com")
        self.contest = Contest.objects.create(
            name="Token Serialization Contest",
            time_zone="Europe/Oslo",
            start_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 8, 1, 17, 0, tzinfo=datetime.timezone.utc),
            location="60.0,11.0",
            created_by=self.user,
        )
        self.token_type = TokenType.objects.create(
            name="Large token",
            contestant_limit=50,
            task_type_groups=[CIMA_TASK_TYPE_GROUP],
        )
        self.token_grant = UserTokenGrant.objects.create(
            user=self.user,
            token_type=self.token_type,
            quantity_total=3,
            quantity_consumed=1,
        )
        self.request = APIRequestFactory().get("/")
        self.request.user = self.user

    def test_contest_serializer_exposes_available_token_grants_for_request_user(self):
        data = ContestSerialiser(self.contest, context={"request": self.request}).data

        self.assertEqual(1, len(data["available_token_grants"]))
        item = data["available_token_grants"][0]
        self.assertEqual(self.token_grant.id, item["id"])
        self.assertEqual("Large token", item["token_type_name"])
        self.assertEqual(2, item["quantity_remaining"])
        self.assertEqual([CIMA_TASK_TYPE_GROUP], item["task_type_groups"])
