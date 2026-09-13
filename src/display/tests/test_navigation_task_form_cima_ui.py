import datetime

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings

from display.default_scorecards.create_scorecards import create_scorecards
from display.forms import NavigationTaskForm
from display.models import AccessGrant, Club, ClubManagerMembership, Contest
from display.services.capacity_enforcement import assert_can_add_navigation_task
from display.utilities.cima_task_type_definitions import ANR_CATALOGUE, CIRCLE, CONTRACT_NAVIGATION_TIME_CONTROLS
from display.utilities.navigation_task_type_definitions import ANR_CORRIDOR, PRECISION


class TestNavigationTaskFormCimaUi(TestCase):
    """
    CIMA task-subtype visibility/entitlement coverage for NavigationTaskForm (still used by the
    non-wizard navigation-task edit view, views.py's NavigationTaskUpdateView) and for
    assert_can_add_navigation_task directly. The TaskTypeForm/ContestSelectForm and
    NewNavigationTaskWizard/RouteToTaskWizard tests that used to live here were removed once those
    wizards were replaced by the React nav-task-creation flow (see the wizard->SPA migration plan)
    - equivalent coverage now lives in test_task_template_service.py and
    test_task_templates_and_scorecards_api.py.
    """

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

    def _flatten_choice_values(self, choices):
        values = []
        for value, label in choices:
            if isinstance(label, (list, tuple)):
                values.extend(self._flatten_choice_values(label))
            else:
                values.append(value)
        return values

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
    def test_navigation_task_form_shows_cima_subtypes_when_gate_disabled(self):
        form = NavigationTaskForm(task_family=PRECISION, user=self.user)
        subtype_values = self._flatten_choice_values(form.fields["task_subtype"].choices)
        self.assertIn(CONTRACT_NAVIGATION_TIME_CONTROLS, subtype_values)
        self.assertIn(CIRCLE, subtype_values)

    def test_navigation_task_form_includes_anr_catalogue_choice_for_anr_family(self):
        form = NavigationTaskForm(task_family=ANR_CORRIDOR, user=self.user)
        subtype_values = self._flatten_choice_values(form.fields["task_subtype"].choices)
        self.assertIn(ANR_CATALOGUE, subtype_values)
        self.assertNotIn(CONTRACT_NAVIGATION_TIME_CONTROLS, subtype_values)

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
