import base64
import datetime
import os
from datetime import timedelta
from typing import Optional, Dict

import guardian
import redis_lock
import dateutil
from django.contrib import messages
from django.contrib.auth.decorators import permission_required, login_required
from django.contrib.auth.mixins import PermissionRequiredMixin, LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.models import User

from django.core.cache import cache
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.core.files.storage import FileSystemStorage
from django.db import transaction
from django.db.models import Q
from django.forms import formset_factory
from django.http import HttpResponseRedirect, JsonResponse, HttpResponse, Http404
from django.shortcuts import render, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import ListView, DetailView, UpdateView, CreateView, DeleteView
import logging

from formtools.wizard.views import SessionWizardView, CookieWizardView
from guardian.decorators import guardian.decorators.permission_required
from guardian.mixins import PermissionRequiredMixin as GuardianPermissionRequiredMixin
from guardian.shortcuts import get_objects_for_user, assign_perm, get_users_with_perms, remove_perm, get_user_perms
from redis import Redis
from rest_framework import status, permissions, mixins
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import PermissionDenied, MethodNotAllowed
from rest_framework.generics import RetrieveAPIView, get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, ViewSet, GenericViewSet

from display.calculate_gate_times import calculate_and_get_relative_gate_times
from display.contestant_scheduler import TeamDefinition, Solver
from display.convert_flightcontest_gpx import create_precision_route_from_gpx, create_precision_route_from_csv, \
    load_route_points_from_kml, \
    create_precision_route_from_formset, create_anr_corridor_route_from_kml, load_features_from_kml
from display.forms import PrecisionImportRouteForm, WaypointForm, NavigationTaskForm, FILE_TYPE_CSV, \
    FILE_TYPE_FLIGHTCONTEST_GPX, \
    FILE_TYPE_KML, ContestantForm, ContestForm, Member1SearchForm, TeamForm, PersonForm, \
    Member2SearchForm, AeroplaneSearchForm, ClubSearchForm, ContestantMapForm, LANDSCAPE, \
    MapForm, \
    WaypointFormHelper, TaskTypeForm, ANRCorridorImportRouteForm, ANRCorridorScoreOverrideForm, \
    PrecisionScoreOverrideForm, STARTINGPOINT, FINISHPOINT, TrackingDataForm, ContestTeamOptimisationForm, \
    AssignPokerCardForm, ChangeContestPermissionsForm, AddContestPermissionsForm
from display.map_plotter import plot_route, get_basic_track
from display.models import NavigationTask, Route, Contestant, CONTESTANT_CACHE_KEY, Contest, Team, ContestantTrack, \
    Person, Aeroplane, Club, Crew, ContestTeam, Task, TaskSummary, ContestSummary, TaskTest, \
    TeamTestScore, TRACCAR, Scorecard, MyUser, PlayingCard
from display.permissions import ContestPermissions, NavigationTaskContestPermissions, \
    ContestantPublicPermissions, NavigationTaskPublicPermissions, ContestPublicPermissions, \
    ContestantNavigationTaskContestPermissions, RoutePermissions, ContestModificationPermissions, \
    ContestPermissionsWithoutObjects
from display.schedule_contestants import schedule_and_create_contestants
from display.serialisers import ContestantTrackSerialiser, \
    ExternalNavigationTaskNestedTeamSerialiser, \
    ContestSerialiser, NavigationTaskNestedTeamRouteSerialiser, RouteSerialiser, \
    ContestantTrackWithTrackPointsSerialiser, ContestResultsHighLevelSerialiser, \
    TeamResultsSummarySerialiser, ContestResultsDetailsSerialiser, TeamNestedSerialiser, \
    GpxTrackSerialiser, PersonSerialiser, ExternalNavigationTaskTeamIdSerialiser, \
    ContestantNestedTeamSerialiserWithContestantTrack, AeroplaneSerialiser, ClubSerialiser, ContestTeamNestedSerialiser, \
    TaskWithoutReferenceNestedSerialiser, ContestSummaryWithoutReferenceSerialiser, ContestTeamSerialiser, \
    NavigationTasksSummarySerialiser
from display.show_slug_choices import ShowChoicesMetadata
from display.tasks import import_gpx_track
from display.traccar_factory import get_traccar_instance
from influx_facade import InfluxFacade
from live_tracking_map import settings
from playback_tools import insert_gpx_file
from traccar_facade import Traccar

logger = logging.getLogger(__name__)


class ContestantTimeZoneMixin:
    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        timezone.activate(self.get_object().navigation_task.contest.time_zone)


class NavigationTaskTimeZoneMixin:
    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        timezone.activate(self.get_object().contest.time_zone)


class ContestTimeZoneMixin:
    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        timezone.activate(self.get_object().time_zone)


class SuperuserRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_superuser


def frontend_view_map(request, pk):
    my_contests = get_objects_for_user(request.user, "display.view_contest", accept_global_perms=False)
    public_contests = Contest.objects.filter(is_public=True)
    try:
        navigation_task = NavigationTask.objects.get(
            Q(contest__in=my_contests) | Q(contest__in=public_contests, is_public=True), pk=pk)
    except ObjectDoesNotExist:
        raise Http404
    return render(request, "display/root.html",
                  {"contest_id": navigation_task.contest.pk, "navigation_task_id": pk, "live_mode": "true",
                   "display_map": "true", "display_table": "false", "skip_nav": True})


def global_map(request):
    return render(request, "display/globalmap.html", {"skip_nav": True})


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
@permission_classes([IsAuthenticated, ContestPermissionsWithoutObjects])
def auto_complete_aeroplane(request):
    if request.is_ajax():
        request_number = int(request.data.get("request"))
        if request_number == 1:
            q = request.data.get('search', '')
            search_qs = Aeroplane.objects.filter(registration__icontains=q)
            result = [str(item.registration) for item in search_qs]
            return Response(result)
        else:
            q = request.data.get('search', '')
            search_qs = Aeroplane.objects.filter(registration=q)
            serialiser = AeroplaneSerialiser(search_qs, many=True)
            return Response(serialiser.data)
    raise MethodNotAllowed


