import datetime
import json
import os
import re
from collections import defaultdict
from io import BytesIO
from typing import Dict, List

from django.templatetags.static import static
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
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
from display.services.token_assignment import assign_token_to_contest
from display.models import UserTokenGrant
import rest_framework.exceptions as drf_exceptions
from live_tracking_map import settings


from django.core.cache import cache
from django.conf import settings
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.core.files.base import ContentFile
from django.core.mail import send_mail
from django.db import connection, transaction
from django.db.models import F, Q, ProtectedError
from django.forms import ModelForm

from django.http import HttpResponseRedirect, JsonResponse, HttpResponse, Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import (
    ListView,
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

from display.flight_order_and_maps.map_plotter_shared_utilities import (
    get_map_zoom_levels,
    get_available_map_source_choices_for_navigation_task,
    get_map_zoom_levels_for_definitions,
    get_available_map_source_definitions_for_navigation_task,
)
from display.utilities.calculate_gate_times import calculate_and_get_relative_gate_times
from display.forms import (
    ContestForm,
    ContestantMapForm,
    ChangePermissionsForm,
    AddPermissionsForm,
    ScorecardForm,
    GateScoreForm,
    FlightOrderConfigurationForm,
    UserUploadedMapForm,
    ImportRouteForm,
    DeleteUserForm,
    PersonForm,
    SignUpForm,
)
from display.services.access_resolver import resolve_contest_access
from display.services.capacity_enforcement import assert_can_self_register_contestant, _assert_can_reserve_task_slot
from display.services.task_type_visibility import can_user_see_cima_task_types, get_visible_task_type_groups_for_user
from display.flight_order_and_maps.generate_flight_orders import (
    embed_map_in_pdf,
)
from display.flight_order_and_maps.map_constants import A4, LANDSCAPE
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
    Contest,
    Team,
    Aeroplane,
    Crew,
    Person,
    ContestTeam,
    MyUser,
    EmailMapLink,
    EditableRoute,
    FlightOrderConfiguration,
    UserUploadedMap,
    TrackAnnotation,
    ActualGateTime,
    GateCumulativeScore,
    UserTokenGrant,
    Club,
)
from display.contestant_scheduling.schedule_contestants import schedule_and_create_contestants
from display.tasks import (
    process_flymaster_file,
    process_user_uploaded_map,
)
from display.flight_order_and_maps.user_uploaded_mbtiles_publish import (
    unpublish_user_uploaded_map,
    request_mbtiles_reload,
)

from display.utilities.welcome_emails import render_welcome_email, render_contest_creation_email
from display.utilities.navigation_task_type_definitions import POKER, AIRSPORTS, AIRSPORT_CHALLENGE, ANR_CORRIDOR, PRECISION
from display.waypoint import Waypoint
from display.utilities.gate_definitions import (
    STARTINGPOINT,
    FINISHPOINT,
    INTERMEDIARY_STARTINGPOINT,
    INTERMEDIARY_FINISHPOINT,
)
from live_tracking_map.settings import SUPPORT_EMAIL
from slack_facade import post_slack_competition_message

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


