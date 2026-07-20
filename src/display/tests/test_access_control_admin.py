from django.contrib import admin
from django.test import RequestFactory, SimpleTestCase

from display.admin import (
    AccessGrantAdmin,
    ClubAdmin,
    ClubManagerMembershipAdmin,
    ContestAdmin,
    ContestTokenAssignmentAdmin,
    UserTokenGrantAdmin,
)
from display.models import AccessGrant, Club, ClubManagerMembership, Contest, ContestTokenAssignment, UserTokenGrant


class TestAccessControlAdmin(SimpleTestCase):
    def test_access_control_models_are_registered_in_admin(self):
        self.assertIsInstance(admin.site._registry[Club], ClubAdmin)
        self.assertIsInstance(admin.site._registry[AccessGrant], AccessGrantAdmin)
        self.assertIsInstance(admin.site._registry[ClubManagerMembership], ClubManagerMembershipAdmin)
        self.assertIsInstance(admin.site._registry[UserTokenGrant], UserTokenGrantAdmin)
        self.assertIsInstance(admin.site._registry[ContestTokenAssignment], ContestTokenAssignmentAdmin)

    def test_contest_admin_exposes_ownership_columns(self):
        contest_admin = admin.site._registry[Contest]

        self.assertIsInstance(contest_admin, ContestAdmin)
        self.assertIn("organizing_club", contest_admin.list_display)
        self.assertIn("created_by", contest_admin.list_display)
        self.assertIn("current_token_grant", contest_admin.list_display)
        self.assertIn("current_token_type", contest_admin.list_display)

    def test_access_and_token_admin_hide_audit_fields(self):
        self.assertIn("created_by", admin.site._registry[AccessGrant].exclude)
        self.assertIn("updated_by", admin.site._registry[AccessGrant].exclude)
        self.assertIn("created_by", admin.site._registry[UserTokenGrant].exclude)
        self.assertIn("updated_by", admin.site._registry[UserTokenGrant].exclude)