@api_view(["POST"])
@permission_classes([IsAuthenticated, ContestPermissionsWithoutObjects])
def auto_complete_club(request):
    if request.is_ajax():
        request_number = int(request.data.get("request"))
        if request_number == 1:
            q = request.data.get('search', '')
            search_qs = Club.objects.filter(name__icontains=q)
            result = [{"label": "{} ({})".format(item.name, item.country), "value": item.name} for item in search_qs]
            return Response(result)
        else:
            q = request.data.get('search', '')
            search_qs = Club.objects.filter(name=q)
            serialiser = ClubSerialiser(search_qs, many=True)
            return Response(serialiser.data)
    raise MethodNotAllowed


@api_view(["POST"])
@permission_classes([IsAuthenticated, ContestPermissionsWithoutObjects])
def auto_complete_person_phone(request):
    if request.is_ajax():
        request_number = int(request.data.get("request"))
        if request_number == 1:
            q = request.data.get('search', '')
            search_qs = Person.objects.filter(phone__contains=q)
            result = [str(item.phone) for item in search_qs]
            return Response(result)
        else:
            q = request.data.get('search', '')
            search_qs = Person.objects.filter(phone=q)
            serialiser = PersonSerialiser(search_qs, many=True)
            return Response(serialiser.data)
    raise MethodNotAllowed


@api_view(["POST"])
@permission_classes([IsAuthenticated, ContestPermissionsWithoutObjects])
def auto_complete_person_id(request):
    if request.is_ajax():
        request_number = int(request.data.get("request"))
        if request_number == 1:
            q = request.data.get('search', '')
            search_qs = Person.objects.filter(pk=q)
            result = [str(item.phone) for item in search_qs]
            return Response(result)
        else:
            q = request.data.get('search', '')
            search_qs = Person.objects.filter(pk=q)
            serialiser = PersonSerialiser(search_qs, many=True)
            return Response(serialiser.data)
    raise MethodNotAllowed


@api_view(["POST"])
@permission_classes([IsAuthenticated, ContestPermissionsWithoutObjects])
def auto_complete_person_first_name(request):
    if request.is_ajax():
        request_number = int(request.data.get("request"))
        if request_number == 1:
            q = request.data.get('search', '')
            search_qs = Person.objects.filter(first_name__icontains=q)
            result = [{"label": "{} {}".format(item.first_name, item.last_name), "value": item.first_name} for item in
                      search_qs]
            return Response(result)
        else:
            q = request.data.get('search', '')
            search_qs = Person.objects.filter(first_name=q)
            serialiser = PersonSerialiser(search_qs, many=True)
            return Response(serialiser.data)
    raise MethodNotAllowed


@api_view(["POST"])
@permission_classes([IsAuthenticated, ContestPermissionsWithoutObjects])
def auto_complete_person_last_name(request):
    if request.is_ajax():
        request_number = int(request.data.get("request"))
        if request_number == 1:
            q = request.data.get('search', '')
            search_qs = Person.objects.filter(last_name__icontains=q)
            result = [{"label": "{} {}".format(item.first_name, item.last_name), "value": item.last_name} for item in
                      search_qs]
            return Response(result)
        else:
            q = request.data.get('search', '')
            search_qs = Person.objects.filter(last_name=q)
            serialiser = PersonSerialiser(search_qs, many=True)
            return Response(serialiser.data)
    raise MethodNotAllowed


@api_view(["POST"])
@permission_classes([IsAuthenticated, ContestPermissionsWithoutObjects])
def auto_complete_person_email(request):
    if request.is_ajax():
        request_number = int(request.data.get("request"))
        if request_number == 1:
            q = request.data.get('search', '')
            search_qs = Person.objects.filter(email__icontains=q)
            result = [item.email for item in search_qs]
            return Response(result)
        else:
            q = request.data.get('search', '')
            search_qs = Person.objects.filter(email=q)
            serialiser = PersonSerialiser(search_qs, many=True)
            return Response(serialiser.data)
    raise MethodNotAllowed


def tracking_qr_code_view(request, pk):
    url = reverse("frontend_view_map", kwargs={"pk": pk})
    return render(request, "display/tracking_qr_code.html", {"url": "https://tracking.airsports.no{}".format(url),
                                                             "navigation_task": NavigationTask.objects.get(pk=pk)})


@guardian.decorators.permission_required('display.change_contest', (Contest, "navigationtask__contestant__pk", "pk"))
def deal_card_to_contestant(request, pk):
    contestant = get_object_or_404(Contestant, pk=pk)
    if request.method == "POST":
        form = AssignPokerCardForm(request.POST)
        form.fields["waypoint"].choices = [(item.name, item.name) for item in
                                           contestant.navigation_task.route.waypoints]
        if form.is_valid():
            waypoint = form.cleaned_data["waypoint"]
            card = form.cleaned_data["playing_card"]
            random_card = form.cleaned_data["random_card"]
            if random_card:
                card = PlayingCard.get_random_unique_card(contestant)
            PlayingCard.add_contestant_card(contestant, card, waypoint)
            return redirect(reverse("navigationtask_detail", kwargs={"pk": contestant.navigation_task_id}))
    form = AssignPokerCardForm()
    form.fields["waypoint"].choices = [(item.name, item.name) for item in
                                       contestant.navigation_task.route.waypoints]
    return render(request, "display/deal_card_form.html", {"form": form, "contestant": contestant})


# @guardian.decorators.permission_required('display.change_contest', (Contest, "navigationtask__contestant__pk", "pk"))
# def view_cards(request, pk):


