import datetime
import json
import os
from collections import defaultdict
from io import BytesIO
from typing import Dict, List

from django.templatetags.static import static
from django.views.decorators.csrf import csrf_exempt
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

from playback_tools.playback import validate_gpx_file
import rest_framework.exceptions as drf_exceptions

from django.core.cache import cache
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.core.files.base import ContentFile
from django.core.mail import send_mail
from django.db import connection
from django.db.models import Q, ProtectedError
from django.forms import ModelForm

from django.http import HttpResponseRedirect, JsonResponse, HttpResponse, Http404
from django.shortcuts import render, redirect, get_object_or_404
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

from guardian.decorators import permission_required as guardian_permission_required
from guardian.mixins import PermissionRequiredMixin as GuardianPermissionRequiredMixin
from guardian.shortcuts import (
    get_objects_for_user,
    assign_perm,
    get_users_with_perms,
    remove_perm,
    get_user_perms,
)
from rest_framework import status
from rest_framework.authtoken.models import Token

from display.flight_order_and_maps.map_plotter_shared_utilities import get_map_zoom_levels
from display.utilities.calculator_termination_utilities import cancel_termination_request
from display.forms import (
    ImportContestTeamForm,
    NavigationTaskForm,
    ContestantForm,
    ContestForm,
    ContestantMapForm,
    LANDSCAPE,
    MapForm,
    TrackingDataForm,
    ContestTeamOptimisationForm,
    AssignPokerCardForm,
    ChangePermissionsForm,
    AddPermissionsForm,
    RouteCreationForm,
    ShareForm,
    GPXTrackImportForm,
    PersonPictureForm,
    ScorecardForm,
    GateScoreForm,
    FlightOrderConfigurationForm,
    UserUploadedMapForm,
    ImportRouteForm,
    DeleteUserForm,
    TeamForm,
    PersonForm,
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
    Contestant,
    Contest,
    Team,
    Person,
    ContestTeam,
    MyUser,
    PlayingCard,
    ScoreLogEntry,
    EmailMapLink,
    EditableRoute,
    GateScore,
    FlightOrderConfiguration,
    UserUploadedMap,
)
from display.contestant_scheduling.schedule_contestants import schedule_and_create_contestants
from display.tasks import (
    import_gpx_track,
    process_flymaster_file,
    recalculate_live_data_for_contestant,
)
from display.utilities.welcome_emails import render_welcome_email, render_contest_creation_email
from display.waypoint import Waypoint
from live_tracking_map.settings import SUPPORT_EMAIL
from slack_facade import post_slack_competition_message
from websocket_channels import (
    WebsocketFacade,
)

logger = logging.getLogger(__name__)


def healthz(request):
    """
    Probe used by kubernetes
    """
    return HttpResponse(status=status.HTTP_200_OK)


def readyz(request):
    """
    Probe used by kubernetes
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return HttpResponse(status=200)
    except Exception as ex:
        return HttpResponse(str(ex).encode("utf-8"), status=500)


class ContestantTimeZoneMixin:
    """
    Mixin to ensure that the session time zone is always set to the correct one for the contest
    """

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        timezone.activate(self.get_object().navigation_task.contest.time_zone)


class NavigationTaskTimeZoneMixin:
    """
    Mixin to ensure that the session time zone is always set to the correct one for the contest
    """

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        timezone.activate(self.get_object().contest.time_zone)


class ContestTimeZoneMixin:
    """
    Mixin to ensure that the session time zone is always set to the correct one for the contest
    """

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        timezone.activate(self.get_object().time_zone)


class SuperuserRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """
    Mixin to ensure that the view is only available to superusers.
    """

    def test_func(self):
        return self.request.user.is_superuser


@user_passes_test(lambda u: u.is_superuser)
def get_contest_creators_emails(request):
    """
    List the e-mail address of all users in the system, with a separate section for users with content creation
    privileges.
    """
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
    """
    Render the navigation task tracking map frontend in live mode.
    """
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
            "can_change_navigation_task": (
                "true" if navigation_task.user_has_change_permissions(request.user) else "false"
            ),
            "navigation_task_management_link": reverse("navigationtask_detail", args=(navigation_task.pk,)),
            "playback_link": reverse("frontend_playback_map", args=(navigation_task.pk,)),
            "live_map_link": reverse("frontend_view_map", args=(navigation_task.pk,)),
        },
    )


def frontend_playback_map(request, pk):
    """
    Render the navigation task tracking map frontend in playback mode.
    """
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
            "can_change_navigation_task": (
                "true" if navigation_task.user_has_change_permissions(request.user) else "false"
            ),
            "navigation_task_management_link": reverse("navigationtask_detail", args=(navigation_task.pk,)),
            "playback_link": reverse("frontend_playback_map", args=(navigation_task.pk,)),
            "live_map_link": reverse("frontend_view_map", args=(navigation_task.pk,)),
        },
    )


def global_map(request):
    """
    Render the global map react application
    """
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
                "src": static("img/airsports.png"),
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
    User accessible page to request profile deletion.
    We must provide this link to Google so that it can be included in the play store listing.
    """
    return render(request, "display/request_profile_deletion.html")


