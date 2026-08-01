from django.contrib.auth import get_user_model
from django.urls import reverse
from guardian.shortcuts import assign_perm
from rest_framework import status
from rest_framework.test import APITestCase

from display.models import Club, ClubManagerMembership, Contest


class TestClubManagerMembershipApi(APITestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create(email="club-owner@example.com")
        self.manager = get_user_model().objects.create(email="club-manager@example.com")
        self.other_user = get_user_model().objects.create(email="other-user@example.com")
        self.stranger = get_user_model().objects.create(email="stranger@example.com")
        self.club = Club.objects.create(name="Club API Club")
        ClubManagerMembership.objects.create(club=self.club, user=self.owner, role=ClubManagerMembership.OWNER)
        ClubManagerMembership.objects.create(club=self.club, user=self.manager, role=ClubManagerMembership.MANAGER)

        self.contest = Contest.objects.create(
            name="Club Contest",
            time_zone="Europe/Oslo",
            start_time="2026-10-01T09:00:00+00:00",
            finish_time="2026-10-01T17:00:00+00:00",
            location="60.0,11.0",
            created_by=self.owner,
            organizing_club=self.club,
        )
        assign_perm("change_contest", self.owner, self.contest)
        assign_perm("view_contest", self.owner, self.contest)

    def test_managed_clubs_endpoint_lists_memberships_for_current_manager(self):
        self.client.force_login(self.owner)
        url = reverse("clubs-managed")

        response = self.client.get(url)

        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(1, len(response.data))
        self.assertEqual(self.club.pk, response.data[0]["id"])
        self.assertEqual(2, len(response.data[0]["manager_memberships"]))

    def test_generic_club_create_endpoint_is_not_allowed(self):
        self.client.force_login(self.owner)
        url = reverse("clubs-list")

        response = self.client.post(url, {"name": "New Club", "country": "NO"}, format="json")

        self.assertEqual(status.HTTP_405_METHOD_NOT_ALLOWED, response.status_code)
        self.assertEqual("method_not_allowed", response.data["detail"].code)
        self.assertFalse(Club.objects.filter(name="New Club").exists())

    def test_generic_club_delete_endpoint_is_not_allowed(self):
        self.client.force_login(self.owner)
        url = reverse("clubs-detail", kwargs={"pk": self.club.pk})

        response = self.client.delete(url)

        self.assertEqual(status.HTTP_405_METHOD_NOT_ALLOWED, response.status_code)
        self.assertEqual("method_not_allowed", response.data["detail"].code)
        self.assertTrue(Club.objects.filter(pk=self.club.pk).exists())

    def test_owner_can_add_manager_membership_by_email(self):
        self.client.force_login(self.owner)
        url = reverse("clubs-managers", kwargs={"pk": self.club.pk})

        response = self.client.post(url, {"user_id": self.other_user.email, "role": ClubManagerMembership.MANAGER}, format="json")

        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        self.assertTrue(ClubManagerMembership.objects.filter(club=self.club, user=self.other_user, is_active=True).exists())

    def test_owner_can_add_manager_membership(self):
        self.client.force_login(self.owner)
        url = reverse("clubs-managers", kwargs={"pk": self.club.pk})

        response = self.client.post(url, {"user_id": self.other_user.pk, "role": ClubManagerMembership.MANAGER}, format="json")

        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        membership = ClubManagerMembership.objects.get(club=self.club, user=self.other_user)
        self.assertTrue(membership.is_active)
        self.assertEqual(self.owner, membership.created_by)
        self.assertEqual(self.owner, membership.updated_by)

    def test_non_manager_cannot_add_manager_membership(self):
        self.client.force_login(self.stranger)
        url = reverse("clubs-managers", kwargs={"pk": self.club.pk})

        response = self.client.post(url, {"user_id": self.other_user.pk, "role": ClubManagerMembership.MANAGER}, format="json")

        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_non_owner_manager_cannot_add_manager_membership(self):
        self.client.force_login(self.manager)
        url = reverse("clubs-managers", kwargs={"pk": self.club.pk})

        response = self.client.post(url, {"user_id": self.other_user.pk, "role": ClubManagerMembership.MANAGER}, format="json")

        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)
        self.assertFalse(ClubManagerMembership.objects.filter(club=self.club, user=self.other_user, is_active=True).exists())

    def test_owner_can_deactivate_manager_membership(self):
        membership = ClubManagerMembership.objects.create(club=self.club, user=self.other_user, role=ClubManagerMembership.MANAGER)
        self.client.force_login(self.owner)
        url = reverse("clubs-manager-detail", kwargs={"pk": self.club.pk, "membership_pk": membership.pk})

        response = self.client.delete(url)

        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)
        membership.refresh_from_db()
        self.assertFalse(membership.is_active)
        self.assertEqual(self.owner, membership.updated_by)

    def test_owner_cannot_deactivate_last_active_owner_membership(self):
        self.client.force_login(self.owner)
        owner_membership = ClubManagerMembership.objects.get(club=self.club, user=self.owner)
        url = reverse("clubs-manager-detail", kwargs={"pk": self.club.pk, "membership_pk": owner_membership.pk})

        response = self.client.delete(url)

        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        owner_membership.refresh_from_db()
        self.assertTrue(owner_membership.is_active)

    def test_non_owner_manager_cannot_deactivate_manager_membership(self):
        membership = ClubManagerMembership.objects.create(club=self.club, user=self.other_user, role=ClubManagerMembership.MANAGER)
        self.client.force_login(self.manager)
        url = reverse("clubs-manager-detail", kwargs={"pk": self.club.pk, "membership_pk": membership.pk})

        response = self.client.delete(url)

        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)
        membership.refresh_from_db()
        self.assertTrue(membership.is_active)
