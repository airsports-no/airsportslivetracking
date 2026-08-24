import os
from typing import Optional

from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.files.storage import FileSystemStorage
from django.db import transaction
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from formtools.wizard.views import SessionWizardView
from guardian.mixins import PermissionRequiredMixin as GuardianPermissionRequiredMixin
from guardian.shortcuts import get_objects_for_user
from rest_framework.exceptions import ValidationError as DRFValidationError

from display.forms import ContestForm, NavigationTaskForm, PersonForm, TrackingDataForm
from display.forms_wizards import (
    AeroplaneSearchForm,
    AirsportsImportRouteForm,
    AirsportsParametersForm,
    ANRCorridorImportRouteForm,
    ANRCorridorParametersForm,
    ClubSearchForm,
    ContestSelectForm,
    LandingImportRouteForm,
    Member1SearchForm,
    Member2SearchForm,
    PrecisionImportRouteForm,
    TaskTypeForm,
    _task_template_choices,
)
from display.models import (
    Aeroplane,
    Club,
    Contest,
    ContestTeam,
    Crew,
    EditableRoute,
    NavigationTask,
    Person,
    Route,
    Scorecard,
    Team,
    UserTokenGrant,
)
from display.services.capacity_enforcement import assert_can_add_navigation_task
from display.services.route_compatibility import extract_route_primitives, get_blocking_reasons
from display.services.task_type_visibility import can_user_see_cima_task_types
from display.services.token_assignment import assign_token_to_contest
from display.templatetags.frontend_urls import fe_url
from display.utilities.cima_task_type_definitions import (
    LEGACY_DEFAULT_SUBTYPE_BY_FAMILY,
    NO_BACKBONE_TASK_SUBTYPES,
    get_task_subtype_definition,
)
from display.utilities.navigation_task_type_definitions import (
    AIRSPORT_CHALLENGE,
    AIRSPORTS,
    ANR_CORRIDOR,
    LANDING,
    POKER,
    PRECISION,
)
from live_tracking_map import settings


def _effective_subtype_key(task_type: str, task_subtype: str | None) -> str:
    """The task subtype key the compatibility ruleset should be checked against: the explicit
    CIMA subtype if one was chosen, otherwise the legacy shim for the coarse task_type family."""
    return task_subtype or LEGACY_DEFAULT_SUBTYPE_BY_FAMILY.get(task_type, task_type)


def _no_compatible_routes_message(subtype_key: str) -> str:
    """
    Explain why the internal_route picker is empty for the already-chosen task type, instead of
    just rendering an empty dropdown with no explanation.
    """
    definition = get_task_subtype_definition(subtype_key)
    parts = []
    if definition.required_primitives:
        parts.append("requires: " + ", ".join(definition.required_primitives))
    if definition.forbidden_primitives:
        parts.append("must not have: " + ", ".join(definition.forbidden_primitives))
    requirement_text = "; ".join(parts) if parts else "no specific route features"
    return (
        "None of the routes you can edit currently support this task type "
        f"(it {requirement_text}). Edit an existing route to add what's missing, or create a new one."
    )


def _assert_route_compatible_with_task_type(editable_route: EditableRoute, task_type: str, task_subtype: str | None):
    """
    Defense in depth: re-check compatibility server-side before building a Route, so a
    hand-crafted POST cannot bypass the filtered task_template/internal_route choices.
    """
    subtype_key = _effective_subtype_key(task_type, task_subtype)
    reasons = get_blocking_reasons(extract_route_primitives(editable_route), subtype_key)
    if reasons:
        raise ValidationError(
            f"Route '{editable_route.name}' is not compatible with the selected task type: " + "; ".join(reasons)
        )


def show_precision_path(wizard) -> bool:
    """
    Returns true if the selected task type requires precision task input.
    """
    return (wizard.get_cleaned_data_for_step("task_type") or {}).get("task_type") in (
        PRECISION,
        POKER,
    )


def show_anr_path(wizard) -> bool:
    """
    Returns true if the selected task type requires ANR task input
    """
    return (wizard.get_cleaned_data_for_step("task_type") or {}).get("task_type") in (ANR_CORRIDOR,)


def show_airsports_path(wizard) -> bool:
    """
    Returns true if the selected task type requires airsports task input
    """
    return (wizard.get_cleaned_data_for_step("task_type") or {}).get("task_type") in (
        AIRSPORTS,
        AIRSPORT_CHALLENGE,
    )


