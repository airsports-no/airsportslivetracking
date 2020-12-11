import datetime
from datetime import timedelta
from typing import List, Optional

import guardian
import redis_lock
import dateutil
from django.contrib.auth.decorators import permission_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.cache import cache
from django.shortcuts import render, redirect
from django.http import HttpResponse, Http404
from django.views.generic import View, TemplateView, ListView
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
import logging
import urllib.request
import os

from drf_yasg.app_settings import swagger_settings
from drf_yasg.utils import swagger_auto_schema
from guardian.decorators import permission_required_or_403
from guardian.shortcuts import get_objects_for_user
from redis import Redis
from rest_framework import status, permissions
from rest_framework.decorators import api_view, action
from rest_framework.generics import RetrieveAPIView, get_object_or_404, DestroyAPIView, CreateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet

from display.convert_flightcontest_gpx import create_track_from_gpx, create_track_from_csv
from display.forms import ImportTrackForm
from display.models import NavigationTask, Track, ContestantTrack, Contestant, CONTESTANT_CACHE_KEY, Contest
from display.permissions import ContestPermissions, NavigationTaskPermissions, \
    ContestantPublicPermissions, NavigationTaskPublicPermissions, ContestPublicPermissions
from display.serialisers import NavigationTaskSerialiser, ContestantTrackNestedSerialiser, \
    ExternalNavigationTaskNestedSerialiser, \
    ContestSerialiser, ContestantNestedSerialiser, NavigationTaskNestedSerialiser, TrackSerialiser, ContestantSerialiser
from display.show_slug_choices import ShowChoicesMetadata, ShowChoicesFieldInspector
from influx_facade import InfluxFacade

logger = logging.getLogger(__name__)


def frontend_view(request, pk):
    return render(request, "display/root.html",
                  {"navigation_task_id": pk, "live_mode": "true", "display_map": "true", "display_table": "true"})


def frontend_view_table(request, pk):
    return render(request, "display/root.html",
                  {"navigation_task_id": pk, "live_mode": "true", "display_map": "false", "display_table": "true"})


def frontend_view_map(request, pk):
    return render(request, "display/root.html",
                  {"navigation_task_id": pk, "live_mode": "true", "display_map": "true", "display_table": "false"})


class NavigationTaskList(ListView):
    model = NavigationTask

    def get_queryset(self):
        return NavigationTask.objects.filter(is_public=True)


class ContestList(ListView):
    model = Contest

    def get_queryset(self):
        return Contest.objects.filter(is_public=True)


connection = Redis("redis")


@api_view(["GET"])
def get_data_from_time_for_contestant(request, contestant_pk):
    from_time = request.GET.get("from_time")
    key = "{}.{}.{}".format(CONTESTANT_CACHE_KEY, contestant_pk, from_time)
    response = generate_data(contestant_pk, from_time)
    return Response(response)
    response = cache.get(key)
    if response is None:
        logger.info("Cache miss {}".format(contestant_pk))
        with redis_lock.Lock(connection, "{}.{}".format(CONTESTANT_CACHE_KEY, contestant_pk)):
            response = cache.get(key)
            logger.info("Cache miss second time {}".format(contestant_pk))
            if response is None:
                response = generate_data(contestant_pk, from_time)
                cache.set(key, response)
                logger.info("Completed updating cash {}".format(contestant_pk))
    return Response(response)


def generate_data(contestant_pk, from_time: Optional[datetime.datetime]):
    contestant = get_object_or_404(Contestant, pk=contestant_pk)  # type: Contestant
    influx = InfluxFacade()
    default_start_time = contestant.navigation_task.start_time - timedelta(minutes=30)
    if from_time is None:
        from_time = default_start_time.isoformat()
    from_time_datetime = dateutil.parser.parse(from_time)
    logger.info("Fetching data from time {} {}".format(from_time, contestant.pk))
    result_set = influx.get_positions_for_contestant(contestant_pk, default_start_time.isoformat())
    annotation_results = influx.get_annotations_for_contestant(contestant_pk, from_time)
    annotations = []
    global_latest_time = None
    logger.info("Completed fetching positions for {}".format(contestant.pk))
    position_data = list(result_set.get_points(tags={"contestant": str(contestant.pk)}))
    filtered_position_data = [item for item in position_data if
                              dateutil.parser.parse(item["time"]) > from_time_datetime]
    if len(position_data) > 0:
        global_latest_time = dateutil.parser.parse(position_data[-1]["time"])
    positions = filtered_position_data
    annotation_data = list(annotation_results.get_points(tags={"contestant": str(contestant.pk)}))
    if len(annotation_data):
        annotations = annotation_data
    if hasattr(contestant, "contestanttrack"):
        contestant_track = ContestantTrackNestedSerialiser(contestant.contestanttrack).data
    else:
        contestant_track = None
    logger.info("Completed generating data {}".format(contestant.pk))
    return {"contestant_id": contestant.pk, "latest_time": global_latest_time, "positions": positions,
            "annotations": annotations,
            "contestant_track": contestant_track}


