import base64
import datetime
import os
from typing import Optional, Dict, Tuple

import dateutil
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import permission_required, login_required
from django.contrib.auth.mixins import (
    PermissionRequiredMixin,
    LoginRequiredMixin,
    UserPassesTestMixin,
)
from django.contrib.auth.models import User

from django.core.cache import cache
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.core.files.storage import FileSystemStorage
from django.db import transaction
from django.db.models import Q
from django.forms import formset_factory
from django.http import HttpResponseRedirect, JsonResponse, HttpResponse, Http404
from django.shortcuts import render, redirect
from django.template.loader import render_to_string
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import (
    ListView,
    DetailView,
    UpdateView,
    CreateView,
    DeleteView,
)
import logging

from formtools.wizard.views import SessionWizardView, CookieWizardView
from guardian.decorators import permission_required as guardian_permission_required
from guardian.mixins import PermissionRequiredMixin as GuardianPermissionRequiredMixin
from guardian.shortcuts import (
    get_objects_for_user,
    assign_perm,
    get_users_with_perms,
    remove_perm,
    get_user_perms,
)
from redis import Redis
from rest_framework import status, permissions, mixins
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action, api_view, permission_classes
import rest_framework.exceptions as drf_exceptions
from rest_framework.generics import RetrieveAPIView, get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.status import HTTP_200_OK
from rest_framework.viewsets import ModelViewSet, ViewSet, GenericViewSet

from display.convert_flightcontest_gpx import (
    create_precision_route_from_gpx,
    create_precision_route_from_csv,
    create_precision_route_from_formset,
    create_anr_corridor_route_from_kml,
    load_features_from_kml,
    create_landing_line_from_kml,
)
from display.forms import (
    PrecisionImportRouteForm,
    WaypointForm,
    NavigationTaskForm,
    FILE_TYPE_CSV,
    FILE_TYPE_FLIGHTCONTEST_GPX,
    FILE_TYPE_KML,
    ContestantForm,
    ContestForm,
    Member1SearchForm,
    TeamForm,
    PersonForm,
    Member2SearchForm,
    AeroplaneSearchForm,
    ClubSearchForm,
    ContestantMapForm,
    LANDSCAPE,
    MapForm,
    WaypointFormHelper,
    TaskTypeForm,
    ANRCorridorImportRouteForm,
    ANRCorridorScoreOverrideForm,
    PrecisionScoreOverrideForm,
    TrackingDataForm,
    ContestTeamOptimisationForm,
    AssignPokerCardForm,
    ChangeContestPermissionsForm,
    AddContestPermissionsForm,
    RouteCreationForm,
    LandingImportRouteForm,
    PNG,
    ShareForm,
    SCALE_TO_FIT,
)
from display.map_plotter import (
    plot_route,
    get_basic_track,
    A4,
    get_country_code_from_location,
    country_code_to_map_source,
    generate_turning_point_image,
    generate_flight_orders,
)
from display.models import (
    NavigationTask,
    Route,
    Contestant,
    Contest,
    Team,
    ContestantTrack,
    Person,
    Aeroplane,
    Club,
    Crew,
    ContestTeam,
    Task,
    TaskSummary,
    ContestSummary,
    TaskTest,
    TeamTestScore,
    TRACCAR,
    Scorecard,
    MyUser,
    PlayingCard,
    TRACKING_DEVICE,
    STARTINGPOINT,
    FINISHPOINT,
    ScoreLogEntry,
    EmailMapLink,
    EditableRoute,
)
from display.permissions import (
    ContestPermissions,
    NavigationTaskContestPermissions,
    ContestantPublicPermissions,
    NavigationTaskPublicPermissions,
    ContestPublicPermissions,
    ContestantNavigationTaskContestPermissions,
    RoutePermissions,
    ContestModificationPermissions,
    ContestPermissionsWithoutObjects,
    ChangeContestKeyPermissions,
    TaskContestPermissions,
    TaskContestPublicPermissions,
    TaskTestContestPublicPermissions,
    TaskTestContestPermissions,
    ContestPublicModificationPermissions,
    OrganiserPermission,
    ContestTeamContestPermissions,
    NavigationTaskSelfManagementPermissions,
    NavigationTaskPublicPutPermissions,
    EditableRoutePermission,
)
from display.schedule_contestants import schedule_and_create_contestants
from display.serialisers import (
    ContestantTrackSerialiser,
    ExternalNavigationTaskNestedTeamSerialiser,
    ContestSerialiser,
    NavigationTaskNestedTeamRouteSerialiser,
    RouteSerialiser,
    ContestantTrackWithTrackPointsSerialiser,
    TeamResultsSummarySerialiser,
    ContestResultsDetailsSerialiser,
    TeamNestedSerialiser,
    GpxTrackSerialiser,
    PersonSerialiser,
    ExternalNavigationTaskTeamIdSerialiser,
    ContestantNestedTeamSerialiserWithContestantTrack,
    AeroplaneSerialiser,
    ClubSerialiser,
    ContestTeamNestedSerialiser,
    TaskWithoutReferenceNestedSerialiser,
    ContestSummaryWithoutReferenceSerialiser,
    ContestTeamSerialiser,
    NavigationTasksSummarySerialiser,
    TaskSummaryWithoutReferenceSerialiser,
    TeamTestScoreWithoutReferenceSerialiser,
    TaskTestWithoutReferenceNestedSerialiser,
    TaskSerialiser,
    TaskTestSerialiser,
    ContestantSerialiser,
    TrackAnnotationSerialiser,
    ScoreLogEntrySerialiser,
    GateCumulativeScoreSerialiser,
    PlayingCardSerialiser,
    ContestTeamManagementSerialiser,
    SignupSerialiser,
    PersonSignUpSerialiser,
    SharingSerialiser,
    SelfManagementSerialiser,
    OngoingNavigationSerialiser,
    EditableRouteSerialiser,
)
from display.show_slug_choices import ShowChoicesMetadata
from display.tasks import import_gpx_track, generate_and_notify_flight_order
from display.traccar_factory import get_traccar_instance
from influx_facade import InfluxFacade
from live_tracking_map import settings
from websocket_channels import WebsocketFacade

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
    my_contests = get_objects_for_user(
        request.user, "display.view_contest", accept_global_perms=False
    )
    public_contests = Contest.objects.filter(is_public=True)
    try:
        navigation_task = NavigationTask.objects.get(
            Q(contest__in=my_contests) | Q(contest__in=public_contests, is_public=True),
            pk=pk,
        )
    except ObjectDoesNotExist:
        raise Http404
    return render(
        request,
        "display/root.html",
        {
            "contest_id": navigation_task.contest.pk,
            "navigation_task_id": pk,
            "live_mode": "true",
            "display_map": "true",
            "display_table": "false",
            "skip_nav": True,
            "playback": "false",
        },
    )


def frontend_playback_map(request, pk):
    my_contests = get_objects_for_user(
        request.user, "display.view_contest", accept_global_perms=False
    )
    public_contests = Contest.objects.filter(is_public=True)
    try:
        navigation_task = NavigationTask.objects.get(
            Q(contest__in=my_contests) | Q(contest__in=public_contests, is_public=True),
            pk=pk,
        )
    except ObjectDoesNotExist:
        raise Http404
    return render(
        request,
        "display/root.html",
        {
            "contest_id": navigation_task.contest.pk,
            "navigation_task_id": pk,
            "live_mode": "true",
            "display_map": "true",
            "display_table": "false",
            "skip_nav": True,
            "playback": "true",
        },
    )


def global_map(request):
    visited = request.session.get("visited", False)
    request.session["visited"] = True
    return render(
        request,
        "display/globalmap.html",
        {"skip_nav": False, "first_visit": not visited},
    )


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
                "type": "image/png",
            }
        ],
        "start_url": "/",
        "display": "standalone",
        "orientation": "landscape",
    }
    return JsonResponse(data)


@api_view(["POST"])
@permission_classes([IsAuthenticated, ContestPermissionsWithoutObjects])
def auto_complete_aeroplane(request):
    if request.is_ajax():
        request_number = int(request.data.get("request"))
        if request_number == 1:
            q = request.data.get("search", "")
            search_qs = Aeroplane.objects.filter(registration__icontains=q)
            result = [str(item.registration) for item in search_qs]
            return Response(result)
        else:
            q = request.data.get("search", "")
            search_qs = Aeroplane.objects.filter(registration=q)
            serialiser = AeroplaneSerialiser(search_qs, many=True)
            return Response(serialiser.data)
    raise drf_exceptions.MethodNotAllowed


@api_view(["POST"])
@permission_classes([IsAuthenticated, ContestPermissionsWithoutObjects])
def auto_complete_club(request):
    if request.is_ajax():
        request_number = int(request.data.get("request"))
        if request_number == 1:
            q = request.data.get("search", "")
            search_qs = Club.objects.filter(name__icontains=q)
            result = [
                {"label": "{} ({})".format(item.name, item.country), "value": item.name}
                for item in search_qs
            ]
            return Response(result)
        else:
            q = request.data.get("search", "")
            search_qs = Club.objects.filter(name=q)
            serialiser = ClubSerialiser(search_qs, many=True)
            return Response(serialiser.data)
    raise drf_exceptions.MethodNotAllowed


@api_view(["POST"])
@permission_classes([IsAuthenticated, ContestPermissionsWithoutObjects])
def auto_complete_person_phone(request):
    if request.is_ajax():
        request_number = int(request.data.get("request"))
        if request_number == 1:
            q = request.data.get("search", "")
            search_qs = Person.objects.filter(phone__contains=q)
            result = [str(item.phone) for item in search_qs]
            return Response(result)
        else:
            q = request.data.get("search", "")
            search_qs = Person.objects.filter(phone=q)
            serialiser = PersonSerialiser(search_qs, many=True)
            return Response(serialiser.data)
    raise drf_exceptions.MethodNotAllowed


