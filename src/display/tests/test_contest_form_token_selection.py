from django.test import TestCase

from display.forms import ContestForm
from display.models import TokenType, UserTokenGrant, MyUser


class TestContestFormTokenSelection(TestCase):
    def setUp(self):
        self.user = MyUser.objects.create(email="contest-form@example.com")
        self.small = TokenType.objects.create(name="Small token form", contestant_limit=10, task_limit=1)
        self.large = TokenType.objects.create(name="Large token form", contestant_limit=50, task_limit=5)
        self.available_grant = UserTokenGrant.objects.create(user=self.user, token_type=self.large, quantity_total=2, quantity_consumed=1)
        self.exhausted_grant = UserTokenGrant.objects.create(user=self.user, token_type=self.small, quantity_total=1, quantity_consumed=1)

    def test_contest_form_can_limit_token_choices_to_supplied_queryset(self):
        form = ContestForm(token_grant_queryset=UserTokenGrant.objects.filter(pk=self.available_grant.pk))

        self.assertEqual([self.available_grant.pk], list(form.fields["initial_token_grant"].queryset.values_list("pk", flat=True)))

    def test_contest_form_hides_exhausted_token_grants(self):
        form = ContestForm(token_grant_queryset=UserTokenGrant.objects.filter(user=self.user))

        self.assertEqual(
            [self.available_grant.pk],
            list(form.fields["initial_token_grant"].queryset.values_list("pk", flat=True)),
        )