@login_required
def user_request_profile_deletion(request):
    """
    Send an e-mail to support@airsports.no with the request for a profile deletion. There is a separate superuser view
    to delete a user profile (person object).
    """
    try:
        send_mail(
            f"User requested profile deletion",
            f"The user {request.user.email} has requested their profile to be deleted",
            None,  # Should default to system from email
            recipient_list=[SUPPORT_EMAIL],
        )
    except:
        logger.error(f"Failed sending email about deleting user profile for {request.user.email}")
        post_slack_competition_message(
            "Exception", f"Failed sending email about deleting user profile for {request.user.email}"
        )
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
            my_user = None
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
                    if my_user:
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


def tracking_qr_code_view(request, pk):
    """
    Renderer page that displays a QR code that links to the live tracking map
    """
    url = reverse("frontend_view_map", kwargs={"pk": pk})
    return render(
        request,
        "display/tracking_qr_code.html",
        {
            "url": "https://airsports.no{}".format(url),
            "navigation_task": NavigationTask.objects.get(pk=pk),
        },
    )


@guardian_permission_required("display.change_contest", (Contest, "navigationtask__contestant__pk", "pk"))
def contestant_card_remove(request, pk, card_pk):
    """
    Remove a poker card for a contestants. Return a view with the list of current cards.
    """
    contestant = get_object_or_404(Contestant, pk=pk)
    PlayingCard.remove_contestant_card(contestant, card_pk)
    return redirect(reverse("contestant_cards_list", kwargs={"pk": contestant.pk}))


@guardian_permission_required("display.change_contest", (Contest, "navigationtask__contestant__pk", "pk"))
def contestant_cards_list(request, pk):
    """
    Render a view with the list of the current poker cards that belong to a contestant
    """
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
    """
    Render a form and handle POST to change the sharing settings for the contest.
    """
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
    """
    Render a form and handle POST to change the sharing settings for the navigation task.
    """
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


@guardian_permission_required("display.change_contest", (Contest, "navigationtask__pk", "pk"))
def refresh_editable_route_navigation_task(request, pk):
    """
    Update the navigation task Route with any changes made to the linked editable route. Return the navigation task
    details page
    """
    navigation_task = get_object_or_404(NavigationTask, pk=pk)
    try:
        navigation_task.refresh_editable_route()
        messages.success(request, "Route refreshed")
    except ValidationError as e:
        messages.error(request, str(e))
    return HttpResponseRedirect(reverse("navigationtask_detail", kwargs={"pk": navigation_task.pk}))


@guardian_permission_required("display.change_contest", (Contest, "pk", "pk"))
def view_contest_team_images(request, pk):
    """
    View a list of all profile images used by team members associated with the contest.This view can be used to review
    the images and click a link to remove the background using the remove.bg service.
    """
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
    """
    Calls the external remove.bg service to remove the background for the profile image for the person. Redirects to
    the contest team image page.
    """
    contest = get_object_or_404(Contest, pk=contest_pk)  # Required for permission check, I think
    person = get_object_or_404(Person, pk=pk)
    result = person.remove_profile_picture_background()
    if result is not None:
        messages.error(request, f"Background removal failed for {person}: {result}")
    else:
        messages.success(request, f"Background removal successful for {person}")
    return redirect(reverse("contest_team_images", kwargs={"pk": contest_pk}))


