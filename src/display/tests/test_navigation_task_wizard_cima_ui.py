import datetime
from unittest.mock import MagicMock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.messages import get_messages
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from rest_framework.exceptions import ValidationError as DRFValidationError

from display.default_scorecards.create_scorecards import create_scorecards
from display.forms import NavigationTaskForm
from display.forms_wizards import ContestSelectForm, TaskTypeForm
from display.models import (
    AccessGrant,
    Club,
    ClubManagerMembership,
    Contest,
    EditableRoute,
    Route,
    TokenType,
    UserTokenGrant,
)
from display.services.capacity_enforcement import assert_can_add_navigation_task
from display.utilities.cima_task_type_definitions import ANR_CATALOGUE, CIRCLE, CONTRACT_NAVIGATION_TIME_CONTROLS
from display.utilities.navigation_task_type_definitions import ANR_CORRIDOR, PRECISION
from display.views_wizards import NewNavigationTaskWizard, RouteToTaskWizard


class TestNavigationTaskWizardCimaUi(TestCase):
    def setUp(self):
        create_scorecards()
        self.user = get_user_model().objects.create(email="wizard-cima-ui@example.com")
        self.user.user_permissions.add(Permission.objects.get(codename="change_contest"))
        self.user.user_permissions.add(Permission.objects.get(codename="change_editableroute"))
        self.contest = Contest.objects.create(
            name="Wizard CIMA Contest",
            time_zone="Europe/Oslo",
            start_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 8, 1, 17, 0, tzinfo=datetime.timezone.utc),
            location="60.0,11.0",
            created_by=self.user,
        )
        self.editable_route = EditableRoute.objects.create(name="Wizard Route", route={"features": []})
        # A route authored with the four circle markers the CIRCLE (2.A7) subtype requires - see
        # display.services.route_compatibility - distinct from self.editable_route above, which is
        # deliberately empty for tests that only exercise permission/entitlement gating.
        self.circle_editable_route = EditableRoute.objects.create(
            name="Wizard Circle Route",
            route={
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {
                            "id": "cm-1",
                            "name": "CM",
                            "pointType": "circle_center",
                            "featureType": "circle_center_marker",
                        },
                        "geometry": {"type": "Point", "coordinates": [11.2, 60.2]},
                    },
                    {
                        "type": "Feature",
                        "properties": {
                            "id": "cs-1",
                            "name": "SP",
                            "pointType": "circle_start",
                            "featureType": "circle_start_marker",
                        },
                        "geometry": {"type": "Point", "coordinates": [11.1, 60.1]},
                    },
                    {
                        "type": "Feature",
                        "properties": {
                            "id": "ce-1",
                            "name": "X",
                            "pointType": "circle_entry",
                            "featureType": "circle_entry_marker",
                        },
                        "geometry": {"type": "Point", "coordinates": [11.15, 60.15]},
                    },
                    {
                        "type": "Feature",
                        "properties": {
                            "id": "cx-1",
                            "name": "WP",
                            "pointType": "circle_exit",
                            "featureType": "circle_exit_marker",
                        },
                        "geometry": {"type": "Point", "coordinates": [11.25, 60.25]},
                    },
                ],
            },
        )

    def _flatten_choice_values(self, choices):
        values = []
        for value, label in choices:
            if isinstance(label, (list, tuple)):
                values.extend(self._flatten_choice_values(label))
            else:
                values.append(value)
        return values

    @override_settings(GATE_CIMA_TASK_VISIBILITY=True, DEFAULT_FREE_TASK_TYPE_GROUPS=["legacy"])
    def test_task_type_form_hides_cima_templates_without_access(self):
        form = TaskTypeForm(user=self.user)
        choice_values = self._flatten_choice_values(form.fields["task_template"].choices)
        self.assertNotIn(CONTRACT_NAVIGATION_TIME_CONTROLS, choice_values)

    @override_settings(GATE_CIMA_TASK_VISIBILITY=True, DEFAULT_FREE_TASK_TYPE_GROUPS=["legacy"])
    def test_task_type_form_shows_cima_templates_with_token_access(self):
        token_type = TokenType.objects.create(name="Wizard CIMA token", contestant_limit=10, task_type_groups=["cima"])
        UserTokenGrant.objects.create(user=self.user, token_type=token_type, quantity_total=1, quantity_consumed=0)

        form = TaskTypeForm(user=self.user)
        choice_values = self._flatten_choice_values(form.fields["task_template"].choices)
        self.assertIn(CONTRACT_NAVIGATION_TIME_CONTROLS, choice_values)

    @override_settings(GATE_CIMA_TASK_VISIBILITY=True, DEFAULT_FREE_TASK_TYPE_GROUPS=["legacy"])
    def test_contest_select_form_hides_cima_templates_without_access(self):
        form = ContestSelectForm(user=self.user)
        choice_values = self._flatten_choice_values(form.fields["task_template"].choices)
        self.assertNotIn(ANR_CATALOGUE, choice_values)

    @override_settings(GATE_CIMA_TASK_VISIBILITY=True, DEFAULT_FREE_TASK_TYPE_GROUPS=["legacy"])
    def test_navigation_task_form_hides_cima_subtypes_without_access(self):
        form = NavigationTaskForm(task_family=PRECISION, user=self.user)
        subtype_values = self._flatten_choice_values(form.fields["task_subtype"].choices)
        self.assertNotIn(CONTRACT_NAVIGATION_TIME_CONTROLS, subtype_values)
        self.assertNotIn(CIRCLE, subtype_values)

    @override_settings(GATE_CIMA_TASK_VISIBILITY=True, DEFAULT_FREE_TASK_TYPE_GROUPS=["legacy"])
    def test_navigation_task_form_shows_cima_subtypes_with_club_pass(self):
        club = Club.objects.create(name="Wizard club")
        self.contest.organizing_club = club
        self.contest.save(update_fields=["organizing_club"])
        ClubManagerMembership.objects.create(
            club=club, user=self.user, role=ClubManagerMembership.OWNER, is_active=True
        )
        AccessGrant.objects.create(
            club=club, status=AccessGrant.ACTIVE, contestant_limit=None, task_type_groups=["cima"]
        )

        form = NavigationTaskForm(task_family=PRECISION, user=self.user)
        subtype_values = self._flatten_choice_values(form.fields["task_subtype"].choices)
        self.assertIn(CONTRACT_NAVIGATION_TIME_CONTROLS, subtype_values)
        self.assertIn(CIRCLE, subtype_values)

    @override_settings(GATE_CIMA_TASK_VISIBILITY=False, DEFAULT_FREE_TASK_TYPE_GROUPS=["legacy"])
    def test_task_type_form_shows_cima_templates_when_gate_disabled(self):
        form = TaskTypeForm(user=self.user)
        choice_values = self._flatten_choice_values(form.fields["task_template"].choices)
        self.assertIn(CONTRACT_NAVIGATION_TIME_CONTROLS, choice_values)

    @override_settings(GATE_CIMA_TASK_VISIBILITY=False, DEFAULT_FREE_TASK_TYPE_GROUPS=["legacy"])
    def test_navigation_task_form_shows_cima_subtypes_when_gate_disabled(self):
        form = NavigationTaskForm(task_family=PRECISION, user=self.user)
        subtype_values = self._flatten_choice_values(form.fields["task_subtype"].choices)
        self.assertIn(CONTRACT_NAVIGATION_TIME_CONTROLS, subtype_values)
        self.assertIn(CIRCLE, subtype_values)

    def test_task_type_form_maps_cima_template_to_precision_family_and_subtype(self):
        form = TaskTypeForm(data={"task_template": CONTRACT_NAVIGATION_TIME_CONTROLS}, user=self.user)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["task_type"], PRECISION)
        self.assertEqual(form.cleaned_data["task_subtype"], CONTRACT_NAVIGATION_TIME_CONTROLS)

    def test_contest_select_form_maps_cima_template_to_anr_family_and_subtype(self):
        form = ContestSelectForm(
            data={
                "contest": self.contest.pk,
                "task_template": ANR_CATALOGUE,
                "navigation_task_name": "ANR Catalogue Task",
            },
            user=self.user,
        )
        form.fields["contest"].queryset = Contest.objects.filter(pk=self.contest.pk)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["task_type"], ANR_CORRIDOR)
        self.assertEqual(form.cleaned_data["task_subtype"], ANR_CATALOGUE)

    def test_navigation_task_form_includes_anr_catalogue_choice_for_anr_family(self):
        form = NavigationTaskForm(task_family=ANR_CORRIDOR, user=self.user)
        subtype_values = self._flatten_choice_values(form.fields["task_subtype"].choices)
        self.assertIn(ANR_CATALOGUE, subtype_values)
        self.assertNotIn(CONTRACT_NAVIGATION_TIME_CONTROLS, subtype_values)

    def test_new_navigation_task_wizard_prefills_task_content_subtype(self):
        request = RequestFactory().get("/")
        request.user = self.user
        request.session = {}
        request._messages = MagicMock()
        wizard = NewNavigationTaskWizard()
        wizard.request = request
        wizard.contest = self.contest
        wizard.initial_dict = {}
        wizard.get_cleaned_data_for_step = lambda step: {
            "task_type": {
                "task_template": CONTRACT_NAVIGATION_TIME_CONTROLS,
                "task_type": PRECISION,
                "task_subtype": CONTRACT_NAVIGATION_TIME_CONTROLS,
            }
        }.get(step)

        initial = wizard.get_form_initial("task_content")
        self.assertEqual(initial["task_subtype"], CONTRACT_NAVIGATION_TIME_CONTROLS)

    def test_route_to_task_wizard_includes_task_content_step(self):
        step_names = [name for name, _form in RouteToTaskWizard.form_list]
        self.assertIn("task_content", step_names)

    def test_route_to_task_wizard_prefills_task_content_from_selected_template_and_contest(self):
        request = RequestFactory().get("/")
        request.user = self.user
        request.session = {}
        request._messages = MagicMock()
        wizard = RouteToTaskWizard()
        wizard.request = request
        wizard.editable_route = self.editable_route
        wizard.initial_dict = {}
        wizard.get_cleaned_data_for_step = lambda step: {
            "contest_selection": {
                "contest": self.contest,
                "task_template": CONTRACT_NAVIGATION_TIME_CONTROLS,
                "task_type": PRECISION,
                "task_subtype": CONTRACT_NAVIGATION_TIME_CONTROLS,
                "navigation_task_name": "Contract Task",
            }
        }.get(step)

        initial = wizard.get_form_initial("task_content")
        self.assertEqual(initial["name"], "Contract Task")
        self.assertEqual(initial["task_subtype"], CONTRACT_NAVIGATION_TIME_CONTROLS)
        self.assertEqual(initial["start_time"], self.contest.start_time)
        self.assertEqual(initial["finish_time"], self.contest.finish_time)

    def test_route_to_task_wizard_task_content_scorecards_are_filtered_by_selected_family(self):
        request = RequestFactory().get("/")
        request.user = self.user
        request.session = {}
        request._messages = MagicMock()
        wizard = RouteToTaskWizard()
        wizard.request = request
        wizard.editable_route = self.editable_route
        wizard.initial_dict = {}
        wizard.storage = MagicMock(extra_data={})
        wizard.prefix = "route_to_task_wizard"
        wizard.steps = MagicMock(current="task_content")
        wizard.get_cleaned_data_for_step = lambda step: {
            "contest_selection": {
                "contest": self.contest,
                "task_template": ANR_CATALOGUE,
                "task_type": ANR_CORRIDOR,
                "task_subtype": ANR_CATALOGUE,
                "navigation_task_name": "ANR Task",
            }
        }.get(step)
        form = NavigationTaskForm(
            task_family=ANR_CORRIDOR, initial=wizard.get_form_initial("task_content"), user=self.user
        )
        context = wizard.get_context_data(form=form)
        queryset = context["form"].fields["original_scorecard"].queryset
        self.assertTrue(queryset.filter(name="FAI ANR 2022").exists())
        self.assertFalse(queryset.filter(shortcut_name="FAI Precision").exists())

    @override_settings(
        ACCESS_ENFORCEMENT_MODE="enforce",
        DEFAULT_FREE_CONTESTANT_LIMIT=None,
        DEFAULT_FREE_TASK_TYPE_GROUPS=["legacy"],
    )
    def test_cima_task_group_block_message_is_friendly(self):
        with self.assertRaisesMessage(
            Exception,
            "This task requires the cima task package, but the current contest only has access to other task groups.",
        ):
            assert_can_add_navigation_task(
                self.contest,
                task_type=PRECISION,
                task_subtype=CONTRACT_NAVIGATION_TIME_CONTROLS,
            )

    @override_settings(
        ACCESS_ENFORCEMENT_MODE="enforce",
        DEFAULT_FREE_CONTESTANT_LIMIT=None,
        DEFAULT_FREE_TASK_TYPE_GROUPS=["legacy"],
    )
    def test_route_to_task_wizard_redirects_blocked_access_to_contest_detail_with_message(self):
        request = RequestFactory().post("/")
        request.user = self.user
        SessionMiddleware(lambda req: None).process_request(request)
        request.session.save()
        setattr(request, "_messages", FallbackStorage(request))

        wizard = RouteToTaskWizard()
        wizard.request = request
        wizard.editable_route = self.editable_route
        wizard.get_cleaned_data_for_step = lambda step: {
            "contest_selection": {
                "contest": self.contest,
                "task_template": CONTRACT_NAVIGATION_TIME_CONTROLS,
                "task_type": PRECISION,
                "task_subtype": CONTRACT_NAVIGATION_TIME_CONTROLS,
                "navigation_task_name": "Blocked Contract Task",
            },
            "task_content": {
                "original_scorecard": MagicMock(),
                "task_subtype": CONTRACT_NAVIGATION_TIME_CONTROLS,
            },
        }.get(step)
        wizard.create_route = MagicMock(return_value=MagicMock())

        response = wizard.done([])

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("contest_details", kwargs={"pk": self.contest.pk}))
        messages = [message.message for message in get_messages(request)]
        self.assertTrue(any("This task requires the cima task package" in message for message in messages), messages)

    @override_settings(
        ACCESS_ENFORCEMENT_MODE="enforce",
        DEFAULT_FREE_CONTESTANT_LIMIT=None,
        DEFAULT_FREE_TASK_TYPE_GROUPS=["legacy"],
    )
    def test_new_navigation_task_wizard_blocks_unentitled_cima_task_creation(self):
        """Regression test: the primary 'New Navigation Task' wizard must
        enforce the same CIMA entitlement check as RouteToTaskWizard - a user
        with no token/club/entitlement grant must not be able to create a
        CIMA task through this wizard."""
        request = RequestFactory().post("/")
        request.user = self.user
        request.session = {}
        request._messages = MagicMock()

        wizard = NewNavigationTaskWizard()
        wizard.request = request
        wizard.contest = self.contest
        wizard.get_cleaned_data_for_step = lambda step: {
            "task_type": {
                "task_type": PRECISION,
                "task_subtype": CIRCLE,
            },
            "task_content": {
                "original_scorecard": MagicMock(use_procedure_turns=True),
            },
            "precision_route_import": {
                "internal_route": self.circle_editable_route,
            },
        }.get(step)

        with self.assertRaisesMessage(
            ValidationError,
            "This task requires the cima task package, but the current contest only has access to other task groups.",
        ):
            wizard.done([])

    def test_new_navigation_task_wizard_creates_placeholder_route_for_circle_subtype(self):
        request = RequestFactory().get("/")
        request.user = self.user
        request.session = {}
        request._messages = MagicMock()
        wizard = NewNavigationTaskWizard()
        wizard.request = request
        wizard.contest = self.contest
        wizard.get_cleaned_data_for_step = lambda step: {
            "task_type": {
                "task_type": PRECISION,
                "task_subtype": CIRCLE,
            },
            "task_content": {
                "original_scorecard": MagicMock(use_procedure_turns=True),
            },
            "precision_route_import": {
                "internal_route": self.circle_editable_route,
            },
        }.get(step)

        route, editable_route = wizard.create_route(MagicMock())

        self.assertIsInstance(route, Route)
        self.assertIsNotNone(route.pk)
        self.assertEqual(route.waypoints, [])
        self.assertEqual(route.takeoff_gates, [])
        self.assertEqual(route.landing_gates, [])
        self.assertFalse(route.use_procedure_turns)
        self.assertEqual(editable_route, self.circle_editable_route)
