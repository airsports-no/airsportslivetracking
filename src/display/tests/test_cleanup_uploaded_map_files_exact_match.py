"""
Regression test (local code review, management-commands section, finding #7):
cleanup_uploaded_map_files matched filenames with a bare __endswith, so searching for
"map.mbtiles" also matched a user-chosen name like "my-map.mbtiles" - and "neither flag given"
defaulted to deleting both DB rows and storage files, the most destructive combination for the
least-specific invocation.
"""

import uuid
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase

from display.models.user_uploaded_map import UserUploadedMap


class TestCleanupUploadedMapFilesExactMatch(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create(email="cleanup-uploader@example.com")
        unique = uuid.uuid4().hex[:12]
        self.target = UserUploadedMap.objects.create(
            user=self.user,
            name="Target",
            map_file=SimpleUploadedFile(f"{unique}.mbtiles", b"fake mbtiles bytes"),
        )
        self.decoy = UserUploadedMap.objects.create(
            user=self.user,
            name="Decoy",
            # Storage may still rename on a rare collision, so derive the search filename from
            # what actually got stored (below) rather than assuming it matches the requested name.
            map_file=SimpleUploadedFile(f"my-{unique}.mbtiles", b"other fake mbtiles bytes"),
        )
        self.target_filename = self.target.map_file.name.rsplit("/", 1)[-1]

    def test_only_the_exact_filename_matches(self):
        out = StringIO()
        call_command("cleanup_uploaded_map_files", self.target_filename, stdout=out)
        output = out.getvalue()

        self.assertIn(f"object id={self.target.pk}", output)
        self.assertNotIn(f"object id={self.decoy.pk}", output)
        self.assertIn("matched_objects=1", output)

    def test_no_delete_flags_deletes_nothing_even_with_execute(self):
        out = StringIO()
        call_command("cleanup_uploaded_map_files", self.target_filename, "--execute", stdout=out)

        self.assertTrue(UserUploadedMap.objects.filter(pk=self.target.pk).exists())
        self.assertTrue(UserUploadedMap.objects.filter(pk=self.decoy.pk).exists())
        self.assertTrue(self.target.map_file.storage.exists(self.target.map_file.name))
