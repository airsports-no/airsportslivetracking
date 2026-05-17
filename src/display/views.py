import datetime
import json
import os
from collections import defaultdict
from io import BytesIO
from typing import Dict, List

from django.templatetags.static import static
from django.views.decorators.csrf import csrf_exempt
from django.views import View
from django.views.static import serve

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

from display.templatetags.frontend_urls import fe_url
from display.utilities.calculator_running_utilities import is_calculator_running
from live_tracking_map import settings
from playback_tools.playback import validate_gpx_file
import rest_framework.exceptions as drf_exceptions

from django.core.cache import cache
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.core.files.base import ContentFile
from django.core.mail import send_mail
from django.db import connection, transaction, models
from django.db.models import F, Q, ProtectedError
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
    FormView,
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
from display.utilities.calculate_gate_times import calculate_and_get_relative_gate_times
from display.utilities.calculator_termination_utilities import cancel_termination_request
from display.forms import (
    BatchContestantUpdateForm,
    ImportContestTeamForm,
    NavigationTaskForm,
    ContestantForm,
    ContestantQuickAddForm,
    ContestantRecalculateWithStartTimeForm,
    ContestForm,
    ContestantMapForm,
    LANDSCAPE,
    MapForm,
    TrackingDataForm,
    AssignPokerCardForm,
    ChangePermissionsForm,
    AddPermissionsForm,
    ShareForm,
    GPXTrackImportForm,
    PersonPictureForm,
    ScorecardForm,
    GateScoreForm,
    FlightOrderConfigurationForm,
    UserUploadedMapForm,
    ImportRouteForm,
    DeleteUserForm,
    PersonForm,
    SignUpForm,
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
    MemoryEstimationExceededError,
)
from display.models import (
    NavigationTask,
    Contestant,
    ContestantReceivedPosition,
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
    TrackAnnotation,
    ActualGateTime,
    GateCumulativeScore,
)
from display.contestant_scheduling.schedule_contestants import schedule_and_create_contestants
from display.tasks import (
    import_gpx_track,
    process_flymaster_file,
    process_user_uploaded_map,
    recalculate_existing_positions,
    recalculate_live_data_for_contestant,
)
from display.utilities.welcome_emails import render_welcome_email, render_contest_creation_email
from display.waypoint import Waypoint
from display.utilities.gate_definitions import (
    STARTINGPOINT,
    FINISHPOINT,
    INTERMEDIARY_STARTINGPOINT,
    INTERMEDIARY_FINISHPOINT,
)
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


