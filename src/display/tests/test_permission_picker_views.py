"""
Adding a map/route permission: the user is normally chosen with the type-ahead picker (hidden
user_id), with the exact email address kept as a fallback. Neither path may reveal addresses.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from guardian.shortcuts import assign_perm

from display.models import EditableRoute, Person


class TestAddEditableRoutePermission(TestCase):
    def setUp(self):
        User = get_user_model()
        Person.objects.create(first_name="Route", last_name="Owner", email="owner@example.com")
        self.owner = User.objects.create(email="owner@example.com", first_name="Route", last_name="Owner")
        self.target = User.objects.create(email="target@example.com", first_name="Tina", last_name="Target")
        self.route = EditableRoute.objects.create(name="Route", route={"type": "FeatureCollection", "features": []})
        assign_perm("display.change_editableroute", self.owner, self.route)
        self.client.force_login(user=self.owner)
        self.add_url = reverse("editableroute_permissions_add", kwargs={"pk": self.route.pk})

    def test_form_page_mounts_the_picker_and_does_not_list_emails(self):
        response = self.client.get(self.add_url)
        content = response.content.decode()
        self.assertContains(response, "data-person-picker")
        self.assertContains(response, reverse("people_search"))
        self.assertNotIn("target@example.com", content)

    def test_add_by_user_id_from_the_picker(self):
        response = self.client.post(self.add_url, {"user_id": self.target.pk, "permission": "view"})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(self.target.has_perm("display.view_editableroute", self.route))

    def test_add_by_exact_email_still_works(self):
        self.client.post(self.add_url, {"email": "TARGET@example.com", "permission": "change"})
        self.assertTrue(self.target.has_perm("display.change_editableroute", self.route))

    def test_requires_a_user_or_an_email(self):
        response = self.client.post(self.add_url, {"permission": "view"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.target.has_perm("display.view_editableroute", self.route))

    def test_unknown_user_id_is_reported_not_crashing(self):
        response = self.client.post(self.add_url, {"user_id": 999999, "permission": "view"})
        self.assertEqual(response.status_code, 302)

    def test_list_shows_name_and_masked_email_only(self):
        assign_perm("display.view_editableroute", self.target, self.route)
        response = self.client.get(reverse("editableroute_permissions_list", kwargs={"pk": self.route.pk}))
        content = response.content.decode()
        self.assertIn("Tina Target", content)
        self.assertIn("t*****@***.com", content)
        self.assertNotIn("target@example.com", content)