@guardian_permission_required("display.change_contest", (Contest, "pk", "contest_pk"))
def upload_profile_picture(request, contest_pk, pk):
    """
    Renders form and handles POST request to upload profile image
    """
    contest = get_object_or_404(Contest, pk=contest_pk)  # Required for permission check, I think
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
    """
    Provides a form for uploading a file with a route definition. Imports the file and creates an editable route if able.
    """
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
    """
    Generates the navigation map for specific contestants with optional annotation. My generation is controlled through
    a form, and the resulting file is downloaded as a PDF.
    """
    contestant = get_object_or_404(Contestant, pk=pk)
    if request.method == "POST":
        form = ContestantMapForm(request.POST)
        form.fields["user_map_source"].queryset = contestant.navigation_task.get_available_user_maps()
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
            # noinspection PyTypeChecker
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
        form.fields["user_map_source"].queryset = contestant.navigation_task.get_available_user_maps()
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
    """
    Renders a form and handles POST for updating the flight order configuration of a navigation task.
    """
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
    """
    Renders an image that is a chart of contestant processing statistics.
    """
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
        waypoints_only=not configuration.map_plot_track_between_waypoints,
        dpi=configuration.map_dpi,
        scale=configuration.map_scale,
        map_source=configuration.map_source,
        user_map_source=configuration.map_user_source,
        line_width=configuration.map_line_width,
        colour=configuration.map_line_colour,
        include_meridians_and_parallels_lines=configuration.map_include_meridians_and_parallels_lines,
        margins_mm=margin,
    )
    # noinspection PyTypeChecker
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
    """
    Offers the client ordered PDF file identified by key for download. This is used as part of the flight order
    notification email.
    """
    map_link = get_object_or_404(EmailMapLink, id=key)
    response = HttpResponse(map_link.orders, content_type="application/pdf")
    response["Content-Disposition"] = f"attachment; filename=flight_orders.pdf"
    return response


def get_contestant_email_flying_orders_link(request, pk):
    """
    View to synchronously generate refined orders for contestant and download the PDF file. Mostly used for testing.
    """
    contestant = get_object_or_404(Contestant, id=pk)
    report = generate_flight_orders_latex(contestant)
    response = HttpResponse(bytes(report), content_type="application/pdf")
    response["Content-Disposition"] = f"attachment; filename=flight_orders.pdf"
    return response


@guardian_permission_required("display.view_contest", (Contest, "navigationtask__pk", "pk"))
def generatenavigation_task_orders_template(request, pk):
    """
    Render the template where the user can control flight order generation for the contestants of a navigation task.
    Allows for a preselected set of contestants that will be initially marked as "checked" in the selection form.
    """
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


def get_navigation_task_orders_status_object(pk: int) -> Dict:
    """
    Helper function to generate the flight order generation status dictionary for a navigation task.
    """
    return {
        "completed_flight_orders_map": cache.get(f"completed_flight_orders_map_{pk}"),
        "transmitted_flight_orders_map": cache.get(f"transmitted_flight_orders_map_{pk}"),
        "generate_failed_flight_orders_map": cache.get(f"generate_failed_flight_orders_map_{pk}"),
        "transmit_failed_flight_orders_map": cache.get(f"transmit_failed_flight_orders_map_{pk}"),
    }


@guardian_permission_required("display.view_contest", (Contest, "navigationtask__pk", "pk"))
def download_navigation_task_orders(request, pk):
    """
    Download the selected flight orders for the navigation task. If a single  contestant is selected the flight order
    is downloaded as PDF. If multiple contestants are selected the flight orders are compressed in a zip file.
    """
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


@guardian_permission_required("display.view_contest", (Contest, "navigationtask__pk", "pk"))
def get_navigation_task_map(request, pk):
    """
    Render a form and handle POST for generating the navigation task map pdf. This is a generic map For the navigation
    task and cannot contain contestants specific annotations.
    """
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
            # noinspection PyTypeChecker
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
    Consumes a GPX file that contains the GPS track of a contestant.
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
            data = track_file.read().decode("utf-8")
            try:
                validate_gpx_file(data)
            except Exception as e:
                form.add_error(None, str(e))
            else:
                import_gpx_track.apply_async((contestant.pk, data))
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
    Produces a GPX file from whatever is recorded and offers for download.
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
    Revert to traccar track. Resets track and score and triggers recalculation based of any track that is available
    in traccar.
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
    recalculate_live_data_for_contestant.apply_async((contestant.pk,))
    messages.success(request, "Started loading track")
    return HttpResponseRedirect(reverse("navigationtask_detail", kwargs={"pk": contestant.navigation_task.pk}))


