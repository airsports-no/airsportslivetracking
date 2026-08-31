"""
Regression test (local code review, management-commands section, finding #4):
review_unmapped_uploaded_services built its "already mapped" path set from
published_relative_path alone. A row still only referenced via map_file (e.g. uploaded before
reconcile_uploaded_map_storage --backfill-metadata has run) looked orphaned even though
mbtileserver was actively serving it from that exact blob - --delete-files would delete a live
map's source file while the DB row survived.
"""

from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase

from display.models.user_uploaded_map import UserUploadedMap


class TestReviewUnmappedUploadedServicesMappedPaths(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create(email="uploader@example.com")

    def test_map_referenced_only_via_map_file_is_not_flagged_as_orphan(self):
        uploaded_map = UserUploadedMap.objects.create(
            user=self.user,
            name="Not yet backfilled",
            map_file=SimpleUploadedFile("still-live.mbtiles", b"fake mbtiles bytes"),
        )
        self.assertEqual(uploaded_map.published_relative_path, "")
        filename = uploaded_map.map_file.name.rsplit("/", 1)[-1]
        service_key = filename[: -len(".mbtiles")]

        out = StringIO()
        with (
            patch(
                "display.management.commands.review_unmapped_uploaded_services.default_storage.listdir",
                return_value=([], [filename]),
            ),
            patch(
                "display.management.commands.review_unmapped_uploaded_services.get_available_maps",
                return_value=[{"url": f"https://tiles.example.com/services/{service_key}/"}],
            ),
        ):
            call_command("review_unmapped_uploaded_services", stdout=out)

        output = out.getvalue()
        self.assertNotIn("orphan service file", output)
        self.assertIn("orphan_service_files=0", output)
