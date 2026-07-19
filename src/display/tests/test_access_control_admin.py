from django.contrib import admin
from django.test import SimpleTestCase

from display.admin import AccessGrantAdmin, ClubAdmin, ClubManagerMembershipAdmin, ContestAdmin
from display.models import AccessGrant, Club, ClubManagerMembership, Contest


class TestAccessControlAdmin(SimpleTestCase):
    def test_access_control_models_are_registered_in_admin(self):
        self.assertIsInstance(admin.site._registry[Club], ClubAdmin)
        self.assertIsInstance(admin.site._registry[AccessGrant], AccessGrantAdmin)
        self.assertIsInstance(admin.site._registry[ClubManagerMembership], ClubManagerMembershipAdmin)

    def test_contest_admin_exposes_ownership_columns(self):
        contest_admin = admin.site._registry[Contest]

        self.assertIsInstance(contest_admin, ContestAdmin)
        self.assertIn("organizing_club", contest_admin.list_display)
        self.assertIn("created_by", contest_admin.list_display)