#### Editable route permission management
def map_editable_route_permissions_to_permission_name(permissions: list[str]) -> str:
    if "delete_editableroute" in permissions:
        return "delete"
    elif "change_editableroute" in permissions:
        return "change"
    elif "view_editableroute" in permissions:
        return "view"
    else:
        return "nothing"


@guardian_permission_required("display.change_editableroute", (EditableRoute, "pk", "pk"))
def list_editableroute_permissions(request, pk):
    """
    View to display all users and their permissions related to a specific EditableRoute
    """
    editableroute = get_object_or_404(EditableRoute, pk=pk)
    users_and_permissions = get_users_with_perms(editableroute, attach_perms=True)
    users = []
    for user in users_and_permissions.keys():
        if user == request.user:
            continue
        data = {}
        data["permission"] = map_editable_route_permissions_to_permission_name(users_and_permissions[user]).capitalize()
        data["email"] = user.email
        data["pk"] = user.pk
        users.append(data)
    return render(
        request,
        "display/editableroute_permissions.html",
        {"users": users, "editableroute": editableroute},
    )


EDITABLEROUTE_PERMISSION_MAP = {
    "nothing": [],
    "view": ["view_editableroute"],
    "change": ["view_editableroute", "change_editableroute", "add_editableroute"],
    "delete": ["view_editableroute", "change_editableroute", "add_editableroute", "delete_editableroute"],
}


@guardian_permission_required("display.change_editableroute", (EditableRoute, "pk", "pk"))
def delete_user_editableroute_permissions(request, pk, user_pk):
    """
    Delete all permissions a user has for an editable route
    """
    editableroute = get_object_or_404(EditableRoute, pk=pk)
    user = get_object_or_404(MyUser, pk=user_pk)
    for permission in EDITABLEROUTE_PERMISSION_MAP["delete"]:
        remove_perm(f"display.{permission}", user, editableroute)
    return redirect(reverse("editableroute_permissions_list", kwargs={"pk": pk}))


@guardian_permission_required("display.change_editableroute", (EditableRoute, "pk", "pk"))
def change_user_editableroute_permissions(request, pk, user_pk):
    """
    Change permissions a user has for an editable route
    """
    editableroute = get_object_or_404(EditableRoute, pk=pk)
    user = get_object_or_404(MyUser, pk=user_pk)
    if request.method == "POST":
        form = ChangePermissionsForm(request.POST)
        if form.is_valid():
            for permission in EDITABLEROUTE_PERMISSION_MAP["delete"]:
                remove_perm(f"display.{permission}", user, editableroute)
            for permission in EDITABLEROUTE_PERMISSION_MAP[form.cleaned_data["permission"]]:
                assign_perm(f"display.{permission}", user, editableroute)
            return redirect(reverse("editableroute_permissions_list", kwargs={"pk": pk}))
    existing_permissions = get_user_perms(user, editableroute)
    initial = {"permission": map_editable_route_permissions_to_permission_name(existing_permissions)}
    form = ChangePermissionsForm(initial=initial)
    return render(
        request, "display/editableroute_permissions_form.html", {"form": form, "editableroute": editableroute}
    )


@guardian_permission_required("display.change_editableroute", (EditableRoute, "pk", "pk"))
def add_user_editableroute_permissions(request, pk):
    """
    Add permissions for an editable route to a user
    """
    editableroute = get_object_or_404(EditableRoute, pk=pk)
    if request.method == "POST":
        form = AddPermissionsForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"]
            try:
                user = MyUser.objects.get(email=email)
            except ObjectDoesNotExist:
                messages.error(request, f"User '{email}' does not exist")
                return redirect(reverse("editableroute_permissions_list", kwargs={"pk": pk}))
            for permission in EDITABLEROUTE_PERMISSION_MAP["delete"]:
                remove_perm(f"display.{permission}", user, editableroute)
            for permission in EDITABLEROUTE_PERMISSION_MAP[form.cleaned_data["permission"]]:
                assign_perm(f"display.{permission}", user, editableroute)
            return redirect(reverse("editableroute_permissions_list", kwargs={"pk": pk}))
    form = AddPermissionsForm()
    return render(
        request, "display/editableroute_permissions_form.html", {"form": form, "editableroute": editableroute}
    )


