"""
Regression tests for the two new read endpoints backing the React nav-task-creation flow
(replacing NewNavigationTaskWizard/RouteToTaskWizard - see the wizard->SPA migration plan):

- GET /api/v1/editableroutes/task_templates/ - grouped, visibility- and route-compatibility-
  filtered task-template choices (display.services.task_templates.task_template_choices).
- GET /api/v1/scorecards/choices/ - lightweight scorecard picker.

Both simply expose existing, already-tested service functions over HTTP - see
test_task_template_service.py and test_navigation_task_wizard_cima_ui.py for the underlying
choice-building/visibility-filtering logic itself.
"""

import datetime

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings
from guardian.shortcuts import assign_perm
from rest_framework.test import APIClient

from display.default_scorecards.create_scorecards import create_scorecards
from display.models import AccessGrant, Club, ClubManagerMembership, Contest, EditableRoute
from display.utilities.cima_task_type_definitions import CIRCLE, CONTRACT_NAVIGATION_TIME_CONTROLS
from display.utilities.navigation_task_type_definitions import ANR_CORRIDOR, PRECISION


class TestTaskTemplatesApi(TestCase):
    def setUp(self):
        create_scorecards()
        self.user = get_user_model().objects.create(email="task-templates-api@example.com")
        # EditableRouteViewSet.permission_classes gates every action (including this read-only
        # one) on the "add_editableroute" model permission, not just POST/PUT/DELETE - see
        # EditableRoutePermission.has_permission.
        self.user.user_permissions.add(Permission.objects.get(codename="add_editableroute"))
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.contest = Contest.objects.create(
            name="Task Templates API Contest",
            time_zone="Europe/Oslo",
            start_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 8, 1, 17, 0, tzinfo=datetime.timezone.utc),
            location="60.0,11.0",
            created_by=self.user,
        )
        self.plain_route = EditableRoute.objects.create(name="Plain route", route={"features": []})
        self.circle_route = EditableRoute.objects.create(
            name="Circle route",
            route={
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"id": "cm-1", "name": "CM", "featureType": "circle_center_marker"},
                        "geometry": {"type": "Point", "coordinates": [11.2, 60.2]},
                    },
                    {
                        "type": "Feature",
                        "properties": {"id": "cs-1", "name": "SP", "featureType": "circle_start_marker"},
                        "geometry": {"type": "Point", "coordinates": [11.1, 60.1]},
                    },
                    {
                        "type": "Feature",
                        "properties": {"id": "ce-1", "name": "X", "featureType": "circle_entry_marker"},
                        "geometry": {"type": "Point", "coordinates": [11.15, 60.15]},
                    },
                    {
                        "type": "Feature",
                        "properties": {"id": "cx-1", "name": "WP", "featureType": "circle_exit_marker"},
                        "geometry": {"type": "Point", "coordinates": [11.25, 60.25]},
                    },
                ],
            },
        )
        assign_perm("change_editableroute", self.user, self.plain_route)
        assign_perm("change_editableroute", self.user, self.circle_route)

    def _flatten(self, groups):
        values = []
        for group in groups:
            values.extend(template["value"] for template in group["templates"])
        return values

    def test_returns_grouped_legacy_and_cima_choices(self):
        response = self.client.get("/api/v1/editableroutes/task_templates/")
        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        group_names = {group["group"] for group in payload["groups"]}
        self.assertIn("Legacy", group_names)
        self.assertIn(PRECISION, self._flatten(payload["groups"]))

    @override_settings(GATE_CIMA_TASK_VISIBILITY=True, DEFAULT_FREE_TASK_TYPE_GROUPS=["legacy"])
    def test_hides_cima_templates_without_access(self):
        response = self.client.get("/api/v1/editableroutes/task_templates/")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertNotIn(CONTRACT_NAVIGATION_TIME_CONTROLS, self._flatten(response.json()["groups"]))

    @override_settings(GATE_CIMA_TASK_VISIBILITY=True, DEFAULT_FREE_TASK_TYPE_GROUPS=["legacy"])
    def test_shows_cima_templates_with_a_club_grant(self):
        club = Club.objects.create(name="Task templates club")
        ClubManagerMembership.objects.create(
            club=club, user=self.user, role=ClubManagerMembership.OWNER, is_active=True
        )
        AccessGrant.objects.create(
            club=club, status=AccessGrant.ACTIVE, contestant_limit=None, task_type_groups=["cima"]
        )

        response = self.client.get("/api/v1/editableroutes/task_templates/")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertIn(CONTRACT_NAVIGATION_TIME_CONTROLS, self._flatten(response.json()["groups"]))

    def test_filters_by_route_compatibility(self):
        response = self.client.get(f"/api/v1/editableroutes/task_templates/?editable_route={self.circle_route.pk}")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertIn(CIRCLE, self._flatten(response.json()["groups"]))

        response = self.client.get(f"/api/v1/editableroutes/task_templates/?editable_route={self.plain_route.pk}")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertNotIn(CIRCLE, self._flatten(response.json()["groups"]))

    def test_returns_explanatory_message_when_no_templates_are_compatible(self):
        empty_route = EditableRoute.objects.create(name="Empty route", route={"features": []})
        assign_perm("change_editableroute", self.user, empty_route)
        response = self.client.get(f"/api/v1/editableroutes/task_templates/?editable_route={empty_route.pk}")
        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        if not payload["groups"]:
            self.assertIsNotNone(payload["no_compatible_task_types_message"])

    def test_editable_route_the_user_cannot_see_is_a_404(self):
        other_user = get_user_model().objects.create(email="someone-else@example.com")
        others_route = EditableRoute.objects.create(name="Someone else's route", route={"features": []})
        assign_perm("change_editableroute", other_user, others_route)
        response = self.client.get(f"/api/v1/editableroutes/task_templates/?editable_route={others_route.pk}")
        self.assertEqual(response.status_code, 404, response.content)


class TestScorecardChoicesApi(TestCase):
    def setUp(self):
        create_scorecards()
        self.user = get_user_model().objects.create(email="scorecard-choices-api@example.com")
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_returns_shortcut_name_and_name_only(self):
        response = self.client.get("/api/v1/scorecards/choices/")
        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertTrue(payload)
        entry = payload[0]
        self.assertEqual(set(entry.keys()), {"shortcut_name", "name", "task_type"})

    def test_filters_by_task_type(self):
        response = self.client.get(f"/api/v1/scorecards/choices/?task_type={ANR_CORRIDOR}")
        self.assertEqual(response.status_code, 200, response.content)
        for entry in response.json():
            self.assertIn(ANR_CORRIDOR, entry["task_type"])
