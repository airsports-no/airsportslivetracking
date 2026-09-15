"""
Regression test for a production bug: 22 UserUploadedMap rows across many different owners had
zero guardian object permissions for anyone, including their own owner, making them permanently
invisible in every navigation task's map list regardless of geographic bounds or contest access
(see get_available_user_maps() and get_available_map_source_definitions_for_navigation_task()).

Root cause: UserUploadedMap was registered in Django admin as a bare GuardedModelAdmin, unlike
ContestAdmin right above it in the same file, which does auto-assign guardian permissions on
save. A map added directly via admin (e.g. staff adding a file a user emailed in rather than
self-uploading through UserUploadedMapCreate, the only code path that called assign_perm) got a
row with no permissions and no error to signal it.
"""

from unittest.mock import MagicMock

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from guardian.shortcuts import get_perms

from display.admin import UserUploadedMapAdmin
from display.models.user_uploaded_map import UserUploadedMap


class TestUserUploadedMapAdmin(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create(email="map-owner@example.com")
        self.staff = get_user_model().objects.create(email="staff@example.com", is_staff=True)
        self.request = RequestFactory().get("/admin/display/useruploadedmap/add/")
        self.request.user = self.staff

    def test_registered_as_user_uploaded_map_admin(self):
        self.assertIsInstance(admin.site._registry[UserUploadedMap], UserUploadedMapAdmin)

    def test_save_model_assigns_permissions_to_the_maps_owner_not_the_staff_member(self):
        uploaded_map = UserUploadedMap(user=self.owner, name="Support-uploaded map")

        admin_instance = UserUploadedMapAdmin(UserUploadedMap, admin.site)
        admin_instance.save_model(self.request, uploaded_map, form=MagicMock(), change=False)

        owner_perms = set(get_perms(self.owner, uploaded_map))
        self.assertEqual(
            owner_perms,
            {
                "view_useruploadedmap",
                "change_useruploadedmap",
                "delete_useruploadedmap",
                "add_useruploadedmap",
            },
        )
        self.assertEqual(get_perms(self.staff, uploaded_map), [])
