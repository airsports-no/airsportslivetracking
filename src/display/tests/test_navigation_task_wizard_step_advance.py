import datetime

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from guardian.shortcuts import assign_perm

from display.default_scorecards.create_scorecards import create_scorecards
from display.models import Contest


class TestNavigationTaskWizardStepAdvance(TestCase):
    """
    Regression test for Sentry issue PYTHON-DJANGO-N: AttributeError: 'NewNavigationTaskWizard'
    object has no attribute '_resolved_form_list', surfaced as a 500 from formtools' own post()
    (`del self._resolved_form_list`) whenever a step form validated successfully.

    Root cause: SessionWizardOverrideView.get_form() bypasses get_form_list() - a long-standing
    "hack to avoid recursion error with conditional steps" that's been redundant since at least
    django-formtools 2.5.1 (its own get_form_list() already guards against that recursion via
    _check_cond_started). Because of that bypass, get_form_list() was never called during a
    request, so it never populated _resolved_form_list/_cache_signature - a per-request cache
    django-formtools >=2.6 added, whose own post() unconditionally deletes both after a valid
    form. Fixed via a new SessionWizardOverrideView.post() override that calls get_form_list()
    once, unconditionally, before delegating to super().post().
    """

    def setUp(self):
        create_scorecards()
        self.user = get_user_model().objects.create(email="wizard-step-advance@example.com")
        self.user.user_permissions.add(Permission.objects.get(codename="change_contest"))
        self.contest = Contest.objects.create(
            name="Wizard Step Advance Contest",
            time_zone="Europe/Oslo",
            start_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 8, 1, 17, 0, tzinfo=datetime.timezone.utc),
            location="60.0,11.0",
            created_by=self.user,
        )
        assign_perm("change_contest", self.user, self.contest)
        self.client.force_login(self.user)

    def test_submitting_first_step_advances_without_500(self):
        url = reverse("navigationtaskwizard", kwargs={"contest_pk": self.contest.pk})
        # GET first to initialise the wizard's session storage, matching how a real browser
        # session starts the wizard before ever POSTing a step.
        self.client.get(url)

        response = self.client.post(
            url,
            data={
                "new_navigation_task_wizard-current_step": "task_type",
                "task_type-task_template": "precision",
            },
        )

        self.assertNotEqual(response.status_code, 500)
        self.assertIn(response.status_code, (200, 302))
