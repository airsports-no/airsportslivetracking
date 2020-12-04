import datetime
from datetime import timedelta
from typing import List, Optional
import redis_lock
import dateutil
from django.core.cache import cache
from django.shortcuts import render, redirect
from django.http import HttpResponse, Http404
from django.views.generic import View, TemplateView, ListView
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
import logging
import urllib.request
import os

from redis import Redis
from rest_framework.decorators import api_view
from rest_framework.generics import RetrieveAPIView, get_object_or_404
from rest_framework.response import Response

from display.forms import ImportTrackForm
from display.models import Contest, Track, ContestantTrack, Contestant, CONTESTANT_CACHE_KEY
from display.serialisers import ContestSerialiser, ContestantTrackSerialiser
from influx_facade import InfluxFacade

logger = logging.getLogger(__name__)


def frontend_view(request, pk):
    return render(request, "display/root.html",
                  {"contest_id": pk, "live_mode": "true", "display_map": "true", "display_table": "true"})


def frontend_view_table(request, pk):
    return render(request, "display/root.html",
                  {"contest_id": pk, "live_mode": "true", "display_map": "false", "display_table": "true"})


def frontend_view_map(request, pk):
    return render(request, "display/root.html",
                  {"contest_id": pk, "live_mode": "true", "display_map": "true", "display_table": "false"})


def frontend_view_offline(request, pk):
    return render(request, "display/root.html", {"contest_id": pk, "live_mode": "false"})


class RetrieveContestApi(RetrieveAPIView):
    serializer_class = ContestSerialiser
    queryset = Contest.objects.all()
    lookup_field = "pk"


class ContestList(ListView):
    model = Contest


@api_view(["GET"])
def get_data_from_time_for_contest(request, contest_pk):
    contest = get_object_or_404(Contest, pk=contest_pk)  # type: Contest
    influx = InfluxFacade()
    from_time = request.GET.get("from_time", (contest.start_time - timedelta(minutes=30)).isoformat())
    logger.info("Fetching data from time {}".format(from_time))
    result_set = influx.get_positions_for_contest(contest_pk, from_time)
    annotation_results = influx.get_annotations_for_contest(contest_pk, from_time)
    positions = []
    annotations = []
    global_latest_time = None
    for contestant in contest.contestant_set.all():
        logger.debug("Contestant_pk: {}".format(contestant.pk))
        position_data = list(result_set.get_points(tags={"contestant": str(contestant.pk)}))
        logger.debug(position_data)
        if len(position_data):
            latest_time = dateutil.parser.parse(position_data[-1]["time"])
            global_latest_time = latest_time if not global_latest_time else max(latest_time, global_latest_time)
            contest_data = {
                "contestant_id": contestant.pk,
                "position_data": position_data
            }
            positions.append(contest_data)
        annotation_data = list(annotation_results.get_points(tags={"contestant": str(contestant.pk)}))
        if len(annotation_data):
            annotations.append({"contestant_id": contestant.pk, "annotations": annotation_data})

    return Response({"latest_time": global_latest_time, "positions": positions, "annotations": annotations,
                     "contestant_tracks": [ContestantTrackSerialiser(item).data for item in
                                           ContestantTrack.objects.filter(contestant__contest=contest)]})


connection = Redis("redis")


@api_view(["GET"])
def get_data_from_time_for_contestant(request, contestant_pk):
    from_time = request.GET.get("from_time")
    key = "{}.{}.{}".format(CONTESTANT_CACHE_KEY, contestant_pk, from_time)
    logger.info("Fetching key {}".format(key))
    response = cache.get(key)
    if response is None:
        with redis_lock.Lock(connection, "{}.{}".format(CONTESTANT_CACHE_KEY, contestant_pk)):
            response = generate_data(contestant_pk, from_time)
            cache.set(key, response, timeout=300)
    return Response(response)


def generate_data(contestant_pk, from_time: Optional[datetime.datetime]):
    contestant = get_object_or_404(Contestant, pk=contestant_pk)  # type: Contestant
    influx = InfluxFacade()
    default_start_time = contestant.contest.start_time - timedelta(minutes=30)
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
            data = [item.decode(encoding="UTF-8") for item in request.FILES['file'].readlines()]
            create_track_from_csv(name, data[1:])
            return redirect("/")
    return render(request, "display/import_track_form.html", {"form": form})


def create_track_from_csv(name: str, lines: List[str]) -> Track:
    track_data = []
    for line in lines:
        line = [item.strip() for item in line.split(",")]
        track_data.append({"name": line[0], "longitude": float(line[1]), "latitude": float(line[2]),
                           "type": line[3], "width": float(line[4])})
    return Track.create(name=name, waypoints=track_data)
