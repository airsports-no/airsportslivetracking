import os

from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.files.storage import FileSystemStorage
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse
from formtools.wizard.views import SessionWizardView
from guardian.mixins import PermissionRequiredMixin as GuardianPermissionRequiredMixin

from display.forms import PersonForm, TrackingDataForm
from display.forms_wizards import AeroplaneSearchForm, ClubSearchForm, Member1SearchForm, Member2SearchForm
from display.models import Aeroplane, Club, Contest, Crew, Person, Team
from live_tracking_map import settings


class SessionWizardOverrideView(SessionWizardView):
    def post(self, *args, **kwargs):
        # django-formtools >=2.6 added a per-request cache (_resolved_form_list/
        # _cache_signature) that get_form_list() populates on first call, and its own
        # post() unconditionally deletes both after a valid form - see get_form_list()'s
        # docstring. get_form() below builds forms directly without ever calling
        # get_form_list(), so on any request that only goes through this override, formtools'
        # del raised AttributeError
        # (Sentry PYTHON-DJANGO-N). Call get_form_list() once here, unconditionally, before
        # any of those bypasses run, so the cache is always primed regardless of which
        # get_form() branch this request's step actually uses. Safe against recursion: a
        # condition_dict callable that calls back into get_form_list() (e.g. via
        # get_cleaned_data_for_step -> get_form() -> get_form_list()) is caught by
        # formtools' own _check_cond_started guard.
        self.get_form_list()
        return super().post(*args, **kwargs)

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