@api_view(["POST"])
@permission_classes([IsAuthenticated, ContestPermissionsWithoutObjects])
def auto_complete_person_id(request):
    if request.is_ajax():
        request_number = int(request.data.get("request"))
        if request_number == 1:
            q = request.data.get("search", "")
            search_qs = Person.objects.filter(pk=q)
            result = [str(item.phone) for item in search_qs]
            return Response(result)
        else:
            q = request.data.get("search", "")
            search_qs = Person.objects.filter(pk=q)
            serialiser = PersonSerialiser(search_qs, many=True)
            return Response(serialiser.data)
    raise drf_exceptions.MethodNotAllowed


@api_view(["POST"])
@permission_classes([IsAuthenticated, ContestPermissionsWithoutObjects])
def auto_complete_person_first_name(request):
    if request.is_ajax():
        request_number = int(request.data.get("request"))
        if request_number == 1:
            q = request.data.get("search", "")
            search_qs = Person.objects.filter(first_name__icontains=q)
            result = [
                {
                    "label": "{} {}".format(item.first_name, item.last_name),
                    "value": item.pk,
                }
                for item in search_qs
            ]
            return Response(result)
        else:
            q = request.data.get("search", "")
            search_qs = Person.objects.filter(pk=q)
            serialiser = PersonSerialiser(search_qs, many=True)
            return Response(serialiser.data)
    raise drf_exceptions.MethodNotAllowed


@api_view(["POST"])
@permission_classes([IsAuthenticated, ContestPermissionsWithoutObjects])
def auto_complete_person_last_name(request):
    if request.is_ajax():
        request_number = int(request.data.get("request"))
        if request_number == 1:
            q = request.data.get("search", "")
            search_qs = Person.objects.filter(last_name__icontains=q)
            result = [
                {
                    "label": "{} {}".format(item.first_name, item.last_name),
                    "value": item.pk,
                }
                for item in search_qs
            ]
            return Response(result)
        else:
            q = request.data.get("search", "")
            search_qs = Person.objects.filter(pk=q)
            serialiser = PersonSerialiser(search_qs, many=True)
            return Response(serialiser.data)
    raise drf_exceptions.MethodNotAllowed


@api_view(["POST"])
@permission_classes([IsAuthenticated, ContestPermissionsWithoutObjects])
def auto_complete_person_email(request):
    if request.is_ajax():
        request_number = int(request.data.get("request"))
        if request_number == 1:
            q = request.data.get("search", "")
            search_qs = Person.objects.filter(email__icontains=q)
            result = [item.email for item in search_qs]
            return Response(result)
        else:
            q = request.data.get("search", "")
            search_qs = Person.objects.filter(email=q)
            serialiser = PersonSerialiser(search_qs, many=True)
            return Response(serialiser.data)
    raise drf_exceptions.MethodNotAllowed


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_persons_for_signup(request):
    return Response(
        PersonSignUpSerialiser(
            Person.objects.exclude(email=request.user.email), many=True
        ).data
    )


def tracking_qr_code_view(request, pk):
    url = reverse("frontend_view_map", kwargs={"pk": pk})
    return render(
        request,
        "display/tracking_qr_code.html",
        {
            "url": "https://airsports.no{}".format(url),
            "navigation_task": NavigationTask.objects.get(pk=pk),
        },
    )


@guardian_permission_required("display.change_contest", (Contest, "pk", "pk"))
def create_route_test(request, pk):
    form = RouteCreationForm()
    return render(request, "display/route_creation_form.html", {"form": form})


@guardian_permission_required(
    "display.change_contest", (Contest, "navigationtask__contestant__pk", "pk")
)
def contestant_card_remove(request, pk, card_pk):
    contestant = get_object_or_404(Contestant, pk=pk)
    PlayingCard.remove_contestant_card(contestant, card_pk)
    return redirect(reverse("contestant_cards_list", kwargs={"pk": contestant.pk}))


@guardian_permission_required(
    "display.change_contest", (Contest, "navigationtask__contestant__pk", "pk")
)
def contestant_cards_list(request, pk):
    contestant = get_object_or_404(Contestant, pk=pk)
    waypoint_names = [
        waypoint.name for waypoint in contestant.navigation_task.route.waypoints
    ]

    if request.method == "POST":
        form = AssignPokerCardForm(request.POST)
        form.fields["waypoint"].choices = [
            (str(index), item.name)
            for index, item in enumerate(contestant.navigation_task.route.waypoints)
        ]
        if form.is_valid():
            waypoint_index = int(form.cleaned_data["waypoint"])
            waypoint_name = waypoint_names[waypoint_index]
            card = form.cleaned_data["playing_card"]
            random_card = card == "random"
            if random_card:
                card = PlayingCard.get_random_unique_card(contestant)
            PlayingCard.add_contestant_card(
                contestant, card, waypoint_name, waypoint_index
            )
    cards = contestant.playingcard_set.all().order_by("pk")
    for card in cards:
        print(card)
    try:
        latest_waypoint_index = max([card.waypoint_index for card in cards])
    except ValueError:
        latest_waypoint_index = -1
    print(latest_waypoint_index)
    try:
        next_waypoint_name = waypoint_names[latest_waypoint_index + 1]
    except IndexError:
        next_waypoint_name = None
    print(next_waypoint_name)
    form = AssignPokerCardForm()
    form.fields["waypoint"].choices = [
        (str(index), item.name)
        for index, item in enumerate(contestant.navigation_task.route.waypoints)
    ]
    if next_waypoint_name is not None:
        form.fields["waypoint"].initial = str(latest_waypoint_index + 1)
    cards = sorted(cards, key=lambda c: c.waypoint_index)
    relative_score, hand_description = PlayingCard.get_relative_score(contestant)
    return render(
        request,
        "display/contestant_cards_list.html",
        {
            "cards": cards,
            "contestant": contestant,
            "form": form,
            "current_relative_score": f"{relative_score:.2f}",
            "current_hand": hand_description,
        },
    )


@guardian_permission_required("display.change_contest", (Contest, "pk", "pk"))
def share_contest(request, pk):
    contest = get_object_or_404(Contest, pk=pk)
    if request.method == "POST":
        form = ShareForm(request.POST)
        if form.is_valid():
            if form.cleaned_data["publicity"] == ShareForm.PUBLIC:
                contest.make_public()
            elif form.cleaned_data["publicity"] == ShareForm.UNLISTED:
                contest.make_unlisted()
            elif form.cleaned_data["publicity"] == ShareForm.PRIVATE:
                contest.make_private()
            return HttpResponseRedirect(
                reverse("contest_details", kwargs={"pk": contest.pk})
            )
    if contest.is_public and contest.is_featured:
        initial = ShareForm.PUBLIC
    elif contest.is_public and not contest.is_featured:
        initial = ShareForm.UNLISTED
    else:
        initial = ShareForm.PRIVATE
    form = ShareForm(initial={"publicity": initial})
    return render(
        request, "display/share_contest_form.html", {"form": form, "contest": contest}
    )


@guardian_permission_required(
    "display.change_contest", (Contest, "navigationtask__pk", "pk")
)
def share_navigation_task(request, pk):
    navigation_task = get_object_or_404(NavigationTask, pk=pk)
    if request.method == "POST":
        form = ShareForm(request.POST)
        if form.is_valid():
            if form.cleaned_data["publicity"] == ShareForm.PUBLIC:
                navigation_task.make_public()
            elif form.cleaned_data["publicity"] == ShareForm.UNLISTED:
                navigation_task.make_unlisted()
            elif form.cleaned_data["publicity"] == ShareForm.PRIVATE:
                navigation_task.make_private()
            return HttpResponseRedirect(
                reverse("navigationtask_detail", kwargs={"pk": navigation_task.pk})
            )
    if navigation_task.is_public and navigation_task.is_featured:
        initial = ShareForm.PUBLIC
    elif navigation_task.is_public and not navigation_task.is_featured:
        initial = ShareForm.UNLISTED
    else:
        initial = ShareForm.PRIVATE
    form = ShareForm(initial={"publicity": initial})
    return render(
        request,
        "display/share_navigationtask_form.html",
        {"form": form, "navigation_task": navigation_task},
    )


# @guardian_permission_required('display.change_contest', (Contest, "navigationtask__contestant__pk", "pk"))
# def view_cards(request, pk):
@guardian_permission_required(
    "display.change_contest", (Contest, "navigationtask__pk", "pk")
)
def refresh_editable_route_navigation_task(request, pk):
    navigation_task = get_object_or_404(NavigationTask, pk=pk)
    try:
        navigation_task.refresh_editable_route()
        messages.success(request, "Route refreshed")
    except ValidationError as e:
        messages.error(request, str(e))
    return HttpResponseRedirect(
        reverse("navigationtask_detail", kwargs={"pk": navigation_task.pk})
    )


@guardian_permission_required(
    "display.view_contest", (Contest, "navigationtask__contestant__pk", "pk")
)
def get_contestant_rules(request, pk):
    contestant = get_object_or_404(Contestant, pk=pk)
    return render(
        request,
        "display/contestant_rules.html",
        {
            "contestant": contestant,
            "rules": contestant.navigation_task.scorecard.scores_display(contestant),
        },
    )


