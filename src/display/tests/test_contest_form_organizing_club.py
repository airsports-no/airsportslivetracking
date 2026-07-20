from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase

from display.forms import ContestForm
from display.models import Club, ClubManagerMembership


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