def show_landing_path(wizard) -> bool:
    """
    Returns true if the selected task type requires landing task input
    """
    return (wizard.get_cleaned_data_for_step("task_type") or {}).get("task_type") in (LANDING,)


class SessionWizardOverrideView(SessionWizardView):
    # Hack to avoid get_form_list() which leads to recursion error with conditional steps.
    def get_form(self, step=None, data=None, files=None):
        """
        Constructs the form for a given `step`. If no `step` is defined, the
        current step will be determined automatically.

        The form will be initialized using the `data` argument to prefill the
        new form. If needed, instance or queryset (for `ModelForm` or
        `ModelFormSet`) will be added too.
        """
        if step is None:
            step = self.steps.current
        form_class = self.form_list[step]
        kwargs = self.get_form_kwargs(step)
        kwargs.update(
            {
                "data": data,
                "files": files,
                "prefix": self.get_form_prefix(step, form_class),
                "initial": self.get_form_initial(step),
            }
        )
        if issubclass(form_class, (forms.ModelForm, forms.models.BaseInlineFormSet)):
            kwargs.setdefault("instance", self.get_form_instance(step))
        elif issubclass(form_class, forms.models.BaseModelFormSet):
            kwargs.setdefault("queryset", self.get_form_instance(step))
        return form_class(**kwargs)