###### Editable route permission management ends


#### Contest permission management
def map_contest_permissions_to_permission_name(permissions: list[str]) -> str:
    if "delete_contest" in permissions:
        return "delete"
    elif "change_contest" in permissions:
        return "change"
    elif "view_contest" in permissions:
        return "view"
    else:
        return "nothing"


@guardian_permission_required("display.change_contest", (Contest, "pk", "pk"))
def list_contest_permissions(request, pk):
    """
    View to display all users and their permissions related to a specific Contest
    """
    contest = get_object_or_404(Contest, pk=pk)
    users_and_permissions = get_users_with_perms(contest, attach_perms=True)
    users = []
    for user in users_and_permissions.keys():
        if user == request.user:
            continue
        data = {}
        data["permission"] = map_contest_permissions_to_permission_name(users_and_permissions[user]).capitalize()
        data["email"] = user.email
        data["pk"] = user.pk
        users.append(data)
    return render(
        request,
        "display/contest_permissions.html",
        {"users": users, "contest": contest},
    )


CONTEST_PERMISSION_MAP = {
    "nothing": [],
    "view": ["view_contest"],
    "change": ["view_contest", "change_contest", "add_contest"],
    "delete": ["view_contest", "change_contest", "add_contest", "delete_contest"],
}


@guardian_permission_required("display.change_contest", (Contest, "pk", "pk"))
def delete_user_contest_permissions(request, pk, user_pk):
    """
    Delete all permissions a user has for a Contest
    """
    contest = get_object_or_404(Contest, pk=pk)
    user = get_object_or_404(MyUser, pk=user_pk)
    for permission in CONTEST_PERMISSION_MAP["delete"]:
        remove_perm(f"display.{permission}", user, contest)
    return redirect(reverse("contest_permissions_list", kwargs={"pk": pk}))


@guardian_permission_required("display.change_contest", (Contest, "pk", "pk"))
def change_user_contest_permissions(request, pk, user_pk):
    """
    Change permissions a user has for a Contest
    """
    contest = get_object_or_404(Contest, pk=pk)
    user = get_object_or_404(MyUser, pk=user_pk)
    if request.method == "POST":
        form = ChangePermissionsForm(request.POST)
        if form.is_valid():
            for permission in CONTEST_PERMISSION_MAP["delete"]:
                remove_perm(f"display.{permission}", user, contest)
            for permission in CONTEST_PERMISSION_MAP[form.cleaned_data["permission"]]:
                assign_perm(f"display.{permission}", user, contest)
            return redirect(reverse("contest_permissions_list", kwargs={"pk": pk}))
    existing_permissions = get_user_perms(user, contest)
    initial = {"permission": map_contest_permissions_to_permission_name(existing_permissions)}
    form = ChangePermissionsForm(initial=initial)
    return render(request, "display/contest_permissions_form.html", {"form": form})


@guardian_permission_required("display.change_contest", (Contest, "pk", "pk"))
def add_user_contest_permissions(request, pk):
    """
    Add permissions for a Contest to a user
    """
    contest = get_object_or_404(Contest, pk=pk)
    if request.method == "POST":
        form = AddPermissionsForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"]
            try:
                user = MyUser.objects.get(email=email)
            except ObjectDoesNotExist:
                messages.error(request, f"User '{email}' does not exist")
                return redirect(reverse("contest_permissions_list", kwargs={"pk": pk}))
            for permission in CONTEST_PERMISSION_MAP["delete"]:
                remove_perm(f"display.{permission}", user, contest)
            for permission in CONTEST_PERMISSION_MAP[form.cleaned_data["permission"]]:
                assign_perm(f"display.{permission}", user, contest)
            return redirect(reverse("contest_permissions_list", kwargs={"pk": pk}))
    form = AddPermissionsForm()
    return render(request, "display/contest_permissions_form.html", {"form": form})


###### Contest permission management ends


class ContestList(PermissionRequiredMixin, TemplateView):
    """
    Render the react contest list view
    """

    model = Contest
    permission_required = ("display.view_contest",)
    template_name = "display/contest_list_react.html"


