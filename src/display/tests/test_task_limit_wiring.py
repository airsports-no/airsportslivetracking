from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings
from guardian.shortcuts import assign_perm
from rest_framework.test import APIRequestFactory

from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
from display.models import Contest, EditableRoute, TokenType, UserTokenGrant
from display.serialisers import NavigationTaskEditableRoutReferenceSerialiser
from display.services.task_type_visibility import can_user_see_cima_task_types


class TestTaskLimitWiring(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create(email="task-limit@example.com")
        self.user.user_permissions.add(Permission.objects.get(codename="add_contest"))
        self.contest = Contest.objects.create(
            name="Task Limit Contest",
            time_zone="Europe/Oslo",
            start_time="2026-10-01T09:00:00+00:00",
            finish_time="2026-10-01T17:00:00+00:00",
            location="60,11",
            created_by=self.user,
        )
        self.request = APIRequestFactory().post("/")
        self.request.user = self.user
        with open("display/tests/NM.csv", "r") as file:
            editable_route, _ = EditableRoute.create_from_csv("TaskLimitRoute", file.readlines()[1:])
            self.route = editable_route
        assign_perm("change_editableroute", self.user, self.route)
        self.scorecard = get_default_scorecard()

    def test_navigation_task_serializer_create_succeeds_without_capacity_guard_hook(self):
        serializer = NavigationTaskEditableRoutReferenceSerialiser(
            data={
                "name": "Limited Task",
                "original_scorecard": self.scorecard.shortcut_name,
                "start_time": "2026-10-01T09:00:00Z",
                "finish_time": "2026-10-01T17:00:00Z",
                "allow_self_management": True,
                "editable_route": self.route.pk,
            },
            context={"request": self.request, "contest": self.contest},
        )
        serializer.fields["editable_route"].queryset = EditableRoute.objects.filter(pk=self.route.pk)
        self.assertTrue(serializer.is_valid(), serializer.errors)

        navigation_task = serializer.save()

        self.assertEqual(navigation_task.name, "Limited Task")

    def test_navigation_task_serializer_accepts_turnpoint_hunt_task_config(self):
        # limited_fuel_turnpoint_hunt has no route backbone - it requires the editable route to
        # carry standalone catalogue_turnpoint/known_time_gate features instead (see
        # TASK_SUBTYPE_DEFINITIONS), which self.route (a plain precision CSV import) doesn't have.
        turnpoint_hunt_route = EditableRoute.objects.create(
            name="Turnpoint Hunt Route",
            route={
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"id": "ctp-1", "name": "CTP1", "featureType": "catalogue_turnpoint"},
                        "geometry": {"type": "Point", "coordinates": [11.0, 60.0]},
                    },
                    {
                        "type": "Feature",
                        "properties": {"id": "ktg-1", "name": "KTG1", "featureType": "known_time_gate"},
                        "geometry": {"type": "Point", "coordinates": [11.1, 60.1]},
                    },
                ],
            },
        )
        assign_perm("change_editableroute", self.user, turnpoint_hunt_route)
        serializer = NavigationTaskEditableRoutReferenceSerialiser(
            data={
                "name": "Turnpoint Hunt Task",
                "original_scorecard": "FAI Precision",
                "start_time": "2026-10-01T09:00:00Z",
                "finish_time": "2026-10-01T17:00:00Z",
                "allow_self_management": True,
                "editable_route": turnpoint_hunt_route.pk,
                "task_subtype": "limited_fuel_turnpoint_hunt",
                "task_config": {
                    "maximum_task_duration_minutes": 45,
                    "maximum_task_duration_penalty": 123,
                    "fuel_deadline_penalty": 77,
                    "compulsory_timing_tolerance_seconds": 8,
                },
            },
            context={"request": self.request, "contest": self.contest},
        )
        serializer.fields["editable_route"].queryset = EditableRoute.objects.filter(pk=turnpoint_hunt_route.pk)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        navigation_task = serializer.save()
        self.assertEqual(navigation_task.task_subtype, "limited_fuel_turnpoint_hunt")
        self.assertEqual(
            navigation_task.task_config,
            {
                "maximum_task_duration_minutes": 45,
                "maximum_task_duration_penalty": 123,
                "fuel_deadline_penalty": 77,
                "compulsory_timing_tolerance_seconds": 8,
            },
        )

    def test_navigation_task_serializer_accepts_duration_task_config(self):
        serializer = NavigationTaskEditableRoutReferenceSerialiser(
            data={
                "name": "Duration Task",
                "original_scorecard": "FAI Precision",
                "start_time": "2026-10-01T09:00:00Z",
                "finish_time": "2026-10-01T17:00:00Z",
                "allow_self_management": True,
                "editable_route": self.route.pk,
                "task_subtype": "duration",
                "task_config": {
                    "duration_normalization_policy": "raw_minutes",
                },
            },
            context={"request": self.request, "contest": self.contest},
        )
        serializer.fields["editable_route"].queryset = EditableRoute.objects.filter(pk=self.route.pk)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        navigation_task = serializer.save()
        self.assertEqual(navigation_task.task_subtype, "duration")
        self.assertEqual(
            navigation_task.task_config,
            {
                "duration_normalization_policy": "raw_minutes",
            },
        )

    def test_navigation_task_serializer_accepts_duration_landing_area_polygon(self):
        serializer = NavigationTaskEditableRoutReferenceSerialiser(
            data={
                "name": "Duration Landing Area Task",
                "original_scorecard": "FAI Precision",
                "start_time": "2026-10-01T09:00:00Z",
                "finish_time": "2026-10-01T17:00:00Z",
                "allow_self_management": True,
                "editable_route": self.route.pk,
                "task_subtype": "duration",
                "task_config": {
                    "duration_landing_area_polygon": [[11.0, 60.0], [11.2, 60.0], [11.2, 60.2], [11.0, 60.2]],
                },
            },
            context={"request": self.request, "contest": self.contest},
        )
        serializer.fields["editable_route"].queryset = EditableRoute.objects.filter(pk=self.route.pk)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        navigation_task = serializer.save()
        self.assertEqual(navigation_task.task_subtype, "duration")
        self.assertEqual(
            navigation_task.task_config,
            {
                "duration_landing_area_polygon": [[11.0, 60.0], [11.2, 60.0], [11.2, 60.2], [11.0, 60.2]],
            },
        )

    def test_navigation_task_serializer_accepts_duration_residual_fuel_required(self):
        serializer = NavigationTaskEditableRoutReferenceSerialiser(
            data={
                "name": "Duration Residual Fuel Task",
                "original_scorecard": "FAI Precision",
                "start_time": "2026-10-01T09:00:00Z",
                "finish_time": "2026-10-01T17:00:00Z",
                "allow_self_management": True,
                "editable_route": self.route.pk,
                "task_subtype": "duration",
                "task_config": {
                    "duration_residual_fuel_required": True,
                },
            },
            context={"request": self.request, "contest": self.contest},
        )
        serializer.fields["editable_route"].queryset = EditableRoute.objects.filter(pk=self.route.pk)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        navigation_task = serializer.save()
        self.assertEqual(navigation_task.task_subtype, "duration")
        self.assertEqual(
            navigation_task.task_config,
            {
                "duration_residual_fuel_required": True,
            },
        )

    def test_navigation_task_serializer_accepts_circle_radius_config(self):
        # circle has no route backbone - it requires the editable route to carry all four
        # standalone circle_*_marker features instead (see TASK_SUBTYPE_DEFINITIONS), which
        # self.route (a plain precision CSV import) doesn't have.
        circle_route = EditableRoute.objects.create(
            name="Circle Route",
            route={
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"id": "cm-1", "name": "CM", "featureType": "circle_center_marker"},
                        "geometry": {"type": "Point", "coordinates": [11.0, 60.0]},
                    },
                    {
                        "type": "Feature",
                        "properties": {"id": "cs-1", "name": "CS", "featureType": "circle_start_marker"},
                        "geometry": {"type": "Point", "coordinates": [11.01, 60.0]},
                    },
                    {
                        "type": "Feature",
                        "properties": {"id": "ce-1", "name": "CE", "featureType": "circle_entry_marker"},
                        "geometry": {"type": "Point", "coordinates": [11.02, 60.0]},
                    },
                    {
                        "type": "Feature",
                        "properties": {"id": "cx-1", "name": "CX", "featureType": "circle_exit_marker"},
                        "geometry": {"type": "Point", "coordinates": [11.03, 60.0]},
                    },
                ],
            },
        )
        assign_perm("change_editableroute", self.user, circle_route)
        serializer = NavigationTaskEditableRoutReferenceSerialiser(
            data={
                "name": "Circle Task",
                "original_scorecard": "FAI Precision",
                "start_time": "2026-10-01T09:00:00Z",
                "finish_time": "2026-10-01T17:00:00Z",
                "allow_self_management": True,
                "editable_route": circle_route.pk,
                "task_subtype": "circle",
                "task_config": {
                    "circle_radius_min_m": 250,
                    "circle_radius_max_m": 800,
                },
            },
            context={"request": self.request, "contest": self.contest},
        )
        serializer.fields["editable_route"].queryset = EditableRoute.objects.filter(pk=circle_route.pk)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["task_subtype"], "circle")
        self.assertEqual(
            serializer.validated_data["task_config"],
            {
                "circle_radius_min_m": 250,
                "circle_radius_max_m": 800,
            },
        )

    def test_navigation_task_capacity_guard_no_longer_blocks_creation(self):
        from display.services.capacity_enforcement import assert_can_add_navigation_task

        resolution = assert_can_add_navigation_task(self.contest, task_type=self.scorecard.calculator, task_subtype="")

        self.assertIsNotNone(resolution)

    @override_settings(GATE_CIMA_TASK_VISIBILITY=True, DEFAULT_FREE_TASK_TYPE_GROUPS=["legacy"])
    def test_task_type_visibility_helper_hides_cima_without_access(self):
        self.assertFalse(can_user_see_cima_task_types(self.user))

    @override_settings(GATE_CIMA_TASK_VISIBILITY=True, DEFAULT_FREE_TASK_TYPE_GROUPS=["legacy"])
    def test_task_type_visibility_helper_allows_cima_with_token(self):
        token_type = TokenType.objects.create(name="Visible CIMA token", contestant_limit=10, task_type_groups=["cima"])
        UserTokenGrant.objects.create(user=self.user, token_type=token_type, quantity_total=1, quantity_consumed=0)

        self.assertTrue(can_user_see_cima_task_types(self.user))
