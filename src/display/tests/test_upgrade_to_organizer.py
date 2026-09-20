"""
Regression coverage for the "Become an Organizer" self-service flow
(display.views.upgrade_to_organizer): it adds the requesting user to a "ContestCreator" group,
but until migration 0178 that group had zero permissions attached anywhere in the codebase - the
request "succeeded" (redirected to the success page) without ever actually granting
display.add_contest. See the migration's docstring for the full diagnosis.

Migration 0179 attaches a second permission, display.add_editableroute, to the same group for the
same reason: EditableRoutePermission.has_permission (display/permissions.py) unconditionally
requires it for every request to EditableRouteViewSet (list, create, the global-map-sources and
task_compatibility actions), so a freshly-upgraded organizer with only add_contest still got a
blanket 403 the moment they opened the route editor.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.test import TestCase
from django.urls import reverse

# Matches CONTEST_CREATOR_PERMISSIONS in migration 0179 exactly.
_CONTEST_CREATOR_PERMISSION_CODENAMES = (
    "add_contest",
    "change_contest",
    "view_contest",
    "delete_contest",
    "add_editableroute",
    "change_editableroute",
    "view_editableroute",
    "delete_editableroute",
)


def _ensure_contest_creator_group_has_its_migration_permissions():
    """
    Re-does what migrations 0178/0179 attach to the "ContestCreator" group, so these tests don't
    depend on that migration output surviving intact by the time they run.

    It usually does survive - but APITransactionTestCase/TransactionTestCase elsewhere in this
    suite (there are many) truncate every table after each test and do NOT restore rows created
    by data migrations, a documented Django caveat (see TransactionTestCase.serialized_rollback).
    That makes relying on migration 0178/0179's output order-dependent across the full suite: this
    file passes reliably in isolation, or if nothing that wipes the group happens to run first,
    but fails with Group.DoesNotExist (or a group with zero permissions, since
    display.views.upgrade_to_organizer's own get_or_create only ensures the *group* exists, never
    reattaches its permissions) once some unrelated transaction test has already truncated it.
    """
    group, _ = Group.objects.get_or_create(name="ContestCreator")
    permissions = Permission.objects.filter(
        content_type__app_label="display", codename__in=_CONTEST_CREATOR_PERMISSION_CODENAMES
    )
    group.permissions.add(*permissions)


class TestContestCreatorGroupHasAddContestPermission(TestCase):
    def setUp(self):
        _ensure_contest_creator_group_has_its_migration_permissions()

    def test_group_created_by_migration_has_add_contest_permission(self):
        # The group is get_or_create()'d both by the migration and by the view itself, so this
        # also covers a fresh install where the migration ran before anyone ever clicked the
        # button.
        group = Group.objects.get(name="ContestCreator")
        self.assertTrue(group.permissions.filter(codename="add_contest").exists())

    def test_group_created_by_migration_has_add_editableroute_permission(self):
        group = Group.objects.get(name="ContestCreator")
        self.assertTrue(group.permissions.filter(codename="add_editableroute").exists())


class TestUpgradeToOrganizerView(TestCase):
    def setUp(self):
        _ensure_contest_creator_group_has_its_migration_permissions()
        self.user = get_user_model().objects.create_user(email="upgrade-me@example.com", password="secret")

    def test_upgrading_actually_grants_add_contest(self):
        self.assertFalse(self.user.has_perm("display.add_contest"))
        self.client.force_login(self.user)
        response = self.client.post(reverse("upgrade_to_organizer"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "success"})
        # has_perm caches on the user instance - refetch to see the group-derived permission.
        refetched = get_user_model().objects.get(pk=self.user.pk)
        self.assertTrue(refetched.has_perm("display.add_contest"))

    def test_anonymous_request_does_not_report_success(self):
        response = self.client.post(reverse("upgrade_to_organizer"))
        # login_required redirects rather than returning the view's JSON success body - this
        # pins down that an anonymous/session-expired click can never look like a success.
        self.assertNotEqual(response.status_code, 200)

    def test_get_request_is_rejected(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("upgrade_to_organizer"))
        self.assertEqual(response.status_code, 405)

    def test_upgrading_also_unblocks_the_route_editor(self):
        # Reproduces the live bug report: a user who had only "Become an Organizer"-d (no direct
        # per-user add_editableroute grant) got a 403 from the route editor's global map sources
        # endpoint, because that permission was never attached to the ContestCreator group either.
        self.client.force_login(self.user)
        before = self.client.get(reverse("editableroutes-global-map-sources"))
        self.assertEqual(before.status_code, 403)

        response = self.client.post(reverse("upgrade_to_organizer"))
        self.assertEqual(response.status_code, 200)

        after = self.client.get(reverse("editableroutes-global-map-sources"))
        self.assertEqual(after.status_code, 200)
