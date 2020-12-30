import base64
import datetime
import os
from datetime import timedelta
from typing import Optional

import redis_lock
import dateutil
from django.contrib.auth.decorators import permission_required, login_required
from django.contrib.auth.mixins import PermissionRequiredMixin, LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.core.files.storage import FileSystemStorage
from django.db.models import Q
from django.forms import formset_factory
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import render, redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import ListView, DetailView, UpdateView, CreateView, DeleteView
import logging

from formtools.wizard.views import SessionWizardView
from guardian.mixins import PermissionRequiredMixin as GuardianPermissionRequiredMixin
from guardian.shortcuts import get_objects_for_user, assign_perm
from redis import Redis
from rest_framework import status, permissions
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import PermissionDenied, MethodNotAllowed
from rest_framework.generics import RetrieveAPIView, get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, ViewSet

from display.convert_flightcontest_gpx import create_route_from_gpx, create_route_from_csv, load_route_points_from_kml, \
    create_route_from_formset
from display.forms import ImportRouteForm, WaypointForm, NavigationTaskForm, FILE_TYPE_CSV, FILE_TYPE_FLIGHTCONTEST_GPX, \
    FILE_TYPE_KML, ContestantForm, ContestForm, Member1SearchForm, TeamForm, PersonForm, \
    Member2SearchForm, AeroplaneSearchForm, ClubSearchForm, BasicScoreOverrideForm, TURNPOINT, SECRETPOINT, \
    STARTINGPOINT, FINISHPOINT, TrackingDataForm
from display.models import NavigationTask, Route, Contestant, CONTESTANT_CACHE_KEY, Contest, Team, ContestantTrack, \
    Person, Aeroplane, Club, Crew, BasicScoreOverride, ContestTeam, Task, TaskSummary, ContestSummary, TaskTest, \
    TeamTestScore
from display.permissions import ContestPermissions, NavigationTaskContestPermissions, \
    ContestantPublicPermissions, NavigationTaskPublicPermissions, ContestPublicPermissions, \
    ContestantNavigationTaskContestPermissions, RoutePermissions, ContestModificationPermissions
from display.serialisers import ContestantTrackSerialiser, \
    ExternalNavigationTaskNestedTeamSerialiser, \
    ContestSerialiser, NavigationTaskNestedTeamRouteSerialiser, RouteSerialiser, \
    ContestantTrackWithTrackPointsSerialiser, ContestResultsHighLevelSerialiser, \
    TeamResultsSummarySerialiser, ContestResultsDetailsSerialiser, TeamNestedSerialiser, \
    GpxTrackSerialiser, PersonSerialiser, ExternalNavigationTaskTeamIdSerialiser, \
    ContestantNestedTeamSerialiserWithContestantTrack, AeroplaneSerialiser, ClubSerialiser, ContestTeamNestedSerialiser, \
    TaskWithoutReferenceNestedSerialiser, ContestSummaryWithoutReferenceSerialiser
from display.show_slug_choices import ShowChoicesMetadata
from influx_facade import InfluxFacade
from live_tracking_map import settings
from playback_tools import insert_gpx_file

logger = logging.getLogger(__name__)


class SuperuserRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_superuser


def frontend_view_map(request, pk):
    navigation_task = get_object_or_404(NavigationTask, pk=pk)
    return render(request, "display/root.html",
                  {"contest_id": navigation_task.contest.pk, "navigation_task_id": pk, "live_mode": "true",
                   "display_map": "true", "display_table": "false", "skip_nav": True})


def results_service(request):
    return render(request, "display/resultsservice.html")