@guardian_permission_required(
    "display.view_contest", (Contest, "navigationtask__contestant__pk", "pk")
)
def get_contestant_map(request, pk):
    if request.method == "POST":
        form = ContestantMapForm(request.POST)
        if form.is_valid():
            contestant = get_object_or_404(Contestant, pk=pk)
            map_image, pdf_image = plot_route(
                contestant.navigation_task,
                form.cleaned_data["size"],
                zoom_level=form.cleaned_data["zoom_level"],
                landscape=int(form.cleaned_data["orientation"]) == LANDSCAPE,
                contestant=contestant,
                annotations=form.cleaned_data["include_annotations"],
                waypoints_only=False,
                dpi=form.cleaned_data["dpi"],
                scale=int(form.cleaned_data["scale"]),
                map_source=form.cleaned_data["map_source"],
                line_width=float(form.cleaned_data["line_width"]),
                colour=form.cleaned_data["colour"],
            )
            if int(form.cleaned_data["output_type"]) == PNG:
                response = HttpResponse(map_image, content_type="image/png")
                response["Content-Disposition"] = f"attachment; filename=map.png"
            else:
                response = HttpResponse(pdf_image, content_type="application/pdf")
                response["Content-Disposition"] = f"attachment; filename=map.pdf"
            return response
    form = ContestantMapForm()
    return render(request, "display/map_form.html", {"form": form})


@guardian_permission_required(
    "display.view_contest", (Contest, "navigationtask__contestant__pk", "pk")
)
def get_contestant_default_map(request, pk):
    contestant = get_object_or_404(Contestant, pk=pk)
    waypoint = contestant.navigation_task.route.waypoints[0]  # type: Waypoint
    country_code = get_country_code_from_location(waypoint.latitude, waypoint.longitude)
    map_source = country_code_to_map_source(country_code)
    map_image, pdf_image = plot_route(
        contestant.navigation_task,
        A4,
        zoom_level=12,
        landscape=LANDSCAPE,
        contestant=contestant,
        annotations=True,
        waypoints_only=False,
        dpi=300,
        scale=SCALE_TO_FIT,
        map_source=map_source,
        line_width=1,
        colour="#0000ff",
    )
    response = HttpResponse(pdf_image, content_type="application/pdf")
    response["Content-Disposition"] = f"attachment; filename=map.pdf"
    return response


def get_contestant_email_flight_orders_link(request, key):
    map_link = get_object_or_404(EmailMapLink, id=key)
    # orders = generate_flight_orders(map_link.contestant)
    response = HttpResponse(map_link.orders, content_type="application/pdf")
    response["Content-Disposition"] = f"attachment; filename=flight_orders.pdf"
    return response


def get_contestant_email_flying_orders_link(request, pk):
    contestant = get_object_or_404(Contestant, id=pk)
    report = generate_flight_orders(contestant)
    response = HttpResponse(report, content_type="application/pdf")
    response["Content-Disposition"] = f"attachment; filename=flight_orders.pdf"
    return response


@guardian_permission_required(
    "display.view_contest", (Contest, "navigationtask__pk", "pk")
)
def broadcast_navigation_task_orders(request, pk):
    navigation_task = get_object_or_404(NavigationTask, pk=pk)
    contestants = navigation_task.contestant_set.filter(
        tracker_start_time__gt=datetime.datetime.now(datetime.timezone.utc)
    )
    for contestant in contestants:
        generate_and_notify_flight_order.apply_async(
            (
                contestant.pk,
                contestant.team.crew.member1.email,
                contestant.team.crew.member1.first_name,
            )
        )
    messages.success(
        request,
        f"Started generating flight orders for {contestants.count()} contestants",
    )
    return HttpResponseRedirect(
        reverse("navigationtask_detail", kwargs={"pk": navigation_task.pk})
    )


@guardian_permission_required(
    "display.view_contest", (Contest, "navigationtask__pk", "pk")
)
def get_navigation_task_map(request, pk):
    if request.method == "POST":
        form = MapForm(request.POST)
        if form.is_valid():
            navigation_task = get_object_or_404(NavigationTask, pk=pk)
            print(form.cleaned_data)
            map_image, pdf_image = plot_route(
                navigation_task,
                form.cleaned_data["size"],
                zoom_level=form.cleaned_data["zoom_level"],
                landscape=int(form.cleaned_data["orientation"]) == LANDSCAPE,
                waypoints_only=form.cleaned_data["include_only_waypoints"],
                dpi=form.cleaned_data["dpi"],
                scale=int(form.cleaned_data["scale"]),
                map_source=form.cleaned_data["map_source"],
                line_width=float(form.cleaned_data["line_width"]),
                colour=form.cleaned_data["colour"],
            )
            if int(form.cleaned_data["output_type"]) == PNG:
                response = HttpResponse(map_image, content_type="image/png")
                response["Content-Disposition"] = f"attachment; filename=map.png"
            else:
                response = HttpResponse(pdf_image, content_type="application/pdf")
                response["Content-Disposition"] = f"attachment; filename=map.pdf"
            return response
    form = MapForm()
    return render(request, "display/map_form.html", {"form": form})


@guardian_permission_required("display.change_contest", (Contest, "pk", "pk"))
def list_contest_permissions(request, pk):
    contest = get_object_or_404(Contest, pk=pk)
    users_and_permissions = get_users_with_perms(contest, attach_perms=True)
    users = []
    for user in users_and_permissions.keys():
        if user == request.user:
            continue
        data = {item: True for item in users_and_permissions[user]}
        data["email"] = user.email
        data["pk"] = user.pk
        users.append(data)
    return render(
        request,
        "display/contest_permissions.html",
        {"users": users, "contest": contest},
    )


@guardian_permission_required("display.change_contest", (Contest, "pk", "pk"))
def delete_user_contest_permissions(request, pk, user_pk):
    contest = get_object_or_404(Contest, pk=pk)
    user = get_object_or_404(MyUser, pk=user_pk)
    permissions = ["change_contest", "view_contest", "delete_contest"]
    for permission in permissions:
        remove_perm(f"display.{permission}", user, contest)
    return redirect(reverse("contest_permissions_list", kwargs={"pk": pk}))


@guardian_permission_required("display.change_contest", (Contest, "pk", "pk"))
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


@guardian_permission_required("display.change_contest", (Contest, "pk", "pk"))
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
        objects = get_objects_for_user(
            self.request.user, "display.view_contest", accept_global_perms=False
        )
        print(list(objects))
        return objects


@guardian_permission_required(
    "display.change_contest", (Contest, "navigationtask__contestant__pk", "pk")
)
def terminate_contestant_calculator(request, pk):
    contestant = get_object_or_404(Contestant, pk=pk)
    contestant.request_calculator_termination()
    messages.success(request, "Calculator termination requested")
    return HttpResponseRedirect(
        reverse("navigationtask_detail", kwargs={"pk": contestant.navigation_task.pk})
    )


@guardian_permission_required(
    "display.view_contest", (Contest, "navigationtask__pk", "pk")
)
def view_navigation_task_rules(request, pk):
    navigation_task = get_object_or_404(NavigationTask, pk=pk)
    return render(
        request, "display/navigationtask_rules.html", {"object": navigation_task}
    )


@guardian_permission_required("display.change_contest", (Contest, "pk", "pk"))
def clear_results_service(request, pk):
    contest = get_object_or_404(Contest, pk=pk)
    contest.task_set.all().delete()
    contest.contestsummary_set.all().delete()
    messages.success(
        request, "Successfully cleared contest results from results service"
    )
    return HttpResponseRedirect(reverse("contest_details", kwargs={"pk": pk}))


class ContestCreateView(PermissionRequiredMixin, CreateView):
    model = Contest
    permission_required = ("display.add_contest",)
    form_class = ContestForm

    def form_valid(self, form):
        instance = form.save(commit=False)  # type: Contest
        instance.start_time = instance.time_zone.localize(
            instance.start_time.replace(tzinfo=None)
        )
        instance.finish_time = instance.time_zone.localize(
            instance.finish_time.replace(tzinfo=None)
        )
        instance.save()
        assign_perm("delete_contest", self.request.user, instance)
        assign_perm("view_contest", self.request.user, instance)
        assign_perm("add_contest", self.request.user, instance)
        assign_perm("change_contest", self.request.user, instance)
        self.object = instance
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse("contest_details", kwargs={"pk": self.object.pk})


class ContestDetailView(
    ContestTimeZoneMixin, GuardianPermissionRequiredMixin, DetailView
):
    model = Contest
    permission_required = ("display.view_contest",)


class ContestUpdateView(
    ContestTimeZoneMixin, GuardianPermissionRequiredMixin, UpdateView
):
    model = Contest
    permission_required = ("display.change_contest",)
    form_class = ContestForm

    def get_permission_object(self):
        return self.get_object()

    def get_success_url(self):
        return reverse("contest_details", kwargs={"pk": self.get_object().pk})


class ContestDeleteView(GuardianPermissionRequiredMixin, DeleteView):
    model = Contest
    permission_required = ("display.delete_contest",)
    template_name = "model_delete.html"
    success_url = reverse_lazy("contest_list")

    def get_permission_object(self):
        return self.get_object()


class NavigationTaskDetailView(
    NavigationTaskTimeZoneMixin, GuardianPermissionRequiredMixin, DetailView
):
    model = NavigationTask
    permission_required = ("display.view_contest",)

    def get_permission_object(self):
        return self.get_object().contest


class NavigationTaskUpdateView(
    NavigationTaskTimeZoneMixin, GuardianPermissionRequiredMixin, UpdateView
):
    model = NavigationTask
    permission_required = ("display.change_contest",)
    form_class = NavigationTaskForm

    def get_permission_object(self):
        return self.get_object().contest

    def get_success_url(self):
        return reverse("navigationtask_detail", kwargs={"pk": self.get_object().pk})


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
        return reverse("contest_details", kwargs={"pk": self.get_object().contest.pk})


