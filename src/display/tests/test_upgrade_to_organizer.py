"""
Regression coverage for the "Become an Organizer" self-service flow
(display.views.upgrade_to_organizer): it adds the requesting user to a "ContestCreator" group,
but until migration 0178 that group had zero permissions attached anywhere in the codebase - the
request "succeeded" (redirected to the success page) without ever actually granting
display.add_contest. See the migration's docstring for the full diagnosis.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse


class TestContestCreatorGroupHasAddContestPermission(TestCase):
    def test_group_created_by_migration_has_add_contest_permission(self):
        # The group is get_or_create()'d both by the migration and by the view itself, so this
        # also covers a fresh install where the migration ran before anyone ever clicked the
        # button.
        group = Group.objects.get(name="ContestCreator")
        self.assertTrue(group.permissions.filter(codename="add_contest").exists())


class TestUpgradeToOrganizerView(TestCase):
    def setUp(self):
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
