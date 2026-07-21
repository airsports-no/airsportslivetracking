import datetime

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from guardian.shortcuts import assign_perm

from display.models import Contest, NavigationTask, Route, Scorecard, TokenType, UserTokenGrant
from display.services.token_assignment import assign_token_to_contest


class TestArchiveReadOnlyViews(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create(email="archive-owner@example.com")
        self.user.user_permissions.add(
            Permission.objects.get(codename="view_contest"),
            Permission.objects.get(codename="change_contest"),
        )
        self.contest = Contest.objects.create(
            name="Archive Contest",
            time_zone="Europe/Oslo",
            start_time="2026-10-01T09:00:00+00:00",
            finish_time="2026-10-01T17:00:00+00:00",
            location="60.0,11.0",
            created_by=self.user,
        )
        assign_perm("view_contest", self.user, self.contest)
        assign_perm("change_contest", self.user, self.contest)
        self.navigation_task = NavigationTask.objects.create(
            name="Archive Task",
            contest=self.contest,
            route=Route.objects.create(name="Archive route"),
            original_scorecard=Scorecard.objects.create(name="Archive card", shortcut_name="archive-card"),
            start_time="2026-10-01T09:00:00+00:00",
            finish_time="2026-10-01T17:00:00+00:00",
        )
        self.token_type = TokenType.objects.create(
            name="Archive token",
            contestant_limit=8,
            validity_days=14,
        )
        self.token_grant = UserTokenGrant.objects.create(user=self.user, token_type=self.token_type, quantity_total=1)
        self.assignment = assign_token_to_contest(self.contest, self.user, self.token_grant.id)
        self.assignment.activated_at = datetime.datetime(2026, 10, 1, 9, 0, tzinfo=datetime.timezone.utc)
        self.assignment.expires_at = datetime.datetime(2026, 10, 15, 9, 0, tzinfo=datetime.timezone.utc)
        self.assignment.save(update_fields=["activated_at", "expires_at"])
        self.expired_at = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)

    def test_contest_detail_remains_readable_after_token_expiry(self):
        self.assignment.expires_at = self.expired_at
        self.assignment.save(update_fields=["expires_at"])
        self.client.force_login(self.user)

        response = self.client.get(reverse("contest_details", kwargs={"pk": self.contest.id}))

        self.assertEqual(200, response.status_code)
        self.assertContains(response, "Archive Contest")
        self.assertContains(response, "Archive Mode")
        self.assertContains(response, "This contest token expired on")

    def test_navigationtask_detail_remains_readable_after_token_expiry(self):
        self.assignment.expires_at = self.expired_at
        self.assignment.save(update_fields=["expires_at"])
        self.client.force_login(self.user)

        response = self.client.get(reverse("navigationtask_detail", kwargs={"pk": self.navigation_task.id}))

        self.assertEqual(200, response.status_code)
        self.assertContains(response, "Archive Task")
        self.assertContains(response, "Archive Mode")
        self.assertContains(response, "This contest token expired on")
