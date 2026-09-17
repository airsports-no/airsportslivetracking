"""
Regression tests for the templates-section finding #7 (2026-08-28 review): several destructive
actions were exposed as plain GET links with no CSRF protection (GET isn't covered by Django's
CSRF middleware) - a one-click <img src="..."> on any page a logged-in editor visited could
silently mutate live competition state. All were already permission-checked server-side; only
the CSRF protection was missing.

Originally covered: contestant_remove_score_item (delete_score_item), contestant_stop_calculator
(terminate_contestant_calculator), contestant_restart_calculator (restart_contestant_calculator),
navigationtask_refresheditableroute (refresh_editable_route_navigation_task), renewtoken
(renew_token).

The first four views were removed in Slice 4 of the navigation-task-detail-spa-migration -
navigationtask_detail.html (their only remaining caller) was deleted, and each is now covered by
its REST equivalent instead (ContestantViewSet.remove_score_log_entry/.terminate/.restart,
NavigationTaskViewSet.refresh_editable_route - DRF's own dispatch already rejects unsupported
methods, and CSRF is enforced by SessionAuthentication the same as any other authenticated POST).
Only renew_token remains here.

clear_profile_image_background and remove_team were covered here too, but both views (along with
upload_profile_picture and RegisterTeamWizard's whole surface) were removed as part of the
wizard->SPA migration (see display.services.team_registration): remove_team's "remove a team from
a contest" behavior is now covered by test_contestteam_management.py's coverage of the
ContestTeamViewSet DELETE endpoint the new admin UI actually calls, and
clear_profile_image_background/upload_profile_picture had no reachable UI trigger left once the
wizard's picture-upload templates were deleted (grep confirmed zero references anywhere outside
those templates), so they were retired rather than kept as unreachable dead code.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.authtoken.models import Token


class TestDestructiveViewsRequirePost(TestCase):
    def setUp(self):
        self.manager = get_user_model().objects.create(email="csrf-manager@example.com")
        self.client.force_login(user=self.manager)

    def test_renew_token_rejects_get(self, *args):
        from django.contrib.auth.models import Permission

        self.manager.user_permissions.add(Permission.objects.get(codename="change_contest"))
        url = reverse("renewtoken")
        existing = Token.objects.create(user=self.manager)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)
        self.assertTrue(Token.objects.filter(pk=existing.pk).exists())

    def test_renew_token_post_succeeds(self, *args):
        from django.contrib.auth.models import Permission

        self.manager.user_permissions.add(Permission.objects.get(codename="change_contest"))
        url = reverse("renewtoken")
        existing = Token.objects.create(user=self.manager)
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Token.objects.filter(pk=existing.pk).exists())
        self.assertTrue(Token.objects.filter(user=self.manager).exists())