class NewNavigationTaskWizard(GuardianPermissionRequiredMixin, SessionWizardOverrideView):
    permission_required = ("display.change_contest",)

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.contest = get_object_or_404(Contest, pk=self.kwargs.get("contest_pk"))
        timezone.activate(self.contest.time_zone)

    def get_permission_object(self):
        return self.contest

    form_list = [
        ("task_type", TaskTypeForm),
        ("anr_route_import", ANRCorridorImportRouteForm),
        ("airsports_route_import", AirsportsImportRouteForm),
        ("precision_route_import", PrecisionImportRouteForm),
        ("landing_route_import", LandingImportRouteForm),
        ("task_content", NavigationTaskForm),
    ]
    file_storage = FileSystemStorage(location=os.path.join(settings.TEMPORARY_FOLDER, "importedroutes"))
    condition_dict = {
        "anr_route_import": show_anr_path,
        "airsports_route_import": show_airsports_path,
        "precision_route_import": show_precision_path,
        "landing_route_import": show_landing_path,
    }
    templates = {
        "task_type": "display/navigationtaskwizardform.html",
        "anr_route_import": "display/navigationtaskwizardform.html",
        "airsports_route_import": "display/navigationtaskwizardform.html",
        "landing_route_import": "display/navigationtaskwizardform.html",
        "precision_route_import": "display/navigationtaskwizardform.html",
        "task_content": "display/navigationtaskwizardform.html",
    }

    def get_template_names(self):
        return [self.templates[self.steps.current]]

    def render_done(self, form, **kwargs):
        try:
            return super().render_done(form, **kwargs)
        except ValidationError as e:
            messages.error(self.request, str(e))
            return self.render_revalidation_failure("task_type", self.get_form_instance("task_type"), **kwargs)

    def create_route(self, scorecard: Scorecard) -> tuple[Route, Optional[EditableRoute]]:
        task_step = self.get_cleaned_data_for_step("task_type") or {}
        task_type = task_step["task_type"]
        task_subtype = task_step.get("task_subtype")
        editable_route = None
        route = None
        if task_type in (PRECISION, POKER):
            initial_step_data = self.get_cleaned_data_for_step("precision_route_import")
            internal_route = initial_step_data["internal_route"]
            _assert_route_compatible_with_task_type(internal_route, task_type, task_subtype)
            if task_subtype in NO_BACKBONE_TASK_SUBTYPES:
                route = Route.objects.create(
                    name=internal_route.name,
                    waypoints=[],
                    takeoff_gates=[],
                    landing_gates=[],
                    use_procedure_turns=False,
                )
                internal_route.amend_route_with_additional_features(route)
            else:
                use_procedure_turns = self.get_cleaned_data_for_step("task_content")[
                    "original_scorecard"
                ].use_procedure_turns
                route = internal_route.create_precision_route(use_procedure_turns, scorecard)
            editable_route = internal_route
        elif task_type == ANR_CORRIDOR:
            initial_step_data = self.get_cleaned_data_for_step("anr_route_import")
            internal_route = initial_step_data["internal_route"]
            _assert_route_compatible_with_task_type(internal_route, task_type, task_subtype)
            rounded_corners = initial_step_data["rounded_corners"]
            corridor_width = initial_step_data["corridor_width"]
            route = internal_route.create_anr_route(rounded_corners, corridor_width, scorecard)
            editable_route = internal_route
        elif task_type in (AIRSPORTS, AIRSPORT_CHALLENGE):
            initial_step_data = self.get_cleaned_data_for_step("airsports_route_import")
            internal_route = initial_step_data["internal_route"]
            _assert_route_compatible_with_task_type(internal_route, task_type, task_subtype)
            rounded_corners = initial_step_data["rounded_corners"]
            route = internal_route.create_airsports_route(rounded_corners, scorecard)
            editable_route = internal_route
        elif task_type == LANDING:
            initial_step_data = self.get_cleaned_data_for_step("landing_route_import")
            internal_route = initial_step_data["internal_route"]
            _assert_route_compatible_with_task_type(internal_route, task_type, task_subtype)
            route = internal_route.create_landing_route()
            editable_route = internal_route
        return route, editable_route

    def done(self, form_list, **kwargs):
        scorecard = self.get_cleaned_data_for_step("task_content")["original_scorecard"]
        task_step = self.get_cleaned_data_for_step("task_type") or {}
        task_type = task_step["task_type"]
        task_subtype = task_step.get("task_subtype")
        route, ediable_route = self.create_route(scorecard)

        if ediable_route:
            corridor_width = None
            if task_type == ANR_CORRIDOR:
                corridor_width = self.get_cleaned_data_for_step("anr_route_import")["corridor_width"]

            for warning in ediable_route.get_validation_errors(corridor_width=corridor_width):
                messages.warning(self.request, warning)

        try:
            assert_can_add_navigation_task(
                self.contest, task_type=task_type, task_subtype=task_subtype, user=self.request.user
            )
        except DRFValidationError as exc:
            # render_done() below only catches Django's ValidationError, matching
            # this wizard's existing error-handling pattern.
            raise ValidationError(str(exc))

        final_data = self.get_cleaned_data_for_step("task_content")
        navigation_task = NavigationTask.create(
            **final_data,
            contest=self.contest,
            route=route,
            editable_route=ediable_route,
        )
        return HttpResponseRedirect(reverse("navigationtask_detail", kwargs={"pk": navigation_task.pk}))

    def get_context_data(self, form, **kwargs):
        context = super().get_context_data(form=form, **kwargs)
        if self.steps.current == "task_content":
            useful_cards = []
            for scorecard in Scorecard.get_originals():
                if self.get_cleaned_data_for_step("task_type")["task_type"] in scorecard.task_type:
                    useful_cards.append(scorecard.pk)
            form.fields["original_scorecard"].queryset = Scorecard.get_originals().filter(pk__in=useful_cards)
            form.fields["original_scorecard"].initial = Scorecard.get_originals().filter(pk__in=useful_cards).first()
        return context

    def get_form(self, step=None, data=None, files=None):
        current_step = step or self.steps.current
        form = super().get_form(step, data, files)
        if current_step == "task_type":
            form.fields["task_template"].choices = _task_template_choices(self.request.user)
            form.visible_cima = can_user_see_cima_task_types(self.request.user)
        if current_step == "task_content":
            selected = self.get_cleaned_data_for_step("task_type") or {}
            form = self.form_list[current_step](
                data=data,
                files=files,
                prefix=self.get_form_prefix(current_step, self.form_list[current_step]),
                initial=self.get_form_initial(current_step),
                task_family=selected.get("task_type"),
                user=self.request.user,
            )
        if "internal_route" in form.fields:
            queryset = EditableRoute.get_for_user(self.request.user)
            task_step = self.get_cleaned_data_for_step("task_type") or {}
            if task_step.get("task_type"):
                subtype_key = _effective_subtype_key(task_step["task_type"], task_step.get("task_subtype"))
                # Hard filter, matching RouteToTaskWizard: since the task type is already chosen
                # at this point, only offer routes whose authored content actually supports it.
                queryset = queryset.filter(compatible_task_types__contains=[subtype_key])
                if not queryset.exists():
                    form.fields["internal_route"].help_text = _no_compatible_routes_message(subtype_key)
            form.fields["internal_route"].queryset = queryset
        return form

    def get_form_initial(self, step):
        initial = super().get_form_initial(step)
        if step == "task_content":
            task_step = self.get_cleaned_data_for_step("task_type") or {}
            if task_step.get("task_subtype"):
                initial.update({"task_subtype": task_step["task_subtype"]})
        return initial