def manifest(request):
    data = {
        "short_name": "Airsports live tracking",
        "name": "Airsports live tracking",
        "icons": [
            {
                "src": "/static/img/airsports.png",
                "sizes": "192x192",
                "type": "image/png"
            }
        ],
        "start_url": "/",
        "display": "standalone",
        "orientation": "landscape"
    }
    return JsonResponse(data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def auto_complete_aeroplane(request):
    if request.is_ajax():
        request_number = int(request.POST.get("request"))
        if request_number == 1:
            q = request.POST.get('search', '')
            search_qs = Aeroplane.objects.filter(registration__icontains=q)
            result = [str(item.registration) for item in search_qs]
            return Response(result)
        else:
            q = request.POST.get('search', '')
            search_qs = Aeroplane.objects.filter(registration=q)
            serialiser = AeroplaneSerialiser(search_qs, many=True)
            return Response(serialiser.data)
    raise MethodNotAllowed


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def auto_complete_club(request):
    if request.is_ajax():
        request_number = int(request.POST.get("request"))
        if request_number == 1:
            q = request.POST.get('search', '')
            search_qs = Club.objects.filter(name__icontains=q)
            result = [{"label": "{} ({})".format(item.name, item.country), "value": item.name} for item in search_qs]
            return Response(result)
        else:
            q = request.POST.get('search', '')
            search_qs = Club.objects.filter(name=q)
            serialiser = ClubSerialiser(search_qs, many=True)
            return Response(serialiser.data)
    raise MethodNotAllowed


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def auto_complete_person_phone(request):
    if request.is_ajax():
        request_number = int(request.POST.get("request"))
        if request_number == 1:
            q = request.POST.get('search', '')
            search_qs = Person.objects.filter(phone__contains=q)
            result = [str(item.phone) for item in search_qs]
            return Response(result)
        else:
            q = request.POST.get('search', '')
            search_qs = Person.objects.filter(phone=q)
            serialiser = PersonSerialiser(search_qs, many=True)
            return Response(serialiser.data)
    raise MethodNotAllowed


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def auto_complete_person_id(request):
    if request.is_ajax():
        request_number = int(request.POST.get("request"))
        if request_number == 1:
            q = request.POST.get('search', '')
            search_qs = Person.objects.filter(pk=q)
            result = [str(item.phone) for item in search_qs]
            return Response(result)
        else:
            q = request.POST.get('search', '')
            search_qs = Person.objects.filter(pk=q)
            serialiser = PersonSerialiser(search_qs, many=True)
            return Response(serialiser.data)
    raise MethodNotAllowed


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def auto_complete_person_first_name(request):
    if request.is_ajax():
        request_number = int(request.POST.get("request"))
        if request_number == 1:
            q = request.POST.get('search', '')
            search_qs = Person.objects.filter(first_name__icontains=q)
            result = [{"label": "{} {}".format(item.first_name, item.last_name), "value": item.first_name} for item in
                      search_qs]
            return Response(result)
        else:
            q = request.POST.get('search', '')
            search_qs = Person.objects.filter(first_name=q)
            serialiser = PersonSerialiser(search_qs, many=True)
            return Response(serialiser.data)
    raise MethodNotAllowed


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def auto_complete_person_last_name(request):
    if request.is_ajax():
        request_number = int(request.POST.get("request"))
        if request_number == 1:
            q = request.POST.get('search', '')
            search_qs = Person.objects.filter(last_name__icontains=q)
            result = [{"label": "{} {}".format(item.first_name, item.last_name), "value": item.last_name} for item in
                      search_qs]
            return Response(result)
        else:
            q = request.POST.get('search', '')
            search_qs = Person.objects.filter(last_name=q)
            serialiser = PersonSerialiser(search_qs, many=True)
            return Response(serialiser.data)
    raise MethodNotAllowed


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def auto_complete_person_email(request):
    if request.is_ajax():
        request_number = int(request.POST.get("request"))
        if request_number == 1:
            q = request.POST.get('search', '')
            search_qs = Person.objects.filter(email__icontains=q)
            result = [item.email for item in search_qs]
            return Response(result)
        else:
            q = request.POST.get('search', '')
            search_qs = Person.objects.filter(email=q)
            serialiser = PersonSerialiser(search_qs, many=True)
            return Response(serialiser.data)
    raise MethodNotAllowed


def person_search_view(request):
    return render(request, "display/personsearch_form.html", {"form": Member1SearchForm()})


class NavigationTaskList(ListView):
    model = NavigationTask

    def get_queryset(self):
        contests = get_objects_for_user(self.request.user, "view_contest",
                                        klass=Contest)
        return NavigationTask.objects.filter(Q(contest__in=contests) | Q(is_public=True, contest__is_public=True))


class ContestList(ListView):
    model = Contest

    def get_queryset(self):
        return get_objects_for_user(self.request.user, "view_contest",
                                    klass=Contest) | Contest.objects.filter(is_public=True)


class ContestCreateView(PermissionRequiredMixin, CreateView):
    model = Contest
    success_url = reverse_lazy("contest_list")
    permission_required = ("delete_contest",)
    form_class = ContestForm


class ContestUpdateView(GuardianPermissionRequiredMixin, UpdateView):
    model = Contest
    success_url = reverse_lazy("contest_list")
    permission_required = ("update_contest",)
    form_class = ContestForm

    def get_permission_object(self):
        return self.get_object()


class ContestDeleteView(GuardianPermissionRequiredMixin, DeleteView):
    model = Contest
    permission_required = ("delete_contest",)
    template_name = "model_delete.html"
    success_url = reverse_lazy("contest_list")

    def get_permission_object(self):
        return self.get_object()


class NavigationTaskDetailView(GuardianPermissionRequiredMixin, DetailView):
    model = NavigationTask
    permission_required = ("view_contest",)

    def get_permission_object(self):
        return self.get_object().contest


class NavigationTaskUpdateView(GuardianPermissionRequiredMixin, UpdateView):
    model = NavigationTask
    permission_required = ("change_contest",)
    form_class = NavigationTaskForm
    success_url = reverse_lazy("contest_list")

    def get_permission_object(self):
        return self.get_object().contest


class BasicScoreOverrideUpdateView(GuardianPermissionRequiredMixin, UpdateView):
    model = BasicScoreOverride
    permission_required = ("change_contest",)
    form_class = BasicScoreOverrideForm
    success_url = reverse_lazy("contest_list")

    def get_permission_object(self):
        return self.get_object().navigation_task.contest

    def get_object(self, queryset=None):
        return self.model.objects.get_or_create(navigation_task_id=self.kwargs["pk"], defaults={
            "for_gate_types": [TURNPOINT, SECRETPOINT, STARTINGPOINT, FINISHPOINT]})[0]


class NavigationTaskDeleteView(GuardianPermissionRequiredMixin, DeleteView):
    model = NavigationTask
    permission_required = ("delete_contest",)
    template_name = "model_delete.html"
    success_url = reverse_lazy("contest_list")

    def get_permission_object(self):
        return self.get_object().contest


class ContestantGateTimesView(GuardianPermissionRequiredMixin, DetailView):
    model = Contestant
    permission_required = ("view_contest",)
    template_name = "display/contestant_gate_times.html"


class ContestantUpdateView(GuardianPermissionRequiredMixin, UpdateView):
    form_class = ContestantForm
    model = Contestant
    permission_required = ("change_contest",)

    def get_form_kwargs(self):
        arguments = super().get_form_kwargs()
        arguments["navigation_task"] = self.get_object().navigation_task
        return arguments

    def get_success_url(self):
        return reverse("navigationtask_detail", kwargs={"pk": self.get_object().navigation_task.pk})

    def get_permission_object(self):
        return self.get_object().navigation_task.contest


class ContestantDeleteView(GuardianPermissionRequiredMixin, DeleteView):
    model = Contestant
    permission_required = ("delete_contest",)
    template_name = "model_delete.html"

    def get_success_url(self):
        return reverse("navigationtask_detail", kwargs={"pk": self.get_object().navigation_task.pk})

    def get_permission_object(self):
        return self.get_object().navigation_task.contest


class ContestantCreateView(GuardianPermissionRequiredMixin, CreateView):
    form_class = ContestantForm
    model = Contestant
    permission_required = ("change_contest",)

    def get_form_kwargs(self):
        arguments = super().get_form_kwargs()
        arguments["navigation_task"] = get_object_or_404(NavigationTask, pk=self.kwargs.get("navigationtask_pk"))
        return arguments

    def get_success_url(self):
        return reverse("navigationtask_detail", kwargs={"pk": self.kwargs.get("navigationtask_pk")})

    def get_permission_object(self):
        navigation_task = get_object_or_404(NavigationTask, pk=self.kwargs.get("navigationtask_pk"))
        return navigation_task.contest

    def form_valid(self, form):
        navigation_task = get_object_or_404(NavigationTask, pk=self.kwargs.get("navigationtask_pk"))
        object = form.save(commit=False)
        object.navigation_task = navigation_task
        object.save()
        return HttpResponseRedirect(self.get_success_url())


connection = Redis("redis")


class GetDataFromTimeForContestant(RetrieveAPIView):
    permission_classes = [
        ContestantPublicPermissions | permissions.IsAuthenticated & ContestantNavigationTaskContestPermissions]
    lookup_url_kwarg = "contestant_pk"

    def get_queryset(self):
        contests = get_objects_for_user(self.request.user, "change_contest",
                                        klass=Contest)
        return Contestant.objects.filter(Q(navigation_task__contest__in=contests) | Q(navigation_task__is_public=True,
                                                                                      navigation_task__contest__is_public=True))

    def get(self, request, *args, **kwargs):
        contestant = self.get_object()  # type: Contestant
        from_time = request.GET.get("from_time")
        key = "{}.{}.{}".format(CONTESTANT_CACHE_KEY, contestant.pk, from_time)
        response = cache.get(key)
        if response is None:
            logger.info("Cache miss {}".format(contestant.pk))
            with redis_lock.Lock(connection, "{}.{}".format(CONTESTANT_CACHE_KEY, contestant.pk), expire=30,
                                 auto_renewal=True):
                response = cache.get(key)
                logger.info("Cache miss second time {}".format(contestant.pk))
                if response is None:
                    response = generate_data(contestant.pk, from_time)
                    cache.set(key, response)
                    logger.info("Completed updating cash {}".format(contestant.pk))
        return Response(response)


influx = InfluxFacade()


def generate_data(contestant_pk, from_time: Optional[datetime.datetime]):
    LIMIT = None
    TIME_INTERVAL = 10
    contestant = get_object_or_404(Contestant, pk=contestant_pk)  # type: Contestant
    default_start_time = contestant.navigation_task.start_time - timedelta(minutes=30)
    if from_time is None:
        from_time = default_start_time.isoformat()
    from_time_datetime = dateutil.parser.parse(from_time)
    # This is to differentiate the first request from later requests. The first request will with from time epoch 0
    if from_time_datetime < default_start_time:
        from_time_datetime = default_start_time
    logger.info("Fetching data from time {} {}".format(from_time, contestant.pk))
    result_set = influx.get_positions_for_contestant(contestant_pk, from_time, limit=LIMIT)
    logger.info("Completed fetching positions for {}".format(contestant.pk))
    position_data = list(result_set.get_points(tags={"contestant": str(contestant.pk)}))
    if len(position_data) > 0:
        global_latest_time = dateutil.parser.parse(position_data[-1]["time"])
    else:
        global_latest_time = from_time_datetime
    annotation_results = influx.get_annotations_for_contestant(contestant_pk, from_time, global_latest_time)
    annotations = []

    more_data = len(position_data) == LIMIT and len(position_data) > 0
    # if len(position_data) > 0:
    #     reduced_data = [position_data[0]]
    #     for item in position_data:
    #         if dateutil.parser.parse(item["time"]) > dateutil.parser.parse(
    #                 reduced_data[-1]["time"]) + datetime.timedelta(
    #             seconds=TIME_INTERVAL):
    #             reduced_data.append(item)
    # else:
    #     reduced_data = []
    # positions = reduced_data
    reduced_data = []
    for item in position_data:
        reduced_data.append({
            "latitude": item["latitude"],
            "longitude": item["longitude"]
        })
    # Calculate route progress
    # first_gate = contestant.navigation_task.route.takeoff_gate or contestant.navigation_task.route.waypoints[0]
    # last_gate = contestant.navigation_task.route.landing_gate or contestant.navigation_task.route.waypoints[-1]
    route_progress = 100
    if len(contestant.navigation_task.route.waypoints) > 0:
        first_gate = contestant.navigation_task.route.waypoints[0]
        last_gate = contestant.navigation_task.route.waypoints[-1]

        first_gate_time = contestant.gate_times[first_gate.name]
        last_gate_time = contestant.gate_times[last_gate.name]
        route_duration = (last_gate_time - first_gate_time).total_seconds()
        route_duration_progress = (global_latest_time - first_gate_time).total_seconds()
        route_progress = 100 * route_duration_progress / route_duration
    positions = reduced_data
    annotation_data = list(annotation_results.get_points(tags={"contestant": str(contestant.pk)}))
    if len(annotation_data):
        annotations = annotation_data
    if hasattr(contestant, "contestanttrack"):
        contestant_track = ContestantTrackSerialiser(contestant.contestanttrack).data
    else:
        contestant_track = None
    logger.info("Completed generating data {}".format(contestant.pk))
    # if len(positions) == 0:
    #     return {}
    data = {"contestant_id": contestant.pk, "latest_time": global_latest_time, "positions": positions,
            "annotations": annotations, "more_data": more_data, "progress": route_progress}
    # if len(positions) > 0:
    data["contestant_track"] = contestant_track
    return data


@permission_required("display.add_route", login_url='/accounts/login/')
def import_route(request):
    form = ImportRouteForm()
    if request.method == "POST":
        form = ImportRouteForm(request.POST, request.FILES)
        if form.is_valid():
            name = form.cleaned_data["name"]
            file_type = form.cleaned_data["file_type"]
            print(file_type)
            route = None
            if file_type == FILE_TYPE_CSV:
                data = [item.decode(encoding="UTF-8") for item in request.FILES['file'].readlines()]
                route = create_route_from_csv(name, data[1:])
            elif file_type == FILE_TYPE_FLIGHTCONTEST_GPX:
                route = create_route_from_gpx(request.FILES["file"])
            else:
                raise ValidationError("Currently unsupported type: {}".format(file_type))
            if route is not None:
                assign_perm("view_route", request.user, route)
                assign_perm("delete_route", request.user, route)
                assign_perm("change_route", request.user, route)

            return redirect("/")
    return render(request, "display/import_route_form.html", {"form": form})


# Everything below he is related to management and requires authentication
def show_route_definition_step(wizard):
    cleaned_data = wizard.get_cleaned_data_for_step("0") or {}
    return cleaned_data.get("file_type") == FILE_TYPE_KML


class NewNavigationTaskWizard(GuardianPermissionRequiredMixin, SessionWizardView):
    permission_required = ("update_contest",)

    def get_permission_object(self):
        contest = get_object_or_404(Contest, pk=self.kwargs.get("contest_pk"))
        return contest

    file_storage = FileSystemStorage(location=os.path.join(settings.MEDIA_ROOT, "importedroutes"))
    template_name = "display/navigationtaskwizardform.html"
    condition_dict = {"1": show_route_definition_step}

    def done(self, form_list, **kwargs):
        contest = get_object_or_404(Contest, pk=self.kwargs.get("contest_pk"))
        initial_step_data = self.get_cleaned_data_for_step("0")
        if initial_step_data["file_type"] == FILE_TYPE_CSV:
            data = [item.decode(encoding="UTF-8") for item in initial_step_data['file'].readlines()]
            route = create_route_from_csv(initial_step_data["name"], data[1:])
        elif initial_step_data["file_type"] == FILE_TYPE_FLIGHTCONTEST_GPX:
            route = create_route_from_gpx(initial_step_data["file"].read())
        else:
            second_step_data = self.get_cleaned_data_for_step("1")
            route = create_route_from_formset(initial_step_data["name"], second_step_data)
        final_data = self.get_cleaned_data_for_step("2")
        navigation_task = NavigationTask.objects.create(**final_data, contest=contest, route=route)
        return HttpResponseRedirect(reverse("navigationtask_detail", kwargs={"pk": navigation_task.pk}))

    form_list = [ImportRouteForm, formset_factory(WaypointForm, extra=0), NavigationTaskForm]

    def get_form_initial(self, step):
        if step == "1":
            data = self.get_cleaned_data_for_step("0")
            print("Data: {}".format(data))
            if data.get("file_type") == FILE_TYPE_KML:
                # print(" (subfile contents {}".format(data["file"].read()))
                data["file"].seek(0)
                positions = load_route_points_from_kml(data['file'])
                initial = []
                for position in positions:
                    initial.append({
                        "latitude": position[0],
                        "longitude": position[1],
                    })
                return initial
        return {}


class ContestTeamTrackingUpdate(GuardianPermissionRequiredMixin, UpdateView):
    permission_required = ("update_contest",)

    def get_permission_object(self):
        contest = get_object_or_404(Contest, pk=self.kwargs.get("contest_pk"))
        return contest

    model = ContestTeam
    form_class = TrackingDataForm

    def get_success_url(self):
        return reverse_lazy('contest_team_list', kwargs={"contest_pk": self.kwargs["contest_pk"]})


class TeamUpdateView(GuardianPermissionRequiredMixin, UpdateView):
    permission_required = ("update_contest",)

    def get_permission_object(self):
        contest = get_object_or_404(Contest, pk=self.kwargs.get("contest_pk"))
        return contest

    model = Team
    form_class = TeamForm

    def get_success_url(self):
        return reverse_lazy('contest_team_list', kwargs={"contest_pk": self.kwargs["contest_pk"]})


def create_new_pilot(wizard):
    cleaned = wizard.get_post_data_for_step("member1search") or {}
    print(cleaned)
    print(cleaned.get("use_existing_pilot"))
    print(cleaned.get("use_existing_pilot") is not None)
    return cleaned.get("use_existing_pilot") is None


def create_new_copilot(wizard):
    cleaned = wizard.get_post_data_for_step("member2search") or {}
    return cleaned.get("use_existing_copilot") is None and cleaned.get("skip_copilot") is None


class RegisterTeamWizard(GuardianPermissionRequiredMixin, SessionWizardView):
    permission_required = ("update_contest",)

    def get_permission_object(self):
        contest = get_object_or_404(Contest, pk=self.kwargs.get("contest_pk"))
        return contest

    condition_dict = {
        "member1create": create_new_pilot,
        "member2create": create_new_copilot,
    }
    post_data = {}
    file_storage = FileSystemStorage(location=os.path.join(settings.MEDIA_ROOT, "teams"))
    form_list = [
        ("member1search", Member1SearchForm),
        ("member1create", PersonForm),
        ("member2search", Member2SearchForm),
        ("member2create", PersonForm),
        ("aeroplane", AeroplaneSearchForm),
        ("club", ClubSearchForm),
        ("tracking", TrackingDataForm)
    ]
    templates = {
        "member1search": "display/membersearch_form.html",
        "member1create": "display/membercreate_form.html",
        "member2search": "display/membersearch_form.html",
        "member2create": "display/membercreate_form.html",
        "aeroplane": "display/aeroplane_form.html",
        "club": "display/club_form.html",
        "tracking": "display/basicwizardform.html"
    }

    def get_next_step(self, step=None):
        return self.request.POST.get("wizard_next_step", super().get_next_step(step))

    def post(self, *args, **kwargs):
        self.post_data[self.steps.current] = self.request.POST
        return super().post(*args, **kwargs)

    def get_post_data_for_step(self, step):
        return self.post_data.get(step, {})

    def done(self, form_list, **kwargs):
        form_dict = kwargs['form_dict']
        team_pk = self.kwargs.get("team_pk")
        contest_pk = self.kwargs.get("contest_pk")
        # Must be retrieved before we delete the existing relationship
        tracking_data = self.get_cleaned_data_for_step("tracking")
        contest = get_object_or_404(Contest, pk=contest_pk)
        if team_pk:
            original_team = get_object_or_404(Team, pk=team_pk)
        else:
            original_team = None
        affected_contestants = None
        if original_team:
            affected_contestants = Contestant.objects.filter(navigation_task__contest=contest, team=original_team)
            ContestTeam.objects.filter(contest=contest, team=original_team).delete()
        # Check if member one has been created
        member_one_search = self.get_post_data_for_step("member1search")
        use_existing1 = member_one_search.get("use_existing_pilot") is not None
        if use_existing1:
            existing_member_one_data = self.get_cleaned_data_for_step("member1search")
            member1 = get_object_or_404(Person, pk=existing_member_one_data["person_id"])
        else:
            member1 = form_dict["member1create"].save()

        member_two_search = self.get_post_data_for_step("member2search")
        member_two_skip = member_two_search.get("skip_copilot") is not None
        if not member_two_skip:
            use_existing2 = member_two_search.get("use_existing_copilot") is not None
            if use_existing2:
                existing_member_two_data = self.get_cleaned_data_for_step("member2search")
                member2 = Person.objects.get(pk=existing_member_two_data["person_id"])
            else:
                member2 = form_dict["member2create"].save()
        else:
            member2 = None
        crew, _ = Crew.objects.get_or_create(member1=member1, member2=member2)
        aeroplane_data = self.get_cleaned_data_for_step("aeroplane")
        aeroplane_data.pop("picture_display_field")
        aeroplane, _ = Aeroplane.objects.get_or_create(registration=aeroplane_data.get("registration"),
                                                       defaults=aeroplane_data)
        if aeroplane_data["picture"] is not None:
            aeroplane.picture = aeroplane_data["picture"]
        aeroplane.colour = aeroplane_data["colour"]
        aeroplane.type = aeroplane_data["type"]
        aeroplane.save()
        club_data = self.get_cleaned_data_for_step("club")
        club_data.pop("logo_display_field")
        club_data.pop("country_flag_display_field")
        club, _ = Club.objects.get_or_create(name=club_data.get("name"), country=club_data.get("country"),
                                             defaults=club_data)
        if club_data["logo"] is not None:
            club.logo = club_data["logo"]
        club.country = club_data["country"]
        club.save()
        team, created_team = Team.objects.get_or_create(crew=crew, aeroplane=aeroplane, club=club)
        ContestTeam.objects.get_or_create(contest=contest, team=team, defaults=tracking_data)
        if affected_contestants is not None:
            affected_contestants.update(team=team)
        return HttpResponseRedirect(reverse("team_update", kwargs={"contest_pk": contest_pk, "pk": team.pk}))

    def get_form_prefix(self, step=None, form=None):
        return ''

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


class PersonList(SuperuserRequiredMixin, ListView):
    model = Person

    def get_queryset(self):
        return Person.objects.all().order_by("last_name", "first_name")


class PersonUpdateView(SuperuserRequiredMixin, UpdateView):
    model = Person
    success_url = reverse_lazy("person_list")
    form_class = PersonForm


class ContestTeamList(GuardianPermissionRequiredMixin, ListView):
    model = ContestTeam
    permission_required = ("view_contest",)

    def get_permission_object(self):
        contest = get_object_or_404(Contest, pk=self.kwargs.get("contest_pk"))
        return contest

    def get_queryset(self):
        contest = get_object_or_404(Contest, pk=self.kwargs.get("contest_pk"))
        return ContestTeam.objects.filter(contest=contest).order_by("team__crew__member1__last_name",
                                                                    "team__crew__member1__first_name")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["contest"] = get_object_or_404(Contest, pk=self.kwargs.get("contest_pk"))
        return context


def remove_team_from_contest(request, contest_pk, team_pk):
    contest = get_object_or_404(Contest, pk=contest_pk)
    team = get_object_or_404(Team, pk=team_pk)
    ContestTeam.objects.filter(contest=contest, team=team).delete()
    return HttpResponseRedirect(reverse("contest_team_list", kwargs={"contest_pk": contest_pk}))


class IsPublicMixin:
    def check_publish_permissions(self, user: User):
        instance = self.get_object()
        if isinstance(instance, Contest):
            if user.has_perm("change_contest", instance):
                return True
        if isinstance(instance, NavigationTask):
            if user.has_perm("change_contest", instance.contest):
                return True
        raise PermissionDenied("User does not have permission to publish {}".format(instance))

    @action(detail=True, methods=["put"])
    def publish(self, request, **kwargs):
        """
        Makes the object publicly visible to anonymous users. If a contest is  hidden, all associated tasks will also
        be hidden. If a contest is visible,
        then task visibility is controlled by the individual tasks.

        :param request:
        :param kwargs:
        :return:
        """
        self.check_publish_permissions(request.user)
        instance = self.get_object()
        instance.is_public = True
        instance.save()
        return Response({'is_public': instance.is_public})

    @action(detail=True, methods=["put"])
    def hide(self, request, **kwargs):
        """
        Makes the object invisible to anonymous users. It will only be visible to users who have specific rights to
        view that object. If a contest is  hidden, all associated tasks will also be hidden. If a contest is visible,
        then task visibility is controlled by the individual tasks.

        :param request:
        :param kwargs:
        :return:
        """
        self.check_publish_permissions(request.user)
        instance = self.get_object()
        instance.is_public = False
        instance.save()
        return Response({'is_public': instance.is_public})


class ContestViewSet(IsPublicMixin, ModelViewSet):
    """
    A contest is a high level wrapper for multiple tasks. Currently it mostly consists of a name and a is_public
    flag which controls its visibility for anonymous users.GET Returns a list of contests either owned by the user
    or publicly divisible POST Allows the user to post a new contest and become the owner of that contest.
    """
    queryset = Contest.objects.all()
    serializer_classes = {
        "teams": ContestTeamNestedSerialiser,
        "task_results": TaskWithoutReferenceNestedSerialiser,
        "contest_summary_results": ContestSummaryWithoutReferenceSerialiser
    }
    default_serialiser_class = ContestSerialiser
    lookup_url_kwarg = "pk"
    permission_classes = [ContestPublicPermissions | (permissions.IsAuthenticated & ContestPermissions)]

    def get_serializer_class(self):
        return self.serializer_classes.get(self.action, self.default_serialiser_class)

    def get_queryset(self):
        return get_objects_for_user(self.request.user, "view_contest",
                                    klass=self.queryset) | self.queryset.filter(is_public=True)

    @action(["GET"], detail=True)
    def teams(self, request, pk=None, **kwargs):
        """
        Get the list of teams in the contest
        """
        contest_teams = ContestTeam.objects.filter(contest=pk)
        return Response(ContestTeamNestedSerialiser(contest_teams, many=True).data)

    @action(["PUT"], detail=True, permission_classes=[permissions.IsAuthenticated & ContestModificationPermissions])
    def task_results(self, request, pk=None, **kwargs):
        """
        Post the results for a task (for individual tests and a task summary). This will overwrite any previously
        stored task results for the task (referenced by the task name). Tasks are unique inside a contest, and tests
        are unique inside a task. A team can only have a single TaskSummary and a single TeamTestScore for each test.
        Violating this will result in a validation error and an exception.
        """
        Task.objects.filter(contest=self.get_object(), name=request.data["name"]).delete()
        serialiser = self.get_serializer_class()(data=request.data,
                                                 context={"contest": self.get_object()})
        serialiser.is_valid(True)
        serialiser.save()
        return Response(serialiser.data, status=status.HTTP_201_CREATED)

    @action(["DELETE"], detail=True, permission_classes=[permissions.IsAuthenticated & ContestModificationPermissions])
    def all_task_results(self, request, pk=None, **kwargs):
        """
        Delete all task results for the contest.
        """
        Task.objects.filter(contest=self.get_object()).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(["POST", "DELETE"], detail=True,
            permission_classes=[permissions.IsAuthenticated & ContestModificationPermissions])
    def contest_summary_results(self, request, pk=None, **kwargs):
        """
        Post the combined summary results for the contest. Expects either a list of ContestSummaryWithoutReferenceSerialiser
        where each object represents the total score of the contest for a team, or a single instance of
        ContestSummaryWithoutReferenceSerialiser. DELETE requires no specific input.
        """
        if self.request.method == "POST":
            serialiser = self.get_serializer(data=request.data, many=isinstance(request.data, list),
                                             context={"contest": self.get_object()})
            serialiser.is_valid(True)
            serialiser.save()
            return Response(serialiser.data, status=status.HTTP_201_CREATED)
        else:
            ContestSummary.objects.filter(contest=self.get_object()).delete()
            return Response(status=status.HTTP_204_NO_CONTENT)


class NavigationTaskViewSet(IsPublicMixin, ModelViewSet):
    queryset = NavigationTask.objects.all()
    serializer_class = NavigationTaskNestedTeamRouteSerialiser
    permission_classes = [
        NavigationTaskPublicPermissions | (permissions.IsAuthenticated & NavigationTaskContestPermissions)]

    http_method_names = ['get', 'post', 'delete', 'put']

    def get_queryset(self):
        contest_id = self.kwargs.get("contest_pk")
        contests = get_objects_for_user(self.request.user, "view_contest",
                                        klass=Contest)
        return NavigationTask.objects.filter(
            Q(contest__in=contests) | Q(is_public=True, contest__is_public=True)).filter(contest_id=contest_id)

    def create(self, request, *args, **kwargs):
        contest = get_object_or_404(Contest, pk=self.kwargs.get("contest_pk"))
        serialiser = self.get_serializer(data=request.data,
                                         context={"request": request, "contest": contest})
        if serialiser.is_valid():
            serialiser.save()
            return Response(serialiser.data, status=status.HTTP_201_CREATED)
        return Response(serialiser.errors, status=status.HTTP_400_BAD_REQUEST)

    def update(self, request, *args, **kwargs):
        raise PermissionDenied("It is not possible to modify existing navigation tasks except to publish or hide them")


class RouteViewSet(ModelViewSet):
    queryset = Route.objects.all()
    serializer_class = RouteSerialiser
    permission_classes = [permissions.IsAuthenticated & RoutePermissions]

    http_method_names = ['get', 'post', 'delete', 'put']


class ContestantViewSet(ModelViewSet):
    queryset = Contestant.objects.all()
    serializer_class = ContestantNestedTeamSerialiserWithContestantTrack
    permission_classes = [
        ContestantPublicPermissions | (permissions.IsAuthenticated & ContestantNavigationTaskContestPermissions)]

    def get_serializer_class(self):
        if self.action == "gpx_track":
            return GpxTrackSerialiser
        return super().get_serializer_class()

    def get_queryset(self):
        navigation_task_id = self.kwargs.get("navigationtask_pk")
        contests = get_objects_for_user(self.request.user, "change_contest",
                                        klass=Contest)
        return Contestant.objects.filter(Q(navigation_task__contest__in=contests) | Q(navigation_task__is_public=True,
                                                                                      navigation_task__contest__is_public=True)).filter(
            navigation_task_id=navigation_task_id)

    def create(self, request, *args, **kwargs):
        navigation_task = get_object_or_404(NavigationTask, pk=self.kwargs.get("navigationtask_pk"))
        serialiser = self.get_serializer(data=request.data,
                                         context={"request": request, "navigation_task": navigation_task})
        if serialiser.is_valid():
            serialiser.save()
            return Response(serialiser.data)
        return Response(serialiser.errors, status=status.HTTP_400_BAD_REQUEST)

    def update(self, request, *args, **kwargs):
        navigation_task = get_object_or_404(NavigationTask, pk=self.kwargs.get("navigationtask_pk"))
        instance = self.get_object()
        partial = kwargs.pop('partial', False)
        serialiser = self.get_serializer(instance=instance, data=request.data,
                                         # context={"request": request, "navigation_task": navigation_task},
                                         partial=partial)
        if serialiser.is_valid():
            serialiser.save()
            return Response(serialiser.data)
        return Response(serialiser.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["get"])
    def track(self, request, pk=None, **kwargs):
        contestant = self.get_object()  # This is important, this is where the object permissions are checked
        contestant_track = contestant.contestanttrack
        result_set = influx.get_positions_for_contestant(pk, contestant.tracker_start_time)
        logger.info("Completed fetching positions for {}".format(contestant.pk))
        position_data = list(result_set.get_points(tags={"contestant": str(contestant.pk)}))
        contestant_track.track = position_data
        serialiser = ContestantTrackWithTrackPointsSerialiser(contestant_track)
        return Response(serialiser.data)

    @action(detail=True, methods=["post"])
    def gpx_track(self, request, pk=None, **kwargs):
        contestant = self.get_object()  # This is important, this is where the object permissions are checked
        ContestantTrack.objects.filter(contestant=contestant).delete()
        contestant.save()  # Creates new contestant track
        # Not required, covered by delete above
        # influx.clear_data_for_contestant(contestant.pk)
        track_file = request.data.get("track_file", None)
        if not track_file:
            raise ValidationError("Missing track_file")
        insert_gpx_file(contestant, base64.decodebytes(track_file.encode("utf-8")), influx)
        return Response({}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"])
    def track_frontend(self, request, *args, **kwargs):
        """
        For internal use only. Provides data in the format that the frontend requires
        :param request:
        :param args:
        :param kwargs:
        :return:
        """
        contestant = self.get_object()  # This is important, this is where the object permissions are checked
        from_time = request.GET.get("from_time")
        key = "{}.{}.{}".format(CONTESTANT_CACHE_KEY, contestant.pk, from_time)
        response = cache.get(key)
        if response is None:
            logger.info("Cache miss {}".format(contestant.pk))
            with redis_lock.Lock(connection, "{}.{}".format(CONTESTANT_CACHE_KEY, contestant.pk), expire=30,
                                 auto_renewal=True):
                response = cache.get(key)
                logger.info("Cache miss second time {}".format(contestant.pk))
                if response is None:
                    response = generate_data(contestant.pk, from_time)
                    cache.set(key, response)
                    logger.info("Completed updating cash {}".format(contestant.pk))
        return Response(response)


class ImportFCNavigationTask(ModelViewSet):
    """
    This is a shortcut to post a new navigation task to the tracking system. It requires the existence of a contest to
    which it will belong. The entire task with contestants and their associated times, crews, and aircraft, together
    with the route can be posted to the single endpoint.

    route_file is a utf-8 string that contains a base 64 encoded gpx route file of the format that FC exports. A new
    route object will be created every time this function is called, but it is possible to reuse routes if
    required. This is currently not supported through this endpoint, but this may change in the future.
    """
    queryset = NavigationTask.objects.all()
    serializer_class = ExternalNavigationTaskNestedTeamSerialiser
    permission_classes = [permissions.IsAuthenticated & NavigationTaskContestPermissions]

    metadata_class = ShowChoicesMetadata

    http_method_names = ["post"]

    lookup_key = "contest_pk"

    def create(self, request, *args, **kwargs):
        contest = get_object_or_404(Contest, pk=self.kwargs.get(self.lookup_key))
        serialiser = self.serializer_class(data=request.data,
                                           context={"request": request, "contest": contest})
        if serialiser.is_valid(raise_exception=True):
            serialiser.save()
            return Response(serialiser.data, status=status.HTTP_201_CREATED)
        return Response(serialiser.errors, status=status.HTTP_400_BAD_REQUEST)


class ImportFCNavigationTaskTeamId(ImportFCNavigationTask):
    """
    This is a shortcut to post a new navigation task to the tracking system. It requires the existence of a contest to
    which it will belong. The entire task with contestants and their associated times, crews, and aircraft, together
    with the route can be posted to the single endpoint.

    route_file is a utf-8 string that contains a base 64 encoded gpx route file of the format that FC exports. A new
    route object will be created every time this function is called, but it is possible to reuse routes if
    required. This is currently not supported through this endpoint, but this may change in the future.
    """
    serializer_class = ExternalNavigationTaskTeamIdSerialiser


@login_required()
def renew_token(request):
    user = request.user
    Token.objects.filter(user=user).delete()
    Token.objects.create(user=user)
    return redirect(reverse("token"))


########## Results service ##########
class ContestResultsSummaryViewSet(ModelViewSet):
    queryset = Contest.objects.all()
    serializer_class = ContestResultsHighLevelSerialiser
    permission_classes = [ContestPublicPermissions | permissions.IsAuthenticated & ContestPermissions]

    @action(detail=True, methods=["get"])
    def details(self, request, *args, **kwargs):
        contest = self.get_object()
        serialiser = ContestResultsDetailsSerialiser(contest)
        return Response(serialiser.data)

    @action(detail=True, methods=["get"])
    def teams(self, request, *args, **kwargs):
        contest = self.get_object()
        teams = Team.objects.filter(Q(tasksummary__task__contest=contest) | Q(contestsummary__contest=contest) | Q(
            teamtestscore__task_test__task__contest=contest)).distinct()
        serialiser = TeamNestedSerialiser(teams, many=True)
        return Response(serialiser.data)


class TeamResultsSummaryViewSet(ModelViewSet):
    queryset = Team.objects.all()
    serializer_class = TeamResultsSummarySerialiser
