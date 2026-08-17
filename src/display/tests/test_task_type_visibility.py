import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from display.forms import NavigationTaskForm
from display.forms_wizards import _task_template_choices
from display.models import UserEntitlementGrant
from display.services.task_type_visibility import can_user_see_cima_task_types, can_user_see_task_subtype
from display.utilities.cima_task_type_definitions import CIRCLE, TURNPOINT_HUNT
from display.utilities.navigation_task_type_definitions import PRECISION
from display.utilities.task_type_group_definitions import LEGACY_TASK_TYPE_GROUP


@override_settings(
    GATE_CIMA_TASK_VISIBILITY=True,
    DEFAULT_FREE_TASK_TYPE_GROUPS=[LEGACY_TASK_TYPE_GROUP],
)
class TestFineGrainedTaskSubtypeVisibility(TestCase):
    """A user with only a fine-grained cima:<subtype> grant should see (and be
    offered) exactly that subtype in task-creation UI, not every CIMA subtype -
    the GUI should match what assert_can_add_navigation_task would actually
    allow them to create.
    """

    def setUp(self):
        self.user = get_user_model().objects.create(email="fine-grained-visibility@example.com")
        UserEntitlementGrant.objects.create(
            user=self.user,
            kind=UserEntitlementGrant.KIND_TASK_TYPE_GROUP,
            value="cima:circle",
        )

    def test_can_user_see_task_subtype_respects_fine_grained_grant(self):
        self.assertTrue(can_user_see_task_subtype(self.user, task_subtype=CIRCLE))
        self.assertFalse(can_user_see_task_subtype(self.user, task_subtype=TURNPOINT_HUNT))

    def test_can_user_see_cima_task_types_is_still_true_for_a_fine_only_grant(self):
        # The coarse "does this user have any CIMA access at all" signal
        # (used to decide whether to show the CIMA section header at all)
        # must remain True for a fine-only grant.
        self.assertTrue(can_user_see_cima_task_types(self.user))

    def test_task_template_choices_include_only_the_granted_subtype(self):
        choices = dict(_task_template_choices(self.user))
        cima_keys = [key for key, _label in choices.get("CIMA", [])]
        self.assertIn(CIRCLE, cima_keys)
        self.assertNotIn(TURNPOINT_HUNT, cima_keys)

    def test_navigation_task_form_subtype_choices_include_only_the_granted_subtype(self):
        form = NavigationTaskForm(task_family=PRECISION, user=self.user)
        subtype_values = []
        for _group_label, group_choices in form.fields["task_subtype"].choices:
            if isinstance(group_choices, (list, tuple)):
                subtype_values.extend(key for key, _label in group_choices)
        self.assertIn(CIRCLE, subtype_values)
        self.assertNotIn(TURNPOINT_HUNT, subtype_values)

    def test_user_without_any_grant_sees_no_cima_subtypes(self):
        plain_user = get_user_model().objects.create(email="no-grant-visibility@example.com")
        choices = dict(_task_template_choices(plain_user))
        self.assertNotIn("CIMA", choices)

        form = NavigationTaskForm(task_family=PRECISION, user=plain_user)
        subtype_values = []
        for _group_label, group_choices in form.fields["task_subtype"].choices:
            if isinstance(group_choices, (list, tuple)):
                subtype_values.extend(key for key, _label in group_choices)
        self.assertNotIn(CIRCLE, subtype_values)
        self.assertNotIn(TURNPOINT_HUNT, subtype_values)

    def test_coarse_cima_grant_still_shows_every_subtype(self):
        coarse_user = get_user_model().objects.create(email="coarse-grant-visibility@example.com")
        UserEntitlementGrant.objects.create(
            user=coarse_user,
            kind=UserEntitlementGrant.KIND_TASK_TYPE_GROUP,
            value="cima",
        )
        self.assertTrue(can_user_see_task_subtype(coarse_user, task_subtype=CIRCLE))
        self.assertTrue(can_user_see_task_subtype(coarse_user, task_subtype=TURNPOINT_HUNT))

        choices = dict(_task_template_choices(coarse_user))
        cima_keys = [key for key, _label in choices.get("CIMA", [])]
        self.assertIn(CIRCLE, cima_keys)
        self.assertIn(TURNPOINT_HUNT, cima_keys)