@guardian.decorators.permission_required('display.view_contest', (Contest, "navigationtask__contestant__pk", "pk"))
def get_contestant_map(request, pk):
    if request.method == "POST":
        form = ContestantMapForm(request.POST)
        if form.is_valid():
            contestant = get_object_or_404(Contestant, pk=pk)
            map_image = plot_route(contestant.navigation_task, form.cleaned_data["size"],
                                   zoom_level=form.cleaned_data["zoom_level"],
                                   landscape=int(form.cleaned_data["orientation"]) == LANDSCAPE, contestant=contestant,
                                   annotations=form.cleaned_data["include_annotations"],
                                   waypoints_only=False, dpi=form.cleaned_data["dpi"],
                                   scale=int(form.cleaned_data["scale"]),
                                   map_source=int(form.cleaned_data["map_source"]))
            response = HttpResponse(map_image, content_type='image/png')
            return response
    form = ContestantMapForm()
    return render(request, "display/map_form.html", {"form": form})


@guardian.decorators.permission_required('display.view_contest', (Contest, "navigationtask__pk", "pk"))
def get_navigation_task_map(request, pk):
    if request.method == "POST":
        form = MapForm(request.POST)
        if form.is_valid():
            navigation_task = get_object_or_404(NavigationTask, pk=pk)
            print(form.cleaned_data)
            map_image = plot_route(navigation_task, form.cleaned_data["size"],
                                   zoom_level=form.cleaned_data["zoom_level"],
                                   landscape=int(form.cleaned_data["orientation"]) == LANDSCAPE,
                                   waypoints_only=form.cleaned_data["include_only_waypoints"],
                                   dpi=form.cleaned_data["dpi"], scale=int(form.cleaned_data["scale"]),
                                   map_source=int(form.cleaned_data["map_source"]))
            response = HttpResponse(map_image, content_type='image/png')
            return response
    form = MapForm()
    return render(request, "display/map_form.html", {"form": form})


@guardian.decorators.permission_required('display.change_contest', (Contest, "pk", "pk"))
def list_contest_permissions(request, pk):
    contest = get_object_or_404(Contest, pk=pk)
    users_and_permissions = get_users_with_perms(contest, attach_perms=True)
    users = []
    for user in users_and_permissions.keys():
        data = {item: True for item in users_and_permissions[user]}
        data["email"] = user.email
        data["pk"] = user.pk
        users.append(data)
    return render(request, "display/contest_permissions.html", {"users": users, "contest": contest})


@guardian.decorators.permission_required('display.change_contest', (Contest, "pk", "pk"))
def delete_user_contest_permissions(request, pk, user_pk):
    contest = get_object_or_404(Contest, pk=pk)
    user = get_object_or_404(MyUser, pk=user_pk)
    permissions = ["change_contest", "view_contest", "delete_contest"]
    for permission in permissions:
        remove_perm(f"display.{permission}", user, contest)
    return redirect(reverse("contest_permissions_list", kwargs={"pk": pk}))


@guardian.decorators.permission_required('display.change_contest', (Contest, "pk", "pk"))
def change_user_contest_permissions(request, pk, user_pk):
    contest = get_object_or_404(Contest, pk=pk)
    user = get_object_or_404(MyUser, pk=user_pk)
    if request.method == "POST":
        form = ChangeContestPermissionsForm(request.POST)
        if form.is_valid():
            permissions = ["change_contest", "view_contest", "delete_contest"]
            for permission in permissions:
                if form.cleaned_data[permission]:
                    assign_perm(f"display.{permission}", user, contest)
                else:
                    remove_perm(f"display.{permission}", user, contest)
            return redirect(reverse("contest_permissions_list", kwargs={"pk": pk}))
    existing_permissions = get_user_perms(user, contest)
    initial = {item: True for item in existing_permissions}
    form = ChangeContestPermissionsForm(initial=initial)
    return render(request, "display/contest_permissions_form.html", {"form": form})


@guardian.decorators.permission_required('display.change_contest', (Contest, "pk", "pk"))
def add_user_contest_permissions(request, pk):
    contest = get_object_or_404(Contest, pk=pk)
    if request.method == "POST":
        form = AddContestPermissionsForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"]
            try:
                user = MyUser.objects.get(email=email)
            except ObjectDoesNotExist:
                messages.error(request, f"User '{email}' does not exist")
                return redirect(reverse("contest_permissions_list", kwargs={"pk": pk}))
            permissions = ["change_contest", "view_contest", "delete_contest"]
            for permission in permissions:
                if form.cleaned_data[permission]:
                    assign_perm(f"display.{permission}", user, contest)
                else:
                    remove_perm(f"display.{permission}", user, contest)
            return redirect(reverse("contest_permissions_list", kwargs={"pk": pk}))
    form = AddContestPermissionsForm()
    return render(request, "display/contest_permissions_form.html", {"form": form})


class ContestList(PermissionRequiredMixin, ListView):
    model = Contest
    permission_required = ("display.view_contest",)

    def get_queryset(self):
        print(self.request.user)
        # Important not to accept global permissions, otherwise any content creator can view everything
        objects = get_objects_for_user(self.request.user, "display.view_contest", accept_global_perms=False)
        print(list(objects))
        return objects


class ContestCreateView(PermissionRequiredMixin, CreateView):
    model = Contest
    permission_required = ("display.add_contest",)
    form_class = ContestForm

    def form_valid(self, form):
        instance = form.save(commit=False)  # type: Contest
        instance.start_time = instance.time_zone.localize(instance.start_time.replace(tzinfo=None))
        instance.finish_time = instance.time_zone.localize(instance.finish_time.replace(tzinfo=None))
        instance.save()
        assign_perm("delete_contest", self.request.user, instance)
        assign_perm("view_contest", self.request.user, instance)
        assign_perm("add_contest", self.request.user, instance)
        assign_perm("change_contest", self.request.user, instance)
        self.object = instance
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse('contest_details', kwargs={'pk': self.object.pk})


