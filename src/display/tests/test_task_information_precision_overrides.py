"""
Regression test: _precision_family_overrides (display/utilities/task_information.py) called
scorecard.get_maximum_penalty_for_gate_type(), which doesn't exist (real method:
get_maximum_timing_penalty_for_gate_type) - the resulting AttributeError was swallowed by a
bare `except Exception: pass` around the whole override block, so the "Timed gates currently
score..." override line silently never appeared for any precision-family task type.
"""

import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase

from display.default_scorecards.create_scorecards import create_scorecards
from display.models import Contest, EditableRoute, NavigationTask, Scorecard
from display.utilities.cima_task_type_definitions import PRECISION_NAVIGATION
from display.utilities.task_information import build_navigation_task_information


class TestTaskInformationPrecisionOverrides(TestCase):
    def setUp(self):
        create_scorecards()
        user = get_user_model().objects.create(email="task-information-overrides@example.com")
        contest = Contest.objects.create(
            name="Task Information Overrides Contest",
            time_zone="Europe/Oslo",
            start_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 8, 1, 17, 0, tzinfo=datetime.timezone.utc),
            location="60.0,11.0",
            created_by=user,
        )
        original_scorecard = Scorecard.get_originals().get(shortcut_name="FAI Precision")
        with open("display/tests/NM.csv", "r") as file:
            editable_route, _ = EditableRoute.create_from_csv("TaskInformationOverridesRoute", file.readlines()[1:])
            route = editable_route.create_precision_route(True, original_scorecard)
        self.navigation_task = NavigationTask.create(
            name="Task Information Overrides Task",
            contest=contest,
            route=route,
            original_scorecard=original_scorecard,
            start_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 8, 1, 17, 0, tzinfo=datetime.timezone.utc),
            task_subtype=PRECISION_NAVIGATION,
        )

    def test_precision_navigation_overrides_include_the_timed_gate_scoring_line(self):
        info = build_navigation_task_information(self.navigation_task)
        self.assertTrue(
            any("Timed gates currently score" in line for line in info["overrides"]),
            f"expected a 'Timed gates currently score...' override line, got: {info['overrides']}",
        )
