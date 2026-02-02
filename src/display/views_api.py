from django.core.cache import cache
from django.http import Http404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
import logging
from guardian.decorators import permission_required as guardian_permission_required
from display.tasks import (
    generate_and_maybe_notify_flight_order,
    notify_flight_order,
)

from display.models import Aeroplane, Club, Person, Contest, NavigationTask, Contestant
from display.permissions import ContestPermissionsWithoutObjects
from display.serialisers import (
    AeroplaneSerialiser,
    ClubSerialiser,
    PersonSerialiserExcludingTracking,
    PersonSignUpSerialiser,
    ContestantSerialiser,
)
from display.utilities.calculator_running_utilities import is_calculator_running
from display.views import get_navigation_task_orders_status_object

logger = logging.getLogger(__name__)


@api_view(["POST"])
def get_country_from_location(request):
    latitude = float(request.data.get("latitude"))
    longitude = float(request.data.get("longitude"))
    return Response(get_country_from_location(latitude, longitude))


@api_view(["POST"])
@permission_classes([IsAuthenticated, ContestPermissionsWithoutObjects])
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


@api_view(["POST"])
@permission_classes([IsAuthenticated, ContestPermissionsWithoutObjects])
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


@api_view(["POST"])
@permission_classes([IsAuthenticated, ContestPermissionsWithoutObjects])
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


@api_view(["POST"])
@permission_classes([IsAuthenticated, ContestPermissionsWithoutObjects])
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


@api_view(["POST"])
@permission_classes([IsAuthenticated, ContestPermissionsWithoutObjects])
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


@api_view(["POST"])
@permission_classes([IsAuthenticated, ContestPermissionsWithoutObjects])
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


@api_view(["POST"])
@permission_classes([IsAuthenticated, ContestPermissionsWithoutObjects])
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


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_persons_for_signup(request):
    return Response(PersonSignUpSerialiser(Person.objects.exclude(email=request.user.email), many=True).data)


@api_view(["GET"])
@guardian_permission_required("display.view_contest", (Contest, "navigationtask__pk", "pk"))
def clear_flight_order_generation_cache(request, pk):
    navigation_task = get_object_or_404(NavigationTask, pk=pk)
    cache.delete(f"generate_failed_flight_orders_map_{navigation_task.pk}")
    cache.delete(f"completed_flight_orders_map_{navigation_task.pk}")
    return Response({})


@api_view(["GET"])
@guardian_permission_required("display.view_contest", (Contest, "navigationtask__pk", "pk"))
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


@api_view(["GET"])
@guardian_permission_required("display.view_contest", (Contest, "navigationtask__pk", "pk"))
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


@api_view(["GET"])
@guardian_permission_required("display.view_contest", (Contest, "navigationtask__pk", "pk"))
def get_broadcast_navigation_task_orders_status(request, pk):
    return Response(get_navigation_task_orders_status_object(pk))


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
        status_list.append([contestant.pk, is_calculator_running(contestant.pk)])
    return Response(status_list)


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


@api_view(["GET", "PUT"])
@permission_classes([IsAuthenticated])
def contestant_declaration_api(request, pk):
    contestant = get_object_or_404(Contestant, pk=pk)

    has_perm = request.user.has_perm("display.change_contest", contestant.navigation_task.contest)
    if not has_perm:
        if contestant.team.crew.member1.email == request.user.email:
            has_perm = True
        elif contestant.team.crew.member2 and contestant.team.crew.member2.email == request.user.email:
            has_perm = True

    if not has_perm:
        return Response({"error": "Permission denied"}, status=403)

    if request.method == "GET":
        return Response(ContestantSerialiser(contestant).data)

    elif request.method == "PUT":
        declared_config = request.data.get("declared_configuration")
        if declared_config is not None:
            contestant.declared_configuration = declared_config

            # CIMA: Handle per-contestant route reconstruction (Task 2.A3)
            order = declared_config.get("waypoint_order", [])
            if order:
                logger.info(f"ordering waypoints for contestant {contestant}: {order}")
                from display.utilities.route_building_utilities import (
                    create_precision_route_from_waypoint_list,
                    create_anr_corridor_route_from_waypoint_list,
                )
                from display.utilities.navigation_task_type_definitions import (
                    PRECISION,
                    POKER,
                    ANR_CORRIDOR,
                    AIRSPORTS,
                    AIRSPORT_CHALLENGE,
                )

                task_route = contestant.navigation_task.route
                all_available = {
                    wp.name: wp for wp in list(task_route.waypoints) + list(task_route.standalone_waypoints)
                }
                logger.info(f"All available waypoints: {list(all_available.keys())}")
                reordered_waypoints = [all_available[name] for name in order if name in all_available]
                logger.info(f"Reordered waypoints: {[i.name for i in reordered_waypoints]}")
                # Delete existing override if any
                if contestant.custom_route:
                    old_route = contestant.custom_route
                    contestant.custom_route = None
                    contestant.save()
                    old_route.delete()

                # Create correctly initialized route based on task type
                calc_type = contestant.navigation_task.scorecard.calculator
                new_route = None
                if calc_type in (PRECISION, POKER):
                    logger.info(f"Creating new route for contestant {contestant} with calculator type {calc_type}")
                    new_route = create_precision_route_from_waypoint_list(
                        f"{contestant.navigation_task.name} - #{contestant.contestant_number}",
                        reordered_waypoints,
                        task_route.use_procedure_turns,
                        contestant.navigation_task.scorecard,
                    )
                elif calc_type in (ANR_CORRIDOR, AIRSPORTS, AIRSPORT_CHALLENGE):
                    logger.info(f"Creating new route for contestant {contestant} with calculator type {calc_type}")
                    new_route = create_anr_corridor_route_from_waypoint_list(
                        f"{contestant.navigation_task.name} - #{contestant.contestant_number}",
                        reordered_waypoints,
                        task_route.rounded_corners,
                        contestant.navigation_task.scorecard,
                        corridor_width=task_route.corridor_width,
                    )

                if new_route:
                    # Preserve standalone waypoints for CIMA features visualization
                    new_route.standalone_waypoints = task_route.standalone_waypoints
                    new_route.save()
                    contestant.custom_route = new_route
                    logger.info(
                        f"Set new custom route for contestant {contestant}: {[i.name for i in new_route.waypoints]}"
                    )

            # Trigger gate time recalculation by resetting cached times
            contestant.predefined_gate_times = None
            contestant.save()
            return Response({"status": "success"})
        return Response({"error": "No configuration provided"}, status=400)
