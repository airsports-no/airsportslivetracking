import base64
import datetime
import json
import os
from collections import defaultdict
from io import BytesIO
from typing import Optional, Dict, Tuple, List

import gpxpy
import zipfile
from crispy_forms.layout import Fieldset
from django.contrib import messages
from django.contrib.auth import login, get_user_model, logout
from django.contrib.auth.decorators import permission_required, user_passes_test, login_required
from django.contrib.auth.mixins import (
    PermissionRequiredMixin,
    LoginRequiredMixin,
    UserPassesTestMixin,
)

from django.core.cache import cache
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from django.core.mail import send_mail
from django.db import transaction, connection
from django.db.models import Q, ProtectedError, Count
from django import forms

from django.http import HttpResponseRedirect, JsonResponse, HttpResponse, Http404
from django.shortcuts import render, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import (
    ListView,
    DetailView,
    UpdateView,
    CreateView,
    DeleteView,
    TemplateView,
)
import logging

from formtools.wizard.views import SessionWizardView
from guardian.decorators import permission_required as guardian_permission_required
from guardian.mixins import PermissionRequiredMixin as GuardianPermissionRequiredMixin
from guardian.shortcuts import (
    get_objects_for_user,
    assign_perm,
    get_users_with_perms,
    remove_perm,
    get_user_perms,
)
from rest_framework import status, permissions, mixins
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action, api_view, permission_classes
import rest_framework.exceptions as drf_exceptions
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.status import HTTP_200_OK, HTTP_204_NO_CONTENT
from rest_framework.viewsets import ModelViewSet, GenericViewSet

from display.flight_order_and_maps.map_plotter_shared_utilities import get_map_zoom_levels
from display.utilities.calculator_running_utilities import is_calculator_running
from display.utilities.calculator_termination_utilities import cancel_termination_request
from display.forms import (
    PrecisionImportRouteForm,
    NavigationTaskForm,
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
    TaskTypeForm,
    ANRCorridorImportRouteForm,
    TrackingDataForm,
    ContestTeamOptimisationForm,
    AssignPokerCardForm,
    ChangeContestPermissionsForm,
    AddContestPermissionsForm,
    RouteCreationForm,
    LandingImportRouteForm,
    ShareForm,
    GPXTrackImportForm,
    ContestSelectForm,
    ANRCorridorParametersForm,
    AirsportsParametersForm,
    PersonPictureForm,
    ScorecardForm,
    GateScoreForm,
    AirsportsImportRouteForm,
    FlightOrderConfigurationForm,
    UserUploadedMapForm,
    AddUserUploadedMapPermissionsForm,
    ChangeUserUploadedMapPermissionsForm,
    ChangeEditableRoutePermissionsForm,
    AddEditableRoutePermissionsForm,
    ImportRouteForm,
    DeleteUserForm,
)
from display.flight_order_and_maps.generate_flight_orders import (
    generate_flight_orders_latex,
    embed_map_in_pdf,
)
from display.flight_order_and_maps.map_constants import A4
from display.flight_order_and_maps.map_plotter import (
    plot_route,
    A4_WIDTH,
    A3_HEIGHT,
    A4_HEIGHT,
    A3_WIDTH,
)
from display.models import (
    NavigationTask,
    Route,
    Contestant,
    Contest,
    Team,
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
    Scorecard,
    MyUser,
    PlayingCard,
    ScoreLogEntry,
    EmailMapLink,
    EditableRoute,
    ANOMALY,
    GateScore,
    FlightOrderConfiguration,
    UserUploadedMap,
)
from display.permissions import (
    ContestPermissions,
    NavigationTaskContestPermissions,
    ContestantPublicPermissions,
    NavigationTaskPublicPermissions,
    ContestPublicPermissions,
    ContestantNavigationTaskContestPermissions,
    RoutePermissions,
    ContestPermissionsWithoutObjects,
    TaskContestPermissions,
    TaskContestPublicPermissions,
    TaskTestContestPublicPermissions,
    TaskTestContestPermissions,
    ContestPublicModificationPermissions,
    OrganiserPermission,
    ContestTeamContestPermissions,
    NavigationTaskSelfManagementPermissions,
    EditableRoutePermission,
    NavigationTaskPublicPutDeletePermissions,
)
from display.contestant_scheduling.schedule_contestants import schedule_and_create_contestants
from display.serialisers import (
    ExternalNavigationTaskNestedTeamSerialiser,
    ContestSerialiser,
    NavigationTaskNestedTeamRouteSerialiser,
    RouteSerialiser,
    ContestantTrackWithTrackPointsSerialiser,
    ContestResultsDetailsSerialiser,
    TeamNestedSerialiser,
    GpxTrackSerialiser,
    PersonSerialiser,
    ExternalNavigationTaskTeamIdSerialiser,
    ContestantNestedTeamSerialiserWithContestantTrack,
    AeroplaneSerialiser,
    ClubSerialiser,
    ContestTeamNestedSerialiser,
    ContestSummaryWithoutReferenceSerialiser,
    ContestTeamSerialiser,
    NavigationTasksSummarySerialiser,
    TaskSummaryWithoutReferenceSerialiser,
    TeamTestScoreWithoutReferenceSerialiser,
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
    PositionSerialiser,
    ScorecardNestedSerialiser,
    ContestSerialiserWithResults,
    PersonSerialiserExcludingTracking,
    ContestFrontEndSerialiser,
)
from display.utilities.show_slug_choices import ShowChoicesMetadata
from display.tasks import (
    import_gpx_track,
    revert_gpx_track_to_traccar,
    generate_and_maybe_notify_flight_order,
    notify_flight_order,
)
from display.utilities.welcome_emails import render_welcome_email, render_contest_creation_email
from live_tracking_map import settings
from slack_facade import post_slack_message
from websocket_channels import (
    WebsocketFacade,
    generate_contestant_data_block,
)

logger = logging.getLogger(__name__)


def healthz(request):
    return HttpResponse(status=status.HTTP_200_OK)


def readyz(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return HttpResponse(status=200)
    except Exception as ex:
        return HttpResponse(str(ex).encode("utf-8"), status=500)


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


@user_passes_test(lambda u: u.is_superuser)
def get_contest_creators_emails(request):
    users_with_creation_privileges = get_user_model().objects.filter(groups__name="ContestCreator")
    all_users = get_user_model().objects.all()
    return render(
        request,
        "display/email_lists.html",
        {
            "users_with_creation_privileges": [u.email for u in users_with_creation_privileges],
            "all_users": [u.email for u in all_users],
        },
    )


def frontend_view_map(request, pk):
    my_contests = get_objects_for_user(request.user, "display.view_contest", accept_global_perms=False)
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
            "skip_nav": "true",
            "playback": "false",
            "can_change_navigation_task": "true"
            if navigation_task.user_has_change_permissions(request.user)
            else "false",
            "navigation_task_management_link": reverse("navigationtask_detail", args=(navigation_task.pk,)),
            "playback_link": reverse("frontend_playback_map", args=(navigation_task.pk,)),
            "live_map_link": reverse("frontend_view_map", args=(navigation_task.pk,)),
        },
    )


def frontend_playback_map(request, pk):
    my_contests = get_objects_for_user(request.user, "display.view_contest", accept_global_perms=False)
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
            "skip_nav": "true",
            "playback": "true",
            "can_change_navigation_task": "true"
            if navigation_task.user_has_change_permissions(request.user)
            else "false",
            "navigation_task_management_link": reverse("navigationtask_detail", args=(navigation_task.pk,)),
            "playback_link": reverse("frontend_playback_map", args=(navigation_task.pk,)),
            "live_map_link": reverse("frontend_view_map", args=(navigation_task.pk,)),
        },
    )


def global_map(request):
    visited = request.session.get("visited", False)
    request.session["visited"] = True
    return render(
        request,
        "display/globalmap.html",
        {"skip_nav": True, "first_visit": not visited},
    )


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


def user_start_request_profile_deletion(request):
    """
    We must provide this link to Google so that it can be included in the play store listing.
    """
    return render(request, "display/request_profile_deletion.html")


@login_required
def user_request_profile_deletion(request):
    try:
        send_mail(
            f"User requested profile deletion",
            f"The user {request.user.email} has requested their profile to be deleted",
            None,  # Should default to system from email
            recipient_list=["support@airsports.no"],
        )
    except:
        logger.error(f"Failed sending email about deleting user profile for {request.user.email}")
        post_slack_message("Exception", f"Failed sending email about deleting user profile for {request.user.email}")
    messages.info(request, f"Your request for deleting your user profile has been submitted")
    logout(request)
    return redirect("/")


@user_passes_test(lambda u: u.is_superuser)
def delete_user_and_person(request):
    """
    Deletes the specified MyUser object and tries to delete the associated Person. If deleting the Person fails,
    the person is obfuscated by changing name and email.
    """
    form = DeleteUserForm()
    if request.method == "POST":
        form = DeleteUserForm(request.POST)
        if form.is_valid():
            try:
                my_user = MyUser.objects.get(email=form.cleaned_data["email"])
                my_user.delete()
                if form.cleaned_data["send_email"]:
                    my_user.send_deletion_email()
            except ObjectDoesNotExist:
                messages.error(request, f"A user with the e-mail {form.cleaned_data['email']} does not exist")
            for person in Person.objects.filter(email=form.cleaned_data["email"]):
                try:
                    person.delete()
                    messages.success(request, f"Successfully deleted {person}")
                except ProtectedError:
                    my_user.send_deletion_email()
                    person.first_name = "Unknown"
                    person.last_name = "Unknown"
                    person.email = f"internal_{person.pk}@airsports.no"
                    person.phone = None
                    person.picture = None
                    person.biography = ""
                    person.is_public = False
                    person.save()
                    messages.warning(request, f"Deleting the person failed, but we renamed them to {person}")
    return render(request, "display/delete_user_form.html", {"form": form})


@api_view(["POST"])
def get_country_from_location(request):
    latitude = float(request.data.get("latitude"))
    longitude = float(request.data.get("longitude"))
    return Response(get_country_from_location(latitude, longitude))


@api_view(["POST"])
@permission_classes([IsAuthenticated, ContestPermissionsWithoutObjects])
def auto_complete_aeroplane(request):
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


@api_view(["POST"])
@permission_classes([IsAuthenticated, ContestPermissionsWithoutObjects])
def auto_complete_club(request):
    request_number = int(request.data.get("request"))
    if request_number == 1:
        q = request.data.get("search", "")
        search_qs = Club.objects.filter(name__icontains=q)
        result = [{"label": "{} ({})".format(item.name, item.country), "value": item.name} for item in search_qs]
        return Response(result)
    else:
        q = request.data.get("search", "")
        search_qs = Club.objects.filter(name=q)
        serialiser = ClubSerialiser(search_qs, many=True)
        return Response(serialiser.data)


