"""REST API of the AI flight summaries (see display/services/flight_summaries.py for the rules)."""

from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework import permissions
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
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
                "team__crew__member1", "team__crew__member2", "navigation_task__contest", "contestanttrack"
            ),
            pk=pk,
        )
        if not flight_summaries.may_view(self.request.user, contestant):
            raise Http404
        return contestant

    def _style(self, value) -> str:
        if value in (None, ""):
            return flight_summaries.DEFAULT_STYLE
        if value not in flight_summaries.STYLES:
            raise ValidationError({"style": f"Must be one of {sorted(flight_summaries.STYLES)}."})
        return value

    def retrieve(self, request, pk=None):
        """
        The flight's summary in ``?style=`` (see the ``styles`` it lists), if one has been written for its current
        scores, and whether the user may ask for one.
        """
        style = self._style(request.query_params.get("style"))
        return Response(flight_summaries.summary_state(request.user, self._contestant(pk), style))

    @action(detail=True, methods=["post"])
    def generate(self, request, pk=None):
        """
        Asks for the flight's summary. It is written in the background: poll the summary until ``status`` is ``done``
        or ``failed``. Asking again for a summary that exists is free; ``regenerate`` (superusers only) writes it anew.
        ``style`` picks the voice; each style is a summary of its own.
        """
        contestant = self._contestant(pk)
        style = self._style(request.data.get("style"))
        regenerate = str(request.data.get("regenerate", "")).lower() in {"1", "true", "yes"}
        try:
            flight_summaries.request_summary(request.user, contestant, regenerate=regenerate, style=style)
        except flight_summaries.FlightSummaryRefused as e:
            return Response({"detail": str(e)}, status=e.status_code)
        return Response(flight_summaries.summary_state(request.user, contestant, style), status=202)