@guardian_permission_required(
    "display.change_contest",
    (Contest, "navigationtask__contestant__scorelogentry__pk", "pk"),
)
def delete_score_item(request, pk):
    entry = get_object_or_404(ScoreLogEntry, pk=pk)
    contestant = entry.contestant
    contestant.contestanttrack.update_score(
        contestant.contestanttrack.score - entry.points
    )
    entry.delete()
    # Push the updated data so that it is reflected on the contest track
    wf = WebsocketFacade()
    wf.transmit_score_log_entry(contestant)
    wf.transmit_annotations(contestant)
    wf.transmit_basic_information(contestant)
    return HttpResponseRedirect(
        reverse("contestant_gate_times", kwargs={"pk": contestant.pk})
    )


class ContestantGateTimesView(
    ContestantTimeZoneMixin, GuardianPermissionRequiredMixin, DetailView
):
    model = Contestant
    permission_required = ("display.view_contest",)
    template_name = "display/contestant_gate_times.html"

    def get_permission_object(self):
        return self.get_object().navigation_task.contest

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        log = {}
        for item in self.object.scorelogentry_set.all():  # type: ScoreLogEntry
            if item.gate not in log:
                log[item.gate] = []
            log[item.gate].append(
                {
                    "text": "{} points {}".format(item.points, item.message),
                    "pk": item.pk,
                }
            )
        context["log"] = log
        actual_times = {}
        for item in self.object.actualgatetime_set.all():
            actual_times[item.gate] = item.time
        context["actual_times"] = actual_times
        return context


class ContestantUpdateView(
    ContestantTimeZoneMixin, GuardianPermissionRequiredMixin, UpdateView
):
    form_class = ContestantForm
    model = Contestant
    permission_required = ("display.change_contest",)

    def get_form_kwargs(self):
        arguments = super().get_form_kwargs()
        arguments["navigation_task"] = self.get_object().navigation_task
        return arguments

    def get_success_url(self):
        return reverse(
            "navigationtask_detail", kwargs={"pk": self.get_object().navigation_task.pk}
        )

    def get_permission_object(self):
        return self.get_object().navigation_task.contest


class ContestantDeleteView(GuardianPermissionRequiredMixin, DeleteView):
    model = Contestant
    permission_required = ("display.change_contest",)
    template_name = "model_delete.html"

    def get_success_url(self):
        return reverse(
            "navigationtask_detail", kwargs={"pk": self.get_object().navigation_task.pk}
        )

    def get_permission_object(self):
        return self.get_object().navigation_task.contest


class ContestantCreateView(GuardianPermissionRequiredMixin, CreateView):
    form_class = ContestantForm
    model = Contestant
    permission_required = ("display.change_contest",)

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.navigation_task = get_object_or_404(
            NavigationTask, pk=self.kwargs.get("navigationtask_pk")
        )
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
        return reverse(
            "navigationtask_detail", kwargs={"pk": self.kwargs.get("navigationtask_pk")}
        )

    def get_permission_object(self):
        return self.navigation_task.contest

    def form_valid(self, form):
        object = form.save(commit=False)  # type: Contestant
        object.navigation_task = self.navigation_task
        object.save()
        return HttpResponseRedirect(self.get_success_url())


@api_view(["GET"])
@guardian_permission_required(
    "display.view_contest", (Contest, "navigationtask__pk", "pk")
)
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
        rows.append(
            {
                "c": [
                    {"v": contestant.team.aeroplane.registration},
                    {"v": str(contestant)},
                    {"v": contestant.takeoff_time},
                    {"v": contestant.finished_by_time},
                ]
            }
        )

    return Response({"cols": columns, "rows": rows})


@guardian_permission_required(
    "display.view_contest", (Contest, "navigationtask__pk", "pk")
)
def render_contestants_timeline(request, pk):
    navigation_task = get_object_or_404(NavigationTask, pk=pk)
    return render(
        request,
        "display/contestant_timeline.html",
        context={"navigation_task": navigation_task},
    )


@guardian_permission_required(
    "display.view_contest", (Contest, "navigationtask__pk", "pk")
)
def clear_future_contestants(request, pk):
    navigation_task = get_object_or_404(NavigationTask, pk=pk)
    now = datetime.datetime.now(datetime.timezone.utc)
    candidates = (
        navigation_task.contestant_set.all()
    )  # filter(takeoff_time__gte=now + datetime.timedelta(minutes=15))
    messages.success(request, f"{candidates.count()} contestants have been deleted")
    candidates.delete()
    return redirect(reverse("navigationtask_detail", kwargs={"pk": navigation_task.pk}))


@guardian_permission_required(
    "display.change_contest", (Contest, "navigationtask__pk", "pk")
)
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
        form.fields["contest_teams"].choices = [
            (str(item.pk), str(item))
            for item in navigation_task.contest.contestteam_set.all()
        ]
        if form.is_valid():
            try:
                if not schedule_and_create_contestants(
                        navigation_task,
                        [int(item) for item in form.cleaned_data["contest_teams"]],
                        form.cleaned_data["tracker_lead_time_minutes"],
                        form.cleaned_data["minutes_for_aircraft_switch"],
                        form.cleaned_data["minutes_for_tracker_switch"],
                        form.cleaned_data["minutes_between_contestants"],
                        form.cleaned_data["minutes_for_crew_switch"],
                        optimise=form.cleaned_data.get("optimise", False),
                ):
                    messages.error(request, "Optimisation failed")
                else:
                    messages.success(request, "Optimisation successful")
            except ValidationError as v:
                messages.error(request, f"Failed validating created contestant: {v}")
            return redirect(
                reverse(
                    "navigationtask_contestantstimeline",
                    kwargs={"pk": navigation_task.pk},
                )
            )
    now = datetime.datetime.now(datetime.timezone.utc)
    selected_existing = []
    used_contest_teams = set()
    for contestant in navigation_task.contestant_set.all():
        selected = True
        # if contestant.takeoff_time - datetime.timedelta(
        #         minutes=TIME_LOCK_MINUTES) > now:
        #     selected = True
        try:
            contest_team = navigation_task.contest.contestteam_set.get(
                team=contestant.team
            )
        except ObjectDoesNotExist:
            contest_team = ContestTeam.objects.create(
                team=contestant.team,
                contest=contestant.navigation_task.contest,
                air_speed=contestant.air_speed,
                tracking_device=contestant.tracking_device,
                tracker_device_id=contestant.tracker_device_id,
                tracking_service=contestant.tracking_service,
            )
        selected_existing.append(
            (contest_team, f"{contest_team} (at {contestant.takeoff_time})", selected)
        )
        used_contest_teams.add(contest_team.pk)
    selected_existing.extend(
        [
            (item, str(item), False)
            for item in navigation_task.contest.contestteam_set.exclude(
            pk__in=used_contest_teams
        )
        ]
    )
    # initial = navigation_task.contest.contestteam_set.filter(
    #     team__in=[item.team for item in navigation_task.contestant_set.all()])
    form.fields["contest_teams"].choices = [
        (str(item[0].pk), item[1]) for item in selected_existing
    ]
    form.fields["contest_teams"].initial = [
        str(item[0].pk) for item in selected_existing if item[2]
    ]
    return render(
        request,
        "display/contestteam_optimisation_form.html",
        {"form": form, "navigation_task": navigation_task},
    )


if settings.PRODUCTION:
    connection = Redis(unix_socket_path="/tmp/docker/redis.sock")
else:
    connection = Redis("redis")


def cached_generate_data(contestant_pk) -> Dict:
    return _generate_data(contestant_pk)


influx = InfluxFacade()


def _generate_data(contestant_pk):
    LIMIT = None
    contestant = get_object_or_404(Contestant, pk=contestant_pk)  # type: Contestant
    from_time_datetime = datetime.datetime(2016, 1, 1, tzinfo=datetime.timezone.utc)
    result_set = influx.get_positions_for_contestant(
        contestant_pk, from_time_datetime, limit=LIMIT
    )
    logger.info("Completed fetching positions for {}".format(contestant.pk))
    position_data = list(result_set.get_points(tags={"contestant": str(contestant.pk)}))
    if len(position_data) > 0:
        global_latest_time = dateutil.parser.parse(position_data[-1]["time"])
    else:
        global_latest_time = from_time_datetime
    annotations = TrackAnnotationSerialiser(
        contestant.trackannotation_set.all(), many=True
    ).data
    reduced_data = []
    progress = 0
    for index, item in enumerate(position_data):
        if index % 30 == 0:
            progress = contestant.calculate_progress(
                dateutil.parser.parse(item["time"]), ignore_finished=True
            )
        reduced_data.append(
            {
                "latitude": item["latitude"],
                "longitude": item["longitude"],
                "time": item["time"],
                "progress": progress,
            }
        )
    route_progress = contestant.calculate_progress(global_latest_time)
    positions = reduced_data
    if hasattr(contestant, "contestanttrack"):
        contestant_track = ContestantTrackSerialiser(contestant.contestanttrack).data
    else:
        contestant_track = None
    logger.info("Completed generating data {}".format(contestant.pk))
    data = {
        "contestant_id": contestant.pk,
        "latest_time": global_latest_time,
        "positions": positions,
        "annotations": annotations,
        "progress": route_progress,
        "score_log_entries": ScoreLogEntrySerialiser(
            contestant.scorelogentry_set.all(), many=True
        ).data,
        "gate_scores": GateCumulativeScoreSerialiser(
            contestant.gatecumulativescore_set.all(), many=True
        ).data,
        "playing_cards": PlayingCardSerialiser(
            contestant.playingcard_set.all(), many=True
        ).data,
        "contestant_track": contestant_track,
    }
    return data