class ContestDetailView(ContestTimeZoneMixin, GuardianPermissionRequiredMixin, DetailView):
    model = Contest
    permission_required = ("display.view_contest",)


class ContestUpdateView(ContestTimeZoneMixin, GuardianPermissionRequiredMixin, UpdateView):
    model = Contest
    permission_required = ("display.change_contest",)
    form_class = ContestForm

    def get_permission_object(self):
        return self.get_object()

    def get_success_url(self):
        return reverse('contest_details', kwargs={'pk': self.get_object().pk})


class ContestDeleteView(GuardianPermissionRequiredMixin, DeleteView):
    model = Contest
    permission_required = ("display.delete_contest",)
    template_name = "model_delete.html"
    success_url = reverse_lazy("contest_list")

    def get_permission_object(self):
        return self.get_object()


class NavigationTaskDetailView(NavigationTaskTimeZoneMixin, GuardianPermissionRequiredMixin, DetailView):
    model = NavigationTask
    permission_required = ("display.view_contest",)

    def get_permission_object(self):
        return self.get_object().contest


class NavigationTaskUpdateView(NavigationTaskTimeZoneMixin, GuardianPermissionRequiredMixin, UpdateView):
    model = NavigationTask
    permission_required = ("display.change_contest",)
    form_class = NavigationTaskForm

    def get_permission_object(self):
        return self.get_object().contest

    def get_success_url(self):
        return reverse('contest_details', kwargs={'pk': self.get_object().contest.pk})


# class BasicScoreOverrideUpdateView(GuardianPermissionRequiredMixin, UpdateView):
#     model = BasicScoreOverride
#     permission_required = ("display.change_contest",)
#     form_class = BasicScoreOverrideForm
#     success_url = reverse_lazy("contest_list")
#
#     def get_permission_object(self):
#         return self.get_object().navigation_task.contest
#
#     def get_object(self, queryset=None):
#         return self.model.objects.get_or_create(navigation_task_id=self.kwargs["pk"], defaults={
#             "for_gate_types": [TURNPOINT, SECRETPOINT, STARTINGPOINT, FINISHPOINT]})[0]


class NavigationTaskDeleteView(GuardianPermissionRequiredMixin, DeleteView):
    model = NavigationTask
    permission_required = ("display.delete_contest",)
    template_name = "model_delete.html"
    success_url = reverse_lazy("contest_list")

    def get_permission_object(self):
        return self.get_object().contest

    def get_success_url(self):
        return reverse('contest_details', kwargs={'pk': self.get_object().contest.pk})


class ContestantGateTimesView(ContestantTimeZoneMixin, GuardianPermissionRequiredMixin, DetailView):
    model = Contestant
    permission_required = ("display.view_contest",)
    template_name = "display/contestant_gate_times.html"

    def get_permission_object(self):
        return self.get_object().navigation_task.contest

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if hasattr(self.object, "contestanttrack"):
            contestant_track = self.object.contestanttrack
            log = {}
            for item in contestant_track.score_log:
                if item["gate"] not in log:
                    log[item["gate"]] = []
                log[item["gate"]].append("{} points {}".format(item["points"], item["message"]))
            context["log"] = log
        return context


class ContestantUpdateView(ContestantTimeZoneMixin, GuardianPermissionRequiredMixin, UpdateView):
    form_class = ContestantForm
    model = Contestant
    permission_required = ("display.change_contest",)

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
    permission_required = ("display.change_contest",)
    template_name = "model_delete.html"

    def get_success_url(self):
        return reverse("navigationtask_detail", kwargs={"pk": self.get_object().navigation_task.pk})

    def get_permission_object(self):
        return self.get_object().navigation_task.contest


class ContestantCreateView(GuardianPermissionRequiredMixin, CreateView):
    form_class = ContestantForm
    model = Contestant
    permission_required = ("display.change_contest",)

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.navigation_task = get_object_or_404(NavigationTask, pk=self.kwargs.get("navigationtask_pk"))
        timezone.activate(self.navigation_task.contest.time_zone)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["navigation_task"] = self.navigation_task
        return context

    def get_form_kwargs(self):
        arguments = super().get_form_kwargs()
        arguments["navigation_task"] = self.navigation_task
        return arguments

    def get_success_url(self):
        return reverse("navigationtask_detail", kwargs={"pk": self.kwargs.get("navigationtask_pk")})

    def get_permission_object(self):
        return self.navigation_task.contest

    def form_valid(self, form):
        object = form.save(commit=False)  # type: Contestant
        object.navigation_task = self.navigation_task
        object.save()
        return HttpResponseRedirect(self.get_success_url())


@api_view(["GET"])
@guardian.decorators.permission_required('display.view_contest', (Contest, "navigationtask__pk", "pk"))
def get_contestant_schedule(request, pk):
    navigation_task = get_object_or_404(NavigationTask, pk=pk)
    columns = [
        {"id": "Aircraft", "type": "string"},
        {"id": "Contestant", "type": "string"},
        {"id": "Takeoff", "type": "date"},
        {"id": "Landing", "type": "date"},
    ]
    rows = []
    for contestant in navigation_task.contestant_set.all():
        rows.append({"c": [{"v": contestant.team.aeroplane.registration}, {"v": str(contestant)},
                           {"v": contestant.takeoff_time}, {"v": contestant.finished_by_time}]})

    return Response({"cols": columns, "rows": rows})


@guardian.decorators.permission_required('display.view_contest', (Contest, "navigationtask__pk", "pk"))
def render_contestants_timeline(request, pk):
    navigation_task = get_object_or_404(NavigationTask, pk=pk)
    return render(request, "display/contestant_timeline.html", context={"navigation_task": navigation_task})


