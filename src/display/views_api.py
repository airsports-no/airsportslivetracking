from django.core.cache import cache
from django.http import Http404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, inline_serializer, OpenApiTypes
from rest_framework import serializers

from guardian.decorators import permission_required as guardian_permission_required
from display.tasks import (
    generate_and_maybe_notify_flight_order,
    notify_flight_order,
)

from display.models import Aeroplane, Club, Person, Contest, NavigationTask
from display.serialisers import (
    AeroplaneSerialiser,
    ClubSerialiser,
    PersonSerialiserExcludingTracking,
    PersonSignUpSerialiser,
)
from display.utilities.calculator_running_utilities import is_calculator_running, is_dispatch_pending
from display.utilities.country_code_utilities import get_country_code_from_location
from display.views import get_navigation_task_orders_status_object


_LocationRequestSerialiser = inline_serializer(
    "LocationRequest",
    {
        "latitude": serializers.FloatField(),
        "longitude": serializers.FloatField(),
    },
)

# Shared request shape for the auto_complete_* endpoints below: `request` selects between
# a search-suggestions pass (1) and a full-match lookup (anything else), `search` is the query.
_AutoCompleteRequestSerialiser = inline_serializer(
    "AutoCompleteRequest",
    {
        "request": serializers.IntegerField(),
        "search": serializers.CharField(required=False, allow_blank=True),
    },
)


@extend_schema(request=_LocationRequestSerialiser, responses={200: OpenApiTypes.STR})
@api_view(["POST"])
def get_country_from_location(request):
    latitude = float(request.data.get("latitude"))
    longitude = float(request.data.get("longitude"))
    return Response(get_country_code_from_location(latitude, longitude))


@extend_schema(request=_AutoCompleteRequestSerialiser, responses={200: OpenApiTypes.ANY})
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def auto_complete_aeroplane(request):
    request_number = int(request.data.get("request"))
    if request_number == 1:
        q = request.data.get("search", "")
        search_qs = Aeroplane.objects.filter(registration__icontains=q)
        result = [str(item.registration) for item in search_qs]
        return Response(result)
    else:
        q = request.data.get("search", "")
        search_qs = Aeroplane.objects.filter(registration=q)
        serialiser = AeroplaneSerialiser(search_qs, many=True)
        return Response(serialiser.data)


@extend_schema(request=_AutoCompleteRequestSerialiser, responses={200: OpenApiTypes.ANY})
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def auto_complete_club(request):
    request_number = int(request.data.get("request"))
    if request_number == 1:
        q = request.data.get("search", "")
        search_qs = Club.objects.filter(name__icontains=q)
        result = [{"label": "{} ({})".format(item.name, item.country), "value": item.name} for item in search_qs]
        return Response(result)
    else:
        q = request.data.get("search", "")
        search_qs = Club.objects.filter(name=q)
        serialiser = ClubSerialiser(search_qs, many=True)
        return Response(serialiser.data)


@extend_schema(request=_AutoCompleteRequestSerialiser, responses={200: OpenApiTypes.ANY})
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def auto_complete_person_phone(request):
    request_number = int(request.data.get("request"))
    if request_number == 1:
        q = request.data.get("search", "")
        search_qs = Person.objects.filter(phone__contains=q)
        result = [str(item.phone) for item in search_qs]
        return Response(result)
    else:
        q = request.data.get("search", "")
        search_qs = Person.objects.filter(phone=q)
        serialiser = PersonSerialiserExcludingTracking(search_qs, many=True)
        return Response(serialiser.data)


@extend_schema(request=_AutoCompleteRequestSerialiser, responses={200: OpenApiTypes.ANY})
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def auto_complete_person_id(request):
    request_number = int(request.data.get("request"))
    if request_number == 1:
        q = request.data.get("search", "")
        search_qs = Person.objects.filter(pk=q)
        result = [str(item.phone) for item in search_qs]
        return Response(result)
    else:
        q = request.data.get("search", "")
        search_qs = Person.objects.filter(pk=q)
        serialiser = PersonSerialiserExcludingTracking(search_qs, many=True)
        return Response(serialiser.data)