@api_view(["POST"])
@permission_classes([IsAuthenticated, ContestPermissionsWithoutObjects])
def auto_complete_person_phone(request):
    request_number = int(request.data.get("request"))
    if request_number == 1:
        q = request.data.get("search", "")
        search_qs = Person.objects.filter(phone__contains=q)
        result = [str(item.phone) for item in search_qs]
        return Response(result)
    else:
        q = request.data.get("search", "")
        search_qs = Person.objects.filter(phone=q)
        serialiser = PersonSerialiserExcludingTracking(search_qs, many=True)
        return Response(serialiser.data)


@api_view(["POST"])
@permission_classes([IsAuthenticated, ContestPermissionsWithoutObjects])
def auto_complete_person_id(request):
    request_number = int(request.data.get("request"))
    if request_number == 1:
        q = request.data.get("search", "")
        search_qs = Person.objects.filter(pk=q)
        result = [str(item.phone) for item in search_qs]
        return Response(result)
    else:
        q = request.data.get("search", "")
        search_qs = Person.objects.filter(pk=q)
        serialiser = PersonSerialiserExcludingTracking(search_qs, many=True)
        return Response(serialiser.data)


@api_view(["POST"])
@permission_classes([IsAuthenticated, ContestPermissionsWithoutObjects])
def auto_complete_person_first_name(request):
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
        serialiser = PersonSerialiserExcludingTracking(search_qs, many=True)
        return Response(serialiser.data)


@api_view(["POST"])
@permission_classes([IsAuthenticated, ContestPermissionsWithoutObjects])
def auto_complete_person_last_name(request):
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
        serialiser = PersonSerialiserExcludingTracking(search_qs, many=True)
        return Response(serialiser.data)