@guardian.decorators.permission_required('display.view_contest', (Contest, "navigationtask__pk", "pk"))
def clear_future_contestants(request, pk):
    navigation_task = get_object_or_404(NavigationTask, pk=pk)
    now = datetime.datetime.now(datetime.timezone.utc)
    candidates = navigation_task.contestant_set.all()  # filter(takeoff_time__gte=now + datetime.timedelta(minutes=15))
    messages.success(request, f"{candidates.count()} contestants have been deleted")
    candidates.delete()
    return redirect(reverse("navigationtask_detail", kwargs={"pk": navigation_task.pk}))


@guardian.decorators.permission_required('display.change_contest', (Contest, "navigationtask__pk", "pk"))
def add_contest_teams_to_navigation_task(request, pk):
    """
    Add all teams registered for a contest to a task. If the team is already assigned as a contestant, ignore it.

    Apply basic the conflicting of speed, aircraft, and trackers
    """
    TIME_LOCK_MINUTES = 30
    navigation_task = get_object_or_404(NavigationTask, pk=pk)
    form = ContestTeamOptimisationForm()
    if request.method == "POST":
        form = ContestTeamOptimisationForm(request.POST)
        form.fields["contest_teams"].choices = [(str(item.pk), str(item)) for item in
                                                navigation_task.contest.contestteam_set.all()]
        if form.is_valid():
            if not schedule_and_create_contestants(navigation_task,
                                                   [int(item) for item in form.cleaned_data["contest_teams"]],
                                                   form.cleaned_data["tracker_lead_time_minutes"],
                                                   form.cleaned_data["minutes_for_aircraft_switch"],
                                                   form.cleaned_data["minutes_for_tracker_switch"],
                                                   form.cleaned_data["minutes_between_contestants"],
                                                   form.cleaned_data["minutes_for_crew_switch"],
                                                   optimise=form.cleaned_data.get("optimise", False)):
                messages.error(request, "Optimisation failed")
            else:
                messages.success(request, "Optimisation successful")
            return redirect(reverse("navigationtask_contestantstimeline", kwargs={"pk": navigation_task.pk}))
    now = datetime.datetime.now(datetime.timezone.utc)
    selected_existing = []
    used_contest_teams = set()
    for contestant in navigation_task.contestant_set.all():
        selected = False
        if contestant.takeoff_time - datetime.timedelta(
                minutes=TIME_LOCK_MINUTES) > now:
            selected = True
        contest_team = navigation_task.contest.contestteam_set.get(team=contestant.team)
        selected_existing.append((contest_team, f"{contest_team} (at {contestant.takeoff_time})", selected))
        used_contest_teams.add(contest_team.pk)
    selected_existing.extend([(item, str(item), False) for item in
                              navigation_task.contest.contestteam_set.exclude(pk__in=used_contest_teams)])
    # initial = navigation_task.contest.contestteam_set.filter(
    #     team__in=[item.team for item in navigation_task.contestant_set.all()])
    form.fields["contest_teams"].choices = [(str(item[0].pk), item[1]) for item in
                                            selected_existing]
    form.fields["contest_teams"].initial = [str(item[0].pk) for item in selected_existing if item[2]]
    return render(request, "display/contestteam_optimisation_form.html",
                  {"form": form, "navigation_task": navigation_task})


connection = Redis("redis")


class GetDataFromTimeForContestant(RetrieveAPIView):
    permission_classes = [
        ContestantPublicPermissions | permissions.IsAuthenticated & ContestantNavigationTaskContestPermissions]
    lookup_url_kwarg = "contestant_pk"

    def get_queryset(self):
        contests = get_objects_for_user(self.request.user, "display.change_contest",
                                        klass=Contest, accept_global_perms=False)
        return Contestant.objects.filter(Q(navigation_task__contest__in=contests) | Q(navigation_task__is_public=True,
                                                                                      navigation_task__contest__is_public=True))

    def get(self, request, *args, **kwargs):
        contestant = self.get_object()  # type: Contestant
        from_time = request.GET.get("from_time")
        response = cached_generate_data(contestant.pk, from_time)
        return Response(response)


def cached_generate_data(contestant_pk, from_time: Optional[datetime.datetime]) -> Dict:
    key = "{}.{}.{}".format(CONTESTANT_CACHE_KEY, contestant_pk, from_time)
    # response = cache.get(key)
    response = None
    if response is None:
        logger.info("Cache miss {}".format(contestant_pk))
        with redis_lock.Lock(connection, "{}.{}".format(CONTESTANT_CACHE_KEY, contestant_pk), expire=30,
                             auto_renewal=True):
            # response = cache.get(key)
            logger.info("Cache miss second time {}".format(contestant_pk))
            if response is None:
                response = _generate_data(contestant_pk, from_time)
                cache.set(key, response)
                logger.info("Completed updating cash {}".format(contestant_pk))
    return response


influx = InfluxFacade()


def _generate_data(contestant_pk, from_time: Optional[datetime.datetime]):
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
    reduced_data = []
    for item in position_data:
        reduced_data.append({
            "latitude": item["latitude"],
            "longitude": item["longitude"],
            "time": item["time"],
        })
    route_progress = contestant.calculate_progress(global_latest_time)
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


# Everything below he is related to management and requires authentication
def show_route_definition_step(wizard):
    cleaned_data = wizard.get_cleaned_data_for_step("precision_route_import") or {}
    return cleaned_data.get("file_type") == FILE_TYPE_KML and wizard.get_cleaned_data_for_step("task_type").get(
        "task_type") in (NavigationTask.PRECISION, NavigationTask.POKER)


def show_precision_path(wizard):
    return (wizard.get_cleaned_data_for_step("task_type") or {}).get("task_type") in (
        NavigationTask.PRECISION, NavigationTask.POKER)


