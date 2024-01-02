import os
from typing import Optional

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.files.storage import FileSystemStorage
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from formtools.wizard.views import SessionWizardView
from guardian.mixins import PermissionRequiredMixin as GuardianPermissionRequiredMixin
from django import forms
from guardian.shortcuts import get_objects_for_user

from display.forms import NavigationTaskForm, ContestForm, TrackingDataForm, PersonForm
from display.forms_wizards import (
    TaskTypeForm,
    ANRCorridorImportRouteForm,
    AirsportsImportRouteForm,
    PrecisionImportRouteForm,
    LandingImportRouteForm,
    ContestSelectForm,
    ANRCorridorParametersForm,
    AirsportsParametersForm,
    Member1SearchForm,
    Member2SearchForm,
    AeroplaneSearchForm,
    ClubSearchForm,
)
from display.models import (
    Contest,
    Scorecard,
    Route,
    EditableRoute,
    NavigationTask,
    Team,
    Person,
    Crew,
    Aeroplane,
    Club,
    ContestTeam,
)
from display.utilities.navigation_task_type_definitions import (
    PRECISION,
    POKER,
    ANR_CORRIDOR,
    AIRSPORTS,
    AIRSPORT_CHALLENGE,
    LANDING,
)
from live_tracking_map import settings


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
        # prepare the kwargs for the form instance.
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
            # If the form is based on ModelForm or InlineFormSet,
            # add instance if available and not previously set.
            kwargs.setdefault("instance", self.get_form_instance(step))
        elif issubclass(form_class, forms.models.BaseModelFormSet):
            # If the form is based on ModelFormSet, add queryset if available
            # and not previous set.
            kwargs.setdefault("queryset", self.get_form_instance(step))
        return form_class(**kwargs)


class NewNavigationTaskWizard(GuardianPermissionRequiredMixin, SessionWizardOverrideView):
    """
    Implements the wizard view for creating a new navigation task. Guides the user through selecting task type, route
    type, and entering the navigation task details.
    """

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
        """
        If the final rendering fails, render the failed form with failure information.
        """
        try:
            return super().render_done(form, **kwargs)
        except ValidationError as e:
            from django.contrib import messages

            messages.error(self.request, str(e))
            return self.render_revalidation_failure("task_type", self.get_form_instance("task_type"), **kwargs)

    def create_route(self, scorecard: Scorecard) -> tuple[Route, Optional[EditableRoute]]:
        """
        Helper function to create the Route instance.
        """
        task_type = self.get_cleaned_data_for_step("task_type")["task_type"]
        editable_route = None
        route = None
        if task_type in (PRECISION, POKER):
            initial_step_data = self.get_cleaned_data_for_step("precision_route_import")
            use_procedure_turns = self.get_cleaned_data_for_step("task_content")[
                "original_scorecard"
            ].use_procedure_turns
            route = initial_step_data["internal_route"].create_precision_route(use_procedure_turns, scorecard)
            editable_route = initial_step_data["internal_route"]
        elif task_type == ANR_CORRIDOR:
            initial_step_data = self.get_cleaned_data_for_step("anr_route_import")
            rounded_corners = initial_step_data["rounded_corners"]
            corridor_width = initial_step_data["corridor_width"]
            route = initial_step_data["internal_route"].create_anr_route(rounded_corners, corridor_width, scorecard)
            editable_route = initial_step_data["internal_route"]
        elif task_type in (AIRSPORTS, AIRSPORT_CHALLENGE):
            initial_step_data = self.get_cleaned_data_for_step("airsports_route_import")
            rounded_corners = initial_step_data["rounded_corners"]
            route = initial_step_data["internal_route"].create_airsports_route(rounded_corners, scorecard)
            editable_route = initial_step_data["internal_route"]
        elif task_type == LANDING:
            initial_step_data = self.get_cleaned_data_for_step("landing_route_import")
            route = initial_step_data["internal_route"].create_landing_route()
            editable_route = initial_step_data["internal_route"]
        # Check for gate polygons that do not match a turning point
        route.validate_gate_polygons()
        return route, editable_route

    def done(self, form_list, **kwargs):
        """
        The final step of the wizard. Create the Route and navigation task and redirect to the navigation task detail
        view.
        """
        scorecard = self.get_cleaned_data_for_step("task_content")["original_scorecard"]
        route, ediable_route = self.create_route(scorecard)
        final_data = self.get_cleaned_data_for_step("task_content")
        navigation_task = NavigationTask.create(
            **final_data,
            contest=self.contest,
            route=route,
            editable_route=ediable_route,
        )
        return HttpResponseRedirect(reverse("navigationtask_detail", kwargs={"pk": navigation_task.pk}))

    def get_context_data(self, form, **kwargs):
        """
        Gets the context for the different steps.
        """
        context = super().get_context_data(form=form, **kwargs)
        if self.steps.current == "task_content":
            # The task content step needs the list of original scorecards
            useful_cards = []
            for scorecard in Scorecard.get_originals():
                if self.get_cleaned_data_for_step("task_type")["task_type"] in scorecard.task_type:
                    useful_cards.append(scorecard.pk)
            form.fields["original_scorecard"].queryset = Scorecard.get_originals().filter(pk__in=useful_cards)
            form.fields["original_scorecard"].initial = Scorecard.get_originals().filter(pk__in=useful_cards).first()
        return context

    def get_form(self, step=None, data=None, files=None):
        """
        Override form fields for different steps.
        """
        form = super().get_form(step, data, files)
        if "internal_route" in form.fields:
            # If the form references an internal_route, get the editable routes that are available to the user.
            form.fields["internal_route"].queryset = EditableRoute.get_for_user(self.request.user)
        return form

    def get_form_initial(self, step):
        """
        Provide initial values to the forms for different steps.
        """
        if step == "task_content":
            return {
                "score_sorting_direction": self.contest.summary_score_sorting_direction,
            }
        return {}