@api_view(["POST"])
@permission_classes([IsAuthenticated, ContestPermissionsWithoutObjects])
def auto_complete_person_email(request):
    request_number = int(request.data.get("request"))
    if request_number == 1:
        q = request.data.get("search", "")
        search_qs = Person.objects.filter(email__icontains=q)
        result = [item.email for item in search_qs]
        return Response(result)
    else:
        q = request.data.get("search", "")
        search_qs = Person.objects.filter(email=q)
        serialiser = PersonSerialiserExcludingTracking(search_qs, many=True)
        return Response(serialiser.data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_persons_for_signup(request):
    return Response(PersonSignUpSerialiser(Person.objects.exclude(email=request.user.email), many=True).data)


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


@guardian_permission_required("display.change_contest", (Contest, "navigationtask__contestant__pk", "pk"))
def contestant_card_remove(request, pk, card_pk):
    contestant = get_object_or_404(Contestant, pk=pk)
    PlayingCard.remove_contestant_card(contestant, card_pk)
    return redirect(reverse("contestant_cards_list", kwargs={"pk": contestant.pk}))


@guardian_permission_required("display.change_contest", (Contest, "navigationtask__contestant__pk", "pk"))
def contestant_cards_list(request, pk):
    contestant = get_object_or_404(Contestant, pk=pk)
    waypoint_names = [waypoint.name for waypoint in contestant.navigation_task.route.waypoints]

    if request.method == "POST":
        form = AssignPokerCardForm(request.POST)
        form.fields["waypoint"].choices = [
            (str(index), item.name) for index, item in enumerate(contestant.navigation_task.route.waypoints)
        ]
        if form.is_valid():
            waypoint_index = int(form.cleaned_data["waypoint"])
            waypoint_name = waypoint_names[waypoint_index]
            card = form.cleaned_data["playing_card"]
            random_card = card == "random"
            if random_card:
                card = PlayingCard.get_random_unique_card(contestant)
            PlayingCard.add_contestant_card(contestant, card, waypoint_name, waypoint_index)
    cards = contestant.playingcard_set.all().order_by("pk")
    try:
        latest_waypoint_index = max([card.waypoint_index for card in cards])
    except ValueError:
        latest_waypoint_index = -1
    try:
        next_waypoint_name = waypoint_names[latest_waypoint_index + 1]
    except IndexError:
        next_waypoint_name = None
    form = AssignPokerCardForm()
    form.fields["waypoint"].choices = [
        (str(index), item.name) for index, item in enumerate(contestant.navigation_task.route.waypoints)
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
            return HttpResponseRedirect(reverse("contest_details", kwargs={"pk": contest.pk}))
    if contest.is_public and contest.is_featured:
        initial = ShareForm.PUBLIC
    elif contest.is_public and not contest.is_featured:
        initial = ShareForm.UNLISTED
    else:
        initial = ShareForm.PRIVATE
    form = ShareForm(initial={"publicity": initial})
    return render(request, "display/share_contest_form.html", {"form": form, "contest": contest})


@guardian_permission_required("display.change_contest", (Contest, "navigationtask__pk", "pk"))
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
            return HttpResponseRedirect(reverse("navigationtask_detail", kwargs={"pk": navigation_task.pk}))
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
@guardian_permission_required("display.change_contest", (Contest, "navigationtask__pk", "pk"))
def refresh_editable_route_navigation_task(request, pk):
    navigation_task = get_object_or_404(NavigationTask, pk=pk)
    try:
        navigation_task.refresh_editable_route()
        messages.success(request, "Route refreshed")
    except ValidationError as e:
        messages.error(request, str(e))
    return HttpResponseRedirect(reverse("navigationtask_detail", kwargs={"pk": navigation_task.pk}))


@guardian_permission_required("display.change_contest", (Contest, "pk", "pk"))
def view_contest_team_images(request, pk):
    contest = get_object_or_404(Contest, pk=pk)
    return render(
        request,
        "display/contest_team_images.html",
        {
            "contest": contest,
            "object_list": Person.objects.filter(
                Q(crewmember_two__team__contest=contest) | Q(crewmember_one__team__contest=contest)
            )
            .distinct()
            .order_by("last_name", "first_name"),
        },
    )


@guardian_permission_required("display.change_contest", (Contest, "pk", "contest_pk"))
def clear_profile_image_background(request, contest_pk, pk):
    contest = get_object_or_404(Contest, pk=contest_pk)
    person = get_object_or_404(Person, pk=pk)
    result = person.remove_profile_picture_background()
    if result is not None:
        messages.error(request, f"Background removal failed for {person}: {result}")
    else:
        messages.success(request, f"Background removal successful for {person}")
    return redirect(reverse("contest_team_images", kwargs={"pk": contest_pk}))


@guardian_permission_required("display.change_contest", (Contest, "pk", "contest_pk"))
def upload_profile_picture(request, contest_pk, pk):
    contest = get_object_or_404(Contest, pk=contest_pk)
    person = get_object_or_404(Person, pk=pk)
    if request.method == "POST":
        form = PersonPictureForm(request.POST, request.FILES, instance=person)
        if form.is_valid():
            form.save()
            return redirect(reverse("contest_team_images", kwargs={"pk": contest_pk}))
    form = PersonPictureForm(instance=person)
    return render(
        request,
        "display/person_upload_picture_form.html",
        {"form": form, "object": person},
    )


@permission_required("display.change_contest")
def import_route(request):
    if request.method == "POST":
        form = ImportRouteForm(request.POST, request.FILES)
        if form.is_valid():
            route_file = request.FILES["file"]
            base, extension = os.path.splitext(route_file.name)
            editable_route = None
            return_messages = []
            if extension.lower() == ".csv":
                editable_route, return_messages = EditableRoute.create_from_csv(
                    form.cleaned_data["name"], [string.decode("utf-8") for string in route_file.readlines()]
                )
            elif extension.lower() in (".kml", ".kmz"):
                editable_route, return_messages = EditableRoute.create_from_kml(form.cleaned_data["name"], route_file)
            elif extension.lower() in (".gpx",):
                editable_route, return_messages = EditableRoute.create_from_gpx(
                    form.cleaned_data["name"], route_file.read()
                )
            else:
                return_messages.append(f"Unknown file extension '{extension}'")
            if not editable_route:
                for message in return_messages:
                    messages.error(request, message)
                return render(request, "display/import_route_form.html", {"form": form})
            assign_perm(f"display.change_editableroute", request.user, editable_route)
            assign_perm(f"display.delete_editableroute", request.user, editable_route)
            assign_perm(f"display.view_editableroute", request.user, editable_route)
            for message in return_messages:
                messages.success(request, message)
            return redirect(f"/routeeditor/{editable_route.pk}/")
    form = ImportRouteForm()
    return render(request, "display/import_route_form.html", {"form": form})


@guardian_permission_required("display.view_contest", (Contest, "navigationtask__contestant__pk", "pk"))
def get_contestant_map(request, pk):
    contestant = get_object_or_404(Contestant, pk=pk)
    if request.method == "POST":
        form = ContestantMapForm(request.POST)
        form.fields["user_map_source"].choices = [("", "----")] + [
            (item.map_file, item.name) for item in contestant.navigation_task.get_available_user_maps()
        ]
        if form.is_valid():
            margin = 10
            map_image = plot_route(
                contestant.navigation_task,
                form.cleaned_data["size"],
                zoom_level=int(form.cleaned_data["zoom_level"]),
                landscape=form.cleaned_data["orientation"] == LANDSCAPE,
                contestant=contestant,
                annotations=form.cleaned_data["include_annotations"],
                waypoints_only=not form.cleaned_data["plot_track_between_waypoints"],
                dpi=form.cleaned_data["dpi"],
                scale=int(form.cleaned_data["scale"]),
                map_source=form.cleaned_data["map_source"],
                user_map_source=form.cleaned_data["user_map_source"],
                line_width=float(form.cleaned_data["line_width"]),
                minute_mark_line_width=float(form.cleaned_data["minute_mark_line_width"]),
                colour=form.cleaned_data["colour"],
                include_meridians_and_parallels_lines=form.cleaned_data["include_meridians_and_parallels_lines"],
                margins_mm=margin,
            )
            pdf = embed_map_in_pdf(
                "a4paper" if form.cleaned_data["size"] == A4 else "a3paper",
                map_image.read(),
                10 * A4_WIDTH - 2 * margin if form.cleaned_data["size"] else 10 * A3_WIDTH - 2 * margin,
                10 * A4_HEIGHT - 2 * margin if form.cleaned_data["size"] == A4 else 10 * A3_HEIGHT - 2 * margin,
                form.cleaned_data["orientation"] == LANDSCAPE,
            )

            response = HttpResponse(pdf, content_type="application/pdf")
            response["Content-Disposition"] = f"attachment; filename=map.pdf"
            return response
    else:
        configuration = contestant.navigation_task.flightorderconfiguration
        form = ContestantMapForm(
            initial={
                "dpi": configuration.map_dpi,
                "zoom_level": configuration.map_zoom_level,
                "orientation": configuration.map_orientation,
                "scale": configuration.map_scale,
                "map_source": configuration.map_source,
                "user_map_source": configuration.map_user_source,
                "include_annotations": configuration.map_include_annotations,
                "plot_track_between_waypoints": configuration.map_plot_track_between_waypoints,
                "include_meridians_and_parallels_lines": configuration.map_include_meridians_and_parallels_lines,
                "line_width": configuration.map_line_width,
                "minute_mark_line_width": configuration.map_minute_mark_line_width,
                "colour": configuration.map_line_colour,
            }
        )
        form.fields["user_map_source"].choices = [("", "----")] + [
            (item.map_file, item.name) for item in contestant.navigation_task.get_available_user_maps()
        ]
        form.fields["user_map_source"].initial = contestant.navigation_task.flightorderconfiguration.map_user_source

    return render(
        request,
        "display/map_form.html",
        {
            "form": form,
            "redirect": reverse("navigationtask_detail", kwargs={"pk": contestant.navigation_task.pk}),
            "system_map_zoom_levels": json.dumps(get_map_zoom_levels()),
        },
    )


@guardian_permission_required("display.change_contest", (Contest, "navigationtask__pk", "pk"))
def update_flight_order_configurations(request, pk):
    navigation_task = get_object_or_404(NavigationTask, pk=pk)
    configuration = get_object_or_404(FlightOrderConfiguration, navigation_task__pk=pk)
    if request.method == "POST":
        form = FlightOrderConfigurationForm(request.POST, instance=configuration)
        form.fields["map_user_source"].queryset = UserUploadedMap.objects.filter(
            pk__in=[item.pk for item in navigation_task.get_available_user_maps()]
        )
        if form.is_valid():
            form.save()
            return redirect(reverse("navigationtask_detail", kwargs={"pk": pk}))
    else:
        form = FlightOrderConfigurationForm(instance=configuration)
        form.fields["map_user_source"].queryset = UserUploadedMap.objects.filter(
            pk__in=[item.pk for item in navigation_task.get_available_user_maps()]
        )
    return render(
        request,
        "display/flight_order_configuration_form.html",
        {
            "form": form,
            "navigation_task": navigation_task,
            "initial_color": configuration.map_line_colour,
            "system_map_zoom_levels": json.dumps(get_map_zoom_levels()),
        },
    )


@guardian_permission_required("display.change_contest", (Contest, "navigationtask__contestant__pk", "pk"))
def get_contestant_processing_statistics(request, pk):
    contestant = get_object_or_404(Contestant, pk=pk)
    figure = contestant.generate_processing_statistics()
    response = HttpResponse(figure, content_type="image/png")
    return response


@guardian_permission_required("display.view_contest", (Contest, "navigationtask__contestant__pk", "pk"))
def get_contestant_default_map(request, pk):
    contestant = get_object_or_404(Contestant, pk=pk)
    configuration = contestant.navigation_task.flightorderconfiguration
    margin = 10
    map_image = plot_route(
        contestant.navigation_task,
        configuration.document_size,
        zoom_level=configuration.map_zoom_level,
        landscape=configuration.map_orientation == LANDSCAPE,
        contestant=contestant,
        annotations=configuration.map_include_annotations,
        waypoints_only=not configuration.map_include_waypoints,
        dpi=configuration.map_dpi,
        scale=configuration.map_scale,
        map_source=configuration.map_source,
        user_map_source=configuration.map_user_source,
        line_width=configuration.map_line_width,
        colour=configuration.map_line_colour,
        include_meridians_and_parallels_lines=configuration.map_include_meridians_and_parallels_lines,
        margins_mm=margin,
    )
    pdf = embed_map_in_pdf(
        "a4paper" if configuration.document_size == A4 else "a3paper",
        map_image.read(),
        10 * A4_WIDTH - 2 * margin if configuration.document_size == A4 else 10 * A3_WIDTH - 2 * margin,
        10 * A4_HEIGHT - 2 * margin if configuration.document_size == A4 else 10 * A3_HEIGHT - 2 * margin,
        configuration.map_orientation == LANDSCAPE,
    )
    response = HttpResponse(pdf, content_type="application/pdf")
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
    report = generate_flight_orders_latex(contestant)
    response = HttpResponse(bytes(report), content_type="application/pdf")
    response["Content-Disposition"] = f"attachment; filename=flight_orders.pdf"
    return response


@guardian_permission_required("display.view_contest", (Contest, "navigationtask__pk", "pk"))
def generatenavigation_task_orders_template(request, pk):
    navigation_task = get_object_or_404(NavigationTask, pk=pk)
    single_contestant_pk = request.GET.get("contestant_pk")
    selected_contestants = navigation_task.contestant_set.filter(
        takeoff_time__gt=datetime.datetime.now(datetime.timezone.utc)
    )
    if single_contestant_pk:
        selected_contestants = navigation_task.contestant_set.filter(pk=single_contestant_pk)
    return render(
        request,
        "display/flight_order_progress.html",
        {
            "navigation_task": navigation_task,
            "selected_contestants": selected_contestants,
            "contestant_pk": [c.pk for c in navigation_task.contestant_set.all()],
        },
    )


def get_navigation_task_orders_status_object(pk) -> Dict:
    return {
        "completed_flight_orders_map": cache.get(f"completed_flight_orders_map_{pk}"),
        "transmitted_flight_orders_map": cache.get(f"transmitted_flight_orders_map_{pk}"),
        "generate_failed_flight_orders_map": cache.get(f"generate_failed_flight_orders_map_{pk}"),
        "transmit_failed_flight_orders_map": cache.get(f"transmit_failed_flight_orders_map_{pk}"),
    }


@api_view(["GET"])
@guardian_permission_required("display.view_contest", (Contest, "navigationtask__pk", "pk"))
def clear_flight_order_generation_cache(request, pk):
    navigation_task = get_object_or_404(NavigationTask, pk=pk)
    cache.delete(f"generate_failed_flight_orders_map_{navigation_task.pk}")
    cache.delete(f"completed_flight_orders_map_{navigation_task.pk}")
    return Response({})


@api_view(["GET"])
@guardian_permission_required("display.view_contest", (Contest, "navigationtask__pk", "pk"))
def generate_navigation_task_orders(request, pk):
    navigation_task = get_object_or_404(NavigationTask, pk=pk)
    contestant_pks = request.GET.get("contestant_pks")
    if not contestant_pks or len(contestant_pks) == 0:
        raise Http404
    contestant_pks = contestant_pks.split(",")
    contestants = navigation_task.contestant_set.filter(pk__in=contestant_pks)
    cache.set(
        f"completed_flight_orders_map_{navigation_task.pk}",
        {contestant.pk: False for contestant in contestants},
    )
    cache.set(f"generate_failed_flight_orders_map_{navigation_task.pk}", {})
    cache.delete(f"transmitted_flight_orders_map_{navigation_task.pk}")
    cache.delete(f"transmit_failed_flight_orders_map_{navigation_task.pk}")
    for contestant in contestants:
        # Delete existing order
        contestant.emailmaplink_set.all().delete()
        generate_and_maybe_notify_flight_order.apply_async(
            (
                contestant.pk,
                contestant.team.crew.member1.email,
                contestant.team.crew.member1.first_name,
                False,
            )
        )
    return Response(get_navigation_task_orders_status_object(pk))


@api_view(["GET"])
@guardian_permission_required("display.view_contest", (Contest, "navigationtask__pk", "pk"))
def broadcast_navigation_task_orders(request, pk):
    navigation_task = get_object_or_404(NavigationTask, pk=pk)
    contestant_pks = request.GET.get("contestant_pks")
    if not contestant_pks or len(contestant_pks) == 0:
        raise Http404
    contestant_pks = contestant_pks.split(",")
    contestants = navigation_task.contestant_set.filter(pk__in=contestant_pks)
    cache.set(
        f"transmitted_flight_orders_map_{navigation_task.pk}",
        {contestant.pk: False for contestant in contestants},
    )

    for contestant in contestants:
        notify_flight_order.apply_async(
            (
                contestant.pk,
                contestant.team.crew.member1.email,
                contestant.team.crew.member1.first_name,
            )
        )
    return Response(get_navigation_task_orders_status_object(pk))


@guardian_permission_required("display.view_contest", (Contest, "navigationtask__pk", "pk"))
def download_navigation_task_orders(request, pk):
    navigation_task = get_object_or_404(NavigationTask, pk=pk)
    contestant_pks = request.GET.get("contestant_pks")
    if not contestant_pks or len(contestant_pks) == 0:
        messages.error(request, f"No contestants were selected to download flight orders for.")
        return redirect("navigationtask_flightordersprogress", pk=pk)
    contestant_pks = contestant_pks.split(",")
    contestants = navigation_task.contestant_set.filter(pk__in=contestant_pks)
    orders = EmailMapLink.objects.filter(contestant__in=contestants)
    if orders.count() > 1:
        # set up zip folder
        zip_subdir = "flight_orders"
        zip_filename = zip_subdir + ".zip"
        byte_stream = BytesIO()
        zf = zipfile.ZipFile(byte_stream, "w")
        for order in EmailMapLink.objects.filter(contestant__in=contestants):
            zf.writestr(f"{order.contestant}.pdf", order.orders)
        zf.close()
        response = HttpResponse(byte_stream.getvalue(), content_type="application/x-zip-compressed")
        response["Content-Disposition"] = "attachment; filename=%s" % zip_filename
        return response
    elif orders.count() == 1:
        response = HttpResponse(orders.first().orders, content_type="application/pdf")
        response["Content-Disposition"] = f"attachment; filename=flight_orders.pdf"
        return response
    messages.error(request, f"There were no flight orders to download. Maybe they are still generating?")
    return redirect("navigationtask_flightordersprogress", pk=pk)


@api_view(["GET"])
@guardian_permission_required("display.view_contest", (Contest, "navigationtask__pk", "pk"))
def get_broadcast_navigation_task_orders_status(request, pk):
    return Response(get_navigation_task_orders_status_object(pk))


# @guardian_permission_required(
#     "display.view_contest", (Contest, "navigationtask__pk", "pk")
# )
# def get_broadcast_navigation_task_orders_status_template(request, pk):
#     navigation_task = get_object_or_404(NavigationTask, pk=pk)
#     return render(request, "display/broadcast_flight_order_progress.html", {"navigation_task": navigation_task})


@guardian_permission_required("display.view_contest", (Contest, "navigationtask__pk", "pk"))
def get_navigation_task_map(request, pk):
    navigation_task = get_object_or_404(NavigationTask, pk=pk)
    if request.method == "POST":
        form = MapForm(request.POST)
        form.fields["user_map_source"].queryset = navigation_task.get_available_user_maps()
        if form.is_valid():
            margin = 10
            map_image = plot_route(
                navigation_task,
                form.cleaned_data["size"],
                zoom_level=form.cleaned_data["zoom_level"],
                landscape=form.cleaned_data["orientation"] == LANDSCAPE,
                waypoints_only=not form.cleaned_data["plot_track_between_waypoints"],
                dpi=form.cleaned_data["dpi"],
                scale=int(form.cleaned_data["scale"]),
                map_source=form.cleaned_data["map_source"],
                user_map_source=form.cleaned_data["user_map_source"],
                line_width=float(form.cleaned_data["line_width"]),
                colour=form.cleaned_data["colour"],
                margins_mm=margin,
                include_meridians_and_parallels_lines=form.cleaned_data["include_meridians_and_parallels_lines"],
            )
            pdf = embed_map_in_pdf(
                "a4paper" if form.cleaned_data["size"] == A4 else "a3paper",
                map_image.read(),
                10 * A4_WIDTH - 2 * margin if form.cleaned_data["size"] == A4 else 10 * A3_WIDTH - 2 * margin,
                10 * A4_HEIGHT - 2 * margin if form.cleaned_data["size"] == A4 else 10 * A3_HEIGHT - 2 * margin,
                form.cleaned_data["orientation"] == LANDSCAPE,
            )

            response = HttpResponse(pdf, content_type="application/pdf")

            response["Content-Disposition"] = f"attachment; filename=map.pdf"
            return response
    else:
        configuration = navigation_task.flightorderconfiguration
        form = MapForm(
            initial={
                "zoom_level": configuration.map_zoom_level,
                "orientation": configuration.map_orientation,
                "plot_track_between_waypoints": configuration.map_plot_track_between_waypoints,
                "include_meridians_and_parallels_lines": configuration.map_include_meridians_and_parallels_lines,
                "scale": configuration.map_scale,
                "map_source": configuration.map_source,
                "user_map_source": configuration.map_user_source,
                "dpi": configuration.map_dpi,
                "line_width": configuration.map_line_width,
                "colour": configuration.map_line_colour,
            }
        )
        form.fields["user_map_source"].queryset = navigation_task.get_available_user_maps()
        form.fields["user_map_source"].initial = navigation_task.flightorderconfiguration.map_user_source
    return render(
        request,
        "display/map_form.html",
        {
            "form": form,
            "redirect": reverse("navigationtask_detail", kwargs={"pk": navigation_task.pk}),
            "system_map_zoom_levels": json.dumps(get_map_zoom_levels()),
        },
    )


@guardian_permission_required("display.change_contest", (Contest, "navigationtask__contestant__pk", "pk"))
def upload_gpx_track_for_contesant(request, pk):
    """
    Consumes a FC GPX file that contains the GPS track of a contestant.
    """
    contestant = get_object_or_404(Contestant, pk=pk)
    try:
        if not contestant.contestanttrack.calculator_finished and contestant.contestanttrack.calculator_started:
            messages.error(
                request,
                "Calculator is running, terminate it or wait until it is terminated",
            )
            return HttpResponseRedirect(
                reverse(
                    "navigationtask_detail",
                    kwargs={"pk": contestant.navigation_task.pk},
                )
            )
    except:
        pass

    if request.method == "POST":
        form = GPXTrackImportForm(request.POST, request.FILES)
        if form.is_valid():
            contestant.reset_track_and_score()
            track_file = request.FILES["track_file"]
            import_gpx_track.apply_async((contestant.pk, track_file.read().decode("utf-8")))
            messages.success(request, "Started loading track")
            return HttpResponseRedirect(
                reverse(
                    "navigationtask_detail",
                    kwargs={"pk": contestant.navigation_task.pk},
                )
            )
    else:
        form = GPXTrackImportForm()
    return render(
        request,
        "display/upload_gpx_form.html",
        {"form": form, "contestant": contestant},
    )


@guardian_permission_required("display.change_contest", (Contest, "navigationtask__contestant__pk", "pk"))
def download_gpx_track_contestant(request, pk):
    """
    Produces a GPX file from whatever is recorded
    """
    contestant = get_object_or_404(Contestant, pk=pk)
    recorded_track = contestant.get_track()
    gpx = gpxpy.gpx.GPX()
    track = gpxpy.gpx.GPXTrack()
    gpx.tracks.append(track)
    segment = gpxpy.gpx.GPXTrackSegment()
    track.segments.append(segment)
    for position in recorded_track:
        segment.points.append(
            gpxpy.gpx.GPXTrackPoint(
                position.latitude,
                position.longitude,
                elevation=position.altitude,
                time=position.time,
                comment="Interpolated" if position.interpolated else "",
            )
        )
    response = HttpResponse(gpx.to_xml(), content_type="application/gpx+xml")
    response["Content-Disposition"] = f"attachment; filename=track.gpx"
    return response


@guardian_permission_required("display.change_contest", (Contest, "navigationtask__contestant__pk", "pk"))
def revert_uploaded_gpx_track_for_contestant(request, pk):
    """
    Revert to traccar track
    """
    contestant = get_object_or_404(Contestant, pk=pk)
    try:
        if not contestant.contestanttrack.calculator_finished and contestant.contestanttrack.calculator_started:
            messages.error(
                request,
                "Calculator is running, terminate it or wait until it is terminated",
            )
            return HttpResponseRedirect(
                reverse(
                    "navigationtask_detail",
                    kwargs={"pk": contestant.navigation_task.pk},
                )
            )
    except:
        pass
    contestant.reset_track_and_score()
    revert_gpx_track_to_traccar.apply_async((contestant.pk,))
    messages.success(request, "Started loading track")
    return HttpResponseRedirect(reverse("navigationtask_detail", kwargs={"pk": contestant.navigation_task.pk}))


#### Editable route permission management
@guardian_permission_required("display.change_editableroute", (EditableRoute, "pk", "pk"))
def list_editableroute_permissions(request, pk):
    editableroute = get_object_or_404(EditableRoute, pk=pk)
    users_and_permissions = get_users_with_perms(editableroute, attach_perms=True)
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
        "display/editableroute_permissions.html",
        {"users": users, "editableroute": editableroute},
    )


@guardian_permission_required("display.change_editableroute", (EditableRoute, "pk", "pk"))
def delete_user_editableroute_permissions(request, pk, user_pk):
    editableroute = get_object_or_404(EditableRoute, pk=pk)
    user = get_object_or_404(MyUser, pk=user_pk)
    permissions = ["change_editableroute", "view_editableroute", "delete_editableroute"]
    for permission in permissions:
        remove_perm(f"display.{permission}", user, editableroute)
    return redirect(reverse("editableroute_permissions_list", kwargs={"pk": pk}))


@guardian_permission_required("display.change_editableroute", (EditableRoute, "pk", "pk"))
def change_user_editableroute_permissions(request, pk, user_pk):
    editableroute = get_object_or_404(EditableRoute, pk=pk)
    user = get_object_or_404(MyUser, pk=user_pk)
    if request.method == "POST":
        form = ChangeEditableRoutePermissionsForm(request.POST)
        if form.is_valid():
            permissions = ["change_editableroute", "view_editableroute", "delete_editableroute"]
            for permission in permissions:
                if form.cleaned_data[permission]:
                    assign_perm(f"display.{permission}", user, editableroute)
                else:
                    remove_perm(f"display.{permission}", user, editableroute)
            return redirect(reverse("editableroute_permissions_list", kwargs={"pk": pk}))
    existing_permissions = get_user_perms(user, editableroute)
    initial = {item: True for item in existing_permissions}
    form = ChangeEditableRoutePermissionsForm(initial=initial)
    return render(
        request, "display/editableroute_permissions_form.html", {"form": form, "editableroute": editableroute}
    )


@guardian_permission_required("display.change_editableroute", (EditableRoute, "pk", "pk"))
def add_user_editableroute_permissions(request, pk):
    editableroute = get_object_or_404(EditableRoute, pk=pk)
    if request.method == "POST":
        form = AddEditableRoutePermissionsForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"]
            try:
                user = MyUser.objects.get(email=email)
            except ObjectDoesNotExist:
                messages.error(request, f"User '{email}' does not exist")
                return redirect(reverse("editableroute_permissions_list", kwargs={"pk": pk}))
            permissions = ["change_editableroute", "view_editableroute", "delete_editableroute"]
            for permission in permissions:
                if form.cleaned_data[permission]:
                    assign_perm(f"display.{permission}", user, editableroute)
                else:
                    remove_perm(f"display.{permission}", user, editableroute)
            return redirect(reverse("editableroute_permissions_list", kwargs={"pk": pk}))
    form = AddEditableRoutePermissionsForm()
    return render(
        request, "display/editableroute_permissions_form.html", {"form": form, "editableroute": editableroute}
    )


###### Editable route permission management ends


#### Contest permission management
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


###### Contest permission management ends


class ContestList(PermissionRequiredMixin, ListView):
    model = Contest
    permission_required = ("display.view_contest",)
    # todo: Temporary change to try the react version
    template_name = "display/contest_list_react.html"

    def get_queryset(self):
        # Important not to accept global permissions, otherwise any content creator can view everything
        objects = get_objects_for_user(self.request.user, "display.view_contest", accept_global_perms=False)
        return objects


@guardian_permission_required("display.change_contest", (Contest, "navigationtask__contestant__pk", "pk"))
def terminate_contestant_calculator(request, pk):
    contestant = get_object_or_404(Contestant, pk=pk)

    try:
        contestant.blocking_request_calculator_termination()
        messages.success(request, "Calculator terminated successfully")
    except TimeoutError:
        messages.info(request, "Calculator termination requested, but not stopped in time")
    return HttpResponseRedirect(reverse("navigationtask_detail", kwargs={"pk": contestant.navigation_task.pk}))


@guardian_permission_required("display.change_contest", (Contest, "navigationtask__contestant__pk", "pk"))
def restart_contestant_calculator(request, pk):
    contestant = get_object_or_404(Contestant, pk=pk)
    contestant.blocking_request_calculator_termination()
    messages.success(
        request,
        "Calculator should have been restarted. It may take a few minutes for it to come back to life.",
    )
    contestant.reset_track_and_score()
    cancel_termination_request(pk)
    return HttpResponseRedirect(reverse("navigationtask_detail", kwargs={"pk": contestant.navigation_task.pk}))


@api_view(["GET"])
@guardian_permission_required("display.view_contest", (Contest, "navigationtask__pk", "pk"))
def get_running_calculators(request, pk):
    """
    Returns a list of (contestant_id, boolean) tuples where the boolean indicates whether a calculator is currently
    running for the contestant.
    """
    navigation_task = get_object_or_404(NavigationTask, pk=pk)
    status_list = []
    for contestant in navigation_task.contestant_set.all():
        status_list.append([contestant.pk, is_calculator_running(contestant.pk)])
    return Response(status_list)


@guardian_permission_required("display.view_contest", (Contest, "navigationtask__pk", "pk"))
def view_navigation_task_rules(request, pk):
    navigation_task = get_object_or_404(NavigationTask, pk=pk)
    timezone.activate(navigation_task.contest.time_zone)
    return render(request, "display/navigationtask_rules.html", {"object": navigation_task})


@guardian_permission_required("display.change_contest", (Contest, "pk", "pk"))
def clear_results_service(request, pk):
    contest = get_object_or_404(Contest, pk=pk)
    contest.task_set.all().delete()
    contest.contestsummary_set.all().delete()
    messages.success(request, "Successfully cleared contest results from results service")
    return HttpResponseRedirect(reverse("contest_details", kwargs={"pk": pk}))


class ContestCreateView(PermissionRequiredMixin, CreateView):
    model = Contest
    permission_required = ("display.add_contest",)
    form_class = ContestForm

    def form_valid(self, form):
        instance = form.save(commit=False)  # type: Contest
        instance.validate_and_set_country()
        instance.initialise(self.request.user)
        self.object = instance
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse("contest_details", kwargs={"pk": self.object.pk})


class ContestDetailView(ContestTimeZoneMixin, GuardianPermissionRequiredMixin, DetailView):
    model = Contest
    permission_required = ("display.view_contest",)


class ContestUpdateView(ContestTimeZoneMixin, GuardianPermissionRequiredMixin, UpdateView):
    model = Contest
    permission_required = ("display.change_contest",)
    form_class = ContestForm

    def form_valid(self, form):
        instance = form.save(commit=False)  # type: Contest
        instance.validate_and_set_country()
        instance.save()
        return HttpResponseRedirect(self.get_success_url())

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
        return reverse("navigationtask_detail", kwargs={"pk": self.get_object().pk})


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
    contestant.contestanttrack.update_score(contestant.contestanttrack.score - entry.points)
    entry.delete()
    # Push the updated data so that it is reflected on the contest track
    wf = WebsocketFacade()
    wf.transmit_score_log_entry(contestant)
    wf.transmit_annotations(contestant)
    wf.transmit_basic_information(contestant)
    return HttpResponseRedirect(reverse("contestant_gate_times", kwargs={"pk": contestant.pk}))


class ContestantGateTimesView(ContestantTimeZoneMixin, GuardianPermissionRequiredMixin, DetailView):
    model = Contestant
    permission_required = ("display.view_contest",)
    template_name = "display/contestant_gate_times.html"

    def get_permission_object(self):
        return self.get_object().navigation_task.contest

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        log = {}
        distances = {}
        total_distance = 0
        for waypoint in self.object.navigation_task.route.waypoints:  # type: Waypoint
            distances[waypoint.name] = waypoint.distance_previous
            total_distance += waypoint.distance_previous if waypoint.distance_previous > 0 else 0
        context["distances"] = distances
        context["total_distance"] = total_distance
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


class ContestantUpdateView(ContestantTimeZoneMixin, GuardianPermissionRequiredMixin, UpdateView):
    form_class = ContestantForm
    model = Contestant
    permission_required = ("display.change_contest",)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["redirect"] = self.get_success_url()
        return context

    def get_form_kwargs(self):
        arguments = super().get_form_kwargs()
        arguments["navigation_task"] = self.get_object().navigation_task
        return arguments

    def get_success_url(self):
        return reverse("navigationtask_detail", kwargs={"pk": self.get_object().navigation_task.pk})

    def get_permission_object(self):
        return self.get_object().navigation_task.contest

    def form_valid(self, form):
        instance = form.save(commit=False)  # type: Contestant
        instance.predefined_gate_times = None
        instance.save()
        self.object = instance
        return HttpResponseRedirect(self.get_success_url())


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
        context["redirect"] = self.get_success_url()
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
@guardian_permission_required("display.view_contest", (Contest, "navigationtask__pk", "pk"))
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
                    {"v": f"{contestant}{' (Adaptive)' if contestant.adaptive_start else ''}"},
                    {"v": contestant.takeoff_time if not contestant.adaptive_start else contestant.tracker_start_time},
                    {
                        "v": contestant.landing_time_after_final_gate
                        if not contestant.adaptive_start
                        else contestant.finished_by_time
                    },
                ]
            }
        )

    return Response({"cols": columns, "rows": rows})