# Everything below he is related to management and requires authentication
def show_route_definition_step(wizard):
    cleaned_data = wizard.get_cleaned_data_for_step("precision_route_import") or {}
    return (
            not cleaned_data.get("internal_route")
            and cleaned_data.get("file_type") == FILE_TYPE_KML
            and wizard.get_cleaned_data_for_step("task_type").get("task_type")
            in (
                NavigationTask.PRECISION,
                NavigationTask.POKER,
            )
    )


def show_precision_path(wizard):
    return (wizard.get_cleaned_data_for_step("task_type") or {}).get("task_type") in (
        NavigationTask.PRECISION,
        NavigationTask.POKER,
    )


def show_anr_path(wizard):
    return (wizard.get_cleaned_data_for_step("task_type") or {}).get("task_type") in (
        NavigationTask.ANR_CORRIDOR,
    )


def show_landing_path(wizard):
    return (wizard.get_cleaned_data_for_step("task_type") or {}).get("task_type") in (
        NavigationTask.LANDING,
    )


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
        ("landing_route_import", LandingImportRouteForm),
        ("waypoint_definition", formset_factory(WaypointForm, extra=0)),
        ("task_content", NavigationTaskForm),
        ("precision_override", PrecisionScoreOverrideForm),
        ("anr_corridor_override", ANRCorridorScoreOverrideForm),
    ]
    file_storage = FileSystemStorage(
        location=os.path.join(settings.MEDIA_ROOT, "importedroutes")
    )
    condition_dict = {
        "anr_route_import": show_anr_path,
        "precision_route_import": show_precision_path,
        "landing_route_import": show_landing_path,
        "waypoint_definition": show_route_definition_step,
        "precision_override": show_precision_path,
        "anr_corridor_override": show_anr_path,
    }
    templates = {
        "task_type": "display/navigationtaskwizardform.html",
        "anr_route_import": "display/navigationtaskwizardform.html",
        "landing_route_import": "display/navigationtaskwizardform.html",
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
            return self.render_revalidation_failure(
                "task_type", self.get_form_instance("task_type"), **kwargs
            )

    def create_route(self) -> Tuple[Route, Optional[EditableRoute]]:
        task_type = self.get_cleaned_data_for_step("task_type")["task_type"]
        editable_route = None
        route = None
        if task_type in (NavigationTask.PRECISION, NavigationTask.POKER):
            initial_step_data = self.get_cleaned_data_for_step("precision_route_import")
            use_procedure_turns = self.get_cleaned_data_for_step("task_content")[
                "scorecard"
            ].use_procedure_turns
            if initial_step_data["internal_route"]:
                route = initial_step_data["internal_route"].create_precision_route(
                    use_procedure_turns
                )
                editable_route = initial_step_data["internal_route"]
            elif initial_step_data["file_type"] == FILE_TYPE_CSV:
                data = [
                    item.decode(encoding="UTF-8")
                    for item in initial_step_data["file"].readlines()
                ]
                route = create_precision_route_from_csv(
                    "route", data[1:], use_procedure_turns
                )
            elif initial_step_data["file_type"] == FILE_TYPE_FLIGHTCONTEST_GPX:
                try:
                    route = create_precision_route_from_gpx(
                        initial_step_data["file"].read(), use_procedure_turns
                    )
                except Exception as e:
                    raise ValidationError(
                        "Failed building route from provided GPX: {}".format(e)
                    )
            else:
                second_step_data = self.get_cleaned_data_for_step("waypoint_definition")
                if initial_step_data["file_type"] == FILE_TYPE_KML:
                    data = self.get_cleaned_data_for_step("precision_route_import")[
                        "file"
                    ]
                    data.seek(0)
                else:
                    data = None
                route = create_precision_route_from_formset(
                    "route", second_step_data, use_procedure_turns, data
                )
        elif task_type == NavigationTask.ANR_CORRIDOR:
            initial_step_data = self.get_cleaned_data_for_step("anr_route_import")
            rounded_corners = initial_step_data["rounded_corners"]
            corridor_width = self.get_cleaned_data_for_step("anr_corridor_override")[
                "corridor_width"
            ]
            if initial_step_data["internal_route"]:
                route = initial_step_data["internal_route"].create_anr_route(
                    rounded_corners, corridor_width
                )
                editable_route = initial_step_data["internal_route"]
            else:
                data = self.get_cleaned_data_for_step("anr_route_import")["file"]
                data.seek(0)
                route = create_anr_corridor_route_from_kml(
                    "route", data, corridor_width, rounded_corners
                )
        elif task_type == NavigationTask.LANDING:
            data = self.get_cleaned_data_for_step("landing_route_import")["file"]
            data.seek(0)
            route = create_landing_line_from_kml("route", data)
        # Check for gate polygons that do not match a turning point
        route.validate_gate_polygons()
        return route, editable_route

    def done(self, form_list, **kwargs):
        task_type = self.get_cleaned_data_for_step("task_type")["task_type"]
        route, ediable_route=self.create_route()
        final_data = self.get_cleaned_data_for_step("task_content")
        navigation_task = NavigationTask.objects.create(
            **final_data,
            contest=self.contest,
            route=route,
            editable_route=ediable_route,
        )
        # Build score overrides
        if task_type == NavigationTask.PRECISION:
            kwargs["form_dict"].get("precision_override").build_score_override(
                navigation_task
            )
        elif task_type == NavigationTask.ANR_CORRIDOR:
            kwargs["form_dict"].get("anr_corridor_override").build_score_override(
                navigation_task
            )
        print(navigation_task.track_score_override)
        # Update contest location if necessary
        self.contest.update_position_if_not_set(
            *route.get_location()
        )
        return HttpResponseRedirect(
            reverse("navigationtask_detail", kwargs={"pk": navigation_task.pk})
        )

    def get_context_data(self, form, **kwargs):
        context = super().get_context_data(form=form, **kwargs)
        if self.steps.current == "waypoint_definition":
            context["helper"] = WaypointFormHelper()
            context["track_image"] = base64.b64encode(
                get_basic_track(
                    [
                        (item["latitude"], item["longitude"])
                        for item in self.get_form_initial("waypoint_definition")
                    ]
                ).getvalue()
            ).decode("utf-8")
        if self.steps.current == "task_content":
            # route, editable = self.create_route()
            # self.request.session["route"] = route
            # self.request.session["editable_route"] = route
            # country_code = get_country_code_from_location(
            #     *self.request.session["route"].get_location()
            # )
            # form.fields["default_map"].initial = country_code_to_map_source(country_code)
            useful_cards = []
            for scorecard in Scorecard.objects.all():
                if (
                        self.get_cleaned_data_for_step("task_type")["task_type"]
                        in scorecard.task_type
                ):
                    useful_cards.append(scorecard.pk)
            form.fields["scorecard"].queryset = Scorecard.objects.filter(
                pk__in=useful_cards
            )
            form.fields["scorecard"].initial = Scorecard.objects.filter(
                pk__in=useful_cards
            ).first()
        return context

    def get_form(self, step=None, data=None, files=None):
        form = super().get_form(step, data, files)
        if step == "waypoint_definition":
            print(len(form))
        if step in (
                "anr_route_import",
                "precision_route_import",
                "landing_route_import",
        ):
            form.fields["internal_route"].queryset = get_objects_for_user(
                self.request.user,
                "display.view_editableroute",
                klass=EditableRoute.objects.all(),
                accept_global_perms=False,
            )
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
                    initial.append(
                        {
                            "name": f"TP {index}",
                            "latitude": position[0],
                            "longitude": position[1],
                        }
                    )
                if len(positions) > 0:
                    initial[0]["type"] = STARTINGPOINT
                    initial[0]["name"] = "SP"
                    initial[-1]["type"] = FINISHPOINT
                    initial[-1]["name"] = "FP"
                return initial
        if step == "anr_corridor_override":
            scorecard = self.get_cleaned_data_for_step("task_content")["scorecard"]
            return ANRCorridorScoreOverrideForm.extract_default_values_from_scorecard(
                scorecard
            )
        if step == "precision_override":
            scorecard = self.get_cleaned_data_for_step("task_content")["scorecard"]
            return PrecisionScoreOverrideForm.extract_default_values_from_scorecard(
                scorecard
            )
        if step == "task_content":
            country_code = get_country_code_from_location(
                self.contest.latitude, self.contest.longitude
            )
            print(country_code)
            return {
                "default_map": country_code_to_map_source(country_code),
                "score_sorting_direction": self.contest.summary_score_sorting_direction,
            }
        return {}


class ContestTeamTrackingUpdate(GuardianPermissionRequiredMixin, UpdateView):
    permission_required = ("display.change_contest",)

    def get_permission_object(self):
        contest = get_object_or_404(Contest, pk=self.kwargs.get("contest_pk"))
        return contest

    model = ContestTeam
    form_class = TrackingDataForm

    def get_success_url(self):
        return reverse_lazy(
            "contest_team_list", kwargs={"contest_pk": self.kwargs["contest_pk"]}
        )


class TeamUpdateView(GuardianPermissionRequiredMixin, UpdateView):
    permission_required = ("display.change_contest",)

    def get_permission_object(self):
        contest = get_object_or_404(Contest, pk=self.kwargs.get("contest_pk"))
        return contest

    model = Team
    form_class = TeamForm

    def get_success_url(self):
        return reverse_lazy(
            "contest_team_list", kwargs={"contest_pk": self.kwargs["contest_pk"]}
        )


def create_new_pilot(wizard):
    cleaned = wizard.get_post_data_for_step("member1search") or {}
    return cleaned.get("use_existing_pilot") is None


def create_new_copilot(wizard):
    cleaned = wizard.get_post_data_for_step("member2search") or {}
    return (
            cleaned.get("use_existing_copilot") is None
            and cleaned.get("skip_copilot") is None
    )


class RegisterTeamWizard(GuardianPermissionRequiredMixin, SessionWizardView):
    permission_required = ("display.change_contest",)

    def get_permission_object(self):
        contest = get_object_or_404(Contest, pk=self.kwargs.get("contest_pk"))
        return contest

    condition_dict = {
        "member1create": create_new_pilot,
        "member2create": create_new_copilot,
    }
    file_storage = FileSystemStorage(
        location=os.path.join(settings.MEDIA_ROOT, "teams")
    )
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
            return self.render_revalidation_failure(
                "tracking", self.get_form_instance("tracking"), **kwargs
            )

    def post(self, *args, **kwargs):
        if "my_post_data" not in self.request.session:
            self.request.session["my_post_data"] = {}
        self.request.session["my_post_data"][self.steps.current] = self.request.POST
        print(f"Post data: {self.request.POST}")
        return super().post(*args, **kwargs)

    def get_post_data_for_step(self, step):
        return self.request.session.get("my_post_data", {}).get(step, {})

    def done(self, form_list, **kwargs):
        print(f"All cleaned data: {self.get_all_cleaned_data()}")
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
            member1 = get_object_or_404(
                Person, pk=existing_member_one_data["person_id"]
            )
        else:
            member1 = form_dict["member1create"].save()
            member1.validated = True
            member1.save()

        member_two_search = self.get_post_data_for_step("member2search")
        member_two_skip = member_two_search.get("skip_copilot") is not None
        if not member_two_skip:
            use_existing2 = member_two_search.get("use_existing_copilot") is not None
            if use_existing2:
                existing_member_two_data = self.get_cleaned_data_for_step(
                    "member2search"
                )
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
        club, _ = Club.objects.get_or_create(
            name=club_data.get("name"), defaults=club_data
        )
        if club_data["logo"] is not None:
            club.logo = club_data["logo"]
        club.country = club_data["country"]
        club.save()
        team, created_team = Team.objects.get_or_create(
            crew=crew, aeroplane=aeroplane, club=club
        )
        contest.replace_team(original_team, team, tracking_data)
        return HttpResponseRedirect(
            reverse("contest_team_list", kwargs={"contest_pk": contest_pk})
        )

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
        return ContestTeam.objects.filter(contest=contest).order_by(
            "team__crew__member1__last_name", "team__crew__member1__first_name"
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["contest"] = get_object_or_404(
            Contest, pk=self.kwargs.get("contest_pk")
        )
        return context


class EditableRouteList(GuardianPermissionRequiredMixin, ListView):
    model = EditableRoute
    permission_required = ("display.view_editableroute",)

    def get_queryset(self):
        return get_objects_for_user(
            self.request.user,
            "display.view_editableroute",
            klass=self.queryset,
            accept_global_perms=False,
        )


class EditableRouteDeleteView(GuardianPermissionRequiredMixin, DeleteView):
    model = EditableRoute
    permission_required = ("display.delete_editableroute",)
    template_name = "model_delete.html"
    success_url = reverse_lazy("editableroute_list")

    def get_permission_object(self):
        return self.get_object()


@guardian_permission_required("display.change_contest", (Contest, "pk", "contest_pk"))
def remove_team_from_contest(request, contest_pk, team_pk):
    contest = get_object_or_404(Contest, pk=contest_pk)
    team = get_object_or_404(Team, pk=team_pk)
    ContestTeam.objects.filter(contest=contest, team=team).delete()
    return HttpResponseRedirect(
        reverse("contest_team_list", kwargs={"contest_pk": contest_pk})
    )


class UserPersonViewSet(GenericViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_classes = {
        "get_current_app_navigation_task": NavigationTasksSummarySerialiser,
        "get_current_sim_navigation_task": NavigationTasksSummarySerialiser,
        "my_contests": ContestTeamManagementSerialiser,
    }
    default_serialiser_class = PersonSerialiser

    def get_serializer_class(self):
        return self.serializer_classes.get(self.action, self.default_serialiser_class)

    def get_object(self):
        instance = self.get_queryset()
        if instance is None:
            raise Http404
        return instance

    def get_queryset(self):
        return Person.objects.get_or_create(
            email=self.request.user.email,
            defaults={
                "first_name": self.request.user.first_name
                if self.request.user.first_name
                   and len(self.request.user.first_name) > 0
                else "",
                "last_name": self.request.user.last_name
                if self.request.user.last_name and len(self.request.user.last_name) > 0
                else "",
                "validated": False,
            },
        )[0]

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

    @action(detail=False, methods=["get"])
    def my_participating_contests(self, request, *args, **kwargs):
        available_contests = Contest.visible_contests_for_user(request.user).filter(
            finish_time__gte=datetime.datetime.now(datetime.timezone.utc)
        )
        print(available_contests)
        print(self.get_object())
        contest_teams = (
            ContestTeam.objects.filter(
                Q(team__crew__member1=self.get_object())
                | Q(team__crew__member2=self.get_object()),
                contest__in=available_contests,
            )
                .order_by("contest__start_time")
                .distinct()
        )
        teams = []
        for team in contest_teams:
            team.can_edit = team.team.crew.member1 == self.get_object()
            teams.append(team)
        return Response(
            ContestTeamManagementSerialiser(
                teams, many=True, context={"request": request}
            ).data
        )

    @action(detail=False, methods=["patch"])
    def partial_update_profile(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update_profile(request, *args, **kwargs)

    @action(detail=False, methods=["get"])
    def retrieve_profile(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def get_current_sim_navigation_task(self, request, *args, **kwargs):
        person = self.get_object()
        contestant, _ = Contestant.get_contestant_for_device_at_time(
            person.simulator_tracking_id, datetime.datetime.now(datetime.timezone.utc)
        )
        if not contestant:
            raise Http404
        return Response(
            NavigationTasksSummarySerialiser(instance=contestant.navigation_task).data
        )

    @action(detail=False, methods=["get"])
    def get_current_app_navigation_task(self, request, *args, **kwargs):
        person = self.get_object()
        contestant, _ = Contestant.get_contestant_for_device_at_time(
            person.simulator_tracking_id, datetime.datetime.now(datetime.timezone.utc)
        )
        if not contestant:
            raise Http404
        return Response(
            NavigationTasksSummarySerialiser(instance=contestant.navigation_task).data
        )

    @action(detail=False, methods=["put", "patch"])
    def update_profile(self, request, *args, **kwargs):
        if self.request.method == "PATCH":
            partial = True
        else:
            partial = False
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        instance.refresh_from_db()
        request.user.first_name = instance.first_name
        request.user.last_name = instance.last_name
        request.user.save()

        if getattr(instance, "_prefetched_objects_cache", None):
            # If 'prefetch_related' has been applied to a queryset, we need to
            # forcibly invalidate the prefetch cache on the instance.
            instance._prefetched_objects_cache = {}

        return Response(serializer.data)


class EditableRouteViewSet(ModelViewSet):
    queryset = EditableRoute.objects.all()
    permission_classes = [EditableRoutePermission]
    serializer_class = EditableRouteSerialiser

    def get_queryset(self):
        return get_objects_for_user(
            self.request.user,
            "display.view_editableroute",
            klass=self.queryset,
            accept_global_perms=False,
        )


class ContestViewSet(ModelViewSet):
    """
    A contest is a high level wrapper for multiple tasks. Currently it mostly consists of a name and a is_public
    flag which controls its visibility for anonymous users.GET Returns a list of contests either owned by the user
    or publicly divisible POST Allows the user to post a new contest and become the owner of that contest.
    """

    queryset = Contest.objects.all()
    serializer_classes = {
        "teams": ContestTeamNestedSerialiser,
        "update_contest_summary": ContestSummaryWithoutReferenceSerialiser,
        "update_task_summary": TaskSummaryWithoutReferenceSerialiser,
        "update_test_result": TeamTestScoreWithoutReferenceSerialiser,
        "results_details": ContestResultsDetailsSerialiser,
        "ongoing_navigation": OngoingNavigationSerialiser,
        "signup": SignupSerialiser,
        "share": SharingSerialiser,
    }
    default_serialiser_class = ContestSerialiser
    lookup_url_kwarg = "pk"

    permission_classes = [
        ContestPublicPermissions | (permissions.IsAuthenticated & ContestPermissions)
    ]

    def get_serializer_class(self):
        return self.serializer_classes.get(self.action, self.default_serialiser_class)

    def get_queryset(self):
        return (
                get_objects_for_user(
                    self.request.user,
                    "display.view_contest",
                    klass=self.queryset,
                    accept_global_perms=False,
                )
                | self.queryset.filter(is_public=True, is_featured=True)
        )

    @action(detail=True, methods=["get"])
    def get_current_time(self, request, *args, **kwargs):
        """
        Return the current time for the appropriate time zone
        """
        contest = self.get_object()
        return Response(
            datetime.datetime.now(datetime.timezone.utc)
                .astimezone(contest.time_zone)
                .strftime("%H:%M:%S")
        )

    @action(detail=True, methods=["put"])
    def share(self, request, *args, **kwargs):
        """
        Change the visibility of the navigation task to one of the public, private, or unlisted
        """
        contest = self.get_object()
        serialiser = self.get_serializer(data=request.data)  # type: SharingSerialiser
        if serialiser.is_valid(True):
            if serialiser.validated_data["visibility"] == serialiser.PUBLIC:
                contest.make_public()
            elif serialiser.validated_data["visibility"] == serialiser.PRIVATE:
                contest.make_private()
            elif serialiser.validated_data["visibility"] == serialiser.UNLISTED:
                contest.make_unlisted()
        return Response(serialiser.data, status=HTTP_200_OK)

    @action(detail=False, methods=["get"])
    def ongoing_navigation(self, request, *args, **kwargs):
        navigation_tasks = NavigationTask.get_visible_navigation_tasks(
            self.request.user
        ).filter(
            contestant__contestanttrack__calculator_started=True,
            contestant__contestanttrack__calculator_finished=False,
        )
        data = self.get_serializer_class()(
            navigation_tasks, many=True, context={"request": self.request}
        ).data
        return Response(data)

    @action(detail=True, methods=["get"])
    def results_details(self, request, *args, **kwargs):
        """
        Retrieve the full list of contest summaries, tasks summaries, and individual test results for the contest
        """
        contest = self.get_object()
        contest.permission_change_contest = request.user.has_perm(
            "display.change_contest", contest
        )
        serialiser = ContestResultsDetailsSerialiser(contest)
        return Response(serialiser.data)

    @action(["GET"], detail=True)
    def teams(self, request, pk=None, **kwargs):
        """
        Get the list of teams in the contest
        """
        contest_teams = ContestTeam.objects.filter(contest=pk)
        return Response(ContestTeamNestedSerialiser(contest_teams, many=True).data)

    @action(detail=True, methods=["put"])
    def update_contest_summary(self, request, *args, **kwargs):
        """
        Update the total score for the contest for a team.
        """
        # I think this is required for the permissions to work
        contest = self.get_object()
        summary, created = ContestSummary.objects.get_or_create(
            team_id=request.data["team"],
            contest=contest,
            defaults={"points": request.data["points"]},
        )
        if not created:
            summary.points = request.data["points"]
            summary.save()

        return Response(status=HTTP_200_OK)

    @action(detail=True, methods=["put"])
    def update_task_summary(self, request, *args, **kwargs):
        """
        Update the total score for a task for a team.
        """
        # I think this is required for the permissions to work
        contest = self.get_object()
        summary, created = TaskSummary.objects.get_or_create(
            team_id=request.data["team"],
            task_id=request.data["task"],
            defaults={"points": request.data["points"]},
        )
        if not created:
            summary.points = request.data["points"]
            summary.save()
        return Response(status=HTTP_200_OK)

    @action(detail=True, methods=["put"])
    def update_test_result(self, request, *args, **kwargs):
        """
        Update the school for an individual test for a team.
        """
        # I think this is required for the permissions to work
        contest = self.get_object()
        results, created = TeamTestScore.objects.get_or_create(
            team_id=int(request.data["team"]),
            task_test_id=int(request.data["task_test"]),
            defaults={"points": int(request.data["points"])},
        )
        if not created:
            results.points = request.data["points"]
            results.save()
        return Response(status=HTTP_200_OK)
        # # Return the same as the initial results request so that we can refresh everything that has been updated
        # contest.permission_change_contest = request.user.has_perm("display.change_contest", contest)
        # serialiser = ContestResultsDetailsSerialiser(contest)
        # return Response(serialiser.data)

    @action(
        detail=True,
        methods=["POST", "PUT"],
        permission_classes=[
            permissions.IsAuthenticated & ContestPublicModificationPermissions
        ],
    )
    def signup(self, request, *args, **kwargs):
        contest = self.get_object()
        if request.method == "POST":
            logger.info(f"POSTING new contest team {request.data}")
            contest = None
        else:
            logger.info(f"UPDATING existing contest team {request.data}")
        serialiser = self.get_serializer(instance=contest, data=request.data)
        serialiser.is_valid(True)
        contest_team = serialiser.save()
        return Response(
            ContestTeamSerialiser(contest_team).data, status=status.HTTP_201_CREATED
        )

    @action(
        detail=True,
        methods=["DELETE"],
        permission_classes=[
            permissions.IsAuthenticated & ContestPublicModificationPermissions
        ],
    )
    def withdraw(self, request, *args, **kwargs):
        contest = self.get_object()
        teams = ContestTeam.objects.filter(
            Q(team__crew__member1__email=self.request.user.email)
            | Q(team__crew__member2__email=self.request.user.email),
            contest=contest,
        )
        contestants = Contestant.objects.filter(
            navigation_task__contest=contest,
            team__in=[item.team for item in teams],
            finished_by_time__gt=datetime.datetime.now(datetime.timezone.utc),
        )
        if contestants.exists():
            raise drf_exceptions.ValidationError(
                f"You are currently participating in at least one navigation task. Cancel all flights before you can withdraw from the contest"
            )
        teams.delete()
        return Response({}, status=status.HTTP_204_NO_CONTENT)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        try:
            context.update({"contest": self.get_object(), "request": self.request})
        except AssertionError:
            # This is when we are creating a new contest
            pass
        return context


class TeamViewSet(ModelViewSet):
    queryset = Team.objects.all()
    serializer_class = TeamNestedSerialiser
    permission_classes = [permissions.IsAuthenticated & OrganiserPermission]

    http_method_names = ["post", "put", "get"]


class ContestTeamViewSet(ModelViewSet):
    queryset = ContestTeam.objects.all()
    serializer_class = ContestTeamSerialiser
    permission_classes = [permissions.IsAuthenticated & ContestTeamContestPermissions]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        try:
            context.update(
                {
                    "contest": get_object_or_404(
                        Contest, pk=self.kwargs.get("contest_pk")
                    )
                }
            )
        except Http404:
            # This has to be handled where we retrieve the context
            pass
        return context

    def get_queryset(self):
        contest_id = self.kwargs.get("contest_pk")
        contests = get_objects_for_user(
            self.request.user,
            "display.view_contest",
            klass=Contest,
            accept_global_perms=False,
        )
        try:
            contest = contests.get(pk=contest_id)
        except ObjectDoesNotExist:
            raise Http404("Contest does not exist")
        return ContestTeam.objects.filter(contest=contest)


class NavigationTaskViewSet(ModelViewSet):
    queryset = NavigationTask.objects.all()
    serializer_classes = {
        "share": SharingSerialiser,
        "contestant_self_registration": SelfManagementSerialiser,
    }
    default_serialiser_class = NavigationTaskNestedTeamRouteSerialiser
    lookup_url_kwarg = "pk"

    permission_classes = [
        NavigationTaskPublicPermissions
        | (permissions.IsAuthenticated & NavigationTaskContestPermissions)
    ]

    http_method_names = ["get", "post", "delete", "put"]

    def get_serializer_class(self):
        return self.serializer_classes.get(self.action, self.default_serialiser_class)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        try:
            context.update(
                {
                    "contest": get_object_or_404(
                        Contest, pk=self.kwargs.get("contest_pk")
                    )
                }
            )
        except Http404:
            # This has to be handled where we retrieve the context
            pass
        return context

    def get_queryset(self):
        contest_id = self.kwargs.get("contest_pk")
        contests = get_objects_for_user(
            self.request.user,
            "display.view_contest",
            klass=Contest,
            accept_global_perms=False,
        )
        return NavigationTask.objects.filter(
            Q(contest__in=contests) | Q(is_public=True, contest__is_public=True)
        ).filter(contest_id=contest_id)

    def create(self, request, *args, **kwargs):
        serialiser = self.get_serializer(data=request.data)
        if serialiser.is_valid():
            serialiser.save()
            return Response(serialiser.data, status=status.HTTP_201_CREATED)
        return Response(serialiser.errors, status=status.HTTP_400_BAD_REQUEST)

    def update(self, request, *args, **kwargs):
        raise drf_exceptions.PermissionDenied(
            "It is not possible to modify existing navigation tasks except to publish or hide them"
        )

    @action(
        detail=True,
        methods=["put", "delete"],
        permission_classes=[
            permissions.IsAuthenticated
            & NavigationTaskSelfManagementPermissions
            & (NavigationTaskPublicPutPermissions | NavigationTaskContestPermissions)
        ],
    )
    def contestant_self_registration(self, request, *args, **kwargs):
        navigation_task = self.get_object()  # type: NavigationTask
        if request.method == "PUT":
            serialiser = self.get_serializer(data=request.data)
            serialiser.is_valid(True)
            contest_team = serialiser.validated_data["contest_team"]
            if contest_team.team.crew.member1.email != request.user.email:
                raise ValidationError(
                    "You cannot add a team where you are not the pilot"
                )
            starting_point_time = serialiser.validated_data[
                "starting_point_time"
            ].astimezone(
                navigation_task.contest.time_zone
            )  # type: datetime
            takeoff_time = starting_point_time - datetime.timedelta(
                minutes=navigation_task.minutes_to_starting_point
            )
            existing_contestants = navigation_task.contestant_set.all()
            if existing_contestants.exists():
                contestant_number = (
                        max([item.contestant_number for item in existing_contestants]) + 1
                )
            else:
                contestant_number = 1
            adaptive_start = serialiser.validated_data["adaptive_start"]
            tracker_start_time = takeoff_time - datetime.timedelta(minutes=10)
            if adaptive_start:
                tracker_start_time = starting_point_time - datetime.timedelta(hours=1)
            contestant = Contestant(
                team=contest_team.team,
                takeoff_time=takeoff_time,
                navigation_task=navigation_task,
                tracker_start_time=tracker_start_time,
                adaptive_start=adaptive_start,
                finished_by_time=takeoff_time + datetime.timedelta(days=1),
                minutes_to_starting_point=navigation_task.minutes_to_starting_point,
                air_speed=contest_team.air_speed,
                contestant_number=contestant_number,
                wind_speed=serialiser.validated_data["wind_speed"],
                wind_direction=serialiser.validated_data["wind_direction"],
            )
            logger.debug("Created contestant")
            final_time = contestant.get_final_gate_time()
            if final_time is None:
                final_time = starting_point_time
            if adaptive_start:
                # Properly account for how final time is created when adaptive start is active
                final_time = (
                        starting_point_time
                        + datetime.timedelta(hours=1)
                        + datetime.timedelta(
                    hours=final_time.hour,
                    minutes=final_time.minute,
                    seconds=final_time.second,
                )
                )
            logger.debug(f"Take-off time is {contestant.takeoff_time}")
            logger.debug(f"Final time is {final_time}")
            contestant.finished_by_time = final_time + datetime.timedelta(
                minutes=navigation_task.minutes_to_landing + 2
            )
            logger.debug(f"Finished by time is {contestant.finished_by_time}")

            contestant.save()
            logger.debug("Updated contestant")
            # mail_link = EmailMapLink.objects.create(contestant=contestant)
            # mail_link.send_email(request.user.email, request.user.first_name)
            generate_and_notify_flight_order.apply_async(
                (contestant.pk, request.user.email, request.user.first_name)
            )
            return Response(status=status.HTTP_201_CREATED)
        elif request.method == "DELETE":
            # Delete all contestants that have not started yet where I am the pilot
            navigation_task.contestant_set.filter(
                finished_by_time__gt=datetime.datetime.now(datetime.timezone.utc),
                team__crew__member1__email=request.user.email,
                contestanttrack__calculator_started=False,
            ).delete()
            # Terminate ongoing contestants
            ongoing = list(
                navigation_task.contestant_set.filter(
                    finished_by_time__gt=datetime.datetime.now(datetime.timezone.utc),
                    team__crew__member1__email=request.user.email,
                    contestanttrack__calculator_started=True,
                )
            )
            navigation_task.contestant_set.filter(
                finished_by_time__gt=datetime.datetime.now(datetime.timezone.utc),
                team__crew__member1__email=request.user.email,
                contestanttrack__calculator_started=True,
            ).update(
                finished_by_time=datetime.datetime.now(datetime.timezone.utc)
                                 - datetime.timedelta(minutes=1)
            )
            for contestant in ongoing:
                contestant.request_calculator_termination()
            return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["put"])
    def share(self, request, *args, **kwargs):
        """
        Change the visibility of the navigation task to one of the public, private, or unlisted
        """
        navigation_task = self.get_object()
        serialiser = self.get_serializer(data=request.data)  # type: SharingSerialiser
        if serialiser.is_valid(True):
            if serialiser.validated_data["visibility"] == serialiser.PUBLIC:
                navigation_task.make_public()
            elif serialiser.validated_data["visibility"] == serialiser.PRIVATE:
                navigation_task.make_private()
            elif serialiser.validated_data["visibility"] == serialiser.UNLISTED:
                navigation_task.make_unlisted()
        return Response(serialiser.data, status=HTTP_200_OK)


class RouteViewSet(ModelViewSet):
    queryset = Route.objects.all()
    serializer_class = RouteSerialiser
    permission_classes = [permissions.IsAuthenticated & RoutePermissions]

    http_method_names = ["get", "post", "delete", "put"]


class AircraftViewSet(ModelViewSet):
    queryset = Aeroplane.objects.all()
    serializer_class = AeroplaneSerialiser
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get"]


class ClubViewSet(ModelViewSet):
    queryset = Club.objects.all()
    serializer_class = ClubSerialiser
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get"]


class ContestantTeamIdViewSet(ModelViewSet):
    queryset = Contestant.objects.all()
    permission_classes = [
        ContestantPublicPermissions
        | (permissions.IsAuthenticated & ContestantNavigationTaskContestPermissions)
    ]
    serializer_classes = {}
    default_serialiser_class = ContestantSerialiser

    def get_serializer_class(self):
        return self.serializer_classes.get(self.action, self.default_serialiser_class)

    def get_queryset(self):
        navigation_task_id = self.kwargs.get("navigationtask_pk")
        contests = get_objects_for_user(
            self.request.user,
            "display.change_contest",
            klass=Contest,
            accept_global_perms=False,
        )
        return Contestant.objects.filter(
            Q(navigation_task__contest__in=contests)
            | Q(
                navigation_task__is_public=True,
                navigation_task__contest__is_public=True,
            )
        ).filter(navigation_task_id=navigation_task_id)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        try:
            navigation_task = get_object_or_404(
                NavigationTask, pk=self.kwargs.get("navigationtask_pk")
            )
            context.update({"navigation_task": navigation_task})
        except Http404:
            # This has to be handled where we retrieve the context
            pass
        return context


class ContestantViewSet(ModelViewSet):
    queryset = Contestant.objects.all()
    permission_classes = [
        ContestantPublicPermissions
        | (permissions.IsAuthenticated & ContestantNavigationTaskContestPermissions)
    ]
    serializer_classes = {
        "track": ContestantTrackWithTrackPointsSerialiser,
        "gpx_track": GpxTrackSerialiser,
        "update_without_team": ContestantSerialiser,
    }
    default_serialiser_class = ContestantNestedTeamSerialiserWithContestantTrack

    def get_serializer_class(self):
        return self.serializer_classes.get(self.action, self.default_serialiser_class)

    def get_queryset(self):
        navigation_task_id = self.kwargs.get("navigationtask_pk")
        contests = get_objects_for_user(
            self.request.user,
            "display.change_contest",
            klass=Contest,
            accept_global_perms=False,
        )
        return Contestant.objects.filter(
            Q(navigation_task__contest__in=contests)
            | Q(
                navigation_task__is_public=True,
                navigation_task__contest__is_public=True,
            )
        ).filter(navigation_task_id=navigation_task_id)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        try:
            navigation_task = get_object_or_404(
                NavigationTask, pk=self.kwargs.get("navigationtask_pk")
            )
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
        partial = kwargs.pop("partial", False)
        serialiser = self.get_serializer(
            instance=instance, data=request.data, partial=partial
        )
        if serialiser.is_valid():
            serialiser.save()
            return Response(serialiser.data)
        return Response(serialiser.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["put", "patch"])
    def update_without_team(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    @action(detail=True, methods=["get"])
    def track(self, request, pk=None, **kwargs):
        """
        Returns the GPS track for the contestant
        """
        contestant = (
            self.get_object()
        )  # This is important, this is where the object permissions are checked
        contestant_track = contestant.contestanttrack
        result_set = influx.get_positions_for_contestant(
            pk, contestant.tracker_start_time
        )
        logger.info("Completed fetching positions for {}".format(contestant.pk))
        position_data = list(
            result_set.get_points(tags={"contestant": str(contestant.pk)})
        )
        contestant_track.track = position_data
        serialiser = ContestantTrackWithTrackPointsSerialiser(contestant_track)
        return Response(serialiser.data)

    @action(detail=True, methods=["post"])
    def gpx_track(self, request, pk=None, **kwargs):
        """
        Consumes a FC GPX file that contains the GPS track of a contestant.
        """
        contestant = (
            self.get_object()
        )  # This is important, this is where the object permissions are checked
        ContestantTrack.objects.filter(contestant=contestant).delete()
        contestant.save()  # Creates new contestant track
        # Not required, covered by delete above
        # influx.clear_data_for_contestant(contestant.pk)
        track_file = request.data.get("track_file", None)
        if not track_file:
            raise ValidationError("Missing track_file")
        import_gpx_track.apply_async((contestant.pk, track_file))
        return Response({}, status=status.HTTP_201_CREATED)


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
    permission_classes = [
        permissions.IsAuthenticated & NavigationTaskContestPermissions
    ]

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


@permission_required("display.change_contest")
def renew_token(request):
    user = request.user
    Token.objects.filter(user=user).delete()
    Token.objects.create(user=user)
    return redirect(reverse("token"))


@permission_required("display.view_contest")
def view_token(request):
    return render(request, "token.html")


########## Results service ##########
class TaskViewSet(ModelViewSet):
    queryset = Task.objects.all()
    permission_classes = [
        TaskContestPublicPermissions
        | permissions.IsAuthenticated & TaskContestPermissions
    ]
    serializer_class = TaskSerialiser

    def get_queryset(self):
        contest_id = self.kwargs.get("contest_pk")
        return Task.objects.filter(contest_id=contest_id)


class TaskTestViewSet(ModelViewSet):
    queryset = TaskTest.objects.all()
    permission_classes = [
        TaskTestContestPublicPermissions
        | permissions.IsAuthenticated & TaskTestContestPermissions
    ]
    serializer_class = TaskTestSerialiser

    def get_queryset(self):
        contest_id = self.kwargs.get("contest_pk")
        return TaskTest.objects.filter(task__contest_id=contest_id)


def firebase_token_login(request):
    from drf_firebase_auth.authentication import FirebaseAuthentication

    token = request.GET.get("token")
    logger.debug(f"Token {token}")
    firebase_authenticator = FirebaseAuthentication()
    try:
        user, decoded_token = firebase_authenticator.authenticate_credentials(token)
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    except drf_exceptions.AuthenticationFailed as e:
        messages.error(request, f"Login failed: {e}")
    return redirect("/")
