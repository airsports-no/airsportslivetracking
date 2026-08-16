from unittest.mock import MagicMock, patch
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.http import HttpResponseRedirect
from django.test import RequestFactory, TestCase
from django.urls import reverse

from display.forms import ContestForm
from display.models import Contest, ContestTokenAssignment, EditableRoute, Route, TokenType, UserTokenGrant
from display.views_wizards import RouteToTaskWizard
from display.utilities.navigation_task_type_definitions import AIRSPORTS
from display.utilities.cima_task_type_definitions import CIRCLE


class TestRouteToTaskWizardTokenCreation(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create(email="wizard-token@example.com")
        self.user.user_permissions.add(Permission.objects.get(codename="change_editableroute"))
        self.editable_route = EditableRoute.objects.create(name="Wizard Route", route={"features": []})
        self.token_type = TokenType.objects.create(name="Wizard token", contestant_limit=25)
        self.token_grant = UserTokenGrant.objects.create(user=self.user, token_type=self.token_type, quantity_total=2)
        self.existing_contest = Contest.objects.create(
            name="Existing contest for wizard",
            time_zone="Europe/Oslo",
            start_time="2026-10-01T09:00:00+00:00",
            finish_time="2026-10-01T17:00:00+00:00",
            location="60,11",
            created_by=self.user,
        )

    def test_contest_creation_form_can_receive_user_token_grants_for_wizard_usage(self):
        form = ContestForm(token_grant_queryset=UserTokenGrant.objects.filter(user=self.user))
        self.assertEqual([self.token_grant.pk], list(form.fields["initial_token_grant"].queryset.values_list("pk", flat=True)))

    @patch.object(Contest, "initialise")
    @patch("display.views_wizards.NavigationTask.create")
    @patch.object(RouteToTaskWizard, "create_route")
    @patch("display.views_wizards.Scorecard.get_originals")
    def test_done_assigns_selected_token_to_newly_created_contest(self, mock_get_originals, mock_create_route, mock_navigation_task_create, mock_initialise):
        mock_get_originals.return_value = [SimpleNamespace(task_type=[AIRSPORTS])]
        mock_create_route.return_value = Route.objects.create()
        mock_navigation_task_create.return_value = SimpleNamespace(pk=123)

        request = RequestFactory().get("/")
        request.user = self.user
        request.session = {}
        request._messages = MagicMock()
        wizard = RouteToTaskWizard()
        wizard.request = request
        wizard.editable_route = self.editable_route
        wizard.get_cleaned_data_for_step = lambda step: {
            "contest_selection": {"task_type": AIRSPORTS, "navigation_task_name": "Generated Task", "contest": None},
            "contest_creation": {
                "name": "WizardContest",
                "time_zone": "Europe/Oslo",
                "start_time": "2026-10-01T09:00:00+00:00",
                "finish_time": "2026-10-01T17:00:00+00:00",
                "location": "60,11",
                "initial_token_grant": self.token_grant,
                "summary_score_sorting_direction": Contest.ASCENDING,
                "autosum_scores": True,
            },
            "task_content": {"original_scorecard": MagicMock(), "task_subtype": ""},
            "airsports_parameters": {"rounded_corners": False},
        }.get(step)

        response = wizard.done([])

        created_contest = Contest.objects.get(name="WizardContest")
        self.token_grant.refresh_from_db()
        self.assertIsInstance(response, HttpResponseRedirect)
        self.assertTrue(ContestTokenAssignment.objects.filter(contest=created_contest, token_grant=self.token_grant).exists())
        self.assertEqual(1, self.token_grant.quantity_consumed)

    @patch("display.views_wizards.assert_can_add_navigation_task")
    @patch("display.views_wizards.NavigationTask.create")
    @patch.object(RouteToTaskWizard, "create_route")
    @patch("display.views_wizards.Scorecard.get_originals")
    def test_done_checks_task_limit_for_existing_contest(self, mock_get_originals, mock_create_route, mock_navigation_task_create, mock_guard):
        mock_get_originals.return_value = [SimpleNamespace(task_type=[AIRSPORTS])]
        mock_create_route.return_value = Route.objects.create()
        mock_navigation_task_create.return_value = SimpleNamespace(pk=456)

        request = RequestFactory().get("/")
        request.user = self.user
        request.session = {}
        request._messages = MagicMock()
        wizard = RouteToTaskWizard()
        wizard.request = request
        wizard.editable_route = self.editable_route
        wizard.get_cleaned_data_for_step = lambda step: {
            "contest_selection": {"task_type": AIRSPORTS, "navigation_task_name": "Existing Contest Task", "contest": self.existing_contest},
            "task_content": {"original_scorecard": MagicMock(), "task_subtype": "", "name": "Existing Contest Task"},
            "airsports_parameters": {"rounded_corners": False},
        }.get(step)

        wizard.done([])

        mock_guard.assert_called_once_with(self.existing_contest, task_type=AIRSPORTS, task_subtype="", user=self.user)

    @patch("display.views_wizards.assert_can_add_navigation_task")
    @patch("display.views_wizards.NavigationTask.create")
    @patch.object(RouteToTaskWizard, "create_route")
    @patch("display.views_wizards.Scorecard.get_originals")
    def test_done_does_not_pass_duplicate_name_to_navigation_task_create(self, mock_get_originals, mock_create_route, mock_navigation_task_create, mock_guard):
        mock_get_originals.return_value = [SimpleNamespace(task_type=[AIRSPORTS])]
        mock_create_route.return_value = Route.objects.create()
        mock_navigation_task_create.return_value = SimpleNamespace(pk=789)

        request = RequestFactory().get("/")
        request.user = self.user
        request.session = {}
        request._messages = MagicMock()
        wizard = RouteToTaskWizard()
        wizard.request = request
        wizard.editable_route = self.editable_route
        wizard.get_cleaned_data_for_step = lambda step: {
            "contest_selection": {"task_type": AIRSPORTS, "navigation_task_name": "Wizard Selected Name", "contest": self.existing_contest},
            "task_content": {
                "original_scorecard": MagicMock(),
                "task_subtype": "",
                "name": "Form Task Name",
                "start_time": "2026-10-02T09:30:00+00:00",
                "finish_time": "2026-10-02T17:30:00+00:00",
            },
            "airsports_parameters": {"rounded_corners": False},
        }.get(step)

        wizard.done([])

        _, kwargs = mock_navigation_task_create.call_args
        self.assertEqual(kwargs["name"], "Form Task Name")
        self.assertEqual(kwargs["start_time"], "2026-10-02T09:30:00+00:00")
        self.assertEqual(kwargs["finish_time"], "2026-10-02T17:30:00+00:00")

    @patch("display.views_wizards.messages.error")
    @patch("display.views_wizards.assert_can_add_navigation_task")
    @patch("display.views_wizards.NavigationTask.create")
    @patch.object(RouteToTaskWizard, "create_route")
    @patch("display.views_wizards.Scorecard.get_originals")
    def test_done_rejects_missing_route_with_user_friendly_message(self, mock_get_originals, mock_create_route, mock_navigation_task_create, mock_guard, mock_messages_error):
        mock_get_originals.return_value = [SimpleNamespace(task_type=[AIRSPORTS])]
        mock_create_route.return_value = None
        mock_navigation_task_create.return_value = SimpleNamespace(pk=999)

        request = RequestFactory().post("/")
        request.user = self.user
        request.session = {}
        request._messages = MagicMock()
        wizard = RouteToTaskWizard()
        wizard.request = request
        wizard.editable_route = self.editable_route
        wizard.get_cleaned_data_for_step = lambda step: {
            "contest_selection": {"task_type": AIRSPORTS, "navigation_task_name": "Broken Route Task", "contest": self.existing_contest},
            "task_content": {"original_scorecard": MagicMock(), "task_subtype": CIRCLE, "name": "Broken Route Task"},
            "airsports_parameters": {"rounded_corners": False},
        }.get(step)

        response = wizard.done([])

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("contest_details", kwargs={"pk": self.existing_contest.pk}))
        mock_navigation_task_create.assert_not_called()
        mock_messages_error.assert_called_once()
        self.assertIn("Unable to create navigation task route", mock_messages_error.call_args.args[1])
