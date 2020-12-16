import datetime
from datetime import timedelta
from typing import Optional

import redis_lock
import dateutil
from django.contrib.auth.decorators import permission_required, login_required
from django.contrib.auth.models import User
from django.core.cache import cache
from django.db.models import Q
from django.shortcuts import render, redirect
from django.urls import reverse
from django.views.generic import ListView
import logging
from guardian.shortcuts import get_objects_for_user, assign_perm
from redis import Redis
from rest_framework import status, permissions
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.generics import RetrieveAPIView, get_object_or_404
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, ViewSet

from display.convert_flightcontest_gpx import create_route_from_gpx, create_route_from_csv
from display.forms import ImportRouteForm
from display.models import NavigationTask, Route, Contestant, CONTESTANT_CACHE_KEY, Contest
from display.permissions import ContestPermissions, NavigationTaskContestPermissions, \
    ContestantPublicPermissions, NavigationTaskPublicPermissions, ContestPublicPermissions, \
    ContestantNavigationTaskContestPermissions, RoutePermissions
from display.serialisers import ContestantTrackSerialiser, \
    ExternalNavigationTaskNestedSerialiser, \
    ContestSerialiser, NavigationTaskNestedSerialiser, RouteSerialiser, \
    ContestantTrackWithTrackPointsSerialiser, ContestantNestedSerialiser
from display.show_slug_choices import ShowChoicesMetadata
from influx_facade import InfluxFacade

logger = logging.getLogger(__name__)


def frontend_view(request, pk):
    navigation_task = get_object_or_404(NavigationTask, pk=pk)
    return render(request, "display/root.html",
                  {"contest_id": navigation_task.contest.pk, "navigation_task_id": pk, "live_mode": "true",
                   "display_map": "true", "display_table": "true"})


def frontend_view_table(request, pk):
    navigation_task = get_object_or_404(NavigationTask, pk=pk)
    return render(request, "display/root.html",
                  {"contest_id": navigation_task.contest.pk, "navigation_task_id": pk, "live_mode": "true",
                   "display_map": "false", "display_table": "true"})


def frontend_view_map(request, pk):
    navigation_task = get_object_or_404(NavigationTask, pk=pk)
    return render(request, "display/root.html",
                  {"contest_id": navigation_task.contest.pk, "navigation_task_id": pk, "live_mode": "true",
                   "display_map": "true", "display_table": "false"})


class NavigationTaskList(ListView):
    model = NavigationTask

    def get_queryset(self):
        return NavigationTask.objects.filter(is_public=True)


class ContestList(ListView):
    model = Contest

    def get_queryset(self):
        return Contest.objects.filter(is_public=True)


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
            if file_type == form.CSV:
                data = [item.decode(encoding="UTF-8") for item in request.FILES['file'].readlines()]
                route = create_route_from_csv(name, data[1:])
            elif file_type == form.FLIGHTCONTEST_GPX:
                route = create_route_from_gpx(name, request.FILES["file"])
            if route is not None:
                assign_perm("view_route", request.user, route)
                assign_perm("delete_route", request.user, route)
                assign_perm("change_route", request.user, route)

            return redirect("/")
    return render(request, "display/import_route_form.html", {"form": form})


# Everything below he is related to management and requires authentication
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

    def get_queryset(
            self):
        contests = get_objects_for_user(self.request.user, "view_contest",
                                        klass=Contest)
        return NavigationTask.objects.filter(Q(contest__in=contests) | Q(is_public=True, contest__is_public=True))

    def create(self, request, *args, **kwargs):
        contest = get_object_or_404(Contest, pk=self.kwargs.get("contest_pk"))
        serialiser = self.get_serializer(data=request.data,
                                         context={"request": request, "contest": contest})
        if serialiser.is_valid():
            serialiser.save()
            return Response(serialiser.data)
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

    def get_queryset(self):
        contests = get_objects_for_user(self.request.user, "change_contest",
                                        klass=Contest)
        return Contestant.objects.filter(Q(navigation_task__contest__in=contests) | Q(navigation_task__is_public=True,
                                                                                      navigation_task__contest__is_public=True))

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
        if serialiser.is_valid():
            serialiser.save()
            return Response(serialiser.data)
        return Response(serialiser.errors, status=status.HTTP_400_BAD_REQUEST)


@login_required()
def renew_token(request):
    user = request.user
    Token.objects.filter(user=user).delete()
    Token.objects.create(user=user)
    return redirect(reverse("token"))