@guardian_permission_required("display.change_contest", (Contest, "navigationtask__contestant__pk", "pk"))
def terminate_contestant_calculator(request, pk):
    """
    Request termination of contestant calculator. The request blocks until termination has completed. Redirects to the
    navigation task detail page.
    """
    contestant = get_object_or_404(Contestant, pk=pk)

    try:
        contestant.blocking_request_calculator_termination()
        messages.success(request, "Calculator terminated successfully")
    except TimeoutError:
        messages.info(request, "Calculator termination requested, but not stopped in time")
    return HttpResponseRedirect(reverse("navigationtask_detail", kwargs={"pk": contestant.navigation_task.pk}))


@guardian_permission_required("display.change_contest", (Contest, "navigationtask__contestant__pk", "pk"))
def restart_contestant_calculator(request, pk):
    """
    Terminates contesting calculator, resets the score, and cancels termination. This should trigger the calculator to
    restart on the next received position. Redirects to the navigation task detail page.
    """
    contestant = get_object_or_404(Contestant, pk=pk)
    contestant.blocking_request_calculator_termination()
    messages.success(
        request,
        "Calculator should have been restarted. It may take a few minutes for it to come back to life.",
    )
    contestant.reset_track_and_score()
    cancel_termination_request(pk)
    return HttpResponseRedirect(reverse("navigationtask_detail", kwargs={"pk": contestant.navigation_task.pk}))


class ContestCreateView(PermissionRequiredMixin, CreateView):
    """
    View to create a new contest
    """

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


@guardian_permission_required("display.change_contest", (Contest, "pk", "contest_pk"))
def import_contest_team_from_contest(request, contest_pk):
    target_contest = get_object_or_404(Contest, pk=contest_pk)
    # All contests that are public or where the user has view permissions
    contests_to_copy_from = get_objects_for_user(
        request.user,
        "display.view_contest",
        klass=Contest,
        accept_global_perms=False,
    ) | Contest.objects.filter(is_public=True, is_featured=True)
    if request.method == "POST":
        form = ImportContestTeamForm(contests_to_copy_from, request.POST)
        if form.is_valid():
            source_contest = form.cleaned_data["contest"]
            for contest_team in source_contest.contestteam_set.all():
                contest_team.id = None
                contest_team.pk = None
                contest_team.contest = target_contest
                contest_team.save()
            return redirect(reverse("contest_team_list", kwargs={"contest_pk": contest_pk}))
    form = ImportContestTeamForm(contests_to_copy_from)
    return render(request, "display/contest_import_contest_team_form.html", {"form": form, "contest": target_contest})


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
    """
    Delete a specific score log entry. Pushes updates to the front end
    """
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
    """
    View that displays the planned (and actual if available) gate times for a user. It also includes any score logs that have been generated, with
    a link to delete that item.
    """

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
        context["navigation_task"] = self.get_object().navigation_task
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


@guardian_permission_required("display.view_contest", (Contest, "navigationtask__pk", "pk"))
def render_contestants_timeline(request, pk):
    """
    Renders a vis.js timeline of the contestants start and finish times.
    """
    navigation_task = get_object_or_404(NavigationTask, pk=pk)
    timezone.activate(navigation_task.contest.time_zone)
    return render(
        request,
        "display/contestant_timeline.html",
        context={"navigation_task": navigation_task},
    )


@guardian_permission_required("display.view_contest", (Contest, "navigationtask__pk", "pk"))
def clear_contestants(request, pk):
    """
    Deletes all contestants from the navigation task and redirects to the navigation task detail page.
    """
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
    """
    Delete the scorecard copy assigned to the navigation task and replace with a new copy of the original scorecard.
    """
    navigation_task = get_object_or_404(NavigationTask, pk=pk)
    navigation_task.assign_scorecard_from_original(force=True)
    messages.success(request, "Original scorecard values have been restored")
    return redirect(reverse("navigationtask_scoredetails", kwargs={"pk": navigation_task.pk}))


@guardian_permission_required("display.change_contest", (Contest, "navigationtask__pk", "pk"))
def navigation_task_scorecard_override_view(request, pk):
    """
    Renders form to update the values of the scorecard copy for navigation task.
    """
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
    """
    Renders form to update the values of a gate score copy for the navigation task.
    """
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


