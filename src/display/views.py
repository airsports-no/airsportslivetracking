import base64
import datetime
import os
from datetime import timedelta
from typing import Optional

import redis_lock
import dateutil
from django.contrib.auth.decorators import permission_required, login_required
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.storage import FileSystemStorage
from django.db.models import Q
from django.forms import formset_factory
from django.http import HttpResponseRedirect
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
from rest_framework.decorators import action, api_view
from rest_framework.exceptions import PermissionDenied, MethodNotAllowed
from rest_framework.generics import RetrieveAPIView, get_object_or_404
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, ViewSet

from display.convert_flightcontest_gpx import create_route_from_gpx, create_route_from_csv, load_route_points_from_kml, \
    create_route_from_formset
from display.forms import ImportRouteForm, WaypointForm, NavigationTaskForm, FILE_TYPE_CSV, FILE_TYPE_FLIGHTCONTEST_GPX, \
    FILE_TYPE_KML, ContestantForm, ContestForm
from display.models import NavigationTask, Route, Contestant, CONTESTANT_CACHE_KEY, Contest, Team, ContestantTrack, \
    Person
from display.permissions import ContestPermissions, NavigationTaskContestPermissions, \
    ContestantPublicPermissions, NavigationTaskPublicPermissions, ContestPublicPermissions, \
    ContestantNavigationTaskContestPermissions, RoutePermissions
from display.serialisers import ContestantTrackSerialiser, \
    ExternalNavigationTaskNestedSerialiser, \
    ContestSerialiser, NavigationTaskNestedSerialiser, RouteSerialiser, \
    ContestantTrackWithTrackPointsSerialiser, ContestantNestedSerialiser, ContestResultsHighLevelSerialiser, \
    ContestSummarySerialiser, TeamResultsSummarySerialiser, ContestResultsDetailsSerialiser, TeamNestedSerialiser, \
    GpxTrackSerialiser, PersonSerialiser
from display.show_slug_choices import ShowChoicesMetadata
from influx_facade import InfluxFacade
from live_tracking_map import settings
from playback_tools import insert_gpx_file

logger = logging.getLogger(__name__)


def frontend_view_map(request, pk):
    navigation_task = get_object_or_404(NavigationTask, pk=pk)
    return render(request, "display/root.html",
                  {"contest_id": navigation_task.contest.pk, "navigation_task_id": pk, "live_mode": "true",
                   "display_map": "true", "display_table": "false", "skip_nav": True})


def results_service(request):
    return render(request, "display/resultsservice.html")


@api_view(["POST"])
def auto_complete_person_phone(request):
    if request.is_ajax():
        request_number = int(request.POST.get("request"))
        if request_number == 1:
            q = request.POST.get('search', '')
            search_qs = Person.objects.filter(phone__contains=q)
            result = [item.phone for item in search_qs]
            return Response(result)
        else:
            q = request.POST.get('phone', '')
            search_qs = Person.objects.filter(phone=q)
            serialiser = PersonSerialiser(search_qs, many=True)
            return Response(serialiser.data)
    raise MethodNotAllowed


@api_view(["POST"])
def auto_complete_person_email(request):
    if request.is_ajax():
        request_number = int(request.POST.get("request"))
        if request_number == 1:
            q = request.POST.get('search', '')
            search_qs = Person.objects.filter(email__contains=q)
            result = [item.phone for item in search_qs]
            return Response(result)
        else:
            q = request.POST.get('phone', '')
            search_qs = Person.objects.filter(email=q)
            serialiser = PersonSerialiser(search_qs, many=True)
            return Response(serialiser.data)
    raise MethodNotAllowed


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


class NewNavigationTaskWizard(SessionWizardView):
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
    serializer_class = ContestSerialiser
    permission_classes = [ContestPublicPermissions | (permissions.IsAuthenticated & ContestPermissions)]

    def get_queryset(self):
        return get_objects_for_user(self.request.user, "view_contest",
                                    klass=self.queryset) | self.queryset.filter(is_public=True)


class NavigationTaskViewSet(IsPublicMixin, ModelViewSet):
    queryset = NavigationTask.objects.all()
    serializer_class = NavigationTaskNestedSerialiser
    permission_classes = [
        NavigationTaskPublicPermissions | (permissions.IsAuthenticated & NavigationTaskContestPermissions)]

    http_method_names = ['get', 'post', 'delete', 'put']

    def get_queryset(self):
        contest_id = self.kwargs["contest_pk"]
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
    serializer_class = ContestantNestedSerialiser
    permission_classes = [
        ContestantPublicPermissions | (permissions.IsAuthenticated & ContestantNavigationTaskContestPermissions)]

    def get_serializer_class(self):
        if self.action == "gpx_track":
            return GpxTrackSerialiser
        return super().get_serializer_class()

    def get_queryset(self):
        navigation_task_id = self.kwargs["navigationtask_pk"]
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
                                         context={"request": request, "navigation_task": navigation_task},
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
    serializer_class = ExternalNavigationTaskNestedSerialiser
    permission_classes = [permissions.IsAuthenticated & NavigationTaskContestPermissions]

    metadata_class = ShowChoicesMetadata

    http_method_names = ["post"]

    lookup_key = "contest_pk"

    def create(self, request, *args, **kwargs):
        contest = get_object_or_404(Contest, pk=self.kwargs.get(self.lookup_key))
        serialiser = ExternalNavigationTaskNestedSerialiser(data=request.data,
                                                            context={"request": request, "contest": contest})
        if serialiser.is_valid(raise_exception=True):
            serialiser.save()
            return Response(serialiser.data, status=status.HTTP_201_CREATED)
        return Response(serialiser.errors, status=status.HTTP_400_BAD_REQUEST)


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
