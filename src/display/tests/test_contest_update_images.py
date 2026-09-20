"""
Coverage for uploading a Contest's logo/header_image via the same REST endpoint the settings
form's other fields already use (PATCH contests-detail). Both are plain ImageFields already
included in ContestSerialiser (fields = "__all__") and DRF's default parser classes already
include MultiPartParser, so no backend change was needed - only the frontend previously never
sent multipart/form-data for these two fields. This pins down that the endpoint actually accepts
and persists them, and that permission enforcement covers this path the same as any other update.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from guardian.shortcuts import assign_perm
from rest_framework import status
from rest_framework.test import APITestCase

from display.models import Contest

# A minimal valid 1x1 GIF - small enough to inline, and real enough for ImageField's Pillow-backed
# validation (matches the helper in test_admin_team_registration_api.py).
_TINY_GIF = bytes.fromhex("47494638396101000100800000000000ffffff21f90401000000002c00000000010001000002024401003b")


def _tiny_image(name: str) -> SimpleUploadedFile:
    return SimpleUploadedFile(name, _TINY_GIF, content_type="image/gif")


class TestContestUpdateImages(APITestCase):
    def setUp(self):
        self.manager = get_user_model().objects.create(email="images-manager@example.com")
        # ContestPermissionsWithoutObjects.has_permission (checked before the per-object guardian
        # grant below) requires the global Django change_contest permission for PUT/PATCH - an
        # object-level-only grant satisfies has_object_permission but never reaches it.
        self.manager.user_permissions.add(Permission.objects.get(codename="change_contest"))
        self.viewer = get_user_model().objects.create(email="images-viewer@example.com")
        self.contest = Contest.objects.create(
            name="Images Contest",
            time_zone="Europe/Oslo",
            start_time="2026-10-01T09:00:00+00:00",
            finish_time="2026-10-01T17:00:00+00:00",
            location="60.0,11.0",
        )
        assign_perm("view_contest", self.manager, self.contest)
        assign_perm("change_contest", self.manager, self.contest)
        assign_perm("view_contest", self.viewer, self.contest)

    def _url(self):
        return reverse("contests-detail", kwargs={"pk": self.contest.pk})

    def test_uploading_logo_and_header_image_persists_both(self):
        self.client.force_login(self.manager)

        response = self.client.patch(
            self._url(),
            data={"logo": _tiny_image("logo.gif"), "header_image": _tiny_image("header.gif")},
            format="multipart",
        )

        self.assertEqual(status.HTTP_200_OK, response.status_code, response.content)
        self.contest.refresh_from_db()
        # Django's storage backend may rename to avoid an on-disk collision (e.g.
        # "logo_LUK82Yq.gif"), so check the shape of the stored name rather than an exact match.
        self.assertTrue(bool(self.contest.logo))
        self.assertTrue(bool(self.contest.header_image))
        self.assertTrue(self.contest.logo.name.endswith(".gif"))
        self.assertTrue(self.contest.header_image.name.endswith(".gif"))

    def test_uploading_only_logo_leaves_header_image_untouched(self):
        self.client.force_login(self.manager)
        self.client.patch(self._url(), data={"header_image": _tiny_image("header.gif")}, format="multipart")
        self.contest.refresh_from_db()
        original_header_name = self.contest.header_image.name

        response = self.client.patch(self._url(), data={"logo": _tiny_image("logo.gif")}, format="multipart")

        self.assertEqual(status.HTTP_200_OK, response.status_code, response.content)
        self.contest.refresh_from_db()
        self.assertTrue(bool(self.contest.logo))
        self.assertEqual(original_header_name, self.contest.header_image.name)

    def test_view_only_permission_cannot_upload_images(self):
        self.client.force_login(self.viewer)

        response = self.client.patch(self._url(), data={"logo": _tiny_image("logo.gif")}, format="multipart")

        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)
        self.contest.refresh_from_db()
        self.assertFalse(bool(self.contest.logo))

    def test_unauthenticated_request_is_rejected(self):
        response = self.client.patch(self._url(), data={"logo": _tiny_image("logo.gif")}, format="multipart")

        self.assertIn(response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))
        self.contest.refresh_from_db()
        self.assertFalse(bool(self.contest.logo))