def _extract_values_from_form(form: ModelForm) -> List:
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
    """
    Render scorecard overview page that shows scorecard values and gate score values with options to modify them.
    """
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


# Everything below he is related to management and requires authentication


class ContestTeamTrackingUpdate(GuardianPermissionRequiredMixin, UpdateView):
    """
    Update the tracking method for a team registered in a contest
    """

    permission_required = ("display.change_contest",)

    def get_permission_object(self):
        contest = get_object_or_404(Contest, pk=self.kwargs.get("contest_pk"))
        return contest

    model = ContestTeam
    form_class = TrackingDataForm

    def get_success_url(self):
        return reverse_lazy("contest_team_list", kwargs={"contest_pk": self.kwargs["contest_pk"]})


class PersonList(SuperuserRequiredMixin, ListView):
    model = Person

    def get_queryset(self):
        return Person.objects.all().order_by("last_name", "first_name")


class PersonUpdateView(SuperuserRequiredMixin, UpdateView):
    model = Person
    success_url = reverse_lazy("person_list")
    form_class = PersonForm


class StatisticsView(SuperuserRequiredMixin, TemplateView):
    """
    Displays a list of statistics for contestants and competitions registered in the system.
    """

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
    """
    Display the list of teams that are registered to the contest.
    """

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


class EditableRouteList(GuardianPermissionRequiredMixin, TemplateView):
    """
    Render the react view to list editable routes
    """

    permission_required = ("display.view_editableroute",)
    template_name = "display/editableroute_list_react.html"


class EditableRouteDeleteView(GuardianPermissionRequiredMixin, DeleteView):
    """
    Delete an editable route
    """

    model = EditableRoute
    permission_required = ("display.delete_editableroute",)
    template_name = "model_delete.html"
    success_url = reverse_lazy("editableroute_list")

    def get_permission_object(self):
        return self.get_object()


@guardian_permission_required("display.change_editableroute", (EditableRoute, "pk", "pk"))
def copy_editable_route(request, pk):
    """
    Creates a copy of the editable route
    """
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


@permission_required("display.change_contest")
def renew_token(request):
    user = request.user
    Token.objects.filter(user=user).delete()
    Token.objects.create(user=user)
    return redirect(reverse("token"))


@permission_required("display.view_contest")
def view_token(request):
    """
    Display the DRF authentication token so the user can copy it into an external application.
    """
    return render(request, "token.html")


class UserUploadedMapCreate(PermissionRequiredMixin, CreateView):
    """
    Upload a new user uploaded map mbtiles file.
    """

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


def map_useruploadedmap_permissions_to_permission_name(permissions: list[str]) -> str:
    if "delete_useruploadedmap" in permissions:
        return "delete"
    elif "change_useruploadedmap" in permissions:
        return "change"
    elif "view_useruploadedmap" in permissions:
        return "view"
    else:
        return "nothing"


@guardian_permission_required("display.change_useruploadedmap", (UserUploadedMap, "pk", "pk"))
def list_useruploadedmap_permissions(request, pk):
    user_uploaded_map = get_object_or_404(UserUploadedMap, pk=pk)
    users_and_permissions = get_users_with_perms(user_uploaded_map, attach_perms=True)
    users = []
    for user in users_and_permissions.keys():
        if user == request.user:
            continue
        data = {}
        data["permission"] = map_useruploadedmap_permissions_to_permission_name(
            users_and_permissions[user]
        ).capitalize()
        data["email"] = user.email
        data["pk"] = user.pk
        users.append(data)
    return render(
        request,
        "display/useruploadedmap_permissions.html",
        {"users": users, "user_uploaded_map": user_uploaded_map},
    )


USERUPLOADEDMAP_PERMISSION_MAP = {
    "nothing": [],
    "view": ["view_useruploadedmap"],
    "change": ["view_useruploadedmap", "change_useruploadedmap", "add_useruploadedmap"],
    "delete": ["view_useruploadedmap", "change_useruploadedmap", "add_useruploadedmap", "delete_useruploadedmap"],
}


