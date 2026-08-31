"""
Regression tests for the critical finding (2026-08-28/29 security review, templates finding
#5): delete_user_contest_permissions / delete_user_editableroute_permissions /
delete_user_useruploadedmap_permissions were plain GET views with no CSRF protection (GET isn't
covered by Django's CSRF middleware) and no server-side self-protection - "don't remove your
own access" was enforced only by hiding the button client-side. Any user holding just
change_<object> could revoke ANY other user's permissions, including the actual owner's, via a
one-click <img src="..."> on any page a logged-in editor visited.
"""

import datetime

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from guardian.shortcuts import assign_perm, get_perms

from display.models import Contest, EditableRoute, Person, UserUploadedMap


class TestContestPermissionDeleteRequiresPost(TestCase):
    def setUp(self):
        self.contest = Contest.objects.create(
            name="Test contest",
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1),
            location="60, 11",
        )
        Person.objects.create(first_name="Editor", last_name="One", email="editor@example.com")
        Person.objects.create(first_name="Owner", last_name="Person", email="owner@example.com")
        self.editor = get_user_model().objects.create(email="editor@example.com")
        self.owner = get_user_model().objects.create(email="owner@example.com")
        for perm in ("view_contest", "change_contest"):
            assign_perm(f"display.{perm}", self.editor, self.contest)
        for perm in ("view_contest", "change_contest", "add_contest", "delete_contest"):
            assign_perm(f"display.{perm}", self.owner, self.contest)
        self.url = reverse("contest_permissions_delete", kwargs={"pk": self.contest.pk, "user_pk": self.owner.pk})

    def test_get_is_rejected_not_executed(self):
        self.client.force_login(user=self.editor)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)
        self.assertTrue(len(get_perms(self.owner, self.contest)) > 0)

    def test_post_by_editor_removes_owner_permissions(self):
        # Legitimate use of the feature still works via POST.
        self.client.force_login(user=self.editor)
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(get_perms(self.owner, self.contest), [])

    def test_post_cannot_remove_your_own_permissions(self):
        self.client.force_login(user=self.owner)
        url = reverse("contest_permissions_delete", kwargs={"pk": self.contest.pk, "user_pk": self.owner.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(len(get_perms(self.owner, self.contest)) > 0)


class TestEditableRoutePermissionDeleteRequiresPost(TestCase):
    def setUp(self):
        # route must be a valid FeatureCollection dict, not the model's bare-list default - a
        # pre-existing, unrelated signal (calculate_editable_route_statistics) crashes on save()
        # otherwise. Not in scope here; just avoiding it.
        self.route = EditableRoute.objects.create(
            name="Test route", route={"type": "FeatureCollection", "features": []}
        )
        Person.objects.create(first_name="Editor", last_name="One", email="editor2@example.com")
        Person.objects.create(first_name="Owner", last_name="Person", email="owner2@example.com")
        self.editor = get_user_model().objects.create(email="editor2@example.com")
        self.owner = get_user_model().objects.create(email="owner2@example.com")
        for perm in ("view_editableroute", "change_editableroute"):
            assign_perm(f"display.{perm}", self.editor, self.route)
        for perm in ("view_editableroute", "change_editableroute", "add_editableroute", "delete_editableroute"):
            assign_perm(f"display.{perm}", self.owner, self.route)
        self.url = reverse(
            "editableroute_permissions_delete", kwargs={"pk": self.route.pk, "user_pk": self.owner.pk}
        )

    def test_get_is_rejected_not_executed(self):
        self.client.force_login(user=self.editor)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)
        self.assertTrue(len(get_perms(self.owner, self.route)) > 0)

    def test_post_by_editor_removes_owner_permissions(self):
        self.client.force_login(user=self.editor)
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(get_perms(self.owner, self.route), [])


class TestUserUploadedMapPermissionDeleteRequiresPost(TestCase):
    def setUp(self):
        Person.objects.create(first_name="Editor", last_name="One", email="editor3@example.com")
        Person.objects.create(first_name="Owner", last_name="Person", email="owner3@example.com")
        self.editor = get_user_model().objects.create(email="editor3@example.com")
        self.owner = get_user_model().objects.create(email="owner3@example.com")
        self.uploaded_map = UserUploadedMap.objects.create(
            user=self.owner,
            name="Test map",
            map_file=SimpleUploadedFile("test.mbtiles", b"fake mbtiles bytes"),
        )
        for perm in ("view_useruploadedmap", "change_useruploadedmap"):
            assign_perm(f"display.{perm}", self.editor, self.uploaded_map)
        for perm in ("view_useruploadedmap", "change_useruploadedmap", "add_useruploadedmap", "delete_useruploadedmap"):
            assign_perm(f"display.{perm}", self.owner, self.uploaded_map)
        self.url = reverse(
            "useruploadedmap_permissions_delete", kwargs={"pk": self.uploaded_map.pk, "user_pk": self.owner.pk}
        )

    def test_get_is_rejected_not_executed(self):
        self.client.force_login(user=self.editor)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)
        self.assertTrue(len(get_perms(self.owner, self.uploaded_map)) > 0)

    def test_post_by_editor_removes_owner_permissions(self):
        self.client.force_login(user=self.editor)
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(get_perms(self.owner, self.uploaded_map), [])