class NavigationTaskTimeZoneMixin:
    """
    Mixin to ensure that the session time zone is always set to the correct one for the contest
    """

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        timezone.activate(self.get_object().contest.time_zone)


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
    redirect_url = fe_url(
        "NAVIGATION_TASK_DETAIL",
        contestId=contestant.navigation_task.contest_id,
        navigationTaskId=contestant.navigation_task.pk,
    )
    map_source_definitions = get_available_map_source_definitions_for_navigation_task(
        contestant.navigation_task,
        request.user,
        uploaded_maps=contestant.navigation_task.get_available_user_maps(),
    )
    map_source_choices = [(item["key"], item["label"]) for item in map_source_definitions]
    map_zoom_levels = get_map_zoom_levels_for_definitions(map_source_definitions)
    if request.method == "POST":
        form = ContestantMapForm(request.POST, redirect_url=redirect_url, map_source_choices=map_source_choices)
        if form.is_valid():
            map_params = {
                "size": form.cleaned_data["size"],
                "zoom_level": int(form.cleaned_data["zoom_level"]),
                "landscape": form.cleaned_data["orientation"] == LANDSCAPE,
                "annotations": form.cleaned_data["include_annotations"],
                "include_contestant_declarations": form.cleaned_data["include_contestant_declarations"],
                "waypoints_only": not form.cleaned_data["plot_track_between_waypoints"],
                "dpi": form.cleaned_data["dpi"],
                "scale": int(form.cleaned_data["scale"]),
                "map_source": form.cleaned_data["map_source"],
                "line_width": float(form.cleaned_data["line_width"]),
                "minute_mark_line_width": float(form.cleaned_data["minute_mark_line_width"]),
                "colour": form.cleaned_data["colour"],
                "include_meridians_and_parallels_lines": form.cleaned_data["include_meridians_and_parallels_lines"],
                "include_openaip_overlay": form.cleaned_data["include_openaip_overlay"],
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
                "include_openaip_overlay": configuration.map_include_openaip_overlay,
                "include_annotations": configuration.map_include_annotations,
                "include_contestant_declarations": configuration.map_include_contestant_declarations,
                "plot_track_between_waypoints": configuration.map_plot_track_between_waypoints,
                "include_meridians_and_parallels_lines": configuration.map_include_meridians_and_parallels_lines,
                "include_openaip_overlay": configuration.map_include_openaip_overlay,
                "line_width": configuration.map_line_width,
                "minute_mark_line_width": configuration.map_minute_mark_line_width,
                "colour": configuration.map_line_colour,
            },
            redirect_url=redirect_url,
            map_source_choices=map_source_choices,
        )

    return render(
        request,
        "display/map_form.html",
        {
            "form": form,
            "redirect": redirect_url,
            "system_map_zoom_levels": json.dumps(map_zoom_levels),
        },
    )


