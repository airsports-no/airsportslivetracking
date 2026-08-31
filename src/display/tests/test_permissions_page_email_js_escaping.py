"""
Regression test (CodeRabbit review of PR #734): contest_permissions.html,
editableroute_permissions.html, and useruploadedmap_permissions.html interpolated a user's
email directly into a single-quoted JavaScript string inside an onsubmit="" attribute
(`onsubmit="return confirm('Remove all permissions for {{ user.email }}?');"`). Django's default
autoescaping HTML-escapes the value (safe against breaking out of the HTML attribute), but the
browser HTML-decodes the attribute value before running it as JavaScript - so an apostrophe in
the email survives that round trip as a literal `'`, breaking out of the JS string literal.
HTML-escaping is not JS-string-escaping.
"""

import datetime

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from guardian.shortcuts import assign_perm

from display.models import Contest, EditableRoute, Person, UserUploadedMap


class TestPermissionsPageEmailJsEscaping(TestCase):
    def setUp(self):
        self.viewer_person = Person.objects.create(first_name="Viewer", last_name="Person", email="viewer@example.com")
        self.viewer = get_user_model().objects.create(email="viewer@example.com")
        self.target_person = Person.objects.create(
            first_name="Target", last_name="Person", email="o'hare@example.com"
        )
        self.target_user = get_user_model().objects.create(email="o'hare@example.com")

    def _assert_email_is_js_escaped_not_raw(self, response):
        content = response.content.decode()
        self.assertNotIn(
            "o'hare@example.com?');",
            content,
            "The raw apostrophe-containing email must not appear inside the JS string literal - "
            "it must be escapejs-escaped so it can't break out of confirm('...').",
        )
        self.assertIn("o\\u0027hare@example.com", content)

    def test_contest_permissions_page_escapes_email_for_js(self):
        contest = Contest.objects.create(
            name="Test contest",
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1),
            location="60, 11",
        )
        assign_perm("display.change_contest", self.viewer, contest)
        assign_perm("display.view_contest", self.target_user, contest)
        self.client.force_login(user=self.viewer)

        response = self.client.get(reverse("contest_permissions_list", kwargs={"pk": contest.pk}))
        self._assert_email_is_js_escaped_not_raw(response)

    def test_editableroute_permissions_page_escapes_email_for_js(self):
        route = EditableRoute.objects.create(
            name="Test route", route={"type": "FeatureCollection", "features": []}
        )
        assign_perm("display.change_editableroute", self.viewer, route)
        assign_perm("display.view_editableroute", self.target_user, route)
        self.client.force_login(user=self.viewer)

        response = self.client.get(reverse("editableroute_permissions_list", kwargs={"pk": route.pk}))
        self._assert_email_is_js_escaped_not_raw(response)

    def test_useruploadedmap_permissions_page_escapes_email_for_js(self):
        uploaded_map = UserUploadedMap.objects.create(
            user=self.viewer,
            name="Test map",
            map_file=SimpleUploadedFile("test.mbtiles", b"fake mbtiles bytes"),
        )
        assign_perm("display.change_useruploadedmap", self.viewer, uploaded_map)
        assign_perm("display.view_useruploadedmap", self.target_user, uploaded_map)
        self.client.force_login(user=self.viewer)

        response = self.client.get(reverse("useruploadedmap_permissions_list", kwargs={"pk": uploaded_map.pk}))
        self._assert_email_is_js_escaped_not_raw(response)