@guardian_permission_required("display.view_contest", (Contest, "navigationtask__pk", "pk"))
def render_contestants_timeline(request, pk):
    navigation_task = get_object_or_404(NavigationTask, pk=pk)
    timezone.activate(navigation_task.contest.time_zone)
    return render(
        request,
        "display/contestant_timeline.html",
        context={"navigation_task": navigation_task},
    )


@guardian_permission_required("display.view_contest", (Contest, "navigationtask__pk", "pk"))
def clear_future_contestants(request, pk):
    navigation_task = get_object_or_404(NavigationTask, pk=pk)
    now = datetime.datetime.now(datetime.timezone.utc)
    candidates = navigation_task.contestant_set.all()  # filter(takeoff_time__gte=now + datetime.timedelta(minutes=15))
    messages.success(request, f"{candidates.count()} contestants have been deleted")
    candidates.delete()
    return redirect(reverse("navigationtask_detail", kwargs={"pk": navigation_task.pk}))


@guardian_permission_required("display.change_contest", (Contest, "navigationtask__pk", "pk"))
def add_contest_teams_to_navigation_task(request, pk):
    """
    Add all teams registered for a contest to a task. If the team is already assigned as a contestant, ignore it.

    Apply basic deconflicting of speed, aircraft, and trackers
    """
    TIME_LOCK_MINUTES = 30
    navigation_task = get_object_or_404(NavigationTask, pk=pk)
    timezone.activate(navigation_task.contest.time_zone)
    form = ContestTeamOptimisationForm()
    if request.method == "POST":
        form = ContestTeamOptimisationForm(request.POST)
        form.fields["contest_teams"].choices = [
            (str(item.pk), str(item)) for item in navigation_task.contest.contestteam_set.all()
        ]
        if form.is_valid():
            try:
                success, returned_messages = schedule_and_create_contestants(
                    navigation_task,
                    [int(item) for item in form.cleaned_data["contest_teams"]],
                    form.cleaned_data["first_takeoff_time"],
                    form.cleaned_data["tracker_lead_time_minutes"],
                    form.cleaned_data["minutes_for_aircraft_switch"],
                    form.cleaned_data["minutes_for_tracker_switch"],
                    form.cleaned_data["minutes_between_contestants_at_start"],
                    form.cleaned_data["minutes_between_contestants_at_finish"],
                    form.cleaned_data["minutes_for_crew_switch"],
                    optimise=form.cleaned_data.get("optimise", False),
                )
                if not success:
                    messages.error(request, "Optimisation failed")
                else:
                    messages.success(request, "Optimisation successful")
                for item in returned_messages:
                    messages.warning(request, item)
            except ValidationError as v:
                messages.error(request, f"Failed validating created contestant: {v}")
            return redirect(
                reverse(
                    "navigationtask_contestantstimeline",
                    kwargs={"pk": navigation_task.pk},
                )
            )
    form.fields["first_takeoff_time"].initial = navigation_task.start_time
    form.fields["contest_teams"].choices = [
        (str(item.pk), str(item)) for item in navigation_task.contest.contestteam_set.all()
    ]
    return render(
        request,
        "display/contestteam_optimisation_form.html",
        {"form": form, "navigation_task": navigation_task},
    )