def contest_not_chosen(wizard) -> bool:
    return (wizard.get_cleaned_data_for_step("contest_selection") or {}).get("contest") is None


def anr_task_type(wizard) -> bool:
    return (wizard.get_cleaned_data_for_step("contest_selection") or {}).get("task_type") == ANR_CORRIDOR


def airsports_task_type(wizard) -> bool:
    return (wizard.get_cleaned_data_for_step("contest_selection") or {}).get("task_type") in (
        AIRSPORTS,
        AIRSPORT_CHALLENGE,
    )


class RouteToTaskWizard(GuardianPermissionRequiredMixin, SessionWizardOverrideView):
    permission_required = ("display.change_editableroute",)
    file_storage = FileSystemStorage(location=os.path.join(settings.TEMPORARY_FOLDER, "unneeded"))

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.editable_route = get_object_or_404(EditableRoute, pk=self.kwargs.get("pk"))

    def get_permission_object(self):
        return self.editable_route

    form_list = [
        ("contest_selection", ContestSelectForm),
        ("anr_parameters", ANRCorridorParametersForm),
        ("airsports_parameters", AirsportsParametersForm),
        ("contest_creation", ContestForm),
        ("task_content", NavigationTaskForm),
    ]

    condition_dict = {
        "contest_creation": contest_not_chosen,
        "anr_parameters": anr_task_type,
        "airsports_parameters": airsports_task_type,
    }
    templates = {
        "contest_selection": "display/navigationtaskwizardform.html",
        "anr_parameters": "display/navigationtaskwizardform.html",
        "airsports_parameters": "display/navigationtaskwizardform.html",
        "contest_creation": "display/navigationtaskwizardform.html",
        "task_content": "display/navigationtaskwizardform.html",
    }

    def get_template_names(self):
        return [self.templates[self.steps.current]]

    def get_context_data(self, form, **kwargs):
        context = super().get_context_data(form=form, **kwargs)
        if self.steps.current == "contest_selection":
            form.fields["contest"].queryset = get_objects_for_user(
                self.request.user,
                "display.change_contest",
                accept_global_perms=False,
            ).order_by("name")
        if self.steps.current == "task_content":
            selected = self.get_cleaned_data_for_step("contest_selection") or {}
            useful_cards = []
            for scorecard in Scorecard.get_originals():
                if selected.get("task_type") in scorecard.task_type:
                    useful_cards.append(scorecard.pk)
            form.fields["original_scorecard"].queryset = Scorecard.get_originals().filter(pk__in=useful_cards)
            form.fields["original_scorecard"].initial = Scorecard.get_originals().filter(pk__in=useful_cards).first()
        return context

    def get_form(self, step=None, data=None, files=None):
        current_step = step or self.steps.current
        if current_step == "task_content":
            selected = self.get_cleaned_data_for_step("contest_selection") or {}
            return NavigationTaskForm(
                data=data,
                files=files,
                prefix=self.get_form_prefix(current_step, NavigationTaskForm),
                initial=self.get_form_initial(current_step),
                task_family=selected.get("task_type"),
                user=self.request.user,
            )
        if current_step == "contest_selection":
            form = ContestSelectForm(
                data=data,
                files=files,
                prefix=self.get_form_prefix(current_step, ContestSelectForm),
                initial=self.get_form_initial(current_step),
                user=self.request.user,
                editable_route=self.editable_route,
            )
            form.visible_cima = can_user_see_cima_task_types(self.request.user)
            return form
        form = super().get_form(step, data, files)
        if current_step == "contest_creation" and "initial_token_grant" in form.fields:
            form.fields["initial_token_grant"].queryset = UserTokenGrant.objects.filter(
                user=self.request.user
            ).select_related("token_type")
        return form

    def create_route(self, scorecard: Scorecard) -> Route:
        selected_task = self.get_cleaned_data_for_step("contest_selection")
        task_type = selected_task["task_type"]
        task_subtype = selected_task.get("task_subtype")
        _assert_route_compatible_with_task_type(self.editable_route, task_type, task_subtype)
        rounded_corners = False
        corridor_width = 0
        if task_type == ANR_CORRIDOR:
            initial_step_data = self.get_cleaned_data_for_step("anr_parameters")
            rounded_corners = initial_step_data["rounded_corners"]
            corridor_width = initial_step_data["corridor_width"]
        elif task_type in (AIRSPORTS, AIRSPORT_CHALLENGE):
            initial_step_data = self.get_cleaned_data_for_step("airsports_parameters")
            rounded_corners = initial_step_data["rounded_corners"]
        return self.editable_route.create_route(
            task_type, scorecard, rounded_corners, corridor_width, task_subtype=task_subtype
        )

    @transaction.atomic
    def done(self, form_list, **kwargs):
        selected_task = self.get_cleaned_data_for_step("contest_selection")
        task_type = selected_task["task_type"]
        task_name = selected_task["navigation_task_name"]
        if selected_task["contest"] is None:
            contest_data = dict(self.get_cleaned_data_for_step("contest_creation"))
            initial_token_grant = contest_data.pop("initial_token_grant", None)
            contest = Contest.objects.create(**contest_data)
            contest.initialise(self.request.user)
            if initial_token_grant is not None:
                assign_token_to_contest(contest, self.request.user, initial_token_grant.id)
        else:
            contest = selected_task["contest"]
        try:
            final_data = dict(self.get_cleaned_data_for_step("task_content") or {})
            task_name = final_data.pop("name", task_name)
            task_start_time = final_data.pop("start_time", contest.start_time)
            task_finish_time = final_data.pop("finish_time", contest.finish_time)
            scorecard = final_data["original_scorecard"]
            route = self.create_route(scorecard)
            if route is None:
                raise ValidationError("Unable to create navigation task route from this editable route and task type.")

            corridor_width = None
            if task_type == ANR_CORRIDOR:
                corridor_width = self.get_cleaned_data_for_step("anr_parameters")["corridor_width"]

            for warning in self.editable_route.get_validation_errors(corridor_width=corridor_width):
                messages.warning(self.request, warning)

            assert_can_add_navigation_task(
                contest, task_type=task_type, task_subtype=final_data.get("task_subtype"), user=self.request.user
            )
            navigation_task = NavigationTask.create(
                **final_data,
                name=task_name,
                contest=contest,
                route=route,
                editable_route=self.editable_route,
                start_time=task_start_time,
                finish_time=task_finish_time,
            )
            return HttpResponseRedirect(reverse("navigationtask_detail", kwargs={"pk": navigation_task.pk}))
        except IndexError:
            messages.error(
                self.request,
                f"Unable to find original scorecard for task type {task_type}. Please notify support@airsports.no.",
            )
            if contest and contest.pk:
                return redirect(reverse("contest_details", kwargs={"pk": contest.pk}))
            return redirect(fe_url("ROUTE_EDITOR_LIST"))
        except (ValidationError, DRFValidationError) as e:
            message = getattr(e, "message", str(e))
            messages.error(self.request, message)
            if contest and contest.pk:
                return redirect(reverse("contest_details", kwargs={"pk": contest.pk}))
            return redirect(fe_url("ROUTE_EDITOR_LIST"))

    def get_form_initial(self, step):
        initial = super().get_form_initial(step)
        if step == "task_content":
            selected = self.get_cleaned_data_for_step("contest_selection") or {}
            contest = selected.get("contest")
            if contest is not None:
                initial.update(
                    {
                        "name": selected.get("navigation_task_name"),
                        "task_subtype": selected.get("task_subtype"),
                        "start_time": contest.start_time,
                        "finish_time": contest.finish_time,
                    }
                )
        return initial


