from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from display.forms import ContestForm
from display.models import Club, ClubManagerMembership, Contest


class TestContestFormOrganizingClubChoices(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create(email="form-owner@example.com")
        self.user.user_permissions.add(Permission.objects.get(codename="add_contest"))
        self.user.user_permissions.add(Permission.objects.get(codename="change_contest"))
        self.club = Club.objects.create(name="Form Club")
        self.manager_club = Club.objects.create(name="Manager Club")
        ClubManagerMembership.objects.create(club=self.club, user=self.user, role=ClubManagerMembership.OWNER)
        ClubManagerMembership.objects.create(club=self.manager_club, user=self.user, role=ClubManagerMembership.MANAGER)

    def test_form_can_receive_managed_club_queryset(self):
        form = ContestForm(managed_club_queryset=Club.objects.filter(pk__in=[self.club.pk, self.manager_club.pk]))

        self.assertIn("organizing_club", form.fields)
        self.assertEqual(
            {self.club.pk, self.manager_club.pk},
            set(form.fields["organizing_club"].queryset.values_list("pk", flat=True)),
        )

    def test_form_layout_includes_organizing_club_field(self):
        form = ContestForm(managed_club_queryset=Club.objects.filter(pk__in=[self.club.pk, self.manager_club.pk]))
        contest_details = form.helper.layout.fields[0]

        self.assertIn("organizing_club", contest_details.fields)

    def test_manager_membership_is_included_in_managed_club_queryset(self):
        self.client.force_login(self.user)

        create_response = self.client.get(reverse("contest_create"))
        self.assertEqual(200, create_response.status_code)
        create_form = create_response.context["form"]
        self.assertEqual(
            {self.club.pk, self.manager_club.pk},
            set(create_form.fields["organizing_club"].queryset.values_list("pk", flat=True)),
        )

        contest = Contest.objects.create(
            name="Existing contest",
            time_zone="Europe/Oslo",
            start_time="2026-10-01T09:00:00+00:00",
            finish_time="2026-10-01T17:00:00+00:00",
            location="60.0,11.0",
            created_by=self.user,
        )
        from guardian.shortcuts import assign_perm
        assign_perm("change_contest", self.user, contest)
        update_response = self.client.get(reverse("contest_update", kwargs={"pk": contest.pk}))
        self.assertEqual(200, update_response.status_code)
        update_form = update_response.context["form"]
        self.assertEqual(
            {self.club.pk, self.manager_club.pk},
            set(update_form.fields["organizing_club"].queryset.values_list("pk", flat=True)),
        )