@guardian_permission_required("display.change_contest", (Contest, "navigationtask__pk", "pk"))
def navigation_task_restore_original_scorecard_view(request, pk):
    navigation_task = get_object_or_404(NavigationTask, pk=pk)
    navigation_task.assign_scorecard_from_original(force=True)
    messages.success(request, "Original scorecard values have been restored")
    return redirect(reverse("navigationtask_scoredetails", kwargs={"pk": navigation_task.pk}))


@guardian_permission_required("display.change_contest", (Contest, "navigationtask__pk", "pk"))
def navigation_task_scorecard_override_view(request, pk):
    navigation_task = get_object_or_404(NavigationTask, pk=pk)
    form = ScorecardForm(instance=navigation_task.scorecard)
    if request.method == "POST":
        if "cancel" in request.POST:
            return redirect(reverse("navigationtask_scoredetails", kwargs={"pk": navigation_task.pk}))
        form = ScorecardForm(request.POST, instance=navigation_task.scorecard)
        if form.is_valid():
            form.save()
            return redirect(reverse("navigationtask_scoredetails", kwargs={"pk": navigation_task.pk}))
    return render(
        request,
        "display/scorecard_override_form.html",
        {"form": form, "navigation_task": navigation_task},
    )


@guardian_permission_required("display.change_contest", (Contest, "navigationtask__pk", "pk"))
def navigation_task_gatescore_override_view(request, pk, gate_score_pk):
    navigation_task = get_object_or_404(NavigationTask, pk=pk)
    gate_score = get_object_or_404(GateScore, pk=gate_score_pk)
    form = GateScoreForm(instance=gate_score)
    if request.method == "POST":
        if "cancel" in request.POST:
            return redirect(reverse("navigationtask_scoredetails", kwargs={"pk": navigation_task.pk}))
        form = GateScoreForm(request.POST, instance=gate_score)
        if form.is_valid():
            form.save()
            return redirect(reverse("navigationtask_scoredetails", kwargs={"pk": navigation_task.pk}))
    return render(
        request,
        "display/gatescore_override_form.html",
        {"form": form, "navigation_task": navigation_task, "gate_score": gate_score},
    )


def _extract_values_from_form(form: "Form") -> List:
    """
    Extracts the data from a crispy form using the data in the helper layout.
    """
    content = []
    for field in form.helper.layout:
        if isinstance(field, Fieldset):
            data = {"legend": field.legend, "values": []}
            for internal_field in field.fields:
                data["values"].append(
                    {
                        "label": form.fields[internal_field].label,
                        "value": getattr(form.instance, internal_field),
                    }
                )
            content.append(data)
    return content


def navigation_task_view_detailed_score(request, pk):
    navigation_task = get_object_or_404(NavigationTask, pk=pk)
    scorecard_form = ScorecardForm(instance=navigation_task.scorecard)
    content = _extract_values_from_form(scorecard_form)
    for key in list(scorecard_form.fields.keys()):
        if key not in navigation_task.scorecard.visible_fields:
            scorecard_form.fields.pop(key)
    scorecard_form.pk = navigation_task.scorecard.pk
    scorecard_form.content = content
    scorecard_form.free_text = navigation_task.scorecard.free_text
    gate_score_forms = []
    for gate_score in navigation_task.scorecard.gatescore_set.all().order_by("gate_type"):
        if len(gate_score.visible_fields) > 0:
            form = GateScoreForm(instance=gate_score)
            form.pk = gate_score.pk
            form.name = gate_score.get_gate_type_display()
            content = _extract_values_from_form(form)
            for key in list(form.fields.keys()):
                if key not in gate_score.visible_fields:
                    form.fields.pop(key)
                else:
                    form.fields[key].disabled = True
            form.helper.layout.pop(-1)  # Remove submit
            form.content = content
            gate_score_forms.append(form)
    return render(
        request,
        "display/scorecard_details.html",
        {
            "navigation_task": navigation_task,
            "scorecard_form": scorecard_form,
            "gate_score_forms": gate_score_forms,
        },
    )


def cached_generate_data(contestant_pk) -> Dict:
    return _generate_data(contestant_pk)


