"""REST API of the AI flight summaries (see display/services/flight_summaries.py for the rules)."""

from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework import permissions
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from display.models import Contestant, NavigationTask
from display.permissions import IsSuperUser
from display.services import flight_summaries
from display.services.contest_visibility import can_view_navigation_task


class FlightSummaryViewSet(ViewSet):
    """
    The AI summary of a flight, addressed by the contestant's id. Anybody who may open the flight's navigation task
    reads it (anybody else gets a 404, whether or not the flight exists); only superusers have one written.
    """

    def get_permissions(self):
        if self.action == "generate":
            return [permissions.IsAuthenticated(), IsSuperUser()]
        return [permissions.AllowAny()]

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

    @action(detail=False, methods=["get"])
    def available(self, request):
        """
        Which flights of ``?navigation_task=`` have a summary to read (``contestant_ids``), and ``all`` when the user is a
        superuser, who may have any of them written. ``enabled`` is false when no summary can be written.
        """
        try:
            navigation_task_id = int(request.query_params.get("navigation_task", ""))
        except ValueError:
            raise ValidationError({"navigation_task": "Must be a navigation task id."})
        navigation_task = get_object_or_404(NavigationTask.objects.select_related("contest"), pk=navigation_task_id)
        if not request.user.is_superuser and not can_view_navigation_task(request.user, navigation_task):
            raise Http404
        return Response(
            {
                "enabled": flight_summaries.is_enabled(),
                "all": flight_summaries.may_generate(request.user),
                "contestant_ids": flight_summaries.summarised_contestant_ids(navigation_task_id),
            }
        )

    def _style(self, value, default: str | None = flight_summaries.DEFAULT_STYLE) -> str | None:
        if value in (None, ""):
            return default
        if value not in flight_summaries.STYLES:
            raise ValidationError({"style": f"Must be one of {sorted(flight_summaries.STYLES)}."})
        return value

    def retrieve(self, request, pk=None):
        """
        The newest summary written of the flight's current scores, in ``?style=`` if given (see the ``styles`` it lists
        for superusers), and whether the user may ask for one.
        """
        style = self._style(request.query_params.get("style"), default=None)
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
