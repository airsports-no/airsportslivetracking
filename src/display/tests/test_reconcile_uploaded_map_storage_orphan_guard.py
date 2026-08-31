"""
Regression test (local code review, management-commands section, finding #1): SEVERE -
reconcile_uploaded_map_storage built its orphan-detection referenced_paths set only from the
rows a --limit/--after-id narrowed queryset inspected, but then walked ALL files under the
storage prefix looking for orphans - so any --delete-orphan-files run combined with batching
treated every row outside that slice as unreferenced and deleted its file.
"""

from django.core.management import CommandError, call_command
from django.test import TestCase


class TestReconcileUploadedMapStorageOrphanGuard(TestCase):
    def test_delete_orphan_files_with_limit_is_refused(self):
        with self.assertRaises(CommandError):
            call_command("reconcile_uploaded_map_storage", "--limit", "5", "--delete-orphan-files")

    def test_list_orphan_files_with_after_id_is_refused(self):
        with self.assertRaises(CommandError):
            call_command("reconcile_uploaded_map_storage", "--after-id", "10", "--list-orphan-files")

    def test_limit_without_orphan_flags_is_not_refused(self):
        # No UserUploadedMap rows exist, so this only exercises that the new guard doesn't
        # fire for the metadata-only (non-orphan-scanning) use of --limit.
        try:
            call_command("reconcile_uploaded_map_storage", "--limit", "5")
        except CommandError:
            self.fail("--limit alone (no orphan-file flags) must not trigger the orphan guard")