def _generate_data(contestant_pk):
    contestant = get_object_or_404(Contestant, pk=contestant_pk)  # type: Contestant
    logger.debug("Fetching track for {} {}".format(contestant.pk, contestant))
    # Do not include track if we have not started a calculator yet
    position_data = (
        contestant.get_track()
        if hasattr(contestant, "contestanttrack") and contestant.contestanttrack.calculator_started
        else []
    )
    if len(position_data) > 0:
        global_latest_time = position_data[-1].time
    else:
        global_latest_time = datetime.datetime(2016, 1, 1, tzinfo=datetime.timezone.utc)
    progress = 0
    for index, item in enumerate(position_data):
        if index % 30 == 0:
            progress = contestant.calculate_progress(item.time, ignore_finished=True)
        item.progress = progress
    logger.debug(
        "Completed generating data {} {} with {} positions".format(contestant.pk, contestant, len(position_data))
    )
    data = generate_contestant_data_block(
        contestant,
        positions=PositionSerialiser(position_data, many=True).data,
        annotations=TrackAnnotationSerialiser(contestant.trackannotation_set.all(), many=True).data,
        log_entries=ScoreLogEntrySerialiser(contestant.scorelogentry_set.filter(type=ANOMALY), many=True).data,
        latest_time=global_latest_time,
        gate_scores=GateCumulativeScoreSerialiser(contestant.gatecumulativescore_set.all(), many=True).data,
        playing_cards=PlayingCardSerialiser(contestant.playingcard_set.all(), many=True).data,
        include_contestant_track=True,
        gate_times=contestant.gate_times,
    )
    return data


# Everything below he is related to management and requires authentication
def show_precision_path(wizard):
    return (wizard.get_cleaned_data_for_step("task_type") or {}).get("task_type") in (
        NavigationTask.PRECISION,
        NavigationTask.POKER,
    )


def show_anr_path(wizard):
    return (wizard.get_cleaned_data_for_step("task_type") or {}).get("task_type") in (NavigationTask.ANR_CORRIDOR,)


def show_airsports_path(wizard):
    return (wizard.get_cleaned_data_for_step("task_type") or {}).get("task_type") in (
        NavigationTask.AIRSPORTS,
        NavigationTask.AIRSPORT_CHALLENGE,
    )


def show_landing_path(wizard):
    return (wizard.get_cleaned_data_for_step("task_type") or {}).get("task_type") in (NavigationTask.LANDING,)


class SessionWizardOverrideView(SessionWizardView):
    #### Hack to avoid get_form_list() which leads to recursion error with conditional steps.
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
            from django.contrib import messages

            messages.error(self.request, str(e))
            return self.render_revalidation_failure("task_type", self.get_form_instance("task_type"), **kwargs)

    def create_route(self, scorecard: Scorecard) -> Tuple[Route, Optional[EditableRoute]]:
        task_type = self.get_cleaned_data_for_step("task_type")["task_type"]
        editable_route = None
        route = None
        if task_type in (NavigationTask.PRECISION, NavigationTask.POKER):
            initial_step_data = self.get_cleaned_data_for_step("precision_route_import")
            use_procedure_turns = self.get_cleaned_data_for_step("task_content")[
                "original_scorecard"
            ].use_procedure_turns
            route = initial_step_data["internal_route"].create_precision_route(use_procedure_turns, scorecard)
            editable_route = initial_step_data["internal_route"]
        elif task_type == NavigationTask.ANR_CORRIDOR:
            initial_step_data = self.get_cleaned_data_for_step("anr_route_import")
            rounded_corners = initial_step_data["rounded_corners"]
            corridor_width = initial_step_data["corridor_width"]
            route = initial_step_data["internal_route"].create_anr_route(rounded_corners, corridor_width, scorecard)
            editable_route = initial_step_data["internal_route"]
        elif task_type in (NavigationTask.AIRSPORTS, NavigationTask.AIRSPORT_CHALLENGE):
            initial_step_data = self.get_cleaned_data_for_step("airsports_route_import")
            rounded_corners = initial_step_data["rounded_corners"]
            route = initial_step_data["internal_route"].create_airsports_route(rounded_corners, scorecard)
            editable_route = initial_step_data["internal_route"]
        elif task_type == NavigationTask.LANDING:
            initial_step_data = self.get_cleaned_data_for_step("landing_route_import")
            route = initial_step_data["internal_route"].create_landing_route()
            editable_route = initial_step_data["internal_route"]
        # Check for gate polygons that do not match a turning point
        route.validate_gate_polygons()
        return route, editable_route

    def done(self, form_list, **kwargs):
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
        form = super().get_form(step, data, files)
        if step in (
            "anr_route_import",
            "precision_route_import",
            "landing_route_import",
        ):
            form.fields["internal_route"].queryset = EditableRoute.get_for_user(self.request.user)
        return form

    def get_form_initial(self, step):
        if step == "task_content":
            return {
                "score_sorting_direction": self.contest.summary_score_sorting_direction,
            }
        return {}


def contest_not_chosen(wizard):
    return (wizard.get_cleaned_data_for_step("contest_selection") or {}).get("contest") is None


def anr_task_type(wizard):
    return (wizard.get_cleaned_data_for_step("contest_selection") or {}).get("task_type") == NavigationTask.ANR_CORRIDOR


def airsports_task_type(wizard):
    return (wizard.get_cleaned_data_for_step("contest_selection") or {}).get("task_type") in (
        NavigationTask.AIRSPORTS,
        NavigationTask.AIRSPORT_CHALLENGE,
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
        route = None
        if task_type in (NavigationTask.PRECISION, NavigationTask.POKER):
            use_procedure_turns = scorecard.use_procedure_turns
            route = self.editable_route.create_precision_route(use_procedure_turns, scorecard)
        elif task_type == NavigationTask.ANR_CORRIDOR:
            initial_step_data = self.get_cleaned_data_for_step("anr_parameters")
            rounded_corners = initial_step_data["rounded_corners"]
            corridor_width = initial_step_data["corridor_width"]
            route = self.editable_route.create_anr_route(rounded_corners, corridor_width, scorecard)
        elif task_type in (NavigationTask.AIRSPORTS, NavigationTask.AIRSPORT_CHALLENGE):
            initial_step_data = self.get_cleaned_data_for_step("airsports_parameters")
            rounded_corners = initial_step_data["rounded_corners"]
            route = self.editable_route.create_airsports_route(rounded_corners, scorecard)
        elif task_type == NavigationTask.LANDING:
            route = self.editable_route.create_landing_route()
        # Check for gate polygons that do not match a turning point
        route.validate_gate_polygons()
        return route

    def done(self, form_list, **kwargs):
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


class ContestTeamTrackingUpdate(GuardianPermissionRequiredMixin, UpdateView):
    permission_required = ("display.change_contest",)

    def get_permission_object(self):
        contest = get_object_or_404(Contest, pk=self.kwargs.get("contest_pk"))
        return contest

    model = ContestTeam
    form_class = TrackingDataForm

    def get_success_url(self):
        return reverse_lazy("contest_team_list", kwargs={"contest_pk": self.kwargs["contest_pk"]})


class TeamUpdateView(GuardianPermissionRequiredMixin, UpdateView):
    permission_required = ("display.change_contest",)

    def get_permission_object(self):
        contest = get_object_or_404(Contest, pk=self.kwargs.get("contest_pk"))
        return contest

    model = Team
    form_class = TeamForm

    def get_success_url(self):
        return reverse_lazy("contest_team_list", kwargs={"contest_pk": self.kwargs["contest_pk"]})


def create_new_pilot(wizard):
    cleaned = wizard.get_post_data_for_step("member1search") or {}
    return cleaned.get("use_existing_pilot") is None


def create_new_copilot(wizard):
    cleaned = wizard.get_post_data_for_step("member2search") or {}
    return cleaned.get("use_existing_copilot") is None and cleaned.get("skip_copilot") is None


class RegisterTeamWizard(GuardianPermissionRequiredMixin, SessionWizardOverrideView):
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


class PersonList(SuperuserRequiredMixin, ListView):
    model = Person

    def get_queryset(self):
        return Person.objects.all().order_by("last_name", "first_name")


class PersonUpdateView(SuperuserRequiredMixin, UpdateView):
    model = Person
    success_url = reverse_lazy("person_list")
    form_class = PersonForm


class StatisticsView(SuperuserRequiredMixin, TemplateView):
    template_name = "display/statistics.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        navigation_task_by_country = defaultdict(lambda: 0)
        contest_by_country = defaultdict(lambda: 0)
        for task in NavigationTask.objects.all():
            navigation_task_by_country[task.country_name] += 1
        for contest in Contest.objects.all():
            for code in contest.country_names:
                contest_by_country[code] += 1
        started_contestants = Contestant.objects.filter(contestanttrack__calculator_started=True).exclude(
            contestanttrack__current_state="Waiting..."
        )
        person_with_started_contestant = (
            Person.objects.filter(
                Q(crewmember_one__team__contestant__in=started_contestants)
                | Q(crewmember_two__team__contestant__in=started_contestants)
            )
            .distinct()
            .count()
        )
        context["number_of_persons_crossed_starting"] = person_with_started_contestant
        context["number_of_persons"] = Person.objects.all().count()
        context["number_of_tasks"] = NavigationTask.objects.all().count()
        context["number_of_contests"] = Contest.objects.all().count()
        context["number_of_contestants"] = Contestant.objects.all().count()
        context["number_of_started_contestants"] = Contestant.objects.filter(
            contestanttrack__calculator_started=True
        ).count()
        context["number_of_contestants_crossed_starting"] = started_contestants.count()
        context["navigation_task_per_country"] = sorted(
            ((country, count) for country, count in navigation_task_by_country.items()),
            key=lambda k: k[1],
            reverse=True,
        )
        context["contest_per_country"] = sorted(
            ((country, count) for country, count in contest_by_country.items()), key=lambda k: k[1], reverse=True
        )
        return context


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
        context["contest"] = get_object_or_404(Contest, pk=self.kwargs.get("contest_pk"))
        return context


class EditableRouteList(GuardianPermissionRequiredMixin, ListView):
    model = EditableRoute
    permission_required = ("display.view_editableroute",)
    # todo: Temporary change to test react view
    template_name = "display/editableroute_list_react.html"

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


@guardian_permission_required("display.change_editableroute", (EditableRoute, "pk", "pk"))
def copy_editable_route(request, pk):
    editable_route = get_object_or_404(EditableRoute, pk=pk)
    editable_route.pk = None
    editable_route.id = None
    editable_route.name += "_copy"
    editable_route.save()
    assign_perm(f"display.change_editableroute", request.user, editable_route)
    assign_perm(f"display.delete_editableroute", request.user, editable_route)
    assign_perm(f"display.view_editableroute", request.user, editable_route)
    return HttpResponseRedirect(reverse("editableroute_list"))


@guardian_permission_required("display.change_contest", (Contest, "pk", "contest_pk"))
def remove_team_from_contest(request, contest_pk, team_pk):
    contest = get_object_or_404(Contest, pk=contest_pk)
    team = get_object_or_404(Team, pk=team_pk)
    ContestTeam.objects.filter(contest=contest, team=team).delete()
    return HttpResponseRedirect(reverse("contest_team_list", kwargs={"contest_pk": contest_pk}))


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
                if self.request.user.first_name and len(self.request.user.first_name) > 0
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
        person = self.get_object()
        contest_teams = (
            ContestTeam.objects.filter(
                Q(team__crew__member1=self.get_object()) | Q(team__crew__member2=self.get_object()),
                contest__in=available_contests,
            )
            .order_by("contest__start_time")
            .distinct()
        )
        teams = []
        for team in contest_teams:
            team.can_edit = team.team.crew.member1 == self.get_object()
            teams.append(team)
        return Response(ContestTeamManagementSerialiser(teams, many=True, context={"request": request}).data)

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
        return Response(NavigationTasksSummarySerialiser(instance=contestant.navigation_task).data)

    @action(detail=False, methods=["get"])
    def get_current_app_navigation_task(self, request, *args, **kwargs):
        person = self.get_object()
        contestant, _ = Contestant.get_contestant_for_device_at_time(
            person.simulator_tracking_id, datetime.datetime.now(datetime.timezone.utc)
        )
        if not contestant:
            raise Http404
        return Response(NavigationTasksSummarySerialiser(instance=contestant.navigation_task).data)

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
        ).order_by("name")

    def perform_update(self, serializer):
        super().perform_update(serializer)
        self.get_object().update_thumbnail()

    def perform_create(self, serializer):
        super().perform_create(serializer)
        try:
            serializer.instance.thumbnail.save(
                serializer.instance.name + "_thumbnail.png",
                ContentFile(serializer.instance.create_thumbnail().getvalue()),
                save=True,
            )
        except:
            logger.exception("Failed creating editable route thumbnail")


