from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from guardian.shortcuts import assign_perm, get_perms

from display.models.user_uploaded_map import UserUploadedMap

ALL_PERMS = {"view_useruploadedmap", "change_useruploadedmap", "delete_useruploadedmap", "add_useruploadedmap"}


class TestBackfillUploadedMapPermissions(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create(email="owner@example.com")

    def _run(self, *args):
        out = StringIO()
        call_command("backfill_uploaded_map_permissions", *args, stdout=out, stderr=out)
        return out.getvalue()

    def test_grants_permissions_to_owner_of_orphaned_map(self):
        orphaned = UserUploadedMap.objects.create(user=self.owner, name="Orphaned map")

        self._run()

        self.assertEqual(set(get_perms(self.owner, orphaned)), ALL_PERMS)

    def test_does_not_touch_map_that_already_has_permissions(self):
        already_ok = UserUploadedMap.objects.create(user=self.owner, name="Already ok")
        assign_perm("view_useruploadedmap", self.owner, already_ok)

        output = self._run()

        self.assertIn("skipped_already_has_perms=1", output)
        self.assertEqual(set(get_perms(self.owner, already_ok)), {"view_useruploadedmap"})

    def test_force_reassigns_even_when_some_permissions_exist(self):
        partial = UserUploadedMap.objects.create(user=self.owner, name="Partial perms")
        assign_perm("view_useruploadedmap", self.owner, partial)

        self._run("--force")

        self.assertEqual(set(get_perms(self.owner, partial)), ALL_PERMS)

    def test_unprotected_maps_are_skipped(self):
        unprotected = UserUploadedMap.objects.create(user=self.owner, name="Unprotected", unprotected=True)

        self._run()

        self.assertEqual(get_perms(self.owner, unprotected), [])

    def test_dry_run_does_not_write(self):
        orphaned = UserUploadedMap.objects.create(user=self.owner, name="Orphaned map")

        output = self._run("--dry-run")

        self.assertIn("dry-run=1", output)
        self.assertEqual(get_perms(self.owner, orphaned), [])

    def test_map_id_filter_scopes_to_specified_rows(self):
        target = UserUploadedMap.objects.create(user=self.owner, name="Target")
        other = UserUploadedMap.objects.create(user=self.owner, name="Other")

        self._run("--map-id", str(target.pk))

        self.assertEqual(set(get_perms(self.owner, target)), ALL_PERMS)
        self.assertEqual(get_perms(self.owner, other), [])