def import_track(request):
    form = ImportTrackForm()
    if request.method == "POST":
        form = ImportTrackForm(request.POST, request.FILES)
        if form.is_valid():
            name = form.cleaned_data["name"]
            file_type = form.cleaned_data["file_type"]
            print(file_type)
            if file_type == form.CSV:
                data = [item.decode(encoding="UTF-8") for item in request.FILES['file'].readlines()]
                create_track_from_csv(name, data[1:])
            elif file_type == form.FLIGHTCONTEST_GPX:
                create_track_from_gpx(name, request.FILES["file"])
            return redirect("/")
    return render(request, "display/import_track_form.html", {"form": form})


# Everything below he is related to management and requires authentication
class IsPublicMixin:
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
        object = self.get_object()
        object.is_public = True
        object.save()
        return Response({'is_public': object.is_public})

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
        object = self.get_object()
        object.is_public = False
        object.save()
        return Response({'is_public': object.is_public})


class ContestViewSet(IsPublicMixin, ModelViewSet):
    """
    A contest is a high level wrapper for multiple tasks. Currently it mostly consists of a name and a is_public
    flag which controls its visibility for anonymous users.GET Returns a list of contests either owned by the user
    or publicly divisible POST Allows the user to post a new contest and become the owner of that contest.
    """
    queryset = Contest.objects.all()
    serializer_class = ContestSerialiser
    permission_classes = [ContestPublicPermissions | permissions.IsAuthenticated & NavigationTaskPermissions]

    def get_queryset(self):
        return get_objects_for_user(self.request.user, "view_navigationtask",
                                    klass=self.queryset) | self.queryset.filter(is_public=True)


class NavigationTaskViewSet(IsPublicMixin, ModelViewSet):
    queryset = NavigationTask.objects.all()
    serializer_class = NavigationTaskSerialiser
    permission_classes = [NavigationTaskPublicPermissions | permissions.IsAuthenticated & NavigationTaskPermissions]

    def get_queryset(self):
        return get_objects_for_user(self.request.user, "view_navigationtask",
                                    klass=self.queryset) | self.queryset.filter(is_public=True)


class TrackViewSet(ModelViewSet):
    queryset = Track.objects.all()
    serializer_class = TrackSerialiser
    permission_classes = [permissions.IsAuthenticated]

    http_method_names = ['get', 'post', 'delete', 'put']


class NavigationTaskNestedViewSet(IsPublicMixin, ModelViewSet):
    queryset = NavigationTask.objects.all()
    serializer_class = NavigationTaskNestedSerialiser
    permission_classes = [NavigationTaskPublicPermissions | permissions.IsAuthenticated & NavigationTaskPermissions]

    http_method_names = ['get']

    def get_queryset(self):
        return get_objects_for_user(self.request.user, "view_navigationtask",
                                    klass=self.queryset) | self.queryset.filter(is_public=True)


class ContestantViewSet(ModelViewSet):
    queryset = Contestant.objects.all()
    serializer_class = ContestantSerialiser
    permission_classes = [permissions.IsAuthenticated & NavigationTaskPermissions]

    http_method_names = ['get', 'post', 'delete', 'patch']

    def get_queryset(self):
        return get_objects_for_user(self.request.user, "view_navigationtask",
                                    klass=self.queryset) | self.queryset.filter(navigation_task__is_public=True)


class ImportFCNavigationTask(ModelViewSet):
    """
    This is a shortcut to post a new navigation task to the tracking system. It requires the existence of a contest to
    which it will belong. The entire task with contestants and their associated times, crews, and aircraft, together
    with the track can be posted to the single endpoint.

    track_file is a utf-8 string that contains a base 64 encoded gpx route file of the format that FC exports. A new
    track object lacquers will be created every time this function is called, but it is possible to reuse tracks if
    required. This is currently not supported through this endpoint, but this may change in the future.
    """
    queryset = NavigationTask.objects.all()
    serializer_class = ExternalNavigationTaskNestedSerialiser
    permission_classes = [permissions.IsAuthenticated & NavigationTaskPermissions]

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
