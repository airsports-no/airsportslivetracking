from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase

from display.forms import ContestForm
from display.models import Club, ClubManagerMembership, Contest


class TestContestFormOrganizingClubChoices(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create(email="form-owner@example.com")
        self.user.user_permissions.add(Permission.objects.get(codename="add_contest"))
        self.club = Club.objects.create(name="Form Club")
        ClubManagerMembership.objects.create(club=self.club, user=self.user, role=ClubManagerMembership.OWNER)

    def test_form_can_receive_managed_club_queryset(self):
        form = ContestForm(managed_club_queryset=Club.objects.filter(pk=self.club.pk))

        self.assertIn("organizing_club", form.fields)
        self.assertEqual([self.club.pk], list(form.fields["organizing_club"].queryset.values_list("pk", flat=True)))

    def test_form_layout_includes_organizing_club_field(self):
        form = ContestForm(managed_club_queryset=Club.objects.filter(pk=self.club.pk))
        contest_details = form.helper.layout.fields[0]

        self.assertIn("organizing_club", contest_details.fields)

    def test_model_help_text_is_used_for_organizing_club_field(self):
        form = ContestForm(managed_club_queryset=Club.objects.filter(pk=self.club.pk))

        self.assertEqual(
            Contest._meta.get_field("organizing_club").help_text,
            form.fields["organizing_club"].help_text,
        )