@login_required
def upgrade_to_organizer(request):
    if request.method == "POST":
        from django.contrib.auth.models import Group

        group, created = Group.objects.get_or_create(name="ContestCreator")
        request.user.groups.add(group)
        return JsonResponse({"status": "success"})
    return JsonResponse({"status": "error", "message": "Invalid method"}, status=405)


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
            "User requested profile deletion",
            f"The user {request.user.email} has requested their profile to be deleted",
            None,  # Should default to system from email
            recipient_list=[SUPPORT_EMAIL],
        )
    except:
        logger.error(f"Failed sending email about deleting user profile for {request.user.email}")
        post_slack_competition_message(
            "Exception", f"Failed sending email about deleting user profile for {request.user.email}"
        )
    messages.info(request, "Your request for deleting your user profile has been submitted")
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
    navigation_task = NavigationTask.objects.get(pk=pk)
    url = fe_url("COMPETITION_MAP_DETAIL", contestId=navigation_task.contest.pk, navigationTaskId=navigation_task.pk)
    return render(
        request,
        "display/tracking_qr_code.html",
        {
            "url": "https://app.airsports.no{}".format(url),
            "navigation_task": navigation_task,
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
            assign_perm("display.change_editableroute", request.user, editable_route)
            assign_perm("display.delete_editableroute", request.user, editable_route)
            assign_perm("display.view_editableroute", request.user, editable_route)
            for message in return_messages:
                messages.success(request, message)
            return redirect(fe_url("ROUTE_EDITOR_EDIT", routeId=editable_route.pk))
    form = ImportRouteForm()
    return render(request, "display/import_route_form.html", {"form": form})


@guardian_permission_required("display.view_contest", (Contest, "navigationtask__contestant__pk", "pk"))
def get_contestant_map(request, pk):
    """
    Triggers async generation of the navigation map for specific contestants.
    """
    contestant = get_object_or_404(Contestant, pk=pk)
    redirect_url = reverse("navigationtask_detail", kwargs={"pk": contestant.navigation_task.pk})
    if request.method == "POST":
        form = ContestantMapForm(request.POST, redirect_url=redirect_url)
        form.fields["user_map_source"].queryset = contestant.navigation_task.get_available_user_maps()
        if form.is_valid():
            map_params = {
                "size": form.cleaned_data["size"],
                "zoom_level": int(form.cleaned_data["zoom_level"]),
                "landscape": form.cleaned_data["orientation"] == LANDSCAPE,
                "annotations": form.cleaned_data["include_annotations"],
                "waypoints_only": not form.cleaned_data["plot_track_between_waypoints"],
                "dpi": form.cleaned_data["dpi"],
                "scale": int(form.cleaned_data["scale"]),
                "map_source": form.cleaned_data["map_source"],
                "user_map_source_id": (
                    form.cleaned_data["user_map_source"].pk if form.cleaned_data["user_map_source"] else None
                ),
                "line_width": float(form.cleaned_data["line_width"]),
                "minute_mark_line_width": float(form.cleaned_data["minute_mark_line_width"]),
                "colour": form.cleaned_data["colour"],
                "include_meridians_and_parallels_lines": form.cleaned_data["include_meridians_and_parallels_lines"],
                "margin": 10,
            }

            # Clear any old result
            cache_key = f"map_gen_result_{contestant.navigation_task.pk}_{contestant.pk}_{request.user.id}"
            cache.delete(cache_key)

            from display.tasks import generate_map_async

            generate_map_async.delay(contestant.navigation_task.pk, contestant.pk, map_params, request.user.id)

            redirect_url_status = reverse(
                "map_generation_status",
                kwargs={"task_id": contestant.navigation_task.pk, "contestant_id": contestant.pk},
            )
            logger.info(f"Redirecting contestant map to: {redirect_url_status}")
            return redirect(redirect_url_status)

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
            },
            redirect_url=redirect_url,
        )
        form.fields["user_map_source"].queryset = contestant.navigation_task.get_available_user_maps()
        form.fields["user_map_source"].initial = contestant.navigation_task.flightorderconfiguration.map_user_source

    return render(
        request,
        "display/map_form.html",
        {
            "form": form,
            "redirect": redirect_url,
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
    """
    Triggers async generation of the default navigation map for specific contestants.
    """
    contestant = get_object_or_404(Contestant, pk=pk)
    configuration = contestant.navigation_task.flightorderconfiguration

    map_params = {
        "size": configuration.document_size,
        "zoom_level": configuration.map_zoom_level,
        "landscape": configuration.map_orientation == LANDSCAPE,
        "annotations": configuration.map_include_annotations,
        "waypoints_only": not configuration.map_plot_track_between_waypoints,
        "dpi": configuration.map_dpi,
        "scale": configuration.map_scale,
        "map_source": configuration.map_source,
        "user_map_source_id": configuration.map_user_source.pk if configuration.map_user_source else None,
        "line_width": configuration.map_line_width,
        "colour": configuration.map_line_colour,
        "include_meridians_and_parallels_lines": configuration.map_include_meridians_and_parallels_lines,
        "margin": 10,
    }

    # Clear any old result
    cache_key = f"map_gen_result_{contestant.navigation_task.pk}_{contestant.pk}_{request.user.id}"
    cache.delete(cache_key)

    from display.tasks import generate_map_async

    generate_map_async.delay(contestant.navigation_task.pk, contestant.pk, map_params, request.user.id)

    redirect_url_status = reverse(
        "map_generation_status", kwargs={"task_id": contestant.navigation_task.pk, "contestant_id": contestant.pk}
    )
    logger.info(f"Redirecting default contestant map to: {redirect_url_status}")
    return redirect(redirect_url_status)


def get_contestant_email_flight_orders_link(request, key):
    """
    Offers the client ordered PDF file identified by key for download. This is used as part of the flight order
    notification email.
    """
    map_link = get_object_or_404(EmailMapLink, id=key)
    response = HttpResponse(map_link.orders, content_type="application/pdf")
    response["Content-Disposition"] = "attachment; filename=flight_orders.pdf"
    return response


def get_contestant_email_flying_orders_link(request, pk):
    """
    View to synchronously generate refined orders for contestant and download the PDF file. Mostly used for testing.
    """
    contestant = get_object_or_404(Contestant, id=pk)
    report = generate_flight_orders_latex(contestant)
    response = HttpResponse(bytes(report), content_type="application/pdf")
    response["Content-Disposition"] = "attachment; filename=flight_orders.pdf"
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
        messages.error(request, "No contestants were selected to download flight orders for.")
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
        response["Content-Disposition"] = "attachment; filename=flight_orders.pdf"
        return response
    messages.error(request, "There were no flight orders to download. Maybe they are still generating?")
    return redirect("navigationtask_flightordersprogress", pk=pk)


def old_tracking_map_redirect(request, pk):
    """
    Redirects old tracking map URLs to the new ones for backward compatibility.
    Old URL: /display/task/<nav_task_id>/map/
    New URL: /competition-map/<contest_id>/<nav_task_id>
    """
    navigation_task = get_object_or_404(NavigationTask, pk=pk)
    target_url = navigation_task.tracking_link
    query_string = request.META.get("QUERY_STRING")
    if query_string:
        target_url = f"{target_url}?{query_string}"
    return redirect(target_url, permanent=True)


@guardian_permission_required("display.view_contest", (Contest, "navigationtask__pk", "pk"))
def get_navigation_task_map(request, pk):
    """
    Triggers async generation of the navigation task map pdf.
    """
    navigation_task = get_object_or_404(NavigationTask, pk=pk)
    redirect_url = reverse("navigationtask_detail", kwargs={"pk": navigation_task.pk})
    if request.method == "POST":
        form = MapForm(request.POST, redirect_url=redirect_url)
        form.fields["user_map_source"].queryset = navigation_task.get_available_user_maps()
        if form.is_valid():
            map_params = {
                "size": form.cleaned_data["size"],
                "zoom_level": form.cleaned_data["zoom_level"],
                "landscape": form.cleaned_data["orientation"] == LANDSCAPE,
                "annotations": False,  # Generic map has no contestant annotations
                "waypoints_only": not form.cleaned_data["plot_track_between_waypoints"],
                "dpi": form.cleaned_data["dpi"],
                "scale": int(form.cleaned_data["scale"]),
                "map_source": form.cleaned_data["map_source"],
                "user_map_source_id": (
                    form.cleaned_data["user_map_source"].pk if form.cleaned_data["user_map_source"] else None
                ),
                "line_width": float(form.cleaned_data["line_width"]),
                "colour": form.cleaned_data["colour"],
                "include_meridians_and_parallels_lines": form.cleaned_data["include_meridians_and_parallels_lines"],
                "margin": 10,
            }

            # Clear any old result
            cache_key = f"map_gen_result_{navigation_task.pk}_None_{request.user.id}"
            cache.delete(cache_key)

            from display.tasks import generate_map_async

            generate_map_async.delay(navigation_task.pk, None, map_params, request.user.id)

            redirect_url_status = reverse(
                "map_generation_status",
                kwargs={"task_id": navigation_task.pk, "contestant_id": 0},  # Use 0 to represent None in URL
            )
            logger.info(f"Redirecting task map to: {redirect_url_status}")
            return redirect(redirect_url_status)

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
            },
            redirect_url=redirect_url,
        )
        form.fields["user_map_source"].queryset = navigation_task.get_available_user_maps()
        form.fields["user_map_source"].initial = navigation_task.flightorderconfiguration.map_user_source
    return render(
        request,
        "display/map_form.html",
        {
            "form": form,
            "redirect": redirect_url,
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
    response["Content-Disposition"] = "attachment; filename=track.gpx"
    return response


@guardian_permission_required("display.change_contest", (Contest, "navigationtask__contestant__pk", "pk"))
def revert_uploaded_gpx_track_for_contestant(request, pk):
    """
    Revert to traccar track. Resets track and score and triggers recalculation based of any track that is available
    in traccar.
    """
    contestant = get_object_or_404(Contestant, pk=pk)
    try:
        if is_calculator_running(pk):
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
        instance.country = form.cleaned_data["country_code"]
        instance.initialise(self.request.user)
        self.object = instance
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse("contest_details", kwargs={"pk": self.object.pk})


class ContestDetailView(ContestTimeZoneMixin, GuardianPermissionRequiredMixin, DetailView):
    model = Contest
    permission_required = ("display.view_contest",)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.is_authenticated:
            context["user_has_routes"] = (
                get_objects_for_user(self.request.user, "display.view_editableroute").exists()
            )
        else:
            context["user_has_routes"] = False
        return context


class ContestUpdateView(ContestTimeZoneMixin, GuardianPermissionRequiredMixin, UpdateView):
    model = Contest
    permission_required = ("display.change_contest",)
    form_class = ContestForm

    def form_valid(self, form):
        instance = form.save(commit=False)  # type: Contest
        instance.country = form.cleaned_data["country_code"]
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
    success_url = f"{fe_url('MISSION_DASHBOARD')}?tab=editorContests"

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
    success_url = f"{fe_url('MISSION_DASHBOARD')}?tab=editorContests"

    def get_permission_object(self):
        return self.get_object().contest

    def get_success_url(self):
        return reverse("contest_details", kwargs={"pk": self.get_object().contest.pk})


@transaction.atomic
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

    # Delete related records.
    # Note: TrackAnnotation has on_delete=models.CASCADE, but we explicitly delete to be certain and push updates.
    annotation = TrackAnnotation.objects.filter(score_log_entry=entry).first()
    gate_type = annotation.gate_type if annotation else None
    TrackAnnotation.objects.filter(score_log_entry=entry).delete()

    if entry.gate:
        # We only delete the actual gate time and cumulative score if this is the only entry for this gate
        if not ScoreLogEntry.objects.filter(contestant=contestant, gate=entry.gate).exclude(pk=entry.pk).exists():
            ActualGateTime.objects.filter(contestant=contestant, gate=entry.gate).delete()
            GateCumulativeScore.objects.filter(contestant=contestant, gate=entry.gate).delete()

            # Update ContestantTrack if it was the last gate
            ct = contestant.contestanttrack
            if ct.last_gate == entry.gate:
                previous_entry = (
                    ScoreLogEntry.objects.filter(contestant=contestant).exclude(pk=entry.pk).order_by("-time").first()
                )
                if previous_entry:
                    ct.last_gate = previous_entry.gate
                    if previous_entry.planned and previous_entry.actual:
                        ct.last_gate_time_offset = (previous_entry.actual - previous_entry.planned).total_seconds()
                    else:
                        ct.last_gate_time_offset = 0
                else:
                    ct.last_gate = ""
                    ct.last_gate_time_offset = 0

                # Revert start/finish point flags if applicable
                if gate_type in [FINISHPOINT, INTERMEDIARY_FINISHPOINT]:
                    ct.passed_finish_gate = False
                    ct.current_state = "Flying"
                elif gate_type in [STARTINGPOINT, INTERMEDIARY_STARTINGPOINT]:
                    ct.passed_starting_gate = False
                    ct.current_state = "Waiting..."

                ct.save()
        else:
            # Otherwise just update the cumulative score
            GateCumulativeScore.objects.filter(contestant=contestant, gate=entry.gate).update(
                points=F("points") - entry.points
            )

        # Update subsequent GateCumulativeScore records if they are intended to be cumulative
        route = contestant.navigation_task.route
        ordered_gate_names = (
            [g.name for g in route.takeoff_gates]
            + [g.name for g in route.waypoints if not getattr(g, "on_curved_segment", False)]
            + [g.name for g in route.landing_gates]
        )
        try:
            gate_index = ordered_gate_names.index(entry.gate)
            subsequent_gates = ordered_gate_names[gate_index + 1 :]
            if subsequent_gates:
                GateCumulativeScore.objects.filter(contestant=contestant, gate__in=subsequent_gates).update(
                    points=F("points") - entry.points
                )
        except ValueError:
            # Gate name not in the ordered list (e.g. custom/anomaly gate)
            pass

    entry.delete()

    # Increment score_version to invalidate score_data ETags without affecting track ETags
    type(contestant).objects.filter(pk=contestant.pk).update(score_version=F("score_version") + 1)

    # Push the updated data so that it is reflected on the contest track
    wf = WebsocketFacade()
    wf.transmit_score_log_entry(contestant)
    wf.transmit_annotations(contestant)
    wf.transmit_basic_information(contestant)
    wf.transmit_gate_score_entry(contestant)
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


class ContestantRecalculateWithStartTimeView(GuardianPermissionRequiredMixin, FormView):
    form_class = ContestantRecalculateWithStartTimeForm
    template_name = "display/contestant_recalculate_start_time.html"
    permission_required = ("display.change_contest",)

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.contestant = get_object_or_404(Contestant, pk=self.kwargs.get("pk"))
        timezone.activate(self.contestant.navigation_task.contest.time_zone)

    def get_permission_object(self):
        return self.contestant.navigation_task.contest

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["contestant"] = self.contestant
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        initial["starting_point_time"] = self.contestant.starting_point_time
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["contestant"] = self.contestant
        context["actual_sp_time"] = self.contestant.actualgatetime_set.filter(gate="SP").first()
        return context

    def form_valid(self, form):
        starting_point_time = form.cleaned_data["starting_point_time"]
        nt = self.contestant.navigation_task

        # Calculate new times
        takeoff_time = starting_point_time - datetime.timedelta(minutes=nt.minutes_to_starting_point)
        tracker_start_time = takeoff_time - datetime.timedelta(minutes=10)
        finished_by_time = starting_point_time + self.contestant.flight_duration
        logger.info(
            f"Recalculating contestant {self.contestant.pk} with new starting point time {starting_point_time}, takeoff time {takeoff_time}, tracker start time {tracker_start_time} and finished by time {finished_by_time}"
        )

        with transaction.atomic():
            original_number = self.contestant.contestant_number
            # Use a temporary contestant number to avoid unique constraint violation
            temp_number = (
                nt.contestant_set.aggregate(models.Max("contestant_number"))["contestant_number__max"] or 0
            ) + 100

            # Create new contestant as a copy of the old one but with updated times
            new_contestant = Contestant.objects.create(
                team=self.contestant.team,
                navigation_task=nt,
                contestant_number=temp_number,
                adaptive_start=self.contestant.adaptive_start,
                takeoff_time=takeoff_time,
                tracker_start_time=tracker_start_time,
                finished_by_time=finished_by_time,
                minutes_to_starting_point=nt.minutes_to_starting_point,
                air_speed=self.contestant.air_speed,
                wind_speed=self.contestant.wind_speed,
                wind_direction=self.contestant.wind_direction,
                tracking_service=self.contestant.tracking_service,
                tracking_device=self.contestant.tracking_device,
                tracker_device_id=self.contestant.tracker_device_id,
                competition_class_longform=self.contestant.competition_class_longform,
                competition_class_shortform=self.contestant.competition_class_shortform,
                schedule_locked=self.contestant.schedule_locked,
            )
            # Move positions to new contestant
            positions = ContestantReceivedPosition.objects.filter(contestant=self.contestant)
            positions.update(contestant=new_contestant)

            # Move uploaded track if exists
            try:
                uploaded_track = self.contestant.contestantuploadedtrack
                uploaded_track.contestant = new_contestant
                uploaded_track.save()
            except ObjectDoesNotExist:
                pass

            # Transfer track version
            new_contestant.track_version = self.contestant.track_version
            new_contestant.save(update_fields=["track_version"])

            # Send websocket delete message for the old contestant
            wf = WebsocketFacade()
            wf.transmit_delete_contestant(self.contestant)

            # Delete old contestant
            old_nt_pk = nt.pk
            self.contestant.delete()

            # Restore the original contestant number now that the old one is gone
            new_contestant.contestant_number = original_number
            new_contestant.save(update_fields=["contestant_number"])

            # Trigger recalculation for the new contestant
            logger.info(f"Scheduling recalculation task for new contestant {new_contestant.pk}")
            transaction.on_commit(lambda: wf.transmit_contestant(new_contestant))
            transaction.on_commit(lambda: recalculate_existing_positions.delay(new_contestant.pk))

        messages.success(self.request, f"Contestant timing updated and recalculation started for {new_contestant}")
        return HttpResponseRedirect(reverse("navigationtask_detail", kwargs={"pk": old_nt_pk}))

    def get_success_url(self):
        return reverse("navigationtask_detail", kwargs={"pk": self.contestant.navigation_task.pk})


class BatchContestantUpdateView(LoginRequiredMixin, GuardianPermissionRequiredMixin, View):
    template_name = "display/batch_contestant_update.html"
    permission_required = ("display.change_contest",)

    def get_permission_object(self):
        return get_object_or_404(NavigationTask, pk=self.kwargs["navigationtask_pk"]).contest

    def get(self, request, navigationtask_pk):
        navigation_task = get_object_or_404(NavigationTask, pk=navigationtask_pk)
        contestants = navigation_task.contestant_set.select_related(
            "contestanttrack", "team__crew__member1", "team__crew__member2"
        ).order_by("takeoff_time")
        form = BatchContestantUpdateForm(navigation_task=navigation_task)
        return render(
            request,
            self.template_name,
            {
                "navigation_task": navigation_task,
                "contestants": contestants,
                "form": form,
            },
        )

    def post(self, request, navigationtask_pk):
        navigation_task = get_object_or_404(NavigationTask, pk=navigationtask_pk)
        contestants_qs = navigation_task.contestant_set.select_related(
            "contestanttrack", "team__crew__member1", "team__crew__member2"
        ).order_by("takeoff_time")
        form = BatchContestantUpdateForm(request.POST, navigation_task=navigation_task)
        if form.is_valid():
            cd = form.cleaned_data
            ids = [int(i) for i in cd["contestant_ids"]]
            delta = (
                datetime.timedelta(minutes=float(cd["time_shift_minutes"]))
                if cd.get("shift_times") and cd.get("time_shift_minutes") is not None
                else None
            )
            updated = 0
            for c in navigation_task.contestant_set.select_related("contestanttrack").filter(pk__in=ids):
                if hasattr(c, "contestanttrack") and c.contestanttrack.calculator_started:
                    continue
                if cd.get("update_wind"):
                    c.wind_speed = cd["wind_speed"]
                    c.wind_direction = cd["wind_direction"]
                    c.predefined_gate_times = None
                if delta is not None:
                    c.tracker_start_time += delta
                    c.takeoff_time += delta
                    c.finished_by_time += delta
                    c.predefined_gate_times = None
                c.save()
                updated += 1
            messages.success(request, f"Updated {updated} contestant(s).")
            return redirect("navigationtask_detail", pk=navigationtask_pk)
        return render(
            request,
            self.template_name,
            {
                "navigation_task": navigation_task,
                "contestants": contestants_qs,
                "form": form,
            },
        )


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
        for warning in self.object.get_overlap_warnings():
            messages.warning(self.request, warning)
        return HttpResponseRedirect(self.get_success_url())


class ContestantDeleteView(GuardianPermissionRequiredMixin, DeleteView):
    model = Contestant
    permission_required = ("display.change_contest",)
    template_name = "model_delete.html"

    def get_success_url(self):
        return reverse("navigationtask_detail", kwargs={"pk": self.get_object().navigation_task.pk})

    def get_permission_object(self):
        return self.get_object().navigation_task.contest


class ContestantQuickAddView(GuardianPermissionRequiredMixin, FormView):
    form_class = ContestantQuickAddForm
    template_name = "display/contestant_quick_create.html"
    permission_required = ("display.change_contest",)

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.navigation_task = get_object_or_404(NavigationTask, pk=self.kwargs.get("navigationtask_pk"))
        timezone.activate(self.navigation_task.contest.time_zone)

    def get_permission_object(self):
        return self.navigation_task.contest

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["navigation_task"] = self.navigation_task
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["navigation_task"] = self.navigation_task
        return context

    def form_valid(self, form):
        contest_team = form.cleaned_data["contest_team"]
        starting_point_time = form.cleaned_data["starting_point_time"]
        adaptive_start = form.cleaned_data["adaptive_start"]
        existing_contestants = self.navigation_task.contestant_set.all()
        contestant_number = (
            (max([c.contestant_number for c in existing_contestants]) + 1) if existing_contestants.exists() else 1
        )

        takeoff_time = starting_point_time - datetime.timedelta(minutes=self.navigation_task.minutes_to_starting_point)

        if adaptive_start:
            tracker_start_time = starting_point_time - datetime.timedelta(hours=1)
            takeoff_time = tracker_start_time
        else:
            tracker_start_time = takeoff_time - datetime.timedelta(minutes=10)

        contestant = Contestant(
            team=contest_team.team,
            navigation_task=self.navigation_task,
            contestant_number=contestant_number,
            adaptive_start=adaptive_start,
            takeoff_time=takeoff_time,
            tracker_start_time=tracker_start_time,
            finished_by_time=tracker_start_time + datetime.timedelta(hours=5),
            minutes_to_starting_point=self.navigation_task.minutes_to_starting_point,
            air_speed=contest_team.air_speed,
            wind_speed=self.navigation_task.wind_speed,
            wind_direction=self.navigation_task.wind_direction,
            tracking_service=contest_team.tracking_service,
            tracking_device=contest_team.tracking_device,
            tracker_device_id=contest_team.tracker_device_id,
        )

        if adaptive_start:
            final_gate_time = contestant.get_final_gate_time()
            if final_gate_time:
                duration_delta = datetime.timedelta(
                    hours=final_gate_time.hour,
                    minutes=final_gate_time.minute,
                    seconds=final_gate_time.second,
                )
                final_time_abs = starting_point_time + datetime.timedelta(hours=1) + duration_delta
            else:
                final_time_abs = starting_point_time + datetime.timedelta(hours=1)

            contestant.finished_by_time = final_time_abs + datetime.timedelta(
                minutes=self.navigation_task.minutes_to_landing + 2
            )
        else:
            contestant.finished_by_time = contestant.landing_time + datetime.timedelta(minutes=5)

        contestant.save()
        messages.success(self.request, "Contestant created successfully")
        for warning in contestant.get_overlap_warnings():
            messages.warning(self.request, warning)
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse("navigationtask_detail", kwargs={"pk": self.navigation_task.pk})


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
        for warning in object.get_overlap_warnings():
            messages.warning(self.request, warning)
        return HttpResponseRedirect(self.get_success_url())


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
                try:
                    value = getattr(form.instance, internal_field)
                    if hasattr(form.instance, f"get_{internal_field}_display"):
                        value = getattr(form.instance, f"get_{internal_field}_display")()
                    data["values"].append(
                        {
                            "label": form.fields[internal_field].label,
                            "value": value,
                        }
                    )
                except KeyError:
                    pass
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


from display.utilities.statistics_utilities import get_system_statistics


class StatisticsView(SuperuserRequiredMixin, TemplateView):
    """
    Displays a list of statistics for contestants and competitions registered in the system.
    """

    template_name = "display/statistics.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        stats = get_system_statistics()
        context.update(stats)
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


class FrontEndView(TemplateView):
    """
    Render the react view
    """

    template_name = "display/frontend.html"


class CombinedFrontEndView(View):
    """
    Serve either the marketing site (Astro) or the React app based on the hostname.
    """

    def get(self, request, *args, **kwargs):
        # request.get_host() returns "domain:port". We only want the domain.
        host = request.get_host().split(":")[0]
        if host in ["airsports.no", "www.airsports.no", "127.0.0.1"]:
            # Use the root folder defined in settings (handles dev vs prod)
            marketing_root = getattr(settings, "MARKETING_STATIC_ROOT", "/marketing_dist")
            
            path = kwargs.get("path", "").strip("/")
            if not path:
                path = "index.html"

            # 1. Check if the path exists exactly as requested
            full_path = os.path.join(marketing_root, path)
            
            # 2. If it is a directory, append index.html (Astro's default style)
            if os.path.isdir(full_path):
                path = os.path.join(path, "index.html")
                full_path = os.path.join(marketing_root, path)
            
            # 3. If the file doesn't exist, try common pretty-URL fallbacks
            if not os.path.exists(full_path):
                if os.path.exists(full_path + ".html"):
                    path += ".html"
                elif os.path.exists(os.path.join(full_path, "index.html")):
                    path = os.path.join(path, "index.html")

            # 4. If the file still doesn't exist, and it's not an API call, redirect to app.airsports.no
            # We preserve the full path and query strings.
            if not os.path.exists(os.path.join(marketing_root, path)) and not request.path.startswith("/api") and host != "127.0.0.1":
                return HttpResponseRedirect(f"https://app.airsports.no{request.get_full_path()}", status=301)

            return serve(request, path, document_root=marketing_root)
        else:
            return FrontEndView.as_view()(request, *args, **kwargs)


class EditableRouteDeleteView(GuardianPermissionRequiredMixin, DeleteView):
    """
    Delete an editable route
    """

    model = EditableRoute
    permission_required = ("display.delete_editableroute",)
    template_name = "model_delete.html"
    success_url = "/routeeditor/"

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
    messages.success(request, "Editable route copied successfully. Remember to give it a new name.")
    assign_perm("display.change_editableroute", request.user, editable_route)
    assign_perm("display.delete_editableroute", request.user, editable_route)
    assign_perm("display.view_editableroute", request.user, editable_route)
    return HttpResponseRedirect(fe_url("ROUTE_EDITOR_EDIT", routeId=editable_route.pk))


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
        instance.processing_status = UserUploadedMap.PROCESSING_PENDING
        instance.processing_error = ""
        instance.save(update_fields=["processing_status", "processing_error"])

        assign_perm("delete_useruploadedmap", self.request.user, instance)
        assign_perm("view_useruploadedmap", self.request.user, instance)
        assign_perm("add_useruploadedmap", self.request.user, instance)
        assign_perm("change_useruploadedmap", self.request.user, instance)

        transaction.on_commit(lambda: process_user_uploaded_map.delay(instance.pk))

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
        instance.processing_status = UserUploadedMap.PROCESSING_PENDING
        instance.processing_error = ""
        instance.save(update_fields=["processing_status", "processing_error"])

        transaction.on_commit(lambda: process_user_uploaded_map.delay(instance.pk))

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
        form = AddPermissionsForm(request.POST)
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
    form = AddPermissionsForm()
    return render(request, "display/useruploadedmap_permissions_form.html", {"form": form})


class WelcomeEmailExample(SuperuserRequiredMixin, View):
    """
    Renders an example welcome e-mail.
    """

    def get(self, request, *args, **kwargs):
        person = get_object_or_404(Person, email=request.user.email)
        return HttpResponse(render_welcome_email(person))


class ContestCreationEmailExample(SuperuserRequiredMixin, View):
    """
    Renders an example contest creation e-mail.
    """

    def get(self, request, *args, **kwargs):
        person = get_object_or_404(Person, email=request.user.email)
        return HttpResponse(render_contest_creation_email(person))


def firebase_token_login(request):
    """
    Manual view for authenticating with firebase. Used by apps
    """
    from drf_firebase_auth.authentication import FirebaseAuthentication

    token = request.GET.get("token")
    logger.debug(f"Token {token}")
    firebase_authenticator = FirebaseAuthentication()
    try:
        user, decoded_token = firebase_authenticator.authenticate_credentials(token)
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    except drf_exceptions.AuthenticationFailed as e:
        logger.warning("Firebase login with token from app failed: %s", e)
        messages.error(request, f"Login failed: {e}")
    return redirect("/")


@login_required
def firebase_password_change(request):
    """
    Triggers Firebase to send a password reset email to the logged-in user.
    """
    from django.conf import settings
    import requests
    from display.auth_backends import FirebaseMigrationBackend

    backend = FirebaseMigrationBackend()
    backend._initialize_firebase()

    try:
        api_key = getattr(settings, "FIREBASE_WEB_API_KEY", "")
        url = f"https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode?key={api_key}"
        payload = {
            "requestType": "PASSWORD_RESET",
            "email": request.user.email,
        }

        response = requests.post(url, json=payload, timeout=5)
        response.raise_for_status()

        messages.success(request, f"A password reset email has been sent to {request.user.email}. Please check your inbox.")
        return HttpResponseRedirect("/")
    except Exception as e:
        logger.error(f"Failed to trigger Firebase password reset email for {request.user.email}: {e}")
        messages.error(request, "Failed to initiate password change via Firebase. Please try again later.")
        return HttpResponseRedirect("/")


def firebase_password_reset(request):
    """
    Overrides the default Django password reset to use Firebase.
    Handles migration of legacy users and triggers Firebase to send reset email.
    """
    from django.contrib.auth.forms import PasswordResetForm
    from firebase_admin import auth
    from display.auth_backends import FirebaseMigrationBackend
    from display.models import MyUser
    import requests
    from django.conf import settings

    if request.method == "POST":
        form = PasswordResetForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"]

            # Initialize Firebase
            backend = FirebaseMigrationBackend()
            backend._initialize_firebase()

            firebase_user = None
            try:
                firebase_user = auth.get_user_by_email(email)
            except auth.UserNotFoundError:
                # Check if we should migrate from Django
                django_user = MyUser.objects.filter(email__iexact=email).first()
                if django_user:
                    try:
                        firebase_user = auth.create_user(
                            email=email,
                            display_name=f"{django_user.first_name} {django_user.last_name}".strip() or None
                        )
                        logger.info(f"[PasswordReset] Created Firebase account for {email} to enable reset.")
                        # Purge local password as they are now migrating
                        django_user.set_unusable_password()
                        django_user.save()
                    except Exception as e:
                        logger.error(f"[PasswordReset] Failed to create Firebase user for {email}: {e}")

            if firebase_user:
                try:
                    api_key = getattr(settings, "FIREBASE_WEB_API_KEY", "")
                    url = f"https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode?key={api_key}"
                    payload = {
                        "requestType": "PASSWORD_RESET",
                        "email": email,
                    }

                    response = requests.post(url, json=payload, timeout=5)
                    response.raise_for_status()
                    logger.info(f"[PasswordReset] Firebase reset email triggered for {email}")
                except Exception as e:
                    logger.error(f"[PasswordReset] Error triggering Firebase reset email for {email}: {e}")

            return HttpResponseRedirect(reverse("password_reset_done"))
    else:
        form = PasswordResetForm()

    return render(request, "registration/password_reset_form.html", {"form": form})


def signup(request):
    """
    Dedicated signup view for creating new users.
    Creates user in Firebase first, then in Django.
    """
    from firebase_admin import auth
    from display.auth_backends import FirebaseMigrationBackend
    from display.models import MyUser, Person
    import requests

    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            first_name = form.cleaned_data["first_name"]
            last_name = form.cleaned_data["last_name"]
            email = form.cleaned_data["email"].lower()
            password = form.cleaned_data["password"]

            # 1. Initialize Firebase
            backend = FirebaseMigrationBackend()
            backend._initialize_firebase()

            try:
                # 2. Create Firebase user
                firebase_user = auth.create_user(
                    email=email,
                    password=password,
                    display_name=f"{first_name} {last_name}".strip()
                )
                logger.info(f"[SignUp] Created Firebase user for {email}")

                # 3. Trigger Email Verification
                # We need an idToken to trigger the verification email via REST API.
                # Since we just created the user with a password, we can sign them in.
                api_key = getattr(settings, "FIREBASE_WEB_API_KEY", "")
                signin_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}"
                signin_payload = {
                    "email": email,
                    "password": password,
                    "returnSecureToken": True
                }
                signin_response = requests.post(signin_url, json=signin_payload, timeout=5)
                signin_response.raise_for_status()
                id_token = signin_response.json().get("idToken")

                if id_token:
                    verify_url = f"https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode?key={api_key}"
                    verify_payload = {
                        "requestType": "VERIFY_EMAIL",
                        "idToken": id_token,
                    }
                    verify_response = requests.post(verify_url, json=verify_payload, timeout=5)
                    verify_response.raise_for_status()
                    logger.info(f"[SignUp] Verification email triggered for {email}")
                else:
                    logger.error(f"[SignUp] Failed to obtain idToken for {email} after creation.")
                    messages.error(request, "User created but verification email could not be sent. Please use 'Forgot Password' to verify your account.")
                    return redirect("login")

                # 4. Ensure Django User exists (Inactive or Unusable Password)
                # Since MyUser is a local proxy for Firebase, we tolerate existing records.
                user, created = MyUser.objects.get_or_create(
                    email=email,
                    defaults={
                        "username": email,
                        "first_name": first_name,
                        "last_name": last_name,
                    }
                )
                if not created:
                    user.first_name = first_name
                    user.last_name = last_name
                
                user.set_unusable_password()
                user.save()

                # 5. Create Person profile
                # We use get_or_create in case a Person record exists without a user
                person, created = Person.objects.get_or_create(
                    email=email,
                    defaults={
                        "first_name": first_name,
                        "last_name": last_name,
                    }
                )
                if not created:
                    person.first_name = first_name
                    person.last_name = last_name
                    person.save()

                # Do NOT log the user in automatically. They must verify email first.
                return render(request, "registration/signup_success.html", {"email": email})

            except Exception as e:
                # Handle cases like Email already exists in Firebase
                error_message = str(e)
                if "EMAIL_EXISTS" in error_message or "already exists" in error_message.lower():
                    messages.error(request, "An account with this email already exists.")
                else:
                    logger.error(f"[SignUp] Unexpected error during signup for {email}: {e}")
                    messages.error(request, "An error occurred during signup. Please try again later.")
    else:
        form = SignUpForm()

    return render(request, "registration/signup.html", {"form": form})


@csrf_exempt
def fly_master_data_post(request):
    logger.debug(f"Received {request.method} from Flymaster with files {request.FILES} and post {request.POST}")
    if request.method == "POST":
        data = request.POST["data"]
        process_flymaster_file.apply_async((data,))
    return HttpResponse("OK", status=status.HTTP_200_OK)


class MapGenerationStatusView(LoginRequiredMixin, TemplateView):
    template_name = "display/map_generation_status.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        task_id = self.kwargs.get("task_id")
        contestant_id = self.kwargs.get("contestant_id")
        if contestant_id == 0:
            contestant_id = "None"

        context["task_id"] = task_id
        context["contestant_id"] = contestant_id

        # We use '0' in the URL to represent None for contestant_id
        c_id_for_url = self.kwargs.get("contestant_id")

        context["check_url"] = reverse(
            "check_map_generation_status", kwargs={"task_id": task_id, "contestant_id": c_id_for_url}
        )

        task = get_object_or_404(NavigationTask, pk=task_id)
        context["navigation_task"] = task
        if c_id_for_url != 0:
            context["contestant"] = get_object_or_404(Contestant, pk=c_id_for_url)

        return context


@login_required
def check_map_generation_status(request, task_id, contestant_id):
    user_id = request.user.id
    c_id = None if contestant_id == 0 else contestant_id
    cache_key = f"map_gen_result_{task_id}_{c_id}_{user_id}"
    result = cache.get(cache_key)
    if result:
        return JsonResponse(result)
    return JsonResponse({"status": "pending"})
