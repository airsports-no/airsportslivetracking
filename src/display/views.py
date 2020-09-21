from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.views.generic import View, TemplateView, ListView
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
import logging
import urllib.request
import os

from rest_framework.generics import RetrieveAPIView

from display.forms import ImportTrackForm
from display.models import Contest, Track
from display.serialisers import ContestSerialiser


def frontend_view(request, pk):
    return render(request, "display/root.html", {"contest_id": pk, "live_mode": "true"})


def frontend_view_offline(request, pk):
    return render(request, "display/root.html", {"contest_id": pk, "live_mode": "false"})


class RetrieveContestApi(RetrieveAPIView):
    serializer_class = ContestSerialiser
    queryset = Contest.objects.all()
    lookup_field = "pk"


class ContestList(ListView):
    model = Contest


def import_track(request):
    form = ImportTrackForm()
    if request.method == "POST":
        form = ImportTrackForm(request.POST, request.FILES)
        if form.is_valid():
            name = form.cleaned_data["name"]
            data = request.FILES['file'].readlines()
            track_data = []
            for line in data[1:]:
                line = [item.strip() for item in line.decode(encoding="UTF-8").split(",")]
                track_data.append({"name": line[0], "longitude": float(line[1]), "latitude": float(line[2]),
                                   "type": line[3], "width": float(line[4])})
            Track.create(name=name, waypoints=track_data)
            return redirect("/")
    return render(request, "display/import_track_form.html", {"form": form})