@extend_schema(request=_AutoCompleteRequestSerialiser, responses={200: OpenApiTypes.ANY})
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def auto_complete_person_first_name(request):
    request_number = int(request.data.get("request"))
    if request_number == 1:
        q = request.data.get("search", "")
        search_qs = Person.objects.filter(first_name__icontains=q)
        result = [
            {
                "label": "{} {}".format(item.first_name, item.last_name),
                "value": item.pk,
            }
            for item in search_qs
        ]
        return Response(result)
    else:
        q = request.data.get("search", "")
        search_qs = Person.objects.filter(pk=q)
        serialiser = PersonSerialiserExcludingTracking(search_qs, many=True)
        return Response(serialiser.data)


@extend_schema(request=_AutoCompleteRequestSerialiser, responses={200: OpenApiTypes.ANY})
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def auto_complete_person_last_name(request):
    request_number = int(request.data.get("request"))
    if request_number == 1:
        q = request.data.get("search", "")
        search_qs = Person.objects.filter(last_name__icontains=q)
        result = [
            {
                "label": "{} {}".format(item.first_name, item.last_name),
                "value": item.pk,
            }
            for item in search_qs
        ]
        return Response(result)
    else:
        q = request.data.get("search", "")
        search_qs = Person.objects.filter(pk=q)
        serialiser = PersonSerialiserExcludingTracking(search_qs, many=True)
        return Response(serialiser.data)


@extend_schema(request=_AutoCompleteRequestSerialiser, responses={200: OpenApiTypes.ANY})
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def auto_complete_person_email(request):
    request_number = int(request.data.get("request"))
    if request_number == 1:
        q = request.data.get("search", "")
        search_qs = Person.objects.filter(email__icontains=q)
        result = [item.email for item in search_qs]
        return Response(result)
    else:
        q = request.data.get("search", "")
        search_qs = Person.objects.filter(email=q)
        serialiser = PersonSerialiserExcludingTracking(search_qs, many=True)
        return Response(serialiser.data)


@extend_schema(responses={200: OpenApiTypes.ANY})
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_persons_for_signup(request):
    # Filter for persons with valid-ish emails to prevent empty results or crashes
    persons = Person.objects.exclude(email=request.user.email).filter(email__contains="@")
    return Response(PersonSignUpSerialiser(persons, many=True).data)


@extend_schema(responses={200: OpenApiTypes.ANY})
@api_view(["GET"])
@guardian_permission_required("display.view_contest", (Contest, "navigationtask__pk", "pk"))
def clear_flight_order_generation_cache(request, pk):
    navigation_task = get_object_or_404(NavigationTask, pk=pk)
    cache.delete(f"generate_failed_flight_orders_map_{navigation_task.pk}")
    cache.delete(f"completed_flight_orders_map_{navigation_task.pk}")
    return Response({})


@extend_schema(responses={200: OpenApiTypes.ANY})
@api_view(["GET"])
# change_contest, not view_contest: this deletes every selected contestant's existing
# flight-order links and (re-)triggers generation/email - a read-only collaborator
# should not be able to invalidate distributed links for the whole start list.
@guardian_permission_required("display.change_contest", (Contest, "navigationtask__pk", "pk"))
def generate_navigation_task_orders(request, pk):
    navigation_task = get_object_or_404(NavigationTask, pk=pk)
    contestant_pks = request.GET.get("contestant_pks")
    if not contestant_pks or len(contestant_pks) == 0:
        raise Http404
    contestant_pks = contestant_pks.split(",")
    contestants = navigation_task.contestant_set.filter(pk__in=contestant_pks)
    cache.set(
        f"completed_flight_orders_map_{navigation_task.pk}",
        {contestant.pk: False for contestant in contestants},
    )
    cache.set(f"generate_failed_flight_orders_map_{navigation_task.pk}", {})
    cache.delete(f"transmitted_flight_orders_map_{navigation_task.pk}")
    cache.delete(f"transmit_failed_flight_orders_map_{navigation_task.pk}")
    for contestant in contestants:
        # Delete existing order
        contestant.emailmaplink_set.all().delete()
        generate_and_maybe_notify_flight_order.apply_async(
            (
                contestant.pk,
                contestant.team.crew.member1.email,
                contestant.team.crew.member1.first_name,
                False,
            )
        )
    return Response(get_navigation_task_orders_status_object(pk))


