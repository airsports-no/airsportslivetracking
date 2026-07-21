from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from guardian.shortcuts import assign_perm
from rest_framework.test import APIRequestFactory

from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
from display.models import Contest, EditableRoute
from display.serialisers import NavigationTaskEditableRoutReferenceSerialiser


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

    @patch("display.serialisers.assert_can_add_navigation_task")
    def test_navigation_task_serializer_create_no_longer_calls_capacity_guard(self, mock_guard):
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

        serializer.save()

        mock_guard.assert_not_called()

    def test_navigation_task_capacity_guard_no_longer_blocks_creation(self):
        from display.services.capacity_enforcement import assert_can_add_navigation_task

        resolution = assert_can_add_navigation_task(self.contest)

        self.assertIsNotNone(resolution)