@guardian_permission_required("display.change_useruploadedmap", (UserUploadedMap, "pk", "pk"))
def delete_user_useruploadedmap_permissions(request, pk, user_pk):
    user_uploaded_map = get_object_or_404(UserUploadedMap, pk=pk)
    user = get_object_or_404(MyUser, pk=user_pk)
    for permission in USERUPLOADEDMAP_PERMISSION_MAP["delete"]:
        remove_perm(f"display.{permission}", user, user_uploaded_map)
    return redirect(reverse("useruploadedmap_permissions_list", kwargs={"pk": pk}))


@guardian_permission_required("display.change_useruploadedmap", (UserUploadedMap, "pk", "pk"))
def change_user_useruploadedmap_permissions(request, pk, user_pk):
    user_uploaded_map = get_object_or_404(UserUploadedMap, pk=pk)
    user = get_object_or_404(MyUser, pk=user_pk)
    if request.method == "POST":
        form = ChangePermissionsForm(request.POST)
        if form.is_valid():
            for permission in USERUPLOADEDMAP_PERMISSION_MAP["delete"]:
                remove_perm(f"display.{permission}", user, user_uploaded_map)
            for permission in USERUPLOADEDMAP_PERMISSION_MAP[form.cleaned_data["permission"]]:
                assign_perm(f"display.{permission}", user, user_uploaded_map)
            return redirect(reverse("useruploadedmap_permissions_list", kwargs={"pk": pk}))
    existing_permissions = get_user_perms(user, user_uploaded_map)
    initial = {"permission": map_useruploadedmap_permissions_to_permission_name(existing_permissions)}
    form = ChangePermissionsForm(initial=initial)
    return render(request, "display/useruploadedmap_permissions_form.html", {"form": form})


@guardian_permission_required("display.change_useruploadedmap", (UserUploadedMap, "pk", "pk"))
def add_user_useruploadedmap_permissions(request, pk):
    user_uploaded_map = get_object_or_404(UserUploadedMap, pk=pk)
    if request.method == "POST":
        form = ChangePermissionsForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"]
            try:
                user = MyUser.objects.get(email=email)
            except ObjectDoesNotExist:
                messages.error(request, f"User '{email}' does not exist")
                return redirect(reverse("useruploadedmap_permissions_list", kwargs={"pk": pk}))
            for permission in USERUPLOADEDMAP_PERMISSION_MAP["delete"]:
                remove_perm(f"display.{permission}", user, user_uploaded_map)
            for permission in USERUPLOADEDMAP_PERMISSION_MAP[form.cleaned_data["permission"]]:
                assign_perm(f"display.{permission}", user, user_uploaded_map)
            return redirect(reverse("useruploadedmap_permissions_list", kwargs={"pk": pk}))
    form = ChangePermissionsForm()
    return render(request, "display/useruploadedmap_permissions_form.html", {"form": form})


class WelcomeEmailExample(SuperuserRequiredMixin, View):
    """
    The welcome e-mail is generated based on text written in wordpress. This renders an example email.
    """

    def get(self, request, *args, **kwargs):
        person = get_object_or_404(Person, email=request.user.email)
        return HttpResponse(render_welcome_email(person))


class ContestCreationEmailExample(SuperuserRequiredMixin, View):
    """
    The contest creation e-mail is generated based on text written in wordpress. This renders an example email.
    """

    def get(self, request, *args, **kwargs):
        person = get_object_or_404(Person, email=request.user.email)
        return HttpResponse(render_contest_creation_email(person))


def firebase_token_login(request):
    """
    Manual view for authenticating with firebase. Not sure if this is in use.
    """
    from drf_firebase_auth.authentication import FirebaseAuthentication

    token = request.GET.get("token")
    logger.debug(f"Token {token}")
    firebase_authenticator = FirebaseAuthentication()
    try:
        user, decoded_token = firebase_authenticator.authenticate_credentials(token)
        login(request, user, backend="django.contrib.auth.ba5ckends.ModelBackend")
    except drf_exceptions.AuthenticationFailed as e:
        messages.error(request, f"Login failed: {e}")
    return redirect("/")


@csrf_exempt
def fly_master_data_post(request):
    logger.debug(f"Received {request.method} from Flymaster with files {request.FILES} and post {request.POST}")
    if request.method == "POST":
        data = request.POST["data"]
        process_flymaster_file.apply_async((data,))
    return HttpResponse("OK", status=status.HTTP_200_OK)