def show_anr_path(wizard):
    return (wizard.get_cleaned_data_for_step("task_type") or {}).get("task_type") in (NavigationTask.ANR_CORRIDOR,)


class NewNavigationTaskWizard(GuardianPermissionRequiredMixin, SessionWizardView):
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
        ("precision_route_import", PrecisionImportRouteForm),
        ("waypoint_definition", formset_factory(WaypointForm, extra=0)),
        ("task_content", NavigationTaskForm),
        ("precision_override", PrecisionScoreOverrideForm),
        ("anr_corridor_override", ANRCorridorScoreOverrideForm),
    ]
    file_storage = FileSystemStorage(location=os.path.join(settings.MEDIA_ROOT, "importedroutes"))
    condition_dict = {
        "anr_route_import": show_anr_path,
        "precision_route_import": show_precision_path,
        "waypoint_definition": show_route_definition_step,
        "precision_override": show_precision_path,
        "anr_corridor_override": show_anr_path
    }
    templates = {
        "task_type": "display/navigationtaskwizardform.html",
        "anr_route_import": "display/navigationtaskwizardform.html",
        "precision_route_import": "display/navigationtaskwizardform.html",
        "waypoint_definition": "display/waypoints_form.html",
        "task_content": "display/navigationtaskwizardform.html",
        "precision_override": "display/navigationtaskwizardform.html",
        "anr_corridor_override": "display/navigationtaskwizardform.html",
    }

    def get_template_names(self):
        return [self.templates[self.steps.current]]

    def render_done(self, form, **kwargs):
        try:
            return super().render_done(form, **kwargs)
        except ValidationError as e:
            from django.contrib import messages
            messages.error(self.request, str(e))
            return self.render_revalidation_failure("task_type", self.get_form_instance("task_type"), **kwargs)

    def done(self, form_list, **kwargs):
        task_type = self.get_cleaned_data_for_step("task_type")["task_type"]
        if task_type in (NavigationTask.PRECISION, NavigationTask.POKER):
            initial_step_data = self.get_cleaned_data_for_step("precision_route_import")
            use_procedure_turns = self.get_cleaned_data_for_step("task_content")["scorecard"].use_procedure_turns
            if initial_step_data["file_type"] == FILE_TYPE_CSV:
                data = [item.decode(encoding="UTF-8") for item in initial_step_data['file'].readlines()]
                route = create_precision_route_from_csv("route", data[1:], use_procedure_turns)
            elif initial_step_data["file_type"] == FILE_TYPE_FLIGHTCONTEST_GPX:
                route = create_precision_route_from_gpx(initial_step_data["file"].read(), use_procedure_turns)
            else:
                second_step_data = self.get_cleaned_data_for_step("waypoint_definition")
                if initial_step_data["file_type"] == FILE_TYPE_KML:
                    data = self.get_cleaned_data_for_step("precision_route_import")["file"]
                    data.seek(0)
                else:
                    data = None
                route = create_precision_route_from_formset("route", second_step_data,
                                                            use_procedure_turns, data)
        elif task_type == NavigationTask.ANR_CORRIDOR:
            data = self.get_cleaned_data_for_step("anr_route_import")["file"]
            data.seek(0)
            rounded_corners = self.get_cleaned_data_for_step("anr_route_import")["rounded_corners"]
            corridor_width = self.get_cleaned_data_for_step("anr_corridor_override")["corridor_width"]
            route = create_anr_corridor_route_from_kml("route", data, corridor_width, rounded_corners)
        final_data = self.get_cleaned_data_for_step("task_content")
        navigation_task = NavigationTask.objects.create(**final_data, contest=self.contest, route=route)
        # Build score overrides
        if task_type == NavigationTask.PRECISION:
            kwargs["form_dict"].get("precision_override").build_score_override(navigation_task)
        elif task_type == NavigationTask.ANR_CORRIDOR:
            kwargs["form_dict"].get("anr_corridor_override").build_score_override(navigation_task)
        # Update contest location if necessary
        navigation_task_location = route.waypoints[0]
        self.contest.update_position_if_not_set(navigation_task_location.latitude, navigation_task_location.longitude)
        return HttpResponseRedirect(reverse("navigationtask_detail", kwargs={"pk": navigation_task.pk}))

    def get_context_data(self, form, **kwargs):
        context = super().get_context_data(form=form, **kwargs)
        if self.steps.current == "waypoint_definition":
            context["helper"] = WaypointFormHelper()
            context["track_image"] = base64.b64encode(get_basic_track(
                [(item["latitude"], item["longitude"]) for item in
                 self.get_form_initial("waypoint_definition")]).getvalue()).decode(
                "utf-8")
        if self.steps.current == "task_content":
            useful_cards = []
            for scorecard in Scorecard.objects.all():
                if self.get_cleaned_data_for_step("task_type")["task_type"] in scorecard.task_type:
                    useful_cards.append(scorecard.pk)
            form.fields["scorecard"].queryset = Scorecard.objects.filter(pk__in=useful_cards)
            form.fields["scorecard"].initial = Scorecard.objects.filter(pk__in=useful_cards).first()
        return context

    def get_form(self, step=None, data=None, files=None):
        form = super().get_form(step, data, files)
        if step == "waypoint_definition":
            print(len(form))
        return form

    def get_form_initial(self, step):
        if step == "waypoint_definition":
            data = self.get_cleaned_data_for_step("precision_route_import")
            print("Data: {}".format(data))
            if data.get("file_type") == FILE_TYPE_KML:
                # print(" (subfile contents {}".format(data["file"].read()))
                data["file"].seek(0)
                features = load_features_from_kml(data["file"])
                positions = features.get("route", [])
                initial = []
                for index, position in enumerate(positions):
                    initial.append({
                        "name": f"Waypoint {index}",
                        "latitude": position[0],
                        "longitude": position[1],
                    })
                if len(positions) > 0:
                    initial[0]["type"] = STARTINGPOINT
                    initial[0]["name"] = "Starting point"
                    initial[-1]["type"] = FINISHPOINT
                    initial[-1]["name"] = "Finish point"
                return initial
        if step == "anr_corridor_override":
            scorecard = self.get_cleaned_data_for_step("task_content")["scorecard"]
            return ANRCorridorScoreOverrideForm.extract_default_values_from_scorecard(scorecard)
        if step == "precision_override":
            scorecard = self.get_cleaned_data_for_step("task_content")["scorecard"]
            return PrecisionScoreOverrideForm.extract_default_values_from_scorecard(scorecard)
        return {}


