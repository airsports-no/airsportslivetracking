from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase

from display.models import Contest, EditableRoute, Route, TokenType, UserTokenGrant
from display.views_wizards import RouteToTaskWizard
from display.utilities.navigation_task_type_definitions import AIRSPORTS


class TestRouteToTaskWizardAtomicity(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create(email="wizard-atomic@example.com")
        self.user.user_permissions.add(Permission.objects.get(codename="change_editableroute"))
        self.editable_route = EditableRoute.objects.create(name="Atomic Wizard Route", route={"features": []})
        self.token_type = TokenType.objects.create(name="Atomic Wizard Token", contestant_limit=25)
        self.token_grant = UserTokenGrant.objects.create(user=self.user, token_type=self.token_type, quantity_total=2)

    @patch.object(Contest, "initialise")
    @patch("display.views_wizards.assign_token_to_contest", side_effect=ValidationError("boom"))
    @patch("display.views_wizards.NavigationTask.create")
    @patch.object(RouteToTaskWizard, "create_route")
    @patch("display.views_wizards.Scorecard.get_originals")
    def test_done_does_not_leave_contest_when_token_assignment_fails(self, mock_get_originals, mock_create_route, _mock_nav_create, _mock_assign, _mock_init):
        mock_get_originals.return_value = [MagicMock(task_type=[AIRSPORTS])]
        mock_create_route.return_value = Route.objects.create()

        request = RequestFactory().get("/")
        request.user = self.user
        request.session = {}
        request._messages = MagicMock()
        wizard = RouteToTaskWizard()
        wizard.request = request
        wizard.editable_route = self.editable_route
        wizard.get_cleaned_data_for_step = lambda step: {
            "contest_selection": {"task_type": AIRSPORTS, "navigation_task_name": "Atomic Generated Task", "contest": None},
            "contest_creation": {
                "name": "AtomicWizardContest",
                "time_zone": "Europe/Oslo",
                "start_time": "2026-10-01T09:00:00+00:00",
                "finish_time": "2026-10-01T17:00:00+00:00",
                "location": "60,11",
                "initial_token_grant": self.token_grant,
                "summary_score_sorting_direction": Contest.ASCENDING,
                "autosum_scores": True,
            },
            "airsports_parameters": {"rounded_corners": False},
        }.get(step)

        with self.assertRaises(ValidationError):
            wizard.done([])

        self.assertFalse(Contest.objects.filter(name="AtomicWizardContest").exists())
