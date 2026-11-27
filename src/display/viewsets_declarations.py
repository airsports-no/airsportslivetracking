"""
The declaration of a flight (the turn point times, the sequence, the period T ...) read and changed by the flight's own
pilot until take-off, and by organisers at any time. The rules are in display/services/declaration_access.py.
"""

from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from display.models import Contestant
from display.services.contestant_task_compiler import ContestantTaskCompiler
from display.services.declaration_access import (
    ROLE_PILOT,
    declaration_role,
    declaration_status,
    pilot_edit_refusal,
)
from display.services.self_registration import send_flight_order_after_declaration, stored_declaration
from display.utilities.task_types import DECLARATION_NOT_NEEDED, stored_task_type


class ContestantDeclarationViewSet(ViewSet):
    """
    ``/api/v1/declarations/<contestant id>/``. GET returns the declaration, its status and the points to declare; PUT
    and PATCH replace it with ``{"declaration_payload": {...}}``, the same payload the organiser's page sends (times as
    timestamps, or as seconds after the start point with ``"time_reference": "start_point"``). Anybody who is neither the
    flight's crew nor an organiser of the contest gets a 404, whether or not the flight exists.
    """

    permission_classes = [permissions.IsAuthenticated]

    def _contestant(self, pk) -> tuple[Contestant, str]:
        contestant = get_object_or_404(
            Contestant.objects.select_related(
                "team__crew__member1",
                "team__crew__member2",
                "navigation_task__contest",
                "contestanttrack",
                "contestanttaskconfiguration",
            ),
            pk=pk,
        )
        role = declaration_role(self.request.user, contestant)
        if role is None:
            raise Http404
        return contestant, role

    def _response(self, contestant: Contestant, role: str) -> Response:
        task_type = stored_task_type(contestant.navigation_task)
        config = getattr(contestant, "contestanttaskconfiguration", None)
        form: dict = {}
        if task_type.declaration_need != DECLARATION_NOT_NEEDED:
            form = {
                **ContestantTaskCompiler(contestant).declaration_form(),
                "declares_times": bool(task_type.absolute_time_declaration_key),
                "time_key": task_type.absolute_time_declaration_key,
                "adaptive_start": contestant.adaptive_start,
                # With an adaptive start the clock time of the start is not known before it is flown
                "start_point_time": (None if contestant.adaptive_start else contestant.gate_time_anchor().isoformat()),
            }
        return Response(
            {
                "contestant_id": contestant.pk,
                "task_type": task_type.key,
                "status": declaration_status(contestant, self.request.user),
                "declaration_payload": (config.declaration_payload or {}) if config else {},
                "form": form,
            }
        )

    def retrieve(self, request, pk=None):
        contestant, role = self._contestant(pk)
        return self._response(contestant, role)

    def update(self, request, pk=None):
        contestant, role = self._contestant(pk)
        if stored_task_type(contestant.navigation_task).declaration_need == DECLARATION_NOT_NEEDED:
            raise ValidationError({"detail": "This task has no declaration."})
        if role == ROLE_PILOT:
            refusal = pilot_edit_refusal(contestant)
            if refusal:
                raise PermissionDenied(refusal)
        declaration_input = request.data.get("declaration_payload") if hasattr(request.data, "get") else None
        if not isinstance(declaration_input, dict):
            raise ValidationError({"declaration_payload": 'Send the declaration as {"declaration_payload": {...}}.'})
        previous = stored_declaration(contestant)
        compiler = ContestantTaskCompiler(contestant)
        with transaction.atomic():
            payload = compiler.build_declaration_payload_from_input(declaration_input)
            contestant.contestanttaskconfiguration = compiler.compile(declaration_payload=payload, force=True)
        send_flight_order_after_declaration(contestant, previous)
        return self._response(contestant, role)

    partial_update = update