@extend_schema(responses={200: OpenApiTypes.ANY})
@api_view(["GET"])
# change_contest, not view_contest: this mail-bombs every selected contestant's
# member1.email - a read-only collaborator should not be able to trigger that.
@guardian_permission_required("display.change_contest", (Contest, "navigationtask__pk", "pk"))
def broadcast_navigation_task_orders(request, pk):
    navigation_task = get_object_or_404(NavigationTask, pk=pk)
    contestant_pks = request.GET.get("contestant_pks")
    if not contestant_pks or len(contestant_pks) == 0:
        raise Http404
    contestant_pks = contestant_pks.split(",")
    contestants = navigation_task.contestant_set.filter(pk__in=contestant_pks)
    cache.set(
        f"transmitted_flight_orders_map_{navigation_task.pk}",
        {contestant.pk: False for contestant in contestants},
    )

    for contestant in contestants:
        notify_flight_order.apply_async(
            (
                contestant.pk,
                contestant.team.crew.member1.email,
                contestant.team.crew.member1.first_name,
            )
        )
    return Response(get_navigation_task_orders_status_object(pk))


@extend_schema(responses={200: OpenApiTypes.ANY})
@api_view(["GET"])
@guardian_permission_required("display.view_contest", (Contest, "navigationtask__pk", "pk"))
def get_broadcast_navigation_task_orders_status(request, pk):
    return Response(get_navigation_task_orders_status_object(pk))


@extend_schema(responses={200: OpenApiTypes.ANY})
@api_view(["GET"])
@guardian_permission_required("display.view_contest", (Contest, "navigationtask__pk", "pk"))
def get_running_calculators(request, pk):
    """
    Returns a list of (contestant_id, boolean) tuples where the boolean indicates whether a calculator is currently
    running for the contestant.
    """
    navigation_task = get_object_or_404(NavigationTask, pk=pk)
    status_list = []
    for contestant in navigation_task.contestant_set.all():
        # A calculator just dispatched to Celery may not have posted its own
        # heartbeat yet (see calculator_running_utilities.py) - OR both keys
        # so the UI still shows "running" during that spin-up window, as it
        # did before the dispatch/heartbeat keys were split.
        running = is_calculator_running(contestant.pk) or is_dispatch_pending(contestant.pk)
        status_list.append([contestant.pk, running])
    return Response(status_list)


@extend_schema(responses={200: OpenApiTypes.ANY})
@api_view(["GET"])
@guardian_permission_required("display.view_contest", (Contest, "navigationtask__pk", "pk"))
def get_contestant_schedule(request, pk):
    navigation_task = get_object_or_404(NavigationTask, pk=pk)
    columns = [
        {"id": "Aircraft", "type": "string"},
        {"id": "Contestant", "type": "string"},
        {"id": "Takeoff", "type": "date"},
        {"id": "Landing", "type": "date"},
    ]
    rows = []
    for contestant in navigation_task.contestant_set.all():
        rows.append(
            {
                "c": [
                    {"v": contestant.team.aeroplane.registration},
                    {"v": f"{contestant}{' (Adaptive)' if contestant.adaptive_start else ''}"},
                    {"v": contestant.takeoff_time if not contestant.adaptive_start else contestant.tracker_start_time},
                    {"v": contestant.landing_time if not contestant.adaptive_start else contestant.finished_by_time},
                ]
            }
        )

    return Response({"cols": columns, "rows": rows})