class ContestFrontEndViewSet(mixins.ListModelMixin, GenericViewSet):
    """
    Internal endpoint to drive the contest list front end
    """

    queryset = Contest.objects.all()
    serializer_class = ContestFrontEndSerialiser

    permission_classes = [(permissions.IsAuthenticated & ContestPermissions)]

    def get_queryset(self):
        return (
            get_objects_for_user(
                self.request.user,
                "display.view_contest",
                klass=self.queryset,
                accept_global_perms=False,
            )
            .annotate(Count("navigationtask", distinct=True))
            .order_by("name")
        )


class ContestViewSet(ModelViewSet):
    """
    A contest is a high level wrapper for multiple tasks. It provides a lightweight view of a contest and is used by
    the front end to display the contest list on the global map.
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
        "results": ContestSerialiserWithResults,
    }
    default_serialiser_class = ContestSerialiser
    lookup_url_kwarg = "pk"

    permission_classes = [ContestPublicPermissions | (permissions.IsAuthenticated & ContestPermissions)]

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
        ).prefetch_related("navigationtask_set", "contest_teams")

    @action(detail=False, methods=["get"])
    def results(self, request, *args, **kwargs):
        """
        Get contests with ContestResults. Used by the main page in the results service, ContestSummaryResultsTable.
        This data replaces the original contest data in the redux storage, so it must use a serialiser that includes
        all the original data.
        """
        data = self.get_serializer_class()(self.get_queryset(), many=True, context={"request": self.request}).data
        return Response(data)

    @action(detail=True, methods=["get"])
    def get_current_time(self, request, *args, **kwargs):
        """
        Return the current time for the appropriate time zone. It does not seem to be used by the front end anywhere.
        """
        contest = self.get_object()
        return Response(datetime.datetime.now(datetime.timezone.utc).astimezone(contest.time_zone).strftime("%H:%M:%S"))

    @action(detail=True, methods=["put"])
    def share(self, request, *args, **kwargs):
        """
        Change the visibility of the navigation task to one of the public, private, or unlisted
        """
        contest = self.get_object()
        serialiser = self.get_serializer(data=request.data)  # type: SharingSerialiser
        if serialiser.is_valid():
            if serialiser.validated_data["visibility"] == serialiser.PUBLIC:
                contest.make_public()
            elif serialiser.validated_data["visibility"] == serialiser.PRIVATE:
                contest.make_private()
            elif serialiser.validated_data["visibility"] == serialiser.UNLISTED:
                contest.make_unlisted()
        return Response(serialiser.data, status=HTTP_200_OK)

    @action(detail=False, methods=["get"])
    def ongoing_navigation(self, request, *args, **kwargs):
        navigation_tasks = (
            NavigationTask.get_visible_navigation_tasks(self.request.user)
            .filter(
                contestant__contestanttrack__calculator_started=True,
                contestant__contestanttrack__calculator_finished=False,
                contestant__finished_by_time__gt=datetime.datetime.now(datetime.timezone.utc),
            )
            .distinct()
        )
        data = self.get_serializer_class()(navigation_tasks, many=True, context={"request": self.request}).data
        return Response(data)

    @action(detail=True, methods=["get"])
    def results_details(self, request, *args, **kwargs):
        """
        Retrieve the full list of contest summaries, tasks summaries, and individual test results for the contest
        """
        contest = self.get_object()
        contest.permission_change_contest = request.user.has_perm("display.change_contest", contest)
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

    @action(detail=True, methods=["post"])
    def team_results_delete(self, request, *args, **kwargs):
        contest = self.get_object()
        team_id = request.data["team_id"]
        ContestTeam.objects.filter(contest=contest, team__pk=team_id).delete()
        ContestSummary.objects.filter(contest=contest, team__pk=team_id).delete()
        # from websocket_channels import WebsocketFacade

        ws = WebsocketFacade()
        ws.transmit_contest_results(request.user, contest)
        ws.transmit_teams(contest)
        return Response(status=HTTP_204_NO_CONTENT)

    @action(
        detail=True,
        methods=["POST", "PUT"],
        permission_classes=[permissions.IsAuthenticated & ContestPublicModificationPermissions],
    )
    def signup(self, request, *args, **kwargs):
        contest = self.get_object()
        if request.method == "POST":
            contest = None
        serialiser = self.get_serializer(instance=contest, data=request.data)
        serialiser.is_valid()
        contest_team = serialiser.save()
        return Response(ContestTeamSerialiser(contest_team).data, status=status.HTTP_201_CREATED)

    @action(
        detail=True,
        methods=["DELETE"],
        permission_classes=[permissions.IsAuthenticated & ContestPublicModificationPermissions],
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
            context.update({"contest": get_object_or_404(Contest, pk=self.kwargs.get("contest_pk"))})
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
        except Contest.DoesNotExist:
            raise Http404("Contest does not exist")
        return ContestTeam.objects.filter(contest=contest)


class NavigationTaskViewSet(ModelViewSet):
    """
    Main navigation task view set. Used by the front end to load the tracking map.
    """

    queryset = NavigationTask.objects.all()
    serializer_classes = {
        "share": SharingSerialiser,
        "contestant_self_registration": SelfManagementSerialiser,
        "scorecard": ScorecardNestedSerialiser,
    }
    default_serialiser_class = NavigationTaskNestedTeamRouteSerialiser
    lookup_url_kwarg = "pk"

    permission_classes = [
        NavigationTaskPublicPermissions | (permissions.IsAuthenticated & NavigationTaskContestPermissions)
    ]

    http_method_names = ["get", "post", "delete", "put"]

    def get_serializer_class(self):
        return self.serializer_classes.get(self.action, self.default_serialiser_class)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["selected_contestants"] = [
            item for item in self.request.GET.get("contestantIds", "").split(",") if len(item) > 0
        ]
        try:
            context.update({"contest": get_object_or_404(Contest, pk=self.kwargs.get("contest_pk"))})
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
        methods=["get", "put"],
        permission_classes=[permissions.IsAuthenticated & NavigationTaskContestPermissions],
    )
    def scorecard(self, request, *args, **kwargs):
        navigation_task = self.get_object()  # type: NavigationTask
        if request.method == "PUT":
            serialiser = self.get_serializer(instance=navigation_task.scorecard, data=request.data)
            serialiser.is_valid()
            serialiser.save()
            return Response(serialiser.data, status=status.HTTP_200_OK)
        else:
            serialiser = self.get_serializer(instance=navigation_task.scorecard)
            return Response(serialiser.data, status=status.HTTP_200_OK)

    @action(
        detail=True,
        methods=["put", "delete"],
        permission_classes=[
            permissions.IsAuthenticated
            & NavigationTaskSelfManagementPermissions
            & (NavigationTaskPublicPutDeletePermissions | NavigationTaskContestPermissions)
        ],
    )
    def contestant_self_registration(self, request, *args, **kwargs):
        navigation_task = self.get_object()  # type: NavigationTask
        if request.method == "PUT":
            serialiser = self.get_serializer(data=request.data)
            serialiser.is_valid(raise_exception=True)
            contest_team = serialiser.validated_data["contest_team"]
            if contest_team.team.crew.member1.email != request.user.email:
                raise ValidationError("You cannot add a team where you are not the pilot")
            starting_point_time = serialiser.validated_data["starting_point_time"].astimezone(
                navigation_task.contest.time_zone
            )  # type: datetime
            takeoff_time = starting_point_time - datetime.timedelta(minutes=navigation_task.minutes_to_starting_point)
            existing_contestants = navigation_task.contestant_set.all()
            if existing_contestants.exists():
                contestant_number = max([item.contestant_number for item in existing_contestants]) + 1
            else:
                contestant_number = 1
            adaptive_start = serialiser.validated_data["adaptive_start"]
            tracker_start_time = takeoff_time - datetime.timedelta(minutes=10)
            if adaptive_start:
                tracker_start_time = starting_point_time - datetime.timedelta(hours=1)
                takeoff_time = tracker_start_time
            contestant = Contestant(
                team=contest_team.team,
                takeoff_time=takeoff_time,
                navigation_task=navigation_task,
                tracker_start_time=tracker_start_time,
                adaptive_start=adaptive_start,
                finished_by_time=tracker_start_time + datetime.timedelta(days=1) - datetime.timedelta(minutes=1),
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
            generate_and_maybe_notify_flight_order.apply_async(
                (contestant.pk, request.user.email, request.user.first_name, True)
            )
            return Response(status=status.HTTP_201_CREATED)
        elif request.method == "DELETE":
            my_contestants = navigation_task.contestant_set.filter(team__crew__member1__email=request.user.email)
            # Delete all contestants that have not started yet where I am the pilot
            my_contestants.filter(
                contestanttrack__calculator_started=False,
            ).delete()
            # If the contestant has not reached the takeoff time, delete the contestant
            my_contestants.filter(
                takeoff_time__gte=datetime.datetime.now(datetime.timezone.utc),
            ).delete()
            # Terminate ongoing contestants where the time has passed the takeoff time
            for c in my_contestants.filter(
                finished_by_time__gt=datetime.datetime.now(datetime.timezone.utc),
                contestanttrack__calculator_started=True,
            ):
                # We know the takeoff time is in the past, so we can freely set it to now.
                c.finished_by_time = datetime.datetime.now(datetime.timezone.utc)
                c.save()
                c.request_calculator_termination()
            return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["put"])
    def share(self, request, *args, **kwargs):
        """
        Change the visibility of the navigation task to one of the public, private, or unlisted
        """
        navigation_task = self.get_object()
        serialiser = self.get_serializer(data=request.data)  # type: SharingSerialiser
        if serialiser.is_valid():
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
        ContestantPublicPermissions | (permissions.IsAuthenticated & ContestantNavigationTaskContestPermissions)
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
            navigation_task = get_object_or_404(NavigationTask, pk=self.kwargs.get("navigationtask_pk"))
            context.update({"navigation_task": navigation_task})
        except Http404:
            # This has to be handled where we retrieve the context
            pass
        return context


class ContestantViewSet(ModelViewSet):
    queryset = Contestant.objects.all()
    permission_classes = [
        ContestantPublicPermissions | (permissions.IsAuthenticated & ContestantNavigationTaskContestPermissions)
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
        partial = kwargs.pop("partial", False)
        serialiser = self.get_serializer(instance=instance, data=request.data, partial=partial)
        if serialiser.is_valid():
            serialiser.save()
            return Response(serialiser.data)
        return Response(serialiser.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["put", "patch"])
    def update_without_team(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    @action(detail=True, methods=["get"])
    def initial_track_data(self, request, *args, **kwargs):
        """
        Used by the front end to load initial data
        """
        contestant = self.get_object()  # This is important, this is where the object permissions are checked
        return Response(cached_generate_data(contestant.pk))

    @action(detail=True, methods=["get"])
    def track(self, request, pk=None, **kwargs):
        """
        Returns the GPS track for the contestant
        """
        contestant = self.get_object()  # This is important, this is where the object permissions are checked
        contestant_track = contestant.contestanttrack

        position_data = contestant.get_track()
        contestant_track.track = position_data
        serialiser = ContestantTrackWithTrackPointsSerialiser(contestant_track)
        return Response(serialiser.data)

    @action(detail=True, methods=["post"])
    def gpx_track(self, request, pk=None, **kwargs):
        """
        Consumes a FC GPX file that contains the GPS track of a contestant.
        """
        contestant = self.get_object()  # This is important, this is where the object permissions are checked
        contestant.reset_track_and_score()
        track_file = request.data.get("track_file", None)
        if not track_file:
            raise ValidationError("Missing track_file")
        import_gpx_track.apply_async(
            (
                contestant.pk,
                base64.decodebytes(bytes(track_file, "utf-8")).decode("utf-8"),
            )
        )
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


@permission_required("display.change_contest")
def renew_token(request):
    user = request.user
    Token.objects.filter(user=user).delete()
    Token.objects.create(user=user)
    return redirect(reverse("token"))


@permission_required("display.view_contest")
def view_token(request):
    return render(request, "token.html")


class UserUploadedMapCreate(PermissionRequiredMixin, CreateView):
    model = UserUploadedMap
    permission_required = ("display.add_contest",)
    form_class = UserUploadedMapForm

    def get_initial(self):
        initial = super().get_initial()
        initial["user"] = self.request.user.pk
        return initial

    def form_valid(self, form):
        instance = form.save()  # type: UserUploadedMap
        try:
            filename = os.path.split(instance.map_file.name)[1] + "_thumbnail.png"
            content, minimum_zoom, maximum_zoom = instance.create_thumbnail()
            instance.thumbnail.save(
                filename,
                ContentFile(content.getvalue()),
                save=True,
            )
            instance.minimum_zoom_level = minimum_zoom
            instance.maximum_zoom_level = maximum_zoom
            if not minimum_zoom <= instance.default_zoom_level <= maximum_zoom:
                form.add_error(
                    "default_zoom_level",
                    f"The selected default zoom level {instance.default_zoom_level} is not in the range supported by the map: [{minimum_zoom}, {maximum_zoom}]",
                )
                return super().form_invalid(form)
            instance.save()
        except Exception as ex:
            logger.exception(f"Failed creating thumbnail")
            form.add_error("map_file", f"Failed reading mbtiles file: {ex}")
            return super().form_invalid(form)
        assign_perm("delete_useruploadedmap", self.request.user, instance)
        assign_perm("view_useruploadedmap", self.request.user, instance)
        assign_perm("add_useruploadedmap", self.request.user, instance)
        assign_perm("change_useruploadedmap", self.request.user, instance)

        self.object = instance
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse("useruploadedmap_list")


class UserUploadedMapUpdate(GuardianPermissionRequiredMixin, UpdateView):
    model = UserUploadedMap
    permission_required = ("display.change_useruploadedmap",)
    form_class = UserUploadedMapForm

    def form_valid(self, form):
        instance = form.save()  # type: UserUploadedMap
        instance.clear_local_file_path()
        try:
            content, minimum_zoom, maximum_zoom = instance.create_thumbnail()
            filename = os.path.split(instance.map_file.name)[1] + "_thumbnail.png"
            instance.thumbnail.save(
                filename,
                ContentFile(content.getvalue()),
                save=True,
            )
            instance.minimum_zoom_level = minimum_zoom
            instance.maximum_zoom_level = maximum_zoom
            if not minimum_zoom <= instance.default_zoom_level <= maximum_zoom:
                form.add_error(
                    "default_zoom_level",
                    f"The selected default zoom level {instance.default_zoom_level} is not in the range supported by the map: [{minimum_zoom}, {maximum_zoom}]",
                )
                return super().form_invalid(form)
            instance.save()
        except Exception as ex:
            logger.exception(f"Failed creating thumbnail")
            form.add_error("map_file", f"Failed reading mbtiles file: {ex}")
            return super().form_invalid(form)

        self.object = instance
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse("useruploadedmap_list")

    def get_permission_object(self):
        return self.get_object()


class UserUploadedMapList(PermissionRequiredMixin, ListView):
    model = UserUploadedMap
    permission_required = ("display.add_contest",)

    def get_queryset(self):
        # Important not to accept global permissions, otherwise any content creator can view everything
        objects = get_objects_for_user(self.request.user, "display.view_useruploadedmap", accept_global_perms=False)
        return objects


class UserUploadedMapDelete(GuardianPermissionRequiredMixin, DeleteView):
    model = UserUploadedMap
    permission_required = ("display.delete_useruploadedmap",)
    template_name = "model_delete.html"
    success_url = reverse_lazy("useruploadedmap_list")

    def get_permission_object(self):
        return self.get_object()

    def form_valid(self, form):
        self.object.clear_local_file_path()
        return super().form_valid(form)


@guardian_permission_required("display.change_useruploadedmap", (UserUploadedMap, "pk", "pk"))
def list_useruploadedmap_permissions(request, pk):
    user_uploaded_map = get_object_or_404(UserUploadedMap, pk=pk)
    users_and_permissions = get_users_with_perms(user_uploaded_map, attach_perms=True)
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
        "display/useruploadedmap_permissions.html",
        {"users": users, "user_uploaded_map": user_uploaded_map},
    )


@guardian_permission_required("display.change_useruploadedmap", (UserUploadedMap, "pk", "pk"))
def delete_user_useruploadedmap_permissions(request, pk, user_pk):
    user_uploaded_map = get_object_or_404(UserUploadedMap, pk=pk)
    user = get_object_or_404(MyUser, pk=user_pk)
    permissions = [
        "change_useruploadedmap",
        "view_useruploadedmap",
        "delete_useruploadedmap",
    ]
    for permission in permissions:
        remove_perm(f"display.{permission}", user, user_uploaded_map)
    return redirect(reverse("useruploadedmap_permissions_list", kwargs={"pk": pk}))


@guardian_permission_required("display.change_useruploadedmap", (UserUploadedMap, "pk", "pk"))
def change_user_useruploadedmap_permissions(request, pk, user_pk):
    user_uploaded_map = get_object_or_404(UserUploadedMap, pk=pk)
    user = get_object_or_404(MyUser, pk=user_pk)
    if request.method == "POST":
        form = ChangeUserUploadedMapPermissionsForm(request.POST)
        if form.is_valid():
            permissions = [
                "change_useruploadedmap",
                "view_useruploadedmap",
                "delete_useruploadedmap",
            ]
            for permission in permissions:
                if form.cleaned_data[permission]:
                    assign_perm(f"display.{permission}", user, user_uploaded_map)
                else:
                    remove_perm(f"display.{permission}", user, user_uploaded_map)
            return redirect(reverse("useruploadedmap_permissions_list", kwargs={"pk": pk}))
    existing_permissions = get_user_perms(user, user_uploaded_map)
    initial = {item: True for item in existing_permissions}
    form = ChangeUserUploadedMapPermissionsForm(initial=initial)
    return render(request, "display/useruploadedmap_permissions_form.html", {"form": form})


@guardian_permission_required("display.change_useruploadedmap", (UserUploadedMap, "pk", "pk"))
def add_user_useruploadedmap_permissions(request, pk):
    user_uploaded_map = get_object_or_404(UserUploadedMap, pk=pk)
    if request.method == "POST":
        form = AddUserUploadedMapPermissionsForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"]
            try:
                user = MyUser.objects.get(email=email)
            except ObjectDoesNotExist:
                messages.error(request, f"User '{email}' does not exist")
                return redirect(reverse("useruploadedmap_permissions_list", kwargs={"pk": pk}))
            permissions = [
                "change_useruploadedmap",
                "view_useruploadedmap",
                "delete_useruploadedmap",
            ]
            for permission in permissions:
                if form.cleaned_data[permission]:
                    assign_perm(f"display.{permission}", user, user_uploaded_map)
                else:
                    remove_perm(f"display.{permission}", user, user_uploaded_map)
            return redirect(reverse("useruploadedmap_permissions_list", kwargs={"pk": pk}))
    form = AddUserUploadedMapPermissionsForm()
    return render(request, "display/useruploadedmap_permissions_form.html", {"form": form})


class WelcomeEmailExample(SuperuserRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        person = get_object_or_404(Person, email=request.user.email)
        return HttpResponse(render_welcome_email(person))


class ContestCreationEmailExample(SuperuserRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        person = get_object_or_404(Person, email=request.user.email)
        return HttpResponse(render_contest_creation_email(person))


########## Results service ##########
class TaskViewSet(ModelViewSet):
    queryset = Task.objects.all()
    permission_classes = [TaskContestPublicPermissions | permissions.IsAuthenticated & TaskContestPermissions]
    serializer_class = TaskSerialiser

    def get_queryset(self):
        contest_id = self.kwargs.get("contest_pk")
        return Task.objects.filter(contest_id=contest_id)


class TaskTestViewSet(ModelViewSet):
    queryset = TaskTest.objects.all()
    permission_classes = [TaskTestContestPublicPermissions | permissions.IsAuthenticated & TaskTestContestPermissions]
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