@guardian_permission_required("display.change_contest", (Contest, "navigationtask__pk", "pk"))
def update_flight_order_configurations(request, pk):
    """
    Renders a form and handles POST for updating the flight order configuration of a navigation task.
    """
    navigation_task = get_object_or_404(NavigationTask, pk=pk)
    configuration = get_object_or_404(FlightOrderConfiguration, navigation_task__pk=pk)
    map_source_definitions = get_available_map_source_definitions_for_navigation_task(
        navigation_task,
        request.user,
        uploaded_maps=navigation_task.get_available_user_maps(),
    )
    map_source_choices = [(item["key"], item["label"]) for item in map_source_definitions]
    map_zoom_levels = get_map_zoom_levels_for_definitions(map_source_definitions)
    if request.method == "POST":
        form = FlightOrderConfigurationForm(request.POST, instance=configuration, map_source_choices=map_source_choices)
        if form.is_valid():
            form.save()
            return redirect(fe_url("NAVIGATION_TASK_DETAIL", contestId=navigation_task.contest_id, navigationTaskId=pk))
    else:
        form = FlightOrderConfigurationForm(instance=configuration, map_source_choices=map_source_choices)
    return render(
        request,
        "display/flight_order_configuration_form.html",
        {
            "form": form,
            "navigation_task": navigation_task,
            "initial_color": configuration.map_line_colour,
            "system_map_zoom_levels": json.dumps(map_zoom_levels),
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
        "include_contestant_declarations": configuration.map_include_contestant_declarations,
        "waypoints_only": not configuration.map_plot_track_between_waypoints,
        "dpi": configuration.map_dpi,
        "scale": configuration.map_scale,
        "map_source": configuration.map_source,
        "line_width": configuration.map_line_width,
        "colour": configuration.map_line_colour,
        "include_meridians_and_parallels_lines": configuration.map_include_meridians_and_parallels_lines,
        "include_openaip_overlay": configuration.map_include_openaip_overlay,
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


def _safe_zip_entry_name(text: str, extension: str) -> str:
    """
    Builds a flat, path-traversal-safe zip entry name from free text (e.g. a crew/team name
    interpolated via Contestant.__str__). Not every zip extractor sanitises "../" the way
    Python's own zipfile does, so this strips path separators and anything else that isn't
    safe in a plain filename before an entry is ever written to the archive.
    """
    sanitized = re.sub(r"[^\w\- ()]", "_", text)
    return f"{sanitized}.{extension}"


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
            zf.writestr(_safe_zip_entry_name(str(order.contestant), "pdf"), order.orders)
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


@require_POST
@guardian_permission_required("display.change_editableroute", (EditableRoute, "pk", "pk"))
def delete_user_editableroute_permissions(request, pk, user_pk):
    """
    Delete all permissions a user has for an editable route
    """
    editableroute = get_object_or_404(EditableRoute, pk=pk)
    user = get_object_or_404(MyUser, pk=user_pk)
    # See delete_user_contest_permissions for why both of these are here.
    if user.pk == request.user.pk:
        messages.error(request, "You cannot remove your own permissions for this route.")
        return redirect(reverse("editableroute_permissions_list", kwargs={"pk": pk}))
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


class ContestCreateView(PermissionRequiredMixin, CreateView):
    """
    View to create a new contest
    """

    model = Contest
    permission_required = ("display.add_contest",)
    form_class = ContestForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["token_grant_queryset"] = UserTokenGrant.objects.filter(
            user=self.request.user,
            token_type__is_active=True,
            quantity_consumed__lt=F("quantity_total"),
        ).select_related("token_type")
        kwargs["managed_club_queryset"] = Club.objects.filter(
            clubmanagermembership__user=self.request.user,
            clubmanagermembership__is_active=True,
        ).distinct().order_by("name")
        return kwargs

    @transaction.atomic
    def form_valid(self, form):
        instance = form.save(commit=False)  # type: Contest
        instance.country = form.cleaned_data["country_code"]
        instance.initialise(self.request.user)
        token_grant = form.cleaned_data.get("initial_token_grant")
        if token_grant is not None:
            assign_token_to_contest(instance, self.request.user, token_grant.id)
        self.object = instance
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return fe_url("MISSION_DASHBOARD_DETAIL", contestId=self.object.pk)


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
def navigation_task_gatescore_override_view(request, pk, gate_type):
    """
    Renders form to update the values of a gate score copy for the navigation task.
    """
    navigation_task = get_object_or_404(NavigationTask, pk=pk)
    scorecard = navigation_task.scorecard
    try:
        gate_score = scorecard.get_gate_scorecard(gate_type)
    except ValueError:
        raise Http404(f"Unknown gate type '{gate_type}'")
    form = GateScoreForm(scorecard=scorecard, gate_type=gate_type)
    if request.method == "POST":
        if "cancel" in request.POST:
            return redirect(reverse("navigationtask_scoredetails", kwargs={"pk": navigation_task.pk}))
        form = GateScoreForm(request.POST, scorecard=scorecard, gate_type=gate_type)
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


@guardian_permission_required("display.view_contest", (Contest, "navigationtask__pk", "pk"))
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
    for gate_score in navigation_task.scorecard.gate_scores():
        if len(gate_score.visible_fields) > 0:
            form = GateScoreForm(scorecard=navigation_task.scorecard, gate_type=gate_score.gate_type)
            form.pk = gate_score.gate_type  # a gate type key now, not a database pk - see urls.py
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


class PersonList(SuperuserRequiredMixin, ListView):
    model = Person

    def get_queryset(self):
        return Person.objects.all().order_by("last_name", "first_name")


class PersonUpdateView(SuperuserRequiredMixin, UpdateView):
    model = Person
    success_url = reverse_lazy("person_list")
    form_class = PersonForm


class FrontEndView(TemplateView):
    """
    Render the react view
    """

    template_name = "display/frontend.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["show_cima_task_types"] = can_user_see_cima_task_types(self.request.user)
        context["visible_task_type_groups"] = get_visible_task_type_groups_for_user(self.request.user)
        context["gate_cima_task_visibility"] = bool(getattr(settings, "GATE_CIMA_TASK_VISIBILITY", False))
        return context


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


@require_POST
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
        instance.published_service_key = instance.default_service_key
        instance.published_relative_path = instance.map_file.name
        instance.save(update_fields=["processing_status", "processing_error", "published_service_key", "published_relative_path"])

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
        previous_relative_path = getattr(instance, "published_relative_path", "")
        current_relative_path = instance.map_file if isinstance(instance.map_file, str) else (instance.map_file.name if getattr(instance.map_file, "name", "") else instance.default_published_relative_path)
        if previous_relative_path and previous_relative_path != current_relative_path:
            unpublish_user_uploaded_map(instance, relative_path=previous_relative_path)
            request_mbtiles_reload()
            if not isinstance(instance.map_file, str) and getattr(instance.map_file, "storage", None):
                instance.map_file.storage.delete(previous_relative_path)
        instance.clear_local_file_path()
        instance.processing_status = UserUploadedMap.PROCESSING_PENDING
        instance.processing_error = ""
        instance.published_service_key = instance.default_service_key
        instance.published_relative_path = instance.map_file.name if instance.map_file else instance.default_published_relative_path
        instance.published_at = None
        instance.save(update_fields=[
            "processing_status",
            "processing_error",
            "published_service_key",
            "published_relative_path",
            "published_at",
        ])

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
        if not isinstance(self.object.map_file, str) and getattr(self.object.map_file, "storage", None):
            self.object.map_file.storage.delete(self.object.published_relative_path or str(self.object.map_file))
        unpublish_user_uploaded_map(self.object)
        request_mbtiles_reload()
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


@require_POST
@guardian_permission_required("display.change_useruploadedmap", (UserUploadedMap, "pk", "pk"))
def delete_user_useruploadedmap_permissions(request, pk, user_pk):
    user_uploaded_map = get_object_or_404(UserUploadedMap, pk=pk)
    user = get_object_or_404(MyUser, pk=user_pk)
    # See delete_user_contest_permissions for why both of these are here.
    if user.pk == request.user.pk:
        messages.error(request, "You cannot remove your own permissions for this map.")
        return redirect(reverse("useruploadedmap_permissions_list", kwargs={"pk": pk}))
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
    Manual view for authenticating with firebase. Used by apps.

    Prefers the token from the ``Authorization: JWT <token>`` header (not logged by
    reverse proxies/CDNs the way a query string is), falling back to the legacy
    ``?token=`` query parameter so already-deployed app builds that only know the old
    URL-based flow keep working.
    """
    from display.authentication import FirebaseTokenAuthentication

    authorization = request.headers.get("Authorization", "")
    scheme, _, header_token = authorization.partition(" ")
    token = header_token if scheme.lower() == FirebaseTokenAuthentication.keyword.lower() and header_token else None
    if not token:
        token = request.GET.get("token")
    logger.debug("Received Firebase login token")
    firebase_authenticator = FirebaseTokenAuthentication()
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

TAIL_NUMBER_RE = re.compile(r"^[A-Za-z0-9\-]{1,20}$")


def quick_register(request, pk):
    navigation_task = get_object_or_404(NavigationTask, pk=pk)
    if not navigation_task.is_poker_run:
        raise Http404("Quick registration is only available for Poker Run tasks.")
    contest = navigation_task.contest

    # Quick-register is a low-friction walk-up flow, but it must still respect the same
    # visibility gate as every other self-managed-contestant path: only a task the organiser has
    # explicitly opened for self-management and made public, or a manager of the contest itself
    # (e.g. testing the flow), may reach it. Previously any authenticated user could self-enrol
    # in ANY poker task regardless of visibility, bypassing is_public/allow_self_management and
    # every capacity limit.
    is_publicly_self_manageable = (
        navigation_task.allow_self_management and navigation_task.is_public and contest.is_public
    )
    is_contest_manager = request.user.is_authenticated and request.user.has_perm("display.change_contest", contest)
    if not is_publicly_self_manageable and not is_contest_manager:
        raise Http404("Quick registration is only available for Poker Run tasks.")

    if not request.user.is_authenticated:
        return render(request, "display/quick_register_login.html", {"contest": contest, "navigation_task": navigation_task})

    # Check if they already have an active registration for this task
    # (One that hasn't finished yet)
    existing_contestant = Contestant.objects.filter(
        navigation_task=navigation_task,
        team__crew__member1=request.user.person,
        finished_by_time__gt=timezone.now()
    ).first()
    
    if existing_contestant:
        return render(request, "display/quick_register_success.html", {
            "contest": contest,
            "navigation_task": navigation_task,
            "tail_number": existing_contestant.team.aeroplane.registration,
            "contestant": existing_contestant
        })

    if request.method == "POST":
        tail_number = request.POST.get("tail_number", "").strip().upper()
        if tail_number and not TAIL_NUMBER_RE.fullmatch(tail_number):
            return render(request, "display/quick_register.html", {
                "contest": contest,
                "navigation_task": navigation_task,
                "error": "Tail number must be 1-20 alphanumeric characters or hyphens.",
            })
        if tail_number:
            # 1. Create/Get Aeroplane
            aeroplane, _ = Aeroplane.objects.get_or_create(registration=tail_number)

            # 2. Create/Get Crew (member1 is current user)
            crew, _ = Crew.objects.get_or_create(member1=request.user.person, member2=None)

            # 3. Create/Get Team
            team, _ = Team.objects.get_or_create(aeroplane=aeroplane, crew=crew)

            # 4. Capacity check before mutating anything else - _assert_can_reserve_task_slot
            # only needs navigation_task/team/resolution, not a ContestTeam row, so this can (and
            # must) run before step 5 creates one. Checking after would leave a ContestTeam
            # registered for a rejected registration attempt, since there is no rollback here.
            resolution = resolve_contest_access(contest)
            try:
                _assert_can_reserve_task_slot(navigation_task, team, resolution)
            except (ValidationError, drf_exceptions.ValidationError) as exc:
                return render(request, "display/quick_register.html", {
                    "contest": contest,
                    "navigation_task": navigation_task,
                    "error": exc,
                })

            # 5. Create ContestTeam
            contest_team, _ = ContestTeam.objects.get_or_create(contest=contest, team=team)

            # 6. Create Contestant (Scheduled Flight)
            # Determine next contestant number
            last_contestant = Contestant.objects.filter(navigation_task=navigation_task).order_by("-contestant_number").first()
            next_number = (last_contestant.contestant_number + 1) if last_contestant else 1
            
            takeoff_time = timezone.now()
            # Default duration 6 hours
            finished_by_time = takeoff_time + datetime.timedelta(hours=6)
            # Tracker lead time 15 mins
            tracker_start_time = takeoff_time - datetime.timedelta(minutes=15)
            
            Contestant.objects.create(
                team=team,
                navigation_task=navigation_task,
                takeoff_time=takeoff_time,
                finished_by_time=finished_by_time,
                tracker_start_time=tracker_start_time,
                contestant_number=next_number,
                air_speed=contest_team.air_speed,
                wind_speed=navigation_task.wind_speed,
                wind_direction=navigation_task.wind_direction,
                minutes_to_starting_point=navigation_task.minutes_to_starting_point,
                tracking_service=contest_team.tracking_service,
                tracking_device=contest_team.tracking_device,
                tracker_device_id=contest_team.tracker_device_id,
            )
            
            return render(request, "display/quick_register_success.html", {
                "contest": contest,
                "navigation_task": navigation_task,
                "tail_number": tail_number
            })

    return render(request, "display/quick_register.html", {"contest": contest, "navigation_task": navigation_task})


def generate_hangar_flyer_pdf(request, pk):
    navigation_task = get_object_or_404(NavigationTask, pk=pk)
    contest = navigation_task.contest
    is_poker = navigation_task.is_poker_run

    # Check permissions (only editors can generate flyer)
    if not request.user.has_perm("display.change_contest", contest):
        raise Http404("You do not have permission to generate the flyer.")

    from fpdf import FPDF
    import qrcode
    from io import BytesIO
    import os
    import requests

    def load_image_to_buffer(field, name_for_log):
        if not field:
            return None
        # 1. Try Django storage API / local path
        try:
            with field.open('rb') as f:
                return BytesIO(f.read())
        except Exception as e:
            logger.warning(f"Could not open {name_for_log} via storage: {e}")

        # 2. Try fetching via URL (for remote storage or if disk is out of sync)
        try:
            url = field.url
            if url.startswith('/'):
                url = request.build_absolute_uri(url)
            logger.info(f"Attempting to fetch {name_for_log} from URL: {url}")
            resp = requests.get(url, timeout=3)
            if resp.status_code == 200:
                return BytesIO(resp.content)
            else:
                logger.warning(f"Failed to fetch {name_for_log} from {url}: status {resp.status_code}")
        except Exception as e:
            logger.warning(f"Error fetching {name_for_log} from URL: {e}")

        return None

    class MyFPDF(FPDF):
        def footer(self):
            self.set_y(-20)
            logo_paths = [
                "/workspace/src/static/img/AirSportsLiveTracking.png",
                "/src/static/img/AirSportsLiveTracking.png",
                "src/static/img/AirSportsLiveTracking.png"
            ]
            img_found = False
            for img_path in logo_paths:
                if os.path.exists(img_path):
                    try:
                        self.image(img_path, x=65, w=80)
                        img_found = True
                        break
                    except Exception as e:
                        logger.warning(f"FPDF could not render AirSports logo from {img_path}: {e}")

            if not img_found:
                self.set_font("helvetica", "I", 8)
                self.set_text_color(150, 150, 150)
                self.cell(0, 10, "Air Sports Live Tracking - https://airsports.no", align="C")

    # Determine target URL
    if is_poker:
        target_url = request.build_absolute_uri(reverse('quick_register', args=[pk]))
        subtitle = "Digital Poker Run - Navigation & Strategy Challenge"
    else:
        # Use frontend Schedule Flight page
        base_url = request.build_absolute_uri('/')[:-1]
        frontend_path = settings.FRONTEND_ROUTES.get('SCHEDULE_FLIGHT', 'schedule-flight')
        target_url = f"{base_url}/{frontend_path}?contestId={contest.pk}&navigationTaskId={pk}"
        subtitle = "Self-Management Signup - Navigation & Strategy Challenge"

    # Prepare buffers
    qr_img = qrcode.make(target_url)
    qr_buf = BytesIO()
    qr_img.save(qr_buf, format="PNG")
    qr_buf.seek(0)

    logo_buf = load_image_to_buffer(contest.logo, "contest logo")
    # if not logo_buf:
    #     fallback_logo = "/workspace/airsports_static/public/img/airsports.png"
    #     if os.path.exists(fallback_logo):
    #         with open(fallback_logo, 'rb') as f:
    #             logo_buf = BytesIO(f.read())

    header_buf = load_image_to_buffer(contest.header_image, "contest header")
    # if not header_buf:
    #     fallback_header = "/workspace/airsports_static/public/img/nordic2025.png"
    #     if os.path.exists(fallback_header):
    #         with open(fallback_header, 'rb') as f:
    #             header_buf = BytesIO(f.read())

    pdf = MyFPDF()
    pdf.add_page()

    # 1. Contest Header Image (at the top, fixed height to ensure one-page layout)
    if header_buf:
        try:
            # Zoom to fit: Crop top and bottom instead of squeezing
            # We want to fill 190x40mm. 
            # We'll use FPDF's image() with a negative height or manual cropping if needed,
            # but usually, we can just let it overflow or use a clip.
            # Simplified approach: Use a fixed width and let it maintain aspect ratio, 
            # but since we need a fixed height container, we'll use the 'keep aspect ratio' logic.
            
            from PIL import Image
            header_buf.seek(0)
            with Image.open(header_buf) as img:
                img_w, img_h = img.size
                aspect = img_w / img_h
                target_w = 190
                target_h = 40
                target_aspect = target_w / target_h
                
                if aspect > target_aspect:
                    # Image is wider than target area - crop sides
                    new_w = img_h * target_aspect
                    left = (img_w - new_w) / 2
                    img_cropped = img.crop((left, 0, left + new_w, img_h))
                else:
                    # Image is taller than target area - crop top/bottom
                    new_h = img_w / target_aspect
                    top = (img_h - new_h) / 2
                    img_cropped = img.crop((0, top, img_w, top + new_h))
                
                temp_header_buf = BytesIO()
                img_cropped.save(temp_header_buf, format="PNG")
                temp_header_buf.seek(0)
                pdf.image(temp_header_buf, x=10, y=10, w=target_w, h=target_h)
            
            pdf.set_y(55)
        except Exception as e:
            logger.warning(f"FPDF error rendering header image: {e}")
            pdf.set_y(10)
    else:
        pdf.set_y(10)

    # 2. Contest & Task Titles
    pdf.set_font("helvetica", "B", 20)
    pdf.cell(pdf.epw, 10, contest.name, new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("helvetica", "B", 16)
    pdf.set_text_color(0, 102, 204)
    pdf.cell(pdf.epw, 10, navigation_task.name, new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("helvetica", "", 12)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(pdf.epw, 8, subtitle, new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("helvetica", "I", 10)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(pdf.epw, 6, f"Competition Type: {navigation_task.original_scorecard.name}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    # 3. Welcome Text
    pdf.set_font("helvetica", "", 12)
    pdf.set_text_color(0, 0, 0)
    pdf.set_x(pdf.l_margin)
    pdf.write(6, "Welcome pilots! Today's flight uses Air Sports Live Tracking (ASLT) to automate scoring, manage your digital card deck, and live-stream our tracks straight to the hangar leaderboard.")
    pdf.ln(10)
    pdf.set_line_width(0.2)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(5)

    # 4. QR Code Section
    curr_y = pdf.get_y()
    qr_w = 45
    pdf.image(qr_buf, x=(pdf.w - qr_w) / 2, y=curr_y, w=qr_w)
    pdf.set_x(pdf.l_margin)
    pdf.set_y(curr_y + 50)
    pdf.set_font("helvetica", "B", 16)
    pdf.cell(pdf.epw, 8, "Scan to Register", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", "I", 9)
    pdf.cell(pdf.epw, 5, f"Target URL: {target_url}", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(5)

    # 5. Steps Section
    pdf.set_font("helvetica", "B", 14)
    pdf.cell(pdf.epw, 10, "STEPS TO JOIN THE FLIGHT:", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", "", 11)

    if is_poker:
        steps = [
            "1. Scan the QR code above with your smartphone.",
            "2. Enter your Tail Number on the quick web confirmation page.",
            "3. Launch your native ASLT Mobile App normally.",
            "4. Your pre-scheduled Poker Run flight will be active on your app dashboard. Tap 'Start Tracking' and fly!"
        ]
    else:
        steps = [
            "1. Scan the QR code above with your smartphone.",
            "2. Complete the self-management signup on the web page.",
            "3. Launch your native ASLT Mobile App normally.",
            "4. Once registered, your flight will be active on your app dashboard. Tap 'Start Tracking' and fly!"
        ]

    for step in steps:
        pdf.set_x(pdf.l_margin)
        pdf.write(7, step)
        pdf.ln(8)

    pdf.ln(2)
    pdf.set_font("helvetica", "I", 10)
    pdf.set_text_color(80, 80, 80)
    pdf.set_x(pdf.l_margin)
    if is_poker:
        challenge_text = "Optional Challenge Notice: Watch your navigation boundaries. Virtual Penalty Zones are active on this course. Brave the 'Extra Card Gate' if you want to gamble for a stronger poker hand, but mind the obstacles!"
    else:
        challenge_text = "Watch your navigation boundaries. Virtual Penalty Zones may be active on this course. Ensure your tracker is correctly configured before departure."

    pdf.write(5, challenge_text)
    pdf.ln(5)

    # 6. Contest Logo (at the bottom)
    if logo_buf:
        try:
            # Position it at the bottom right
            pdf.image(logo_buf, x=170, y=255, w=30)
        except Exception as e:
            logger.warning(f"FPDF error rendering logo at bottom: {e}")

    # Finalize PDF
    try:

        pdf_bytes = bytes(pdf.output())
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="hangar_flyer_{navigation_task.pk}.pdf"'
        response["Content-Length"] = len(pdf_bytes)
        return response
    except Exception as e:
        logger.error(f"Error finalizing PDF: {e}")
        return HttpResponse(f"Error generating PDF: {e}", content_type="text/plain", status=500)