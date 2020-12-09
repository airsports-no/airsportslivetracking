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
from rest_framework.decorators import api_view
from rest_framework.generics import RetrieveAPIView, get_object_or_404, DestroyAPIView, CreateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet

from display.convert_flightcontest_gpx import create_track_from_gpx, create_track_from_csv
from display.forms import ImportTrackForm
from display.models import NavigationTask, Track, ContestantTrack, Contestant, CONTESTANT_CACHE_KEY, Contest
from display.permissions import ContestPermissions, NavigationTaskPermissions
from display.serialisers import NavigationTaskSerialiser, ContestantTrackSerialiser, ExternalNavigationTaskSerialiser, \
    ContestSerialiser, ContestantSerialiser
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


class RetrieveNavigationTaskApi(RetrieveAPIView):
    serializer_class = NavigationTaskSerialiser
    queryset = NavigationTask.objects.all()
    lookup_field = "pk"


class NavigationTaskList(ListView):
    model = NavigationTask


connection = Redis("redis")


@api_view(["GET"])
def get_data_from_time_for_contestant(request, contestant_pk):
    from_time = request.GET.get("from_time")
    key = "{}.{}.{}".format(CONTESTANT_CACHE_KEY, contestant_pk, from_time)
    response = cache.get(key)
    if response is None:
        with redis_lock.Lock(connection, "{}.{}".format(CONTESTANT_CACHE_KEY, contestant_pk)):
            response = generate_data(contestant_pk, from_time)
            cache.set(key, response, timeout=300)
    return Response(response)


def generate_data(contestant_pk, from_time: Optional[datetime.datetime]):
    contestant = get_object_or_404(Contestant, pk=contestant_pk)  # type: Contestant
    influx = InfluxFacade()
    default_start_time = contestant.navigation_task.start_time - timedelta(minutes=30)
    if from_time is None:
        from_time = default_start_time.isoformat()
    from_time_datetime = dateutil.parser.parse(from_time)
    logger.info("Fetching data from time {}".format(from_time))
    result_set = influx.get_positions_for_contestant(contestant_pk, default_start_time.isoformat())
    annotation_results = influx.get_annotations_for_contestant(contestant_pk, from_time)
    annotations = []
    global_latest_time = None
    logger.debug("Contestant_pk: {}".format(contestant.pk))
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
        contestant_track = ContestantTrackSerialiser(contestant.contestanttrack).data
    else:
        contestant_track = None
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
class ContestViewSet(ModelViewSet):
    queryset = Contest.objects.all()
    serializer_class = ContestSerialiser
    permission_classes = [permissions.IsAuthenticated & ContestPermissions]

    def get_queryset(self):
        return list(get_objects_for_user(self.request.user, "view_contest", klass=self.queryset)) + list(
            self.queryset.filter(is_public=True))


class NavigationTaskViewSet(ModelViewSet):
    queryset = NavigationTask.objects.all()
    serializer_class = NavigationTaskSerialiser
    permission_classes = (NavigationTaskPermissions, )
    lookup_url_kwarg = "pk"


    def get_queryset(self):
        return get_objects_for_user(self.request.user, "view_navigationtask", klass=self.queryset) & self.queryset.filter(is_public=True)


class ContestantViewSet(ModelViewSet):
    queryset = Contestant.objects.all()
    serializer_class = ContestantSerialiser
    permission_classes = (permissions.IsAuthenticated, NavigationTaskPermissions)

    def get_queryset(self):
        return list(get_objects_for_user(self.request.user, "view_navigationtask", klass=self.queryset)) + list(
            self.queryset.filter(navigation_task__is_public=True))


class ImportFCNavigationTask(ModelViewSet):
    queryset = NavigationTask.objects.all()
    serializer_class = ExternalNavigationTaskSerialiser
    permission_classes = (permissions.IsAuthenticated, NavigationTaskPermissions)

    metadata_class = ShowChoicesMetadata

    http_method_names = ["post", "delete"]

    lookup_key = "contest_id"

    def post(self, request, *args, **kwargs):
        contest = get_object_or_404(Contest, pk=self.kwargs.get(self.lookup_key))
        serialiser = ExternalNavigationTaskSerialiser(data=request.data,
                                                      context={"request": request, "contest": contest})
        if serialiser.is_valid():
            serialiser.save()
            return Response(serialiser.data)
        return Response(serialiser.errors, status=status.HTTP_400_BAD_REQUEST)