def contest_not_chosen(wizard) -> bool:
    """
    Returns true if we need to render the contest selection step
    """
    return (wizard.get_cleaned_data_for_step("contest_selection") or {}).get("contest") is None


def anr_task_type(wizard) -> bool:
    return (wizard.get_cleaned_data_for_step("contest_selection") or {}).get("task_type") == ANR_CORRIDOR


def airsports_task_type(wizard) -> bool:
    return (wizard.get_cleaned_data_for_step("contest_selection") or {}).get("task_type") in (
        AIRSPORTS,
        AIRSPORT_CHALLENGE,
    )


class RouteToTaskWizard(GuardianPermissionRequiredMixin, SessionWizardOverrideView):
    """
    Implements a wizard to create a navigation task directly from an editable route. It is a more lightweight method of
    creating navigation tasks than using the navigation task wizard and users a lot of suitable default values instead
    of the full control that is allowed through the navigation task Wizard.
    """

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
            )
        return context

    # def get_form(self, step=None, data=None, files=None):
    #     form = super().get_form(step, data, files)

    def create_route(self, scorecard: Scorecard) -> Route:
        task_type = self.get_cleaned_data_for_step("contest_selection")["task_type"]
        rounded_corners = False
        corridor_width = 0
        if task_type == ANR_CORRIDOR:
            initial_step_data = self.get_cleaned_data_for_step("anr_parameters")
            rounded_corners = initial_step_data["rounded_corners"]
            corridor_width = initial_step_data["corridor_width"]
        elif task_type in (AIRSPORTS, AIRSPORT_CHALLENGE):
            initial_step_data = self.get_cleaned_data_for_step("airsports_parameters")
            rounded_corners = initial_step_data["rounded_corners"]
        return self.editable_route.create_route(task_type, scorecard, rounded_corners, corridor_width)

    def done(self, form_list, **kwargs):
        """
        The wizard is complete, so create the route and navigation task. Redirects to the navigation task detail page.
        """
        task_type = self.get_cleaned_data_for_step("contest_selection")["task_type"]
        task_name = self.get_cleaned_data_for_step("contest_selection")["navigation_task_name"]
        if self.get_cleaned_data_for_step("contest_selection")["contest"] is None:
            contest = Contest.objects.create(**self.get_cleaned_data_for_step("contest_creation"))
            contest.initialise(self.request.user)
        else:
            contest = self.get_cleaned_data_for_step("contest_selection")["contest"]
        scorecards = [item for item in Scorecard.get_originals() if task_type in item.task_type]
        try:
            scorecard = scorecards[0]
            route = self.create_route(scorecard)
            navigation_task = NavigationTask.create(
                name=task_name,
                contest=contest,
                route=route,
                editable_route=self.editable_route,
                original_scorecard=scorecard,
                start_time=contest.start_time,
                finish_time=contest.finish_time,
                allow_self_management=True,
                score_sorting_direction=contest.summary_score_sorting_direction,
            )
            return HttpResponseRedirect(reverse("navigationtask_detail", kwargs={"pk": navigation_task.pk}))
        except IndexError:
            messages.error(
                self.request,
                f"Unable to find original scorecard for task type {task_type}. Please notify support@airsports.no.",
            )
            return redirect("editableroute_list")
        except ValidationError as e:
            messages.error(self.request, str(e))
            return redirect("editableroute_list")


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

    def render_done(self, form, **kwargs):
        """
        This method gets called when all forms passed. The method should also
        re-validate all steps to prevent manipulation. If any form fails to
        validate, `render_revalidation_failure` should get called.
        If everything is fine call `done`.
        """
        try:
            return super().render_done(form, **kwargs)
        except ValidationError as e:
            from django.contrib import messages

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
        """
        The final step of the Wizard. Extract the selected persons, aircraft, and club, and create a new team if an
        existing team for this configuration does not exist. Together with the tracking information, register the team
        with the contest.
        """
        form_dict = kwargs["form_dict"]
        team_pk = self.kwargs.get("team_pk")
        contest_pk = self.kwargs.get("contest_pk")
        # Must be retrieved before we delete the existing relationship
        tracking_data = self.get_cleaned_data_for_step("tracking")
        contest = get_object_or_404(Contest, pk=contest_pk)
        original_team = None
        if team_pk:
            original_team = get_object_or_404(Team, pk=team_pk)
        # Check if member one has been created
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
        aeroplane_data = self.get_cleaned_data_for_step("aeroplane")
        aeroplane_data.pop("picture_display_field")
        aeroplane, _ = Aeroplane.objects.get_or_create(
            registration=aeroplane_data.get("registration"), defaults=aeroplane_data
        )
        if aeroplane_data["picture"] is not None:
            aeroplane.picture = aeroplane_data["picture"]
        aeroplane.colour = aeroplane_data["colour"]
        aeroplane.type = aeroplane_data["type"]
        aeroplane.save()
        club_data = self.get_cleaned_data_for_step("club")
        club_data.pop("logo_display_field")
        club_data.pop("country_flag_display_field")
        club, _ = Club.objects.get_or_create(name=club_data.get("name"), defaults=club_data)
        if club_data["logo"] is not None:
            club.logo = club_data["logo"]
        club.country = club_data["country"]
        club.save()
        team, created_team = Team.objects.get_or_create(crew=crew, aeroplane=aeroplane, club=club)
        contest.replace_team(original_team, team, tracking_data)
        return HttpResponseRedirect(reverse("contest_team_list", kwargs={"contest_pk": contest_pk}))

    def get_form_prefix(self, step=None, form=None):
        return ""

    def get_template_names(self):
        return [self.templates[self.steps.current]]

    # def render_revalidation_failure(self, step, form, **kwargs):
    #     print("Revalidation failure {} {}".format(step, form))

    def get_form_instance(self, step):
        team_pk = self.kwargs.get("team_pk")
        if team_pk:
            team = get_object_or_404(Team, pk=team_pk)
        else:
            team = None

        contest_pk = self.kwargs.get("contest_pk")
        if contest_pk:
            contest = get_object_or_404(Contest, pk=contest_pk)
        else:
            contest = None
        if team and contest:
            if step == "tracking":
                return ContestTeam.objects.get(team=team, contest=contest)

    def get_form_initial(self, step):
        team_pk = self.kwargs.get("team_pk")
        if team_pk:
            team = get_object_or_404(Team, pk=team_pk)
        else:
            team = None
        if step == "member1create":
            member_data = self.get_cleaned_data_for_step("member1search")
            return {
                "first_name": member_data["first_name"],
                "last_name": member_data["last_name"],
                "phone": member_data["phone"],
                "email": member_data["email"],
            }
        if step == "member2create":
            member_data = self.get_cleaned_data_for_step("member2search")
            return {
                "first_name": member_data["first_name"],
                "last_name": member_data["last_name"],
                "phone": member_data["phone"],
                "email": member_data["email"],
            }
        if team:
            if step == "member1search":
                return {
                    "person_id": team.crew.member1.pk
                    # "first_name": team.crew.member1.first_name,
                    # "last_name": team.crew.member1.last_name,
                    # "phone": team.crew.member1.phone,
                    # "email": team.crew.member1.email
                }
            if step == "member2search" and team.crew.member2:
                return {
                    "person_id": team.crew.member2.pk
                    # "first_name": team.crew.member1.first_name,
                    # "last_name": team.crew.member1.last_name,
                    # "phone": team.crew.member1.phone,
                    # "email": team.crew.member1.email
                }
            if step == "aeroplane" and team.aeroplane:
                return {"registration": team.aeroplane.registration}
            if step == "club" and team.club:
                return {"name": team.club.name}
        return {}
