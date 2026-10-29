"""REST API of the AI flight summaries (see display/services/flight_summaries.py for the rules)."""

from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework import permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from display.models import Contestant
from display.services import flight_summaries


class FlightSummaryViewSet(ViewSet):
    """
    The AI summary of a flight, addressed by the contestant's id. Only the flight's crew (pilot or co-pilot) and
    superusers see it; anybody else gets a 404, whether or not the flight exists.
    """

    permission_classes = [permissions.IsAuthenticated]

    def _contestant(self, pk) -> Contestant:
        contestant = get_object_or_404(
            Contestant.objects.select_related(
                "team__crew__member1", "team__crew__member2", "navigation_task", "contestanttrack"
            ),
            pk=pk,
        )
        if not flight_summaries.may_view(self.request.user, contestant):
            raise Http404
        return contestant

    def retrieve(self, request, pk=None):
        """The flight's summary, if one has been written for its current scores, and whether the user may ask for one."""
        return Response(flight_summaries.summary_state(request.user, self._contestant(pk)))

    @action(detail=True, methods=["post"])
    def generate(self, request, pk=None):
        """
        Asks for the flight's summary. It is written in the background: poll the summary until ``status`` is ``done``
        or ``failed``. Asking again for a summary that exists is free; ``regenerate`` (superusers only) writes it anew.
        """
        contestant = self._contestant(pk)
        regenerate = str(request.data.get("regenerate", "")).lower() in {"1", "true", "yes"}
        try:
            flight_summaries.request_summary(request.user, contestant, regenerate=regenerate)
        except flight_summaries.FlightSummaryRefused as e:
            return Response({"detail": str(e)}, status=e.status_code)
        return Response(flight_summaries.summary_state(request.user, contestant), status=202)
