from django.contrib import admin
from django.test import RequestFactory, SimpleTestCase

from display.admin import (
    AccessGrantAdmin,
    ClubAdmin,
    ClubManagerMembershipAdmin,
    ContestAdmin,
    ContestTokenAssignmentAdmin,
    TokenTypeAdmin,
    UserEntitlementGrantAdmin,
    UserTokenGrantAdmin,
)
from display.models import AccessGrant, Club, ClubManagerMembership, Contest, ContestTokenAssignment, TokenType, UserEntitlementGrant, UserTokenGrant
from display.services.token_assignment import revert_token_assignment_for_support


class TestAccessControlAdmin(SimpleTestCase):
    def test_access_control_models_are_registered_in_admin(self):
        self.assertIsInstance(admin.site._registry[Club], ClubAdmin)
        self.assertIsInstance(admin.site._registry[AccessGrant], AccessGrantAdmin)
        self.assertIsInstance(admin.site._registry[ClubManagerMembership], ClubManagerMembershipAdmin)
        self.assertIsInstance(admin.site._registry[UserTokenGrant], UserTokenGrantAdmin)
        self.assertIsInstance(admin.site._registry[ContestTokenAssignment], ContestTokenAssignmentAdmin)
        self.assertIsInstance(admin.site._registry[TokenType], TokenTypeAdmin)
        self.assertIsInstance(admin.site._registry[UserEntitlementGrant], UserEntitlementGrantAdmin)

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
        self.assertIn("tier", admin.site._registry[AccessGrant].exclude)
        self.assertIn("created_by", admin.site._registry[UserTokenGrant].exclude)
        self.assertIn("updated_by", admin.site._registry[UserTokenGrant].exclude)

    def test_access_and_token_admin_expose_task_type_groups(self):
        access_admin = admin.site._registry[AccessGrant]
        token_admin = admin.site._registry[TokenType]
        self.assertIn("task_type_groups", access_admin.list_display)
        self.assertIn("task_type_groups", access_admin.fields)
        self.assertIn("task_type_groups", token_admin.list_display)

    def test_contest_token_assignment_admin_has_support_refund_action(self):
        actions = admin.site._registry[ContestTokenAssignment].actions
        self.assertIn("revert_assignment_and_refund", actions)