class ContestTeamTrackingUpdate(GuardianPermissionRequiredMixin, UpdateView):
    permission_required = ("display.change_contest",)

    def get_permission_object(self):
        contest = get_object_or_404(Contest, pk=self.kwargs.get("contest_pk"))
        return contest

    model = ContestTeam
    form_class = TrackingDataForm

    def get_success_url(self):
        return reverse_lazy('contest_team_list', kwargs={"contest_pk": self.kwargs["contest_pk"]})


class TeamUpdateView(GuardianPermissionRequiredMixin, UpdateView):
    permission_required = ("display.change_contest",)

    def get_permission_object(self):
        contest = get_object_or_404(Contest, pk=self.kwargs.get("contest_pk"))
        return contest

    model = Team
    form_class = TeamForm

    def get_success_url(self):
        return reverse_lazy('contest_team_list', kwargs={"contest_pk": self.kwargs["contest_pk"]})


def create_new_pilot(wizard):
    cleaned = wizard.get_post_data_for_step("member1search") or {}
    return cleaned.get("use_existing_pilot") is None


def create_new_copilot(wizard):
    cleaned = wizard.get_post_data_for_step("member2search") or {}
    return cleaned.get("use_existing_copilot") is None and cleaned.get("skip_copilot") is None


class RegisterTeamWizard(GuardianPermissionRequiredMixin, SessionWizardView):
    permission_required = ("display.change_contest",)

    def get_permission_object(self):
        contest = get_object_or_404(Contest, pk=self.kwargs.get("contest_pk"))
        return contest

    condition_dict = {
        "member1create": create_new_pilot,
        "member2create": create_new_copilot,
    }
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
        "tracking": "display/tracking_form.html"
    }

    def render_done(self, form, **kwargs):
        """
        This method gets called when all forms passed. The method should also
        re-validate all steps to prevent manipulation. If any form fails to
        validate, `render_revalidation_failure` should get called.
        If everything is fine call `done`.
        """
        print(f"All post data: {self.request.session['my_post_data']}")
        return super().render_done(form, **kwargs)

    def post(self, *args, **kwargs):
        if 'my_post_data' not in self.request.session:
            self.request.session['my_post_data'] = {}
        self.request.session['my_post_data'][self.steps.current] = self.request.POST
        print(f"Post data: {self.request.POST}")
        return super().post(*args, **kwargs)

    def get_post_data_for_step(self, step):
        return self.request.session.get('my_post_data', {}).get(step, {})

    def done(self, form_list, **kwargs):
        print(f"All cleaned data: {self.get_all_cleaned_data()}")
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
        club, _ = Club.objects.get_or_create(name=club_data.get("name"),
                                             defaults=club_data)
        if club_data["logo"] is not None:
            club.logo = club_data["logo"]
        club.country = club_data["country"]
        club.save()
        team, created_team = Team.objects.get_or_create(crew=crew, aeroplane=aeroplane, club=club)
        ct, _ = ContestTeam.objects.get_or_create(contest=contest, team=team, defaults=tracking_data)
        if ct.tracking_service == TRACCAR and ct.tracker_device_id and len(ct.tracker_device_id) > 0:
            traccar = get_traccar_instance()
            traccar.get_or_create_device(ct.tracker_device_id, ct.tracker_device_id)
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
        if step == "member1create":
            member_data = self.get_cleaned_data_for_step("member1search")
            return {
                "first_name": member_data["first_name"],
                "last_name": member_data["last_name"],
                "phone": member_data["phone"],
                "email": member_data["email"]
            }
        if step == "member2create":
            member_data = self.get_cleaned_data_for_step("member2search")
            return {
                "first_name": member_data["first_name"],
                "last_name": member_data["last_name"],
                "phone": member_data["phone"],
                "email": member_data["email"]
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
    permission_required = ("display.view_contest",)

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


@guardian.decorators.permission_required('display.change_contest', (Contest, "pk", "contest_pk"))
def remove_team_from_contest(request, contest_pk, team_pk):
    contest = get_object_or_404(Contest, pk=contest_pk)
    team = get_object_or_404(Team, pk=team_pk)
    ContestTeam.objects.filter(contest=contest, team=team).delete()
    return HttpResponseRedirect(reverse("contest_team_list", kwargs={"contest_pk": contest_pk}))


class IsPublicMixin:
    def check_publish_permissions(self, user: User):
        instance = self.get_object()
        if isinstance(instance, Contest):
            if user.has_perm("display.change_contest", instance):
                return True
        if isinstance(instance, NavigationTask):
            if user.has_perm("display.change_contest", instance.contest):
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


class UserPersonViewSet(GenericViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = PersonSerialiser

    def get_object(self):
        instance = self.get_queryset()
        if instance is None:
            raise Http404
        return instance

    def get_queryset(self):
        return Person.objects.get_or_create(email=self.request.user.email,
                                            defaults={"first_name": self.request.user.first_name,
                                                      "last_name": self.request.user.last_name, "validated": False})[0]

    # def create(self, request, *args, **kwargs):
    #     if request.user.person is not None:
    #         raise ValidationError("The user already has a profile")
    #     return super().create(request, *args, **kwargs)
    #
    # def perform_create(self, serializer):
    #     person = serializer.save()
    #     self.request.user.person = person
    #     self.request.user.save()
    #     return person

    def perform_update(self, serializer):
        serializer.save()

    @action(detail=False, methods=["patch"])
    def partial_update_profile(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return self.update_profile(request, *args, **kwargs)

    @action(detail=False, methods=["get"])
    def retrieve_profile(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @action(detail=False, methods=["put"])
    def update_profile(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        if getattr(instance, '_prefetched_objects_cache', None):
            # If 'prefetch_related' has been applied to a queryset, we need to
            # forcibly invalidate the prefetch cache on the instance.
            instance._prefetched_objects_cache = {}

        return Response(serializer.data)


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
        return get_objects_for_user(self.request.user, "display.view_contest",
                                    klass=self.queryset, accept_global_perms=False) | self.queryset.filter(
            is_public=True)

    @action(["GET"], detail=True)
    def navigation_task_summaries(self, request, pk=None, **kwargs):
        contests = get_objects_for_user(self.request.user, "display.view_contest",
                                        klass=Contest, accept_global_perms=False)
        navigation_tasks = NavigationTask.objects.filter(
            Q(contest__in=contests) | Q(is_public=True, contest__is_public=True)).filter(contest_id=pk)
        return Response(NavigationTasksSummarySerialiser(navigation_tasks, many=True).data)

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
        serialiser = self.get_serializer(data=request.data)
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
            serialiser = self.get_serializer(data=request.data, many=isinstance(request.data, list))
            serialiser.is_valid(True)
            serialiser.save()
            return Response(serialiser.data, status=status.HTTP_201_CREATED)
        else:
            ContestSummary.objects.filter(contest=self.get_object()).delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        try:
            context.update({"contest": self.get_object()})
        except AssertionError:
            # This is when we are creating a new contest
            pass
        return context


class NavigationTaskViewSet(IsPublicMixin, ModelViewSet):
    queryset = NavigationTask.objects.all()
    serializer_class = NavigationTaskNestedTeamRouteSerialiser
    permission_classes = [
        NavigationTaskPublicPermissions | (permissions.IsAuthenticated & NavigationTaskContestPermissions)]

    http_method_names = ['get', 'post', 'delete', 'put']

    def get_serializer_context(self):
        context = super().get_serializer_context()
        try:
            context.update({"contest": get_object_or_404(Contest, pk=self.kwargs.get("contest_pk"))})
        except Http404:
            # This has to be handled where we retrieve the context
            pass
        return context

    def get_queryset(self):
        contest_id = self.kwargs.get("contest_pk")
        contests = get_objects_for_user(self.request.user, "display.view_contest",
                                        klass=Contest, accept_global_perms=False)
        return NavigationTask.objects.filter(
            Q(contest__in=contests) | Q(is_public=True, contest__is_public=True)).filter(contest_id=contest_id)

    def create(self, request, *args, **kwargs):
        serialiser = self.get_serializer(data=request.data)
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
    serializer_classes = {
        "track": ContestantTrackWithTrackPointsSerialiser,
        "gpx_track": GpxTrackSerialiser
    }
    default_serialiser_class = ContestantNestedTeamSerialiserWithContestantTrack

    def get_serializer_class(self):
        return self.serializer_classes.get(self.action, self.default_serialiser_class)

    def get_queryset(self):
        navigation_task_id = self.kwargs.get("navigationtask_pk")
        contests = get_objects_for_user(self.request.user, "display.change_contest",
                                        klass=Contest, accept_global_perms=False)
        return Contestant.objects.filter(Q(navigation_task__contest__in=contests) | Q(navigation_task__is_public=True,
                                                                                      navigation_task__contest__is_public=True)).filter(
            navigation_task_id=navigation_task_id)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        try:
            navigation_task = get_object_or_404(NavigationTask, pk=self.kwargs.get("navigationtask_pk"))
            context.update({"navigation_task": navigation_task})
        except Http404:
            # This has to be handled where we retrieve the context
            pass
        return context

    def create(self, request, *args, **kwargs):
        serialiser = self.get_serializer(data=request.data)
        if serialiser.is_valid():
            serialiser.save()
            return Response(serialiser.data)
        return Response(serialiser.errors, status=status.HTTP_400_BAD_REQUEST)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        partial = kwargs.pop('partial', False)
        serialiser = self.get_serializer(instance=instance, data=request.data,
                                         partial=partial)
        if serialiser.is_valid():
            serialiser.save()
            return Response(serialiser.data)
        return Response(serialiser.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["get"])
    def track(self, request, pk=None, **kwargs):
        """
        Returns the GPS track for the contestant
        """
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
        """
        Consumes a FC GPX file that contains the GPS track of a contestant.
        """
        contestant = self.get_object()  # This is important, this is where the object permissions are checked
        ContestantTrack.objects.filter(contestant=contestant).delete()
        contestant.save()  # Creates new contestant track
        # Not required, covered by delete above
        # influx.clear_data_for_contestant(contestant.pk)
        track_file = request.data.get("track_file", None)
        if not track_file:
            raise ValidationError("Missing track_file")
        import_gpx_track.apply_async((contestant.pk, track_file))
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
        response = cached_generate_data(contestant.pk, from_time)
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

    def get_serializer_context(self):
        context = super().get_serializer_context()
        try:
            contest = get_object_or_404(Contest, pk=self.kwargs.get(self.lookup_key))
            context.update({"contest": contest})
        except Http404:
            # This has to be handled below
            pass
        return context

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        serialiser = self.get_serializer(data=request.data)
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


@permission_required('display.change_contest')
def renew_token(request):
    user = request.user
    Token.objects.filter(user=user).delete()
    Token.objects.create(user=user)
    return redirect(reverse("token"))


@permission_required('display.view_contest')
def view_token(request):
    return render(request, "token.html")


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