def create_new_pilot(wizard):
    cleaned = wizard.get_post_data_for_step("member1search") or {}
    return cleaned.get("use_existing_pilot") is None


def create_new_copilot(wizard):
    cleaned = wizard.get_post_data_for_step("member2search") or {}
    return cleaned.get("use_existing_copilot") is None and cleaned.get("skip_copilot") is None


class RegisterTeamWizard(GuardianPermissionRequiredMixin, SessionWizardOverrideView):
    """
    Implements a wizard to create a new team and sign it up to the contest. Usually teams are registered by users
    themselves when they sign up to a contest that allows self-management. This is the admin view that can be used to
    build a new team of existing or new persons, aircraft, and clubs. If the combination of persons, aircraft, and
    club match an existing team, this team is reused.
    """

    permission_required = ("display.change_contest",)

    def get_permission_object(self):
        contest = get_object_or_404(Contest, pk=self.kwargs.get("contest_pk"))
        return contest

    condition_dict = {
        "member1create": create_new_pilot,
        "member2create": create_new_copilot,
    }
    file_storage = FileSystemStorage(location=os.path.join(settings.TEMPORARY_FOLDER, "teams"))
    form_list = [
        ("member1search", Member1SearchForm),
        ("member1create", PersonForm),
        ("member2search", Member2SearchForm),
        ("member2create", PersonForm),
        ("aeroplane", AeroplaneSearchForm),
        ("club", ClubSearchForm),
        ("tracking", TrackingDataForm),
    ]
    templates = {
        "member1search": "display/membersearch_form.html",
        "member1create": "display/membercreate_form.html",
        "member2search": "display/membersearch_form.html",
        "member2create": "display/membercreate_form.html",
        "aeroplane": "display/aeroplane_form.html",
        "club": "display/club_form.html",
        "tracking": "display/tracking_form.html",
    }

    def get_template_names(self):
        return [self.templates[self.steps.current]]

    def render_done(self, form, **kwargs):
        try:
            return super().render_done(form, **kwargs)
        except ValidationError as e:
            messages.error(self.request, str(e))
            return self.render_revalidation_failure("tracking", self.get_form_instance("tracking"), **kwargs)

    def post(self, *args, **kwargs):
        if "my_post_data" not in self.request.session:
            self.request.session["my_post_data"] = {}
        self.request.session["my_post_data"][self.steps.current] = self.request.POST
        return super().post(*args, **kwargs)

    def get_post_data_for_step(self, step):
        return self.request.session.get("my_post_data", {}).get(step, {})

    def done(self, form_list, **kwargs):
        form_dict = kwargs["form_dict"]
        team_pk = self.kwargs.get("team_pk")
        contest_pk = self.kwargs.get("contest_pk")
        tracking_data = self.get_cleaned_data_for_step("tracking")
        contest = get_object_or_404(Contest, pk=contest_pk)
        original_team = None
        if team_pk:
            original_team = get_object_or_404(Team, pk=team_pk)
        member_one_search = self.get_post_data_for_step("member1search")
        use_existing1 = member_one_search.get("use_existing_pilot") is not None
        if use_existing1:
            existing_member_one_data = self.get_cleaned_data_for_step("member1search")
            member1 = get_object_or_404(Person, pk=existing_member_one_data["person_id"])
        else:
            member1 = form_dict["member1create"].save()
            member1.validated = True
            member1.save()

        member_two_search = self.get_post_data_for_step("member2search")
        member_two_skip = member_two_search.get("skip_copilot") is not None
        if not member_two_skip:
            use_existing2 = member_two_search.get("use_existing_copilot") is not None
            if use_existing2:
                existing_member_two_data = self.get_cleaned_data_for_step("member2search")
                member2 = Person.objects.get(pk=existing_member_two_data["person_id"])
            else:
                member2 = form_dict["member2create"].save()
                member2.validated = True
                member2.save()
        else:
            member2 = None

        crew, _ = Crew.objects.get_or_create(member1=member1, member2=member2)

        aeroplane_data = dict(self.get_cleaned_data_for_step("aeroplane"))
        aeroplane_data.pop("picture_display_field", None)
        aeroplane, _ = Aeroplane.objects.get_or_create(
            registration=aeroplane_data.get("registration"), defaults=aeroplane_data
        )
        if aeroplane_data.get("picture") is not None:
            aeroplane.picture = aeroplane_data["picture"]
        aeroplane.colour = aeroplane_data["colour"]
        aeroplane.type = aeroplane_data["type"]
        aeroplane.save()

        club_data = dict(self.get_cleaned_data_for_step("club"))
        club_data.pop("logo_display_field", None)
        club_data.pop("country_flag_display_field", None)
        club, _ = Club.objects.get_or_create(name=club_data.get("name"), defaults=club_data)
        if club_data.get("logo") is not None:
            club.logo = club_data["logo"]
        club.country = club_data["country"]
        club.save()

        team, _ = Team.objects.get_or_create(crew=crew, aeroplane=aeroplane, club=club)

        contest.replace_team(original_team, team, tracking_data)

        return HttpResponseRedirect(reverse("contest_details", kwargs={"pk": contest_pk}))
