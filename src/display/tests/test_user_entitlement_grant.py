import datetime

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import RequestFactory, TestCase

from display.admin import UserEntitlementGrantAdmin
from django.contrib import admin as django_admin

from display.models import UserEntitlementGrant


class TestUserEntitlementGrant(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create(email="grantee@example.com")
        self.granter = get_user_model().objects.create(email="granter@example.com")

    def test_is_active_now_true_without_expiry(self):
        grant = UserEntitlementGrant.objects.create(
            user=self.user, kind=UserEntitlementGrant.KIND_TASK_TYPE_GROUP, value="cima:circle"
        )
        self.assertTrue(grant.is_active_now)

    def test_is_active_now_false_when_expired(self):
        grant = UserEntitlementGrant.objects.create(
            user=self.user,
            kind=UserEntitlementGrant.KIND_TASK_TYPE_GROUP,
            value="cima:circle",
            expires_at=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1),
        )
        self.assertFalse(grant.is_active_now)

    def test_is_active_now_true_when_expiry_in_future(self):
        grant = UserEntitlementGrant.objects.create(
            user=self.user,
            kind=UserEntitlementGrant.KIND_TASK_TYPE_GROUP,
            value="cima:circle",
            expires_at=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1),
        )
        self.assertTrue(grant.is_active_now)

    def test_is_active_now_false_when_manually_deactivated(self):
        grant = UserEntitlementGrant.objects.create(
            user=self.user, kind=UserEntitlementGrant.KIND_TASK_TYPE_GROUP, value="cima:circle", is_active=False
        )
        self.assertFalse(grant.is_active_now)

    def test_unique_together_on_user_kind_value(self):
        UserEntitlementGrant.objects.create(
            user=self.user, kind=UserEntitlementGrant.KIND_TASK_TYPE_GROUP, value="cima:circle"
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                UserEntitlementGrant.objects.create(
                    user=self.user, kind=UserEntitlementGrant.KIND_TASK_TYPE_GROUP, value="cima:circle"
                )

    def test_admin_save_model_sets_granted_by_only_on_creation(self):
        admin_instance = UserEntitlementGrantAdmin(UserEntitlementGrant, django_admin.site)
        request = RequestFactory().post("/admin/")
        request.user = self.granter

        grant = UserEntitlementGrant(
            user=self.user, kind=UserEntitlementGrant.KIND_TASK_TYPE_GROUP, value="cima:circle"
        )
        admin_instance.save_model(request, grant, form=None, change=False)
        self.assertEqual(grant.granted_by_id, self.granter.id)

        other_admin = get_user_model().objects.create(email="other-admin@example.com")
        request.user = other_admin
        admin_instance.save_model(request, grant, form=None, change=True)
        # Editing an existing grant must not silently reassign granted_by.
        self.assertEqual(grant.granted_by_id, self.granter.id)
