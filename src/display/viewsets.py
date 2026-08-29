import base64
import csv
import datetime
import hashlib
import json
import logging
from collections import OrderedDict
from urllib import parse

import dateutil.parser
import redis
import rest_framework.exceptions as drf_exceptions
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.files.base import ContentFile
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.db.models import Count, Prefetch, Q
from django.http import Http404, HttpResponse, StreamingHttpResponse
from django.utils import timezone
from django.utils.cache import add_never_cache_headers, patch_response_headers
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view, inline_serializer
from guardian.models import UserObjectPermission
from guardian.shortcuts import get_objects_for_user
from rest_framework import permissions, serializers, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.generics import get_object_or_404
from rest_framework.pagination import CursorPagination
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet, ModelViewSet, ReadOnlyModelViewSet

from display.contestant_scheduling.schedule_contestants import schedule_and_create_contestants
from display.filters import ContestFilter, NavigationTaskFilter
from display.flight_order_and_maps.map_plotter_shared_utilities import (
    get_builtin_map_source_definitions,
    map_source_definition_to_payload,
    source_definition_from_user_uploaded_map,
)
from display.models import (
    ANOMALY,
    Aeroplane,
    Club,
    ClubManagerMembership,
    Contest,
    Contestant,
    ContestSummary,
    ContestTeam,
    EditableRoute,
    HighlightedContest,
    MyUser,
    NavigationTask,
    NewsletterSubscriber,
    Person,
    Photo,
    Route,
    Scorecard,
    Task,
    TaskSummary,
    TaskTest,
    Team,
    TeamTestScore,
    UserUploadedMap,
)
from display.permissions import (
    ContestantNavigationTaskContestPermissions,
    ContestantPublicPermissions,
    ContestModificationPermissions,
    ContestPermissions,
    ContestPublicModificationPermissions,
    ContestPublicPermissions,
    ContestTeamContestPermissions,
    EditableRoutePermission,
    NavigationTaskContestPermissions,
    NavigationTaskPublicPermissions,
    NavigationTaskPublicPutDeletePermissions,
    NavigationTaskSelfManagementPermissions,
    OrganiserPermission,
    PhotoPermissions,
    RoutePermissions,
    TaskContestPermissions,
    TaskContestPublicPermissions,
    TaskTestContestPermissions,
    TaskTestContestPublicPermissions,
    TeamPermissions,
)
from display.serialisers import (
    AeroplaneSerialiser,
    ClubManagerMembershipCreateSerializer,
    ClubManagerMembershipSerializer,
    ClubSerialiser,
    ContestantNestedTeamSerialiser,
    ContestantNestedTeamSerialiserWithContestantTrack,
    ContestantSerialiser,
    ContestantTickerSerialiser,
    ContestantTrackSerialiser,
    ContestantTrackWithTrackPointsSerialiser,
    ContestResultsDetailsSerialiser,
    ContestSerialiser,
    ContestSummaryWithoutReferenceSerialiser,
    ContestTeamManagementSerialiser,
    ContestTeamNestedSerialiser,
    ContestTeamSerialiser,
    EditableRouteLightSerialiser,
    EditableRouteSerialiser,
    ExternalNavigationTaskNestedTeamSerialiser,
    ExternalNavigationTaskTeamIdSerialiser,
    FutureContestantNestedTeamSerialiser,
    GateCumulativeScoreSerialiser,
    GpxTrackSerialiser,
    HighlightedContestSerialiser,
    NavigationTaskEditableRoutReferenceSerialiser,
    NavigationTaskNestedTeamRouteSerialiser,
    NavigationTaskNestedTeamRouteSerialiserNestedContest,
    NavigationTasksSummarySerialiser,
    NewsletterSubscriberSerialiser,
    OngoingNavigationSerialiser,
    PersonSerialiser,
    PhotoPublicSerialiser,
    PhotoSerialiser,
    PlayingCardSerialiser,
    PositionSerialiser,
    RouteSerialiser,
    ScorecardNestedSerialiser,
    ScoreLogEntrySerialiser,
    SelfManagementSerialiser,
    SharingSerialiser,
    SignupSerialiser,
    TaskSerialiser,
    TaskSummaryWithoutReferenceSerialiser,
    TaskTestSerialiser,
    TeamNestedSerialiser,
    TeamTestScoreWithoutReferenceSerialiser,
    TodaysNavigationSerialiser,
    TrackAnnotationSerialiser,
)
from display.services.access_resolver import resolve_contest_access
from display.services.capacity_enforcement import (
    _assert_can_reserve_task_slot,
    assert_can_register_team,
    assert_can_self_register_contestant,
    scheduling_capacity_preview,
)
from display.services.contestant_task_compiler import ContestantTaskCompiler
from display.services.photo_management import revert_photo_to_satellite, sync_navigation_task_photo_targets
from display.services.route_compatibility import extract_route_primitives, get_blocking_reasons
from display.services.task_compiler import TaskCompiler
from display.services.token_assignment import assign_token_to_contest, replace_token_for_contest
from display.tasks import (
    generate_and_maybe_notify_flight_order,
    generate_editable_route_thumbnail,
    import_gpx_track,
)
from display.utilities.cima_task_type_definitions import TASK_SUBTYPE_DEFINITIONS
from display.utilities.show_slug_choices import ShowChoicesMetadata
from display.utilities.tracking_definitions import TrackingService
from live_tracking_map import settings
from websocket_channels import WebsocketFacade, generate_contestant_data_block

logger = logging.getLogger(__name__)


class AssignContestTokenSerializer(serializers.Serializer):
    token_grant_id = serializers.IntegerField()


def _normalize_contest_team_ids(values):
    if values in (None, "", []):
        return []

    iterable = values.split(",") if isinstance(values, str) else values
    normalized_ids = []
    for item in iterable:
        if item in (None, ""):
            continue
        try:
            normalized_ids.append(int(item))
        except (TypeError, ValueError):
            raise ValidationError("contest_teams must be a comma-separated list of integer ContestTeam IDs.")

    return list(OrderedDict.fromkeys(normalized_ids))


class ScheduleCapacityPreviewQuerySerializer(serializers.Serializer):
    contest_teams = serializers.CharField(required=False, allow_blank=True, default="")
    first_takeoff_time = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def validate_contest_teams(self, value):
        return _normalize_contest_team_ids(value)

    def validate_first_takeoff_time(self, value):
        if value in (None, ""):
            return None
        try:
            return dateutil.parser.parse(value)
        except (TypeError, ValueError, dateutil.parser.ParserError) as exc:
            raise ValidationError(str(exc))


class UserPersonViewSet(GenericViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_classes = {
        "get_current_app_navigation_task": NavigationTasksSummarySerialiser,
        "get_current_sim_navigation_task": NavigationTasksSummarySerialiser,
        "my_contests": ContestTeamManagementSerialiser,
    }
    default_serialiser_class = PersonSerialiser

    def get_serializer_class(self):
        return self.serializer_classes.get(self.action, self.default_serialiser_class)

    def get_object(self):
        instance = self.get_queryset()
        if instance is None:
            raise Http404
        return instance

    def get_queryset(self):
        return Person.objects.get_or_create(
            email=self.request.user.email,
            defaults={
                "first_name": (
                    self.request.user.first_name
                    if self.request.user.first_name and len(self.request.user.first_name) > 0
                    else ""
                ),
                "last_name": (
                    self.request.user.last_name
                    if self.request.user.last_name and len(self.request.user.last_name) > 0
                    else ""
                ),
                "validated": False,
            },
        )[0]

    # def create(self, request, *args, **kwargs):
    #     if request.user.person is not None:
    #         raise ValidationError("The user already has a profile")
    #     return super().create(request, *args, **kwargs)
    #
    # def perform_create(self, serializer):
    #     person = serializer.save()
    #     self.request.user.person = person
    #     self.request.user.save()
    #     return person

    def perform_update(self, serializer):
        serializer.save()

    @action(detail=False, methods=["get"])
    def my_contest_teams(self, request, *args, **kwargs):
        # for authorisation
        person = self.get_object()
        contest_teams = ContestTeam.objects.filter(
            Q(team__crew__member1=person) | Q(team__crew__member2=person),
        )
        return Response(ContestTeamSerialiser(contest_teams, many=True, context={"request": request}).data)

    @action(detail=False, methods=["get"])
    def my_future_flights(self, request, *args, **kwargs):
        available_contests = Contest.visible_contests_for_user(request.user)
        # for authorisation
        person = self.get_object()
        contestants = (
            Contestant.objects.filter(
                Q(team__crew__member1=person) | Q(team__crew__member2=person),
                navigation_task__contest__in=available_contests,
                finished_by_time__gt=datetime.datetime.now(datetime.timezone.utc),
            )
            .order_by("takeoff_time")
            .distinct()
            .prefetch_related("emailmaplink_set")
        )
        return Response(FutureContestantNestedTeamSerialiser(contestants, many=True, context={"request": request}).data)

    @action(detail=False, methods=["get"])
    def my_previous_flights(self, request, *args, **kwargs):
        available_contests = Contest.visible_contests_for_user(request.user).filter()
        # for authorisation
        person = self.get_object()

        contestants = (
            Contestant.objects.filter(
                Q(team__crew__member1=person) | Q(team__crew__member2=person),
                navigation_task__contest__in=available_contests,
                finished_by_time__lt=datetime.datetime.now(datetime.timezone.utc),
            )
            .select_related("navigation_task__contest")
            .prefetch_related(
                "team__aeroplane",
                "team__club",
                "team__crew__member1",
                "team__crew__member2",
                "team__contestsummary_set",
                "contestanttrack",
            )
            .order_by("navigation_task__contest__start_time")
            .distinct()
        )
        return Response(
            ContestantNestedTeamSerialiserWithContestantTrack(
                contestants, many=True, context={"request": request, "exclude_overlaps": True}
            ).data
        )

    @action(detail=False, methods=["patch"])
    def partial_update_profile(self, request, *args, **kwargs):
        kwargs["partial"] = True
        logger.info(f"Updating profile for {self.get_object()} with data {request.data}")
        return self.update_profile(request, *args, **kwargs)

    @action(detail=False, methods=["get"])
    def retrieve_profile(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def get_current_sim_navigation_task(self, request, *args, **kwargs):
        person = self.get_object()
        contestants_data = Contestant.get_contestant_for_device_at_time(
            TrackingService.TRACCAR, person.simulator_tracking_id, datetime.datetime.now(datetime.timezone.utc)
        )
        return self._format_navigation_tasks_response(request, contestants_data)

    @action(detail=False, methods=["get"])
    def get_current_app_navigation_task(self, request, *args, **kwargs):
        person = self.get_object()
        contestants_data = Contestant.get_contestant_for_device_at_time(
            TrackingService.TRACCAR, person.app_tracking_id, datetime.datetime.now(datetime.timezone.utc)
        )
        return self._format_navigation_tasks_response(request, contestants_data)

    def _format_navigation_tasks_response(self, request, contestants_data):
        if not contestants_data:
            raise Http404

        tasks_map = {}
        for contestant, _ in contestants_data:
            task = contestant.navigation_task
            if task.pk not in tasks_map:
                tasks_map[task.pk] = {
                    "navigation_task": NavigationTasksSummarySerialiser(
                        task, context={"request": request, "exclude_route": True}
                    ).data,
                    "active_contestants": [],
                }
            tasks_map[task.pk]["active_contestants"].append(
                ContestantSerialiser(contestant, context={"request": request}).data
            )

        return Response(list(tasks_map.values()))

    @action(detail=False, methods=["put", "patch"])
    def update_profile(self, request, *args, **kwargs):
        if self.request.method == "PATCH":
            partial = True
        else:
            partial = False
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        instance.refresh_from_db()
        request.user.first_name = instance.first_name
        request.user.last_name = instance.last_name
        request.user.save()

        if getattr(instance, "_prefetched_objects_cache", None):
            # If 'prefetch_related' has been applied to a queryset, we need to
            # forcibly invalidate the prefetch cache on the instance.
            instance._prefetched_objects_cache = {}

        return Response(serializer.data)


class EditableRouteViewSet(ModelViewSet):
    queryset = EditableRoute.objects.all()
    permission_classes = [EditableRoutePermission]
    serializer_class = EditableRouteSerialiser

    @staticmethod
    def _build_map_sources_for_user(user):
        sources = []
        for definition in get_builtin_map_source_definitions():
            sources.append(map_source_definition_to_payload(definition))

        uploaded_maps = (
            get_objects_for_user(
                user,
                "display.view_useruploadedmap",
                klass=UserUploadedMap,
                accept_global_perms=False,
                with_superuser=False,
            )
            .filter(processing_status=UserUploadedMap.PROCESSING_READY)
            .exclude(published_service_key="")
        )

        for uploaded_map in uploaded_maps:
            sources.append(
                map_source_definition_to_payload(
                    source_definition_from_user_uploaded_map(uploaded_map),
                    origin="user_upload",
                )
            )

        return sources

    def get_serializer_class(self):
        if self.action == "list":
            return EditableRouteLightSerialiser
        return super().get_serializer_class()

    def get_queryset(self):
        queryset = get_objects_for_user(
            self.request.user,
            "display.view_editableroute",
            klass=self.queryset,
            accept_global_perms=False,
        ).order_by("name")

        if self.action == "list":
            # Defer large JSON fields that are not needed for the list view
            return queryset.defer("route", "settings")
        return queryset

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if self.request.user.is_authenticated:
            # Optimize is_editor check
            # For superusers, we use with_superuser=False so they can still distinguish
            # between routes they are explicitly editors of and all other routes.
            editable_route_ids = set(
                get_objects_for_user(
                    self.request.user,
                    "display.change_editableroute",
                    klass=EditableRoute,
                    accept_global_perms=False,
                    with_superuser=False,
                ).values_list("id", flat=True)
            )
            context["editable_route_ids"] = editable_route_ids

            # Optimize editors list (Bulk fetch UserObjectPermission)
            # Only do this for list action to avoid unnecessary overhead in other actions
            if self.action == "list":
                try:
                    queryset = self.get_queryset()
                    route_ids = [obj.id for obj in queryset]
                    ct = ContentType.objects.get_for_model(EditableRoute)

                    user_perms = UserObjectPermission.objects.filter(
                        content_type=ct,
                        object_pk__in=[str(rid) for rid in route_ids],
                        permission__codename="change_editableroute",
                    ).select_related("user")

                    editors_map = {}
                    for up in user_perms:
                        rid = int(up.object_pk)
                        if rid not in editors_map:
                            editors_map[rid] = []
                        editors_map[rid].append(up.user)

                    context["editors_map"] = editors_map
                except Exception as e:
                    logger.error(f"Failed to bulk fetch editors: {e}")

        return context

    def perform_update(self, serializer):
        super().perform_update(serializer)
        editable_route = serializer.instance
        transaction.on_commit(lambda: generate_editable_route_thumbnail.delay(editable_route.pk))

    def perform_create(self, serializer):
        super().perform_create(serializer)
        editable_route = serializer.instance
        transaction.on_commit(lambda: generate_editable_route_thumbnail.delay(editable_route.pk))

    @action(detail=False, methods=["post"], url_path="task_compatibility")
    def task_compatibility(self, request, *args, **kwargs):
        """
        Dry-run compatibility check: given the current (possibly unsaved) route feature
        collection, report which task subtypes it satisfies the requirements of and, for the
        rest, why not. Used by the route editor to give live feedback on the intended-task-types
        picker without persisting anything - display.services.route_compatibility remains the
        single source of truth for the ruleset itself.
        """
        route_payload = request.data.get("route")
        if not isinstance(route_payload, dict):
            raise ValidationError({"route": "This field is required and must be a GeoJSON feature collection object."})
        unsaved_route = EditableRoute(route=route_payload)
        primitives = extract_route_primitives(unsaved_route)
        subtypes = []
        compatible_task_types = []
        for definition in TASK_SUBTYPE_DEFINITIONS.values():
            missing_reasons = get_blocking_reasons(primitives, definition.key)
            if not missing_reasons:
                compatible_task_types.append(definition.key)
            subtypes.append(
                {
                    "key": definition.key,
                    "display_name": definition.display_name,
                    "group": "Legacy" if definition.key.startswith("legacy_") else "CIMA",
                    "coarse_family": definition.coarse_family,
                    "compatible": not missing_reasons,
                    "missing_reasons": missing_reasons,
                }
            )
        return Response({"compatible_task_types": compatible_task_types, "subtypes": subtypes})

    @action(detail=False, methods=["get"], url_path="global-map-sources")
    def global_map_sources(self, request, *args, **kwargs):
        return Response(self._build_map_sources_for_user(request.user))

    @action(detail=True, methods=["get"])
    def map_sources(self, request, *args, **kwargs):
        self.get_object()
        return Response(self._build_map_sources_for_user(request.user))


TRACK_DATA_PAGE_SIZE_MINUTES = 30


class MyCursorPagination(CursorPagination):
    page_size = TRACK_DATA_PAGE_SIZE_MINUTES * 60
    ordering = ["time", "id"]

    def encode_cursor(self, cursor):
        """
        Given a Cursor instance, return an url with encoded cursor.
        """
        tokens = {}
        if cursor.offset != 0:
            tokens["o"] = str(cursor.offset)
        if cursor.reverse:
            tokens["r"] = "1"
        if cursor.position is not None:
            tokens["p"] = cursor.position

        querystring = parse.urlencode(tokens, doseq=True)
        return base64.b64encode(querystring.encode("ascii")).decode("ascii")

    def get_paginated_response(self, data):
        return Response(
            OrderedDict(
                [
                    ("next", self.get_next_link()),
                    ("previous", self.get_previous_link()),
                    ("results", data),
                ]
            )
        )


def get_contest_list_version():
    """
    Retrieve the current version of the contest list.
    If it doesn't exist, initialize it with a timestamp to prevent ETag collisions.

    If Redis itself is unavailable, fall back to a fresh timestamp on every call rather than
    raising and 500ing the request: this just means ETags won't match until Redis recovers (the
    CDN/browser will revalidate every time), which is a strictly better failure mode than an
    outage.
    """
    try:
        version = cache.get("contest_list_version")
        if version is None:
            version = int(timezone.now().timestamp())
            cache.set("contest_list_version", version, timeout=None)
        return version
    except redis.exceptions.RedisError:
        logger.warning("Redis unavailable while fetching contest_list_version, falling back to a fresh version")
        return int(timezone.now().timestamp())


class ContestPagination(MyCursorPagination):
    page_size = 50
    ordering = ["-start_time", "-finish_time", "id"]
    max_page_size = 200


class ContestViewSet(ModelViewSet):
    """
    A contest is a high level wrapper for multiple tasks. It provides a lightweight view of a contest and is used by
    the front end to display the contest list on the global map.
    """

    queryset = Contest.objects.all()
    serializer_classes = {
        "teams": ContestTeamNestedSerialiser,
        "update_contest_summary": ContestSummaryWithoutReferenceSerialiser,
        "update_task_summary": TaskSummaryWithoutReferenceSerialiser,
        "update_test_result": TeamTestScoreWithoutReferenceSerialiser,
        "results_details": ContestResultsDetailsSerialiser,
        "ongoing_navigation": OngoingNavigationSerialiser,
        "signup": SignupSerialiser,
        "share": SharingSerialiser,
    }
    default_serialiser_class = ContestSerialiser
    lookup_url_kwarg = "pk"
    pagination_class = ContestPagination

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        version = get_contest_list_version()

        # ETag based on global version and object ID
        etag = f'"{version}-contest-{instance.pk}"'
        if request.META.get("HTTP_IF_NONE_MATCH") == etag:
            return Response(status=status.HTTP_304_NOT_MODIFIED)

        response = super().retrieve(request, *args, **kwargs)

        response["ETag"] = etag
        if instance.is_public and instance.is_featured and not request.user.is_authenticated:
            # Public anonymous data can be cached by CDN but MUST be revalidated via ETag.
            # stale-while-revalidate=86400: Serve stale data while fetching fresh in background
            response["Cache-Control"] = "public, no-cache, stale-while-revalidate=86400"
            if "Vary" in response:
                del response["Vary"]
        else:
            response["Cache-Control"] = "private, no-cache"
        return response

    permission_classes = [ContestPublicPermissions | (permissions.IsAuthenticated & ContestPermissions)]
    filter_backends = [DjangoFilterBackend]
    filterset_class = ContestFilter

    def list(self, request, *args, **kwargs):
        public_only = request.query_params.get("public_only", "false").lower() == "true"
        # ContestSerialiser output is per-user (available_token_grants, is_editor, registered,
        # access_status all vary by requester), so only an actually-anonymous public_only request
        # is safe to serve from the shared "global" cache entry / CDN-shareable response. An
        # authenticated request must always get its own cache key, ETag, and a private
        # Cache-Control, even with public_only=true - otherwise one user's personalized response
        # (including their own token inventory) gets cached and served to every other caller.
        is_anonymous_public_request = public_only and not request.user.is_authenticated
        user_id = "global" if is_anonymous_public_request else (request.user.id if request.user.is_authenticated else "anon")
        params = request.query_params.dict()
        sorted_params = json.dumps(params, sort_keys=True)
        params_hash = hashlib.md5(sorted_params.encode("utf-8")).hexdigest()

        version = get_contest_list_version()

        # 1. ETag check (Browser/CDN level validation)
        # The ETag represents a specific version of a specific query, for a specific user.
        etag = f'"{version}-{user_id}-{params_hash}"'
        if request.META.get("HTTP_IF_NONE_MATCH") == etag:
            return Response(status=status.HTTP_304_NOT_MODIFIED)

        # 2. Django-level cache check
        cache_key = f"contest_list_v{version}_u{user_id}_{params_hash}"
        cached_data = cache.get(cache_key)

        if cached_data:
            response = Response(cached_data)
        else:
            response = super().list(request, *args, **kwargs)
            if response.status_code == 200:
                cache.set(cache_key, response.data, timeout=60 * 60 * 24)

        # 3. Set Caching Headers
        response["ETag"] = etag
        if is_anonymous_public_request:
            # Public data can be cached by CDN and shared between anonymous users,
            # but MUST be revalidated via ETag to ensure the list is fresh.
            # stale-while-revalidate=86400: Serve stale data while fetching fresh in background
            response["Cache-Control"] = "public, no-cache, stale-while-revalidate=86400"
            if "Vary" in response:
                del response["Vary"]
        else:
            # Private/personalized data must NOT be cached by CDN or shared.
            response["Cache-Control"] = "private, no-cache"

        return response

    def get_serializer_class(self):
        return self.serializer_classes.get(self.action, self.default_serialiser_class)

    def get_queryset(self):
        user = self.request.user
        queryset = Contest.objects.all()

        # The actual filtering is now primarily handled by ContestFilter (in filters.py).
        # This method defines the 'base' visibility for the user.
        if user.is_superuser:
            # Superusers can see every contest in the database base queryset.
            # Filters will still apply on top of this.
            pass
        elif user.is_authenticated:
            # Authenticated users can see public contests OR contests they have permissions for.
            queryset = (
                get_objects_for_user(user, "display.view_contest", klass=queryset, accept_global_perms=False)
                | Contest.objects.filter(is_public=True, is_featured=True)
            ).distinct()
        else:
            # Anonymous users only see public featured contests.
            queryset = queryset.filter(is_public=True, is_featured=True)

        now = datetime.datetime.now(datetime.timezone.utc)
        queryset = queryset.annotate(
            navigation_task_count=Count("navigationtask", distinct=True),
            has_open_tasks_count=Count(
                "navigationtask",
                filter=Q(
                    navigationtask__allow_self_management=True,
                    navigationtask__start_time__lte=now,
                    navigationtask__finish_time__gte=now,
                ),
                distinct=True,
            ),
            has_flown_contestants_count=Count(
                "navigationtask__contestant",
                filter=Q(navigationtask__contestant__contestanttrack__calculator_started=True),
                distinct=True,
            ),
        )

        if self.action == "list":
            return queryset.order_by("-start_time")

        return queryset.prefetch_related(
            "navigationtask_set__route__prohibited_set",
            "contestteam_set__team__crew__member1",
        ).order_by("-start_time")

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="team_id",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description="Team primary key",
            )
        ]
    )
    @action(detail=True, methods=["get"], url_path=r"contest_team_for_team/(?P<team_id>\d+)")
    def contest_team_for_team(self, request, team_id, **kwargs):
        """Get the ContestTeam that matches the Team id"""
        return Response(
            ContestTeamSerialiser(instance=ContestTeam.objects.get(contest=self.get_object(), team=team_id)).data
        )

    @action(detail=True, methods=["get"])
    def get_current_time(self, request, *args, **kwargs):
        """
        Return the current time for the appropriate time zone. It does not seem to be used by the front end anywhere.
        """
        contest = self.get_object()
        return Response(datetime.datetime.now(datetime.timezone.utc).astimezone(contest.time_zone).strftime("%H:%M:%S"))

    @action(detail=True, methods=["put"])
    def share(self, request, *args, **kwargs):
        """
        Change the visibility of the navigation task to one of the public, private, or unlisted
        """
        contest = self.get_object()
        serialiser = self.get_serializer(data=request.data)  # type: SharingSerialiser
        serialiser.is_valid(raise_exception=True)
        if serialiser.validated_data["visibility"] == serialiser.PUBLIC:
            contest.make_public()
        elif serialiser.validated_data["visibility"] == serialiser.PRIVATE:
            contest.make_private()
        elif serialiser.validated_data["visibility"] == serialiser.UNLISTED:
            contest.make_unlisted()
        return Response(serialiser.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"])
    def ongoing_navigation(self, request, *args, **kwargs):
        # version = cache.get("contest_list_version", 1)
        # etag = f'"{version}-ongoing"'
        # if request.META.get("HTTP_IF_NONE_MATCH") == etag:
        #     return Response(status=status.HTTP_304_NOT_MODIFIED)

        # Synchronize with OngoingNavigationSerialiser definition of 'active'
        navigation_tasks = (
            NavigationTask.get_visible_navigation_tasks(self.request.user)
            .filter(
                contestant__contestanttrack__calculator_started=True,
                contestant__contestanttrack__calculator_finished=False,
                contestant__finished_by_time__gt=datetime.datetime.now(datetime.timezone.utc),
            )
            .distinct()
        )

        # Optimize N+1
        active_contestants_prefetch = Prefetch(
            "contestant_set",
            queryset=Contestant.objects.filter(
                finished_by_time__gt=datetime.datetime.now(datetime.timezone.utc),
                contestanttrack__calculator_started=True,
                contestanttrack__calculator_finished=False,
            ).select_related("team__crew__member1", "team__aeroplane", "contestanttrack"),
            to_attr="prefetched_active_contestants",
        )

        navigation_tasks = navigation_tasks.prefetch_related("contest", active_contestants_prefetch)

        data = self.get_serializer_class()(navigation_tasks, many=True, context={"request": self.request}).data
        response = Response(data)
        # This is a public-facing list of live tasks. No ETag available.
        # s-maxage=120: CDN shields origin by caching for 2 minutes.
        # max-age=0: Browser always checks CDN (no disk cache).
        response["Cache-Control"] = "public, max-age=0, s-maxage=120"
        return response

    @action(detail=False, methods=["get"])
    def todays_navigation(self, request, *args, **kwargs):
        # version = cache.get("contest_list_version", 1)
        # etag = f'"{version}-todays-nav"'
        # if request.META.get("HTTP_IF_NONE_MATCH") == etag:
        #     return Response(status=status.HTTP_304_NOT_MODIFIED)

        timezone_name = request.query_params.get("timezone")

        # Public navigation tasks with at least one valid contestant scheduled today
        navigation_tasks = (
            NavigationTask.objects.filter(
                is_public=True, contest__is_public=True, contestant__in=Contestant.objects.valid_today(timezone_name)
            )
            .distinct()
            .select_related("contest")
        )

        # Prefetch valid today's contestants to avoid N+1
        todays_contestants_prefetch = Prefetch(
            "contestant_set",
            queryset=Contestant.objects.valid_today(timezone_name).select_related(
                "team__crew__member1", "team__aeroplane", "contestanttrack"
            ),
            to_attr="prefetched_todays_contestants",
        )

        navigation_tasks = navigation_tasks.prefetch_related(todays_contestants_prefetch)

        data = TodaysNavigationSerialiser(
            navigation_tasks, many=True, context={"request": self.request, "timezone": timezone_name}
        ).data
        response = Response(data)
        # Public list scheduled for today. No ETag available.
        # s-maxage=120: CDN shields origin by caching for 2 minutes.
        # max-age=0: Browser always checks CDN (no disk cache).
        response["Cache-Control"] = "public, max-age=0, s-maxage=120"
        return response

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[permissions.IsAuthenticated & ContestModificationPermissions],
    )
    def assign_token(self, request, *args, **kwargs):
        contest = self.get_object()
        serializer = AssignContestTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            assignment = assign_token_to_contest(contest, request.user, serializer.validated_data["token_grant_id"])
        except ValidationError as exc:
            raise drf_exceptions.ValidationError(exc.messages)
        return Response(
            {
                "contest": contest.id,
                "token_grant": assignment.token_grant_id,
                "token_type": assignment.token_type_id,
            },
            status=status.HTTP_200_OK,
        )

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[permissions.IsAuthenticated & ContestModificationPermissions],
    )
    def replace_token(self, request, *args, **kwargs):
        contest = self.get_object()
        serializer = AssignContestTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            assignment = replace_token_for_contest(contest, request.user, serializer.validated_data["token_grant_id"])
        except ValidationError as exc:
            raise drf_exceptions.ValidationError(exc.messages)
        return Response(
            {
                "contest": contest.id,
                "token_grant": assignment.token_grant_id,
                "token_type": assignment.token_type_id,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["get"])
    def results_details(self, request, *args, **kwargs):
        """
        Retrieve the full list of contest summaries, tasks summaries, and individual test results for the contest
        """
        contest = self.get_object()

        contest.permission_change_contest = request.user.has_perm("display.change_contest", contest)
        serialiser = ContestResultsDetailsSerialiser(contest)
        response = Response(serialiser.data)

        if contest.is_public and contest.is_featured:
            # Results change whenever scoring updates.
            # s-maxage=60: CDN shields origin by caching for 1 minute.
            # max-age=0: Browser always checks CDN (no disk cache).
            response["Cache-Control"] = "public, max-age=0, s-maxage=60, stale-while-revalidate=600"
        else:
            response["Cache-Control"] = "private, no-cache"
        return response

    @action(detail=True, methods=["get"])
    def results_csv(self, request, *args, **kwargs):
        """
        Download contest results as CSV
        """
        contest = self.get_object()

        tasks = contest.task_set.all().order_by("index")
        tests_by_task = {}
        for task in tasks:
            tests_by_task[task.id] = list(task.tasktest_set.all().order_by("index"))

        summaries = contest.contestsummary_set.select_related(
            "team", "team__crew__member1", "team__crew__member2"
        ).order_by("points")

        if contest.summary_score_sorting_direction == Contest.DESCENDING:
            summaries = summaries.order_by("-points")
        else:
            summaries = summaries.order_by("points")

        headers = ["Rank", "Crew", "Total Score"]

        for task in tasks:
            headers.append(f"Task: {task.heading}")
            for test in tests_by_task[task.id]:
                headers.append(f"Test: {test.heading}")

        response = HttpResponse(
            content_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{contest.name}_results.csv"'},
        )
        if contest.is_public and contest.is_featured:
            # Results change whenever scoring updates.
            # s-maxage=60: CDN shields origin by caching for 1 minute.
            # max-age=0: Browser always checks CDN (no disk cache).
            response["Cache-Control"] = "public, max-age=0, s-maxage=60, stale-while-revalidate=600"
        else:
            response["Cache-Control"] = "private, no-cache"

        writer = csv.writer(response)
        writer.writerow(headers)

        task_summaries = TaskSummary.objects.filter(task__contest=contest)
        test_scores = TeamTestScore.objects.filter(task_test__task__contest=contest)

        task_points = {(s.team_id, s.task_id): s.points for s in task_summaries}
        test_points = {(s.team_id, s.task_test_id): s.points for s in test_scores}

        rank = 1
        for summary in summaries:
            team = summary.team
            parts = []
            if team and team.crew:
                m1 = team.crew.member1
                m2 = team.crew.member2
                if m1:
                    parts.append(f"{m1.first_name} {m1.last_name}")
                if m2:
                    parts.append(f"{m2.first_name} {m2.last_name}")
            crew_name = " / ".join(parts) if parts else "N/A"

            row = [rank, crew_name, summary.points]

            for task in tasks:
                t_points = task_points.get((team.id, task.id), "-")
                row.append(t_points)

                for test in tests_by_task[task.id]:
                    tt_points = test_points.get((team.id, test.id), "-")
                    row.append(tt_points)

            writer.writerow(row)
            rank += 1

        return response

    @action(["GET"], detail=True)
    def teams(self, request, pk=None, **kwargs):
        """
        Get the list of teams in the contest
        """
        contest = self.get_object()
        contest_teams = ContestTeam.objects.filter(contest=contest)
        response = Response(ContestTeamNestedSerialiser(contest_teams, many=True).data)

        if contest.is_public and contest.is_featured:
            # Team lists can change during signup/withdrawal.
            # s-maxage=60: CDN shields origin by caching for 1 minute.
            # max-age=0: Browser always checks CDN (no disk cache).
            response["Cache-Control"] = "public, max-age=0, s-maxage=60, stale-while-revalidate=600"
        else:
            response["Cache-Control"] = "private, no-cache"
        return response

    @action(
        detail=True,
        methods=["put"],
        permission_classes=[permissions.IsAuthenticated & ContestModificationPermissions],
    )
    def update_contest_summary(self, request, *args, **kwargs):
        """
        Update the total score for the contest for a team.
        """
        # I think this is required for the permissions to work
        contest = self.get_object()
        summary, created = ContestSummary.objects.get_or_create(
            team_id=request.data["team"],
            contest=contest,
            defaults={"points": request.data["points"]},
        )
        if not created:
            summary.points = request.data["points"]
            summary.save()

        return Response(status=status.HTTP_200_OK)

    @action(
        detail=True,
        methods=["put"],
        permission_classes=[permissions.IsAuthenticated & ContestModificationPermissions],
    )
    def update_task_summary(self, request, *args, **kwargs):
        """
        Update the total score for a task for a team.
        """
        # I think this is required for the permissions to work
        contest = self.get_object()
        summary, created = TaskSummary.objects.get_or_create(
            team_id=request.data["team"],
            task_id=request.data["task"],
            defaults={"points": request.data["points"]},
        )
        if not created:
            summary.points = request.data["points"]
            summary.save()
        return Response(status=status.HTTP_200_OK)

    @action(
        detail=True,
        methods=["put"],
        permission_classes=[permissions.IsAuthenticated & ContestModificationPermissions],
    )
    def update_test_result(self, request, *args, **kwargs):
        """
        Update the school for an individual test for a team.
        """
        # I think this is required for the permissions to work
        contest = self.get_object()
        results, created = TeamTestScore.objects.get_or_create(
            team_id=int(request.data["team"]),
            task_test_id=int(request.data["task_test"]),
            defaults={"points": int(request.data["points"])},
        )
        if not created:
            results.points = request.data["points"]
            results.save()
        return Response(status=status.HTTP_200_OK)

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[permissions.IsAuthenticated & ContestModificationPermissions],
    )
    def team_results_delete(self, request, *args, **kwargs):
        contest = self.get_object()
        team_id = request.data["team_id"]
        ContestTeam.objects.filter(contest=contest, team__pk=team_id).delete()
        ContestSummary.objects.filter(contest=contest, team__pk=team_id).delete()
        ws = WebsocketFacade()
        ws.transmit_contest_results(request.user, contest)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=True,
        methods=["POST", "PUT"],
        permission_classes=[permissions.IsAuthenticated & ContestPublicModificationPermissions],
    )
    def signup(self, request, *args, **kwargs):
        contest = self.get_object()
        if request.method == "POST":
            contest = None
        serialiser = self.get_serializer(instance=contest, data=request.data)
        serialiser.is_valid(raise_exception=True)
        contest_team = serialiser.save()
        return Response(ContestTeamSerialiser(contest_team).data, status=status.HTTP_201_CREATED)

    @action(
        detail=True,
        methods=["DELETE"],
        permission_classes=[permissions.IsAuthenticated & ContestPublicModificationPermissions],
    )
    def withdraw(self, request, *args, **kwargs):
        contest = self.get_object()
        teams = ContestTeam.objects.filter(
            Q(team__crew__member1__email=self.request.user.email)
            | Q(team__crew__member2__email=self.request.user.email),
            contest=contest,
        )
        contestants = Contestant.objects.filter(
            navigation_task__contest=contest,
            team__in=[item.team for item in teams],
            finished_by_time__gt=datetime.datetime.now(datetime.timezone.utc),
        )
        if contestants.exists():
            raise drf_exceptions.ValidationError(
                "You are currently participating in at least one navigation task. Cancel all flights before you can withdraw from the contest"
            )
        teams.delete()
        return Response({}, status=status.HTTP_204_NO_CONTENT)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        try:
            context.update({"contest": self.get_object(), "request": self.request})
        except AssertionError:
            # This is when we are creating a new contest
            pass
        if self.request:
            context["exclude_tasks"] = self.request.query_params.get("exclude_tasks", "false").lower() == "true"
            context["exclude_teams"] = self.request.query_params.get("exclude_teams", "false").lower() == "true"
            if self.request.user.is_authenticated:
                context["user_person"] = Person.objects.filter(email=self.request.user.email).first()
                context["editable_contest_ids"] = set(
                    get_objects_for_user(
                        self.request.user,
                        "display.change_contest",
                        klass=Contest,
                        accept_global_perms=False,
                        with_superuser=False,
                    ).values_list("id", flat=True)
                )

                context["registered_contest_ids"] = set(
                    ContestTeam.objects.filter(
                        Q(team__crew__member1__email=self.request.user.email)
                        | Q(team__crew__member2__email=self.request.user.email)
                    ).values_list("contest_id", flat=True)
                )
        return context


class TeamViewSet(ModelViewSet):
    queryset = Team.objects.all()
    serializer_class = TeamNestedSerialiser
    permission_classes = [permissions.IsAuthenticated & TeamPermissions]

    http_method_names = ["post", "put", "get"]

    def get_queryset(self):
        # TeamPermissions.has_permission allows any authenticated user for safe methods, and
        # (unlike PhotoViewSet/ContestViewSet) there was previously no queryset scoping at all -
        # TeamNestedSerialiser -> CrewSerialiser -> PersonSerialiserExcludingTracking includes
        # every pilot's name, email and phone number, so this dumped that PII for every team in
        # the system to any logged-in user. Scope to teams the requester can legitimately see:
        # their own team(s), teams registered in a contest they can view, or teams in a public
        # featured contest.
        queryset = super().get_queryset()
        user = self.request.user
        if user.is_superuser:
            return queryset
        visible_contests = get_objects_for_user(user, "display.view_contest", klass=Contest, accept_global_perms=False)
        return queryset.filter(
            Q(contestteam__contest__in=visible_contests)
            | Q(contestteam__contest__is_public=True, contestteam__contest__is_featured=True)
            | Q(crew__member1__email=user.email)
            | Q(crew__member2__email=user.email)
        ).distinct()


class ContestTeamViewSet(ModelViewSet):
    queryset = ContestTeam.objects.all()
    serializer_class = ContestTeamSerialiser
    permission_classes = [permissions.IsAuthenticated & ContestTeamContestPermissions]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        try:
            context.update({"contest": get_object_or_404(Contest, pk=self.kwargs.get("contest_pk"))})
        except Http404:
            # This has to be handled where we retrieve the context
            pass
        return context

    def get_queryset(self):
        contest_id = self.kwargs.get("contest_pk")
        contests = get_objects_for_user(
            self.request.user,
            "display.view_contest",
            klass=Contest,
            accept_global_perms=False,
        )
        try:
            contest = contests.get(pk=contest_id)
        except Contest.DoesNotExist:
            raise Http404("Contest does not exist")
        return ContestTeam.objects.filter(contest=contest)


class GetScorecardsViewSet(ReadOnlyModelViewSet):
    queryset = Scorecard.get_originals()
    serializer_class = ScorecardNestedSerialiser


class NavigationTaskViewSet(ModelViewSet):
    """
    Main navigation task view set. Used by the front end to load the tracking map.
    """

    queryset = NavigationTask.objects.all()
    serializer_classes = {
        "share": SharingSerialiser,
        "contestant_self_registration": SelfManagementSerialiser,
        "scorecard": ScorecardNestedSerialiser,
        "create": NavigationTaskEditableRoutReferenceSerialiser,
    }
    default_serialiser_class = NavigationTaskNestedTeamRouteSerialiser
    lookup_url_kwarg = "pk"

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.task_subtype:
            TaskCompiler(instance).compile(force=False)
        response = super().retrieve(request, *args, **kwargs)

        # if instance.is_public and instance.contest.is_public and instance.is_featured:
        #     response["Cache-Control"] = "public, max-age=0, s-maxage=31536000, stale-while-revalidate=86400"
        #     if "Vary" in response:
        #         del response["Vary"]
        # else:
        #     response["Cache-Control"] = "private, no-cache"
        return response

    permission_classes = [
        NavigationTaskPublicPermissions | (permissions.IsAuthenticated & NavigationTaskContestPermissions)
    ]
    filter_backends = [DjangoFilterBackend]
    filterset_class = NavigationTaskFilter

    http_method_names = ["get", "post", "delete", "put"]

    def get_serializer_class(self):
        return self.serializer_classes.get(self.action, self.default_serialiser_class)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["selected_contestants"] = [
            item for item in self.request.GET.get("contestantIds", "").split(",") if len(item) > 0
        ]
        try:
            context.update({"contest": get_object_or_404(Contest, pk=self.kwargs.get("contest_pk"))})
        except Http404:
            # This has to be handled where we retrieve the context
            pass
        return context

    def get_queryset(self):
        contest_id = self.kwargs.get("contest_pk")
        contests = get_objects_for_user(
            self.request.user,
            "display.view_contest",
            klass=Contest,
            accept_global_perms=False,
        )
        return NavigationTask.objects.filter(
            Q(contest__in=contests) | Q(is_public=True, contest__is_public=True)
        ).filter(contest_id=contest_id)

    def update(self, request, *args, **kwargs):
        raise drf_exceptions.PermissionDenied(
            "It is not possible to modify existing navigation tasks except to publish or hide them"
        )

    @action(
        detail=True,
        methods=["get", "put"],
        permission_classes=[permissions.IsAuthenticated & NavigationTaskContestPermissions],
    )
    def scorecard(self, request, *args, **kwargs):
        navigation_task = self.get_object()  # type: NavigationTask
        if request.method == "PUT":
            serialiser = self.get_serializer(instance=navigation_task.scorecard, data=request.data)
            serialiser.is_valid(raise_exception=True)
            serialiser.save()
            return Response(serialiser.data, status=status.HTTP_200_OK)
        else:
            serialiser = self.get_serializer(instance=navigation_task.scorecard)
            return Response(serialiser.data, status=status.HTTP_200_OK)

    @action(
        detail=True,
        methods=["get"],
        permission_classes=[
            NavigationTaskPublicPermissions | (permissions.IsAuthenticated & NavigationTaskContestPermissions)
        ],
    )
    def photos(self, request, pk=None, contest_pk=None):
        navigation_task = self.get_object()
        photos = sync_navigation_task_photo_targets(navigation_task)
        contestant_id = request.query_params.get("contestant")
        contestant = None
        if contestant_id:
            try:
                contestant = navigation_task.contestant_set.get(pk=contestant_id)
            except Contestant.DoesNotExist:
                raise ValidationError({"contestant": "Contestant not found for this navigation task."})
        if (
            contestant
            and hasattr(contestant, "contestanttaskconfiguration")
            and contestant.contestanttaskconfiguration.is_valid
        ):
            payload = contestant.contestanttaskconfiguration.compiled_effective_route_payload or {}
            observation_photos = payload.get("observation_photos", [])
            observation_names = {item.get("name") for item in observation_photos if item.get("name")}
            if observation_names:
                filtered = [photo for photo in photos if photo.name in observation_names]
                if filtered:
                    photos = filtered
                else:
                    return Response(
                        [
                            {
                                "id": None,
                                "name": item.get("name"),
                                "file": None,
                                "compiled_coordinates": item.get("coordinates"),
                                "latitude": item.get("coordinates", [None, None])[1],
                                "longitude": item.get("coordinates", [None, None])[0],
                                "evidence_category": "observation",
                                "target_kind": "observation",
                            }
                            for item in observation_photos
                        ]
                    )
        if navigation_task.user_has_change_permissions(request.user) and contestant is None:
            serializer = PhotoSerialiser(photos, many=True)
        else:
            serializer = PhotoPublicSerialiser(photos, many=True, context={"contestant": contestant})
        return Response(serializer.data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="contest_teams",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Comma-separated ContestTeam IDs to preview against this task. Duplicate IDs are deduplicated in order.",
            ),
            OpenApiParameter(
                name="first_takeoff_time",
                type=OpenApiTypes.DATETIME,
                location=OpenApiParameter.QUERY,
                description="Optional ISO-8601 takeoff time used to filter overlapping existing contestants.",
            ),
        ],
        responses={
            200: inline_serializer(
                name="ScheduleCapacityPreviewResponse",
                fields={
                    "contestant_limit": serializers.IntegerField(allow_null=True),
                    "reserved_before_count": serializers.IntegerField(),
                    "reserved_after_count": serializers.IntegerField(),
                    "additional_selected_count": serializers.IntegerField(),
                    "remaining_before_count": serializers.IntegerField(allow_null=True),
                    "remaining_after_count": serializers.IntegerField(allow_null=True),
                    "would_exceed": serializers.BooleanField(),
                },
            ),
            400: inline_serializer(
                name="ScheduleCapacityPreviewError",
                fields={"detail": serializers.CharField()},
            ),
        },
        description="Return projected pilot-capacity usage for a proposed schedule before contestants are created.",
    )
    @action(
        detail=True,
        methods=["get"],
        url_path="schedule_capacity_preview",
        permission_classes=[permissions.IsAuthenticated & NavigationTaskContestPermissions],
    )
    def schedule_capacity_preview(self, request, pk=None, **kwargs):
        """Return projected pilot-capacity usage for a proposed schedule."""
        navigation_task = self.get_object()
        query_serializer = ScheduleCapacityPreviewQuerySerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)
        contest_teams_pks = query_serializer.validated_data["contest_teams"]
        first_takeoff_time = query_serializer.validated_data.get("first_takeoff_time")
        if first_takeoff_time is not None and first_takeoff_time.tzinfo is None:
            first_takeoff_time = first_takeoff_time.replace(tzinfo=navigation_task.contest.time_zone)
        try:
            preview = scheduling_capacity_preview(
                navigation_task,
                contest_teams_pks,
                first_takeoff_time=first_takeoff_time,
            )
        except DjangoValidationError as exc:
            detail = exc.message
            return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)
        return Response(preview, status=status.HTTP_200_OK)

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[permissions.IsAuthenticated & NavigationTaskContestPermissions],
    )
    def schedule_contestants(self, request, pk=None, **kwargs):
        navigation_task = self.get_object()
        data = request.data

        try:
            contest_teams_pks = _normalize_contest_team_ids(data.get("contest_teams", []))

            first_takeoff_time = dateutil.parser.parse(data.get("first_takeoff_time"))
            if first_takeoff_time.tzinfo is None:
                first_takeoff_time = first_takeoff_time.replace(tzinfo=navigation_task.contest.time_zone)

            # The frontend has sent this since SchedulingForm.tsx's "Next Takeoff Time" field
            # was added, but it was never read here - schedule_and_create_contestants has always
            # accepted it (falling back to first_takeoff_time when None), the wiring from the
            # API layer down to it was just missing, so the field silently did nothing.
            next_takeoff_time = None
            if data.get("next_takeoff_time"):
                next_takeoff_time = dateutil.parser.parse(data.get("next_takeoff_time"))
                if next_takeoff_time.tzinfo is None:
                    next_takeoff_time = next_takeoff_time.replace(tzinfo=navigation_task.contest.time_zone)

            capacity_preview = scheduling_capacity_preview(
                navigation_task,
                contest_teams_pks,
                first_takeoff_time=first_takeoff_time,
            )
            if capacity_preview["would_exceed"]:
                limit = capacity_preview["contestant_limit"]
                raise drf_exceptions.ValidationError(
                    {
                        "detail": (
                            f"Scheduling these teams would exceed the guest pilot capacity for this task. "
                            f"Reserved now: {capacity_preview['reserved_before_count']} / {limit}. "
                            f"After scheduling: {capacity_preview['reserved_after_count']} / {limit}. "
                            f"New pilot reservations from the selected teams: {capacity_preview['additional_selected_count']}. "
                            f"Remove an unstarted contestant, deselect teams that introduce new pilots, reuse an already-counted pilot, or apply a larger token or club pass."
                        )
                    }
                )

            success, messages = schedule_and_create_contestants(
                navigation_task=navigation_task,
                contest_teams_pks=contest_teams_pks,
                first_takeoff_time=first_takeoff_time,
                tracker_leadtime_minutes=int(data.get("tracker_lead_time_minutes", 15)),
                aircraft_switch_time_minutes=int(data.get("minutes_for_aircraft_switch", 30)),
                tracker_switch_time=int(data.get("minutes_for_tracker_switch", 15)),
                minimum_start_interval=int(data.get("minutes_between_contestants_at_start", 5)),
                minimum_finish_interval=int(data.get("minutes_between_contestants_at_finish", 2)),
                crew_switch_time=int(data.get("minutes_for_crew_switch", 15)),
                optimise=data.get("optimise", False),
                next_takeoff_time=next_takeoff_time,
            )

            if success:
                return Response({"status": "success", "messages": messages})
            else:
                return Response({"status": "error", "messages": messages}, status=status.HTTP_400_BAD_REQUEST)

        except drf_exceptions.ValidationError:
            raise
        except (TypeError, ValueError, dateutil.parser.ParserError) as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            logger.exception("Scheduling failed")
            return Response(
                {"error": "Scheduling failed due to an internal error. Please try again or contact support."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(
        detail=True,
        methods=["post", "put"],
        permission_classes=[
            permissions.IsAuthenticated
            & NavigationTaskSelfManagementPermissions
            & (NavigationTaskPublicPutDeletePermissions | NavigationTaskContestPermissions)
        ],
    )
    def contestant_self_registration(self, request, *args, **kwargs):
        navigation_task = self.get_object()  # type: NavigationTask
        if request.method in ("POST", "PUT"):
            serialiser = self.get_serializer(data=request.data)
            serialiser.is_valid(raise_exception=True)
            contest_team = serialiser.validated_data["contest_team"]
            assert_can_self_register_contestant(navigation_task, contest_team)
            if contest_team.team.crew.member1.email != request.user.email:
                raise drf_exceptions.ValidationError("You cannot add a team where you are not the pilot")
            # Pretend that the submitted time is in the contest time zone
            starting_point_time = serialiser.validated_data["starting_point_time"]
            takeoff_time = starting_point_time - datetime.timedelta(minutes=navigation_task.minutes_to_starting_point)
            existing_contestants = navigation_task.contestant_set.all()
            if existing_contestants.exists():
                contestant_number = max([item.contestant_number for item in existing_contestants]) + 1
            else:
                contestant_number = 1
            adaptive_start = serialiser.validated_data["adaptive_start"]
            tracker_start_time = takeoff_time - datetime.timedelta(minutes=10)
            if adaptive_start:
                tracker_start_time = starting_point_time - datetime.timedelta(hours=1)
                takeoff_time = tracker_start_time

            contestant = Contestant(
                team=contest_team.team,
                takeoff_time=takeoff_time,
                navigation_task=navigation_task,
                tracker_start_time=tracker_start_time,
                adaptive_start=adaptive_start,
                finished_by_time=tracker_start_time + datetime.timedelta(days=1) - datetime.timedelta(minutes=1),
                minutes_to_starting_point=navigation_task.minutes_to_starting_point,
                air_speed=contest_team.air_speed,
                contestant_number=contestant_number,
                wind_speed=serialiser.validated_data["wind_speed"],
                wind_direction=serialiser.validated_data["wind_direction"],
            )
            logger.debug("Created contestant")
            final_time = takeoff_time + contestant.flight_duration
            logger.debug(f"Final gate time is {final_time}")

            if final_time is None:
                final_time = starting_point_time
            if adaptive_start:
                duration = final_time - starting_point_time
                # Properly account for how final time is created when adaptive start is active
                final_time = starting_point_time + datetime.timedelta(hours=1) + duration
            logger.debug(f"Take-off time is {contestant.takeoff_time}")
            logger.debug(f"Final time is {final_time}")
            contestant.finished_by_time = final_time + datetime.timedelta(
                minutes=navigation_task.minutes_to_landing + 2
            )
            logger.debug(f"Finished by time is {contestant.finished_by_time}")

            contestant.save()
            declaration_payload = ContestantTaskCompiler(contestant).build_declaration_payload_from_input(
                serialiser.validated_data.get("declaration_payload")
            )
            ContestantTaskCompiler(contestant).compile(declaration_payload=declaration_payload, force=True)
            logger.debug("Updated contestant")
            # mail_link = EmailMapLink.objects.create(contestant=contestant)
            # mail_link.send_email(request.user.email, request.user.first_name)
            generate_and_maybe_notify_flight_order.apply_async(
                (contestant.pk, request.user.email, request.user.first_name, True)
            )
            return Response(ContestantSerialiser(contestant).data, status=status.HTTP_201_CREATED)

    @action(
        detail=True,
        methods=["delete"],
        url_path="delete_self_managed_contestant/(?P<contestant_id>\\d+)",
        permission_classes=[
            permissions.IsAuthenticated
            & NavigationTaskSelfManagementPermissions
            & (NavigationTaskPublicPutDeletePermissions | NavigationTaskContestPermissions)
        ],
    )
    def delete_self_managed_contestant(self, request, *args, **kwargs):
        navigation_task: NavigationTask = self.get_object()
        my_contestant = get_object_or_404(navigation_task.contestant_set, pk=kwargs["contestant_id"])
        # Matches the DELETE branch of NavigationTaskContestPermissions, the non-public-task path
        # that lets this action through in the first place.
        is_contest_manager = request.user.has_perm("display.delete_contest", navigation_task.contest)
        if not is_contest_manager and my_contestant.team.crew.member1.email != request.user.email:
            raise drf_exceptions.PermissionDenied("You cannot delete a contestant that is not your own")
        try:
            if (
                not my_contestant.contestanttrack.calculator_started
                or my_contestant.takeoff_time > datetime.datetime.now(datetime.timezone.utc)
            ):
                my_contestant.delete()
            else:
                my_contestant.finished_by_time = datetime.datetime.now(datetime.timezone.utc)
                my_contestant.save()
                my_contestant.request_calculator_termination()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            logger.exception("Failed deleting self managed contestant")
            raise e

    @action(detail=True, methods=["put"])
    def share(self, request, *args, **kwargs):
        """
        Change the visibility of the navigation task to one of the public, private, or unlisted
        """
        navigation_task = self.get_object()
        serialiser = self.get_serializer(data=request.data)  # type: SharingSerialiser
        serialiser.is_valid(raise_exception=True)
        if serialiser.validated_data["visibility"] == serialiser.PUBLIC:
            navigation_task.make_public()
        elif serialiser.validated_data["visibility"] == serialiser.PRIVATE:
            navigation_task.make_private()
        elif serialiser.validated_data["visibility"] == serialiser.UNLISTED:
            navigation_task.make_unlisted()
        return Response(serialiser.data, status=status.HTTP_200_OK)


class PhotoViewSet(ModelViewSet):
    queryset = Photo.objects.all()
    serializer_class = PhotoSerialiser
    permission_classes = [permissions.IsAuthenticated & PhotoPermissions]

    def get_queryset(self):
        queryset = super().get_queryset()
        route_id = self.request.query_params.get("route")
        if route_id:
            queryset = queryset.filter(route_id=route_id)
        # PhotoPermissions.has_permission is intentionally permissive (object-level visibility
        # normally decides read/write access) but has_object_permission is never consulted for
        # list() - it only operates on the queryset. Without this filter, any authenticated user
        # could list photos (the observation-photo answer key, including is_decoy) for any route,
        # including ones belonging to a private, unpublished task. Mirrors the same visibility
        # rule as PhotoPermissions.has_object_permission's safe-method branch.
        user = self.request.user
        if user.is_superuser:
            return queryset
        if user.is_authenticated:
            visible_contests = get_objects_for_user(
                user, "display.view_contest", klass=Contest, accept_global_perms=False
            )
            return queryset.filter(
                Q(route__navigationtask__is_public=True) | Q(route__navigationtask__contest__in=visible_contests)
            ).distinct()
        return queryset.filter(route__navigationtask__is_public=True)

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated & PhotoPermissions])
    def revert(self, request, pk=None):
        photo = self.get_object()
        revert_photo_to_satellite(photo)
        serializer = self.get_serializer(photo)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def perform_create(self, serializer):
        # has_object_permission is never consulted for create() either, since the object doesn't
        # exist yet - so without this check, PhotoPermissions.has_permission's unconditional True
        # lets any authenticated user inject photos/decoys into another organiser's route.
        route = serializer.validated_data.get("route")
        nav_task = getattr(route, "navigationtask", None) if route is not None else None
        contest = nav_task.contest if nav_task is not None else None
        user = self.request.user
        can_write = user.is_superuser or (
            contest is not None
            and (user.has_perm("display.change_contest", contest) or user.has_perm("change_contest", contest))
        )
        if not can_write:
            raise drf_exceptions.PermissionDenied("You do not have permission to add photos to this route")
        photo = serializer.save()
        photo.generate_image()

    def perform_destroy(self, instance):
        if instance.file:
            instance.file.delete(save=False)
        instance.delete()


class RouteViewSet(ModelViewSet):
    queryset = Route.objects.all()
    serializer_class = RouteSerialiser
    permission_classes = [permissions.IsAuthenticated & RoutePermissions]

    http_method_names = ["get", "post", "delete", "put"]


class AircraftViewSet(ModelViewSet):
    queryset = Aeroplane.objects.all()
    serializer_class = AeroplaneSerialiser
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get"]


class ClubViewSet(ReadOnlyModelViewSet):
    queryset = Club.objects.all()
    serializer_class = ClubSerialiser
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if self.action == "managed":
            return (
                Club.objects.filter(
                    clubmanagermembership__user=self.request.user,
                    clubmanagermembership__is_active=True,
                )
                .distinct()
                .order_by("name")
            )
        return Club.objects.all().order_by("name")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    def _can_manage_club(self, club):
        return (
            self.request.user.is_superuser
            or ClubManagerMembership.objects.filter(
                club=club,
                user=self.request.user,
                is_active=True,
                role=ClubManagerMembership.OWNER,
            ).exists()
        )

    @action(detail=False, methods=["get"], url_path="managed")
    def managed(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_queryset(), many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="managers")
    def managers(self, request, *args, **kwargs):
        club = self.get_object()
        if not self._can_manage_club(club):
            return Response(status=status.HTTP_403_FORBIDDEN)
        serializer = ClubManagerMembershipCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        managed_user = serializer.context["managed_user"]
        membership, _created = ClubManagerMembership.objects.update_or_create(
            club=club,
            user=managed_user,
            defaults={
                "role": serializer.validated_data["role"],
                "is_active": True,
                "updated_by": request.user,
            },
        )
        if membership.created_by_id is None:
            membership.created_by = request.user
            membership.save(update_fields=["created_by", "updated_at"])
        return Response(ClubManagerMembershipSerializer(membership).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["delete"], url_path=r"managers/(?P<membership_pk>\d+)")
    def manager_detail(self, request, membership_pk=None, *args, **kwargs):
        club = self.get_object()
        if not self._can_manage_club(club):
            return Response(status=status.HTTP_403_FORBIDDEN)
        membership = get_object_or_404(ClubManagerMembership, pk=membership_pk, club=club)
        membership.is_active = False
        membership.updated_by = request.user
        membership.full_clean()
        membership.save(update_fields=["is_active", "updated_by", "updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)


_NAVIGATION_TASK_NESTED_PATH_PARAMETERS = [
    OpenApiParameter(name="contest_pk", type=OpenApiTypes.INT, location=OpenApiParameter.PATH),
    OpenApiParameter(name="navigationtask_pk", type=OpenApiTypes.INT, location=OpenApiParameter.PATH),
]
_NAVIGATION_TASK_NESTED_SCHEMA_VIEW = extend_schema_view(
    list=extend_schema(parameters=_NAVIGATION_TASK_NESTED_PATH_PARAMETERS),
    create=extend_schema(parameters=_NAVIGATION_TASK_NESTED_PATH_PARAMETERS),
    retrieve=extend_schema(parameters=_NAVIGATION_TASK_NESTED_PATH_PARAMETERS),
    update=extend_schema(parameters=_NAVIGATION_TASK_NESTED_PATH_PARAMETERS),
    partial_update=extend_schema(parameters=_NAVIGATION_TASK_NESTED_PATH_PARAMETERS),
    destroy=extend_schema(parameters=_NAVIGATION_TASK_NESTED_PATH_PARAMETERS),
)


@_NAVIGATION_TASK_NESTED_SCHEMA_VIEW
class ContestantTeamIdViewSet(ModelViewSet):
    queryset = Contestant.objects.all()
    permission_classes = [
        ContestantPublicPermissions | (permissions.IsAuthenticated & ContestantNavigationTaskContestPermissions)
    ]
    serializer_classes = {}
    default_serialiser_class = ContestantSerialiser

    def get_serializer_class(self):
        return self.serializer_classes.get(self.action, self.default_serialiser_class)

    def get_queryset(self):
        navigation_task_id = self.kwargs.get("navigationtask_pk")
        contests = get_objects_for_user(
            self.request.user,
            "display.change_contest",
            klass=Contest,
            accept_global_perms=False,
        )
        return Contestant.objects.filter(
            Q(navigation_task__contest__in=contests)
            | Q(
                navigation_task__is_public=True,
                navigation_task__contest__is_public=True,
            )
        ).filter(navigation_task_id=navigation_task_id)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        try:
            navigation_task = get_object_or_404(NavigationTask, pk=self.kwargs.get("navigationtask_pk"))
            context.update({"navigation_task": navigation_task})
        except Http404:
            # This has to be handled where we retrieve the context
            pass
        return context


def generate_score_data(contestant_pk):
    contestant = get_object_or_404(Contestant, pk=contestant_pk)  # type: Contestant

    # Manually serialize related sets to avoid DRF overhead
    annotations = []
    for ann in contestant.trackannotation_set.all():
        annotations.append(
            {
                "id": ann.id,
                "time": ann.time.isoformat() if hasattr(ann.time, "isoformat") else ann.time,
                "latitude": ann.latitude,
                "longitude": ann.longitude,
                "message": ann.message,
                "gate": ann.gate,
                "gate_type": ann.gate_type,
                "type": ann.type,
                "contestant": ann.contestant_id,
                "score_log_entry": ann.score_log_entry_id,
            }
        )

    log_entries = []
    for entry in contestant.scorelogentry_set.filter(type=ANOMALY):
        log_entries.append(
            {
                "id": entry.id,
                "type": entry.type,
                "message": entry.message,
                "points": entry.points,
                "gate": entry.gate,
                "time": entry.time.isoformat() if hasattr(entry.time, "isoformat") else entry.time,
                "planned": (
                    entry.planned.isoformat()
                    if entry.planned and hasattr(entry.planned, "isoformat")
                    else entry.planned
                ),
                "actual": (
                    entry.actual.isoformat() if entry.actual and hasattr(entry.actual, "isoformat") else entry.actual
                ),
                "string": entry.string,
                "offset_string": entry.offset_string,
                "times_string": entry.times_string,
                "contestant": entry.contestant_id,
            }
        )
    administrative_penalties = []
    for penalty in contestant.administrativepenalty_set.select_related("score_log_entry", "actor").all():
        administrative_penalties.append(
            {
                "id": penalty.id,
                "score_log_entry": penalty.score_log_entry_id,
                "category": penalty.category,
                "reason": penalty.reason,
                "actor_id": penalty.actor_id,
                "actor_email": penalty.actor.email if penalty.actor else None,
                "created_at": penalty.created_at.isoformat()
                if hasattr(penalty.created_at, "isoformat")
                else penalty.created_at,
            }
        )

    gate_scores = []
    for gs in contestant.gatecumulativescore_set.all():
        gate_scores.append(
            {
                "id": gs.id,
                "gate": gs.gate,
                "points": gs.points,
                "contestant": gs.contestant_id,
            }
        )

    playing_cards = []
    for pc in contestant.playingcard_set.all():
        playing_cards.append(
            {
                "id": pc.id,
                "waypoint": pc.waypoint,
                "suit": pc.suit,
                "rank": pc.rank,
                "contestant": pc.contestant_id,
            }
        )

    ct = contestant.contestanttrack
    track_data = {
        "id": ct.id,
        "score": ct.score,
        "current_state": ct.current_state,
        "current_leg": ct.current_leg,
        "last_gate": ct.last_gate,
        "last_gate_time_offset": ct.last_gate_time_offset,
        "passed_starting_gate": ct.passed_starting_gate,
        "passed_finish_gate": ct.passed_finish_gate,
        "calculator_finished": ct.calculator_finished,
        "calculator_started": ct.calculator_started,
        "contestant": ct.contestant_id,
        "contest_summary": ct.contest_summary,
    }

    data = generate_contestant_data_block(
        contestant,
        annotations=annotations,
        log_entries=log_entries,
        gate_scores=gate_scores,
        playing_cards=playing_cards,
        contestant_track_data=track_data,
        gate_times=contestant.gate_times,
    )
    data["administrative_penalties"] = administrative_penalties
    if hasattr(contestant, "contestanttaskconfiguration") and contestant.contestanttaskconfiguration.is_valid:
        payload = contestant.contestanttaskconfiguration.compiled_effective_route_payload or {}
        data["compiled_effective_route_payload"] = payload
    else:
        from display.services.contestant_task_compiler import ContestantTaskCompiler

        compiled = ContestantTaskCompiler(contestant).compile(force=True)
        data["compiled_effective_route_payload"] = compiled.compiled_effective_route_payload or {}

    return data


@extend_schema_view(
    **{
        action_name: extend_schema(parameters=_NAVIGATION_TASK_NESTED_PATH_PARAMETERS)
        for action_name in (
            "list",
            "create",
            "retrieve",
            "update",
            "partial_update",
            "destroy",
            "create_with_team",
            "update_with_team",
            "score_data",
            "score_data_versioned",
            "slice",
            "paginated_track_data",
            "score",
            "track",
            "compiled_evidence",
            "gpx_track",
        )
    }
)
class ContestantViewSet(ModelViewSet):
    queryset = Contestant.objects.all()
    permission_classes = [
        ContestantPublicPermissions | (permissions.IsAuthenticated & ContestantNavigationTaskContestPermissions)
    ]
    serializer_classes = {
        "track": ContestantTrackWithTrackPointsSerialiser,
        "gpx_track": GpxTrackSerialiser,
        "create": ContestantSerialiser,
        "update": ContestantSerialiser,
        "create_with_team": ContestantNestedTeamSerialiser,
        "update_with_team": ContestantNestedTeamSerialiser,
    }
    default_serialiser_class = ContestantNestedTeamSerialiserWithContestantTrack

    def get_serializer_class(self):
        return self.serializer_classes.get(self.action, self.default_serialiser_class)

    def get_queryset(self):
        navigation_task_id = self.kwargs.get("navigationtask_pk")
        permission_name = (
            "display.view_contest" if self.request.method in permissions.SAFE_METHODS else "display.change_contest"
        )
        contests = get_objects_for_user(
            self.request.user,
            permission_name,
            klass=Contest,
            accept_global_perms=False,
        )
        qs = Contestant.objects.filter(
            Q(navigation_task__contest__in=contests)
            | Q(
                navigation_task__is_public=True,
                navigation_task__contest__is_public=True,
            )
        )
        if navigation_task_id:
            qs = qs.filter(navigation_task_id=navigation_task_id)
        if self.request.method in permissions.SAFE_METHODS:
            qs = qs.select_related(
                "navigation_task__contest",
                "team__crew__member1",
                "team__crew__member2",
                "team__aeroplane",
                "team__club",
                "contestanttrack",
                "contestanttaskconfiguration",
            )
        return qs

    def get_serializer_context(self):
        context = super().get_serializer_context()
        try:
            navigation_task_id = self.kwargs.get("navigationtask_pk")
            if navigation_task_id:
                navigation_task = get_object_or_404(NavigationTask, pk=navigation_task_id)
                context.update({"navigation_task": navigation_task})
        except Http404:
            # This has to be handled where we retrieve the context
            pass
        return context

    def create(self, request, *args, **kwargs):
        serialiser = self.get_serializer(data=request.data)
        if serialiser.is_valid():
            navigation_task = serialiser.context.get("navigation_task")
            team = serialiser.validated_data.get("team")
            if navigation_task is not None and team is not None:
                resolution = resolve_contest_access(navigation_task.contest)
                _assert_can_reserve_task_slot(navigation_task, team, resolution)
            serialiser.save()
            return Response(serialiser.data)
        return Response(serialiser.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["post"])
    def create_with_team(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        partial = kwargs.pop("partial", False)
        serialiser = self.get_serializer(instance=instance, data=request.data, partial=partial)
        if serialiser.is_valid():
            # Use the existing instance's navigation_task rather than the
            # serializer context, which is only populated when this viewset is
            # reached via the nested .../navigationtasks/<pk>/contestants/ URL -
            # the instance's own navigation_task is always correct regardless
            # of which route (nested or the top-level /contestant/) was used.
            navigation_task = instance.navigation_task
            team = serialiser.validated_data.get("team")
            if navigation_task is not None and team is not None:
                resolution = resolve_contest_access(navigation_task.contest)
                _assert_can_reserve_task_slot(navigation_task, team, resolution, current_contestant=instance)
            serialiser.save()
            return Response(serialiser.data)
        return Response(serialiser.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["put", "patch"])
    def update_with_team(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @extend_schema(
        responses={200: OpenApiTypes.OBJECT},
        description="Same payload as score_data, with the contestant's track/score version embedded in the "
        "path. The frontend already knows both versions from the navigation task's contestant list before "
        "it ever calls this, so it can always request the current version directly - the CDN then sees a "
        "distinct URL per version instead of long-caching one URL that silently goes stale when a finished "
        "contestant is rescored.",
    )
    @action(detail=True, methods=["get"], url_path=r"score_data/(?P<version>[^/]+)")
    def score_data_versioned(self, request, pk=None, version=None, **kwargs):
        return self.score_data(request, pk=pk, **kwargs)

    @extend_schema(
        responses={200: OpenApiTypes.OBJECT},
        description="Return consolidated score data, including compiled task payload and administrative penalties, for the contestant score view.",
    )
    @action(detail=True, methods=["get"])
    def score_data(self, request, *args, **kwargs):
        """
        Used by the front end to load initial data
        """
        contestant = self.get_object()  # This is important, this is where the object permissions are checked
        is_finished = hasattr(contestant, "contestanttrack") and contestant.contestanttrack.calculator_finished
        if not hasattr(contestant, "contestanttaskconfiguration"):
            from display.services.contestant_task_compiler import ContestantTaskCompiler

            ContestantTaskCompiler(contestant).compile(force=True)
        elif not contestant.contestanttaskconfiguration.is_valid:
            from display.services.contestant_task_compiler import ContestantTaskCompiler

            ContestantTaskCompiler(contestant).compile(force=True)

        # ETag based on contestant's track and score versions.
        # track_version only bumps on (re)start. score_version bumps on admin edits.
        # Short-circuiting with 304 is therefore only safe when the flight is finished.
        etag = f'"{contestant.pk}-{contestant.track_version}-{contestant.score_version}-scores"'
        if is_finished and request.META.get("HTTP_IF_NONE_MATCH") == etag:
            return Response(status=status.HTTP_304_NOT_MODIFIED)

        response = Response(generate_score_data(contestant.pk))

        is_public = contestant.navigation_task.is_public and contestant.navigation_task.contest.is_public

        if not is_public:
            response["Cache-Control"] = "private, no-cache"
        elif is_finished:
            response["ETag"] = etag
            # Finished scores are static.
            # s-maxage=31536000: CDN caches for 1 year (explicit invalidation)
            # max-age=0: Browser always checks CDN (no disk cache).
            response["Cache-Control"] = "public, max-age=0, s-maxage=31536000, stale-while-revalidate=86400"
        else:
            # Live scores change frequently.
            # No ETag sent to avoid stale 304s from CDN.
            # s-maxage=10: CDN shields origin by caching for 10 seconds.
            response["Cache-Control"] = "public, max-age=0, s-maxage=10, must-revalidate"

        if is_public and "Vary" in response:
            del response["Vary"]

        return response

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="minute_index",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description="Minute index to inspect",
            ),
            OpenApiParameter(
                name="count",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Number of contiguous one-minute slices to return. Must be between 1 and 60.",
            ),
        ],
        responses={200: OpenApiTypes.OBJECT},
        description="Return one or more cached minute-aligned telemetry slices for a contestant track.",
    )
    @action(detail=True, methods=["get"], url_path=r"slice/(?P<minute_index>\d+)")
    def slice(self, request, minute_index, **kwargs):
        contestant = self.get_object()
        minute_index = int(minute_index)
        try:
            count = int(request.query_params.get("count", 1))
        except (TypeError, ValueError):
            return Response({"detail": "count must be an integer."}, status=status.HTTP_400_BAD_REQUEST)

        # Cap count to bound the time range scanned per request.
        if count < 1 or count > 60:
            return Response(
                {"detail": "count must be between 1 and 60."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Enforce alignment for multi-minute chunks to ensure CDN cache hit consistency.
        # e.g. If count=15, minute_index must be 0, 15, 30, 45...
        if count > 1 and minute_index % count != 0:
            return Response(
                {
                    "detail": f"Multi-minute slices must be aligned to the count. {minute_index} is not a multiple of {count}."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        start_window = datetime.datetime.fromtimestamp(minute_index * 60, tz=datetime.timezone.utc)
        end_window = start_window + datetime.timedelta(seconds=60 * count)
        now = datetime.datetime.now(datetime.timezone.utc)

        # 1. LIGHTWEIGHT CHECK: Only fetch the count to build the ETag.
        # This query is fast because it can be satisfied by a composite index.
        positions_qs = contestant.contestantreceivedposition_set.filter(time__gte=start_window, time__lt=end_window)
        current_count = positions_qs.count()

        # 2. Determine if this specific slice is truly immutable.
        is_immutable = (hasattr(contestant, "contestanttrack") and contestant.contestanttrack.calculator_finished) or (
            contestant.finished_by_time and contestant.finished_by_time < now
        )

        # 3. Create a sensitive ETag including the count of positions.
        # If a new point is appended, the ETag breaks, making it safe to
        # allow 304 short-circuiting even for live slices.
        etag = f'"{contestant.pk}-{contestant.track_version}-{minute_index}-cnt{current_count}"'

        if request.META.get("HTTP_IF_NONE_MATCH") == etag:
            return Response(status=status.HTTP_304_NOT_MODIFIED)

        # 4. HEAVY LIFTING: Only runs if the cache is stale or missing.
        positions_list = list(
            positions_qs.values(
                "time", "latitude", "longitude", "speed", "course", "altitude", "progress", "interpolated"
            )
        )

        response = Response(positions_list)
        response["ETag"] = etag

        is_public = contestant.navigation_task.is_public and contestant.navigation_task.contest.is_public
        if not is_public:
            # Private telemetry must never reach the shared CDN cache.
            response["Cache-Control"] = "private, no-cache"
        elif is_immutable and current_count > 0:
            # ONLY cache for 1 year if it's immutable AND we actually have data.
            # If current_count is 0, someone might have requested a slice before the flight started.
            response["Cache-Control"] = "public, max-age=120, s-maxage=31536000, stale-while-revalidate=86400"
        else:
            # If the flight is ongoing, or the slice is empty, use short-term caching.
            response["Cache-Control"] = "public, max-age=5, s-maxage=10, must-revalidate"

        if is_public and "Vary" in response:
            # Remove Vary: Cookie for public responses to allow Google Cloud CDN caching
            # even when SessionAuthentication is active.
            del response["Vary"]

        return response

    @action(detail=True, methods=["get"])
    def paginated_track_data(self, request, *args, **kwargs):
        contestant: Contestant = (
            self.get_object()
        )  # This is important, this is where the object permissions are checked
        position_data = contestant.get_track()
        pagination = MyCursorPagination()
        page = pagination.paginate_queryset(
            position_data.values(
                "time", "latitude", "longitude", "speed", "course", "altitude", "progress", "interpolated"
            ),
            request,
        )
        if page is not None:
            if len(page):
                page[-1]["progress"] = contestant.calculate_progress(page[-1]["time"], ignore_finished=True)
            result = pagination.get_paginated_response(page)
            response = Response(result.data)
            if (
                pagination.get_next_link() is None
                and hasattr(contestant, "contestanttrack")
                and not contestant.contestanttrack.calculator_finished
            ):
                add_never_cache_headers(response)
            else:
                patch_response_headers(response, 60 * 60 * 24 * 31)
        else:
            # Manually serialize the positions to avoid PositionSerialiser overhead
            positions = position_data.values(
                "time", "latitude", "longitude", "speed", "course", "altitude", "progress", "interpolated"
            )
            if len(positions):
                positions = list(positions)
                positions[-1]["progress"] = contestant.calculate_progress(positions[-1]["time"], ignore_finished=True)
            response = Response(positions)

        return response

    def _stream_track_json(self, ct, position_queryset):
        encoder = DjangoJSONEncoder()
        yield (
            '{"id":'
            + json.dumps(ct.id)
            + ',"score":'
            + json.dumps(float(ct.score))
            + ',"current_state":'
            + json.dumps(ct.current_state)
            + ',"current_leg":'
            + json.dumps(ct.current_leg)
            + ',"last_gate":'
            + json.dumps(ct.last_gate)
            + ',"last_gate_time_offset":'
            + json.dumps(ct.last_gate_time_offset)
            + ',"passed_starting_gate":'
            + json.dumps(ct.passed_starting_gate)
            + ',"passed_finish_gate":'
            + json.dumps(ct.passed_finish_gate)
            + ',"calculator_finished":'
            + json.dumps(ct.calculator_finished)
            + ',"calculator_started":'
            + json.dumps(ct.calculator_started)
            + ',"contestant":'
            + json.dumps(ct.contestant_id)
            + ',"track":['
        )

        first = True
        for pos in position_queryset.iterator():
            if not first:
                yield ","
            yield encoder.encode(pos)
            first = False
        yield "]}"

    def _stream_positions_json(self, position_queryset, contestant):
        encoder = DjangoJSONEncoder()
        yield "["

        first = True
        pending_pos = None
        for pos in position_queryset.iterator():
            if pending_pos:
                if not first:
                    yield ","
                yield encoder.encode(pending_pos)
                first = False
            pending_pos = pos

        if pending_pos:
            if not first:
                yield ","
            pending_pos["progress"] = contestant.calculate_progress(pending_pos["time"], ignore_finished=True)
            yield encoder.encode(pending_pos)

        yield "]"

    @extend_schema(
        responses={200: OpenApiTypes.OBJECT},
        description="Alias for score_data that returns the contestant score payload expected by the score view.",
    )
    @action(detail=True, methods=["get"])
    def score(self, request, pk=None, **kwargs):
        """
        Returns the score for the contestant. This is a wrapper around score_data.
        """
        return self.score_data(request, pk=pk, **kwargs)

    @action(detail=True, methods=["get"])
    def track(self, request, pk=None, **kwargs):
        """
        Returns the GPS track for the contestant
        """
        contestant = self.get_object()  # This is important, this is where the object permissions are checked
        ct = contestant.contestanttrack

        position_data = contestant.get_track()
        positions_qs = position_data.values(
            "time", "latitude", "longitude", "speed", "course", "altitude", "progress", "interpolated"
        )

        response = StreamingHttpResponse(self._stream_track_json(ct, positions_qs), content_type="application/json")

        is_finished = ct.calculator_finished
        is_public = contestant.navigation_task.is_public and contestant.navigation_task.contest.is_public

        # ETag based on contestant's track version.
        # track_version only bumps on (re)start. Short-circuiting with 304 is
        # therefore only safe when the flight is finished.
        etag = f'"{contestant.pk}-{contestant.track_version}-track"'
        if is_finished and request.META.get("HTTP_IF_NONE_MATCH") == etag:
            return Response(status=status.HTTP_304_NOT_MODIFIED)

        if not is_public:
            response["Cache-Control"] = "private, no-cache"
        elif is_finished:
            response["ETag"] = etag
            # Finished tracks are static.
            response["Cache-Control"] = "public, max-age=0, s-maxage=31536000, stale-while-revalidate=86400"
        else:
            # Live tracks change as the flight progresses.
            # No ETag sent to avoid stale 304s from CDN.
            # s-maxage=10: CDN shields origin by caching for 10 seconds.
            response["Cache-Control"] = "public, max-age=0, s-maxage=10, must-revalidate"

        if is_public and "Vary" in response:
            del response["Vary"]

        return response

    @extend_schema(
        responses={
            200: inline_serializer(
                name="CompiledEvidenceResponse",
                fields={
                    "observation_photos": serializers.ListField(child=serializers.DictField(), required=True),
                    "observation_judging_mode": serializers.CharField(allow_null=True),
                    "manual_adjudication_categories": serializers.ListField(child=serializers.CharField()),
                    "hidden_gate_names": serializers.ListField(child=serializers.CharField()),
                    "unknown_leg_names": serializers.ListField(child=serializers.CharField()),
                },
            )
        },
        description="Return organizer-facing compiled evidence metadata derived from the contestant's effective route payload.",
    )
    @action(detail=True, methods=["get"])
    def compiled_evidence(self, request, pk=None, **kwargs):
        """Return organizer-facing compiled evidence metadata for the contestant."""
        contestant = self.get_object()
        from display.services.contestant_task_compiler import ContestantTaskCompiler

        declaration_payload = {}
        if hasattr(contestant, "contestanttaskconfiguration"):
            declaration_payload = contestant.contestanttaskconfiguration.declaration_payload or {}
        refreshed = ContestantTaskCompiler(contestant).compile(declaration_payload=declaration_payload, force=False)
        payload = refreshed.compiled_effective_route_payload or {}
        if payload:
            return Response(
                {
                    "observation_photos": [
                        {
                            **item,
                            "evidence_category": "observation",
                        }
                        for item in payload.get("observation_photos", [])
                    ],
                    "observation_judging_mode": payload.get("observation_judging_mode"),
                    "manual_adjudication_categories": payload.get("manual_adjudication_categories", []),
                    "hidden_gate_names": payload.get("hidden_gate_names", []),
                    "unknown_leg_names": payload.get("unknown_leg_names", []),
                }
            )
        return Response(
            {
                "observation_photos": [],
                "observation_judging_mode": None,
                "manual_adjudication_categories": [],
                "hidden_gate_names": [],
                "unknown_leg_names": [],
            }
        )

    @action(detail=True, methods=["post"])
    def gpx_track(self, request, pk=None, **kwargs):
        """
        Consumes a FC GPX file that contains the GPS track of a contestant.
        """
        contestant = self.get_object()  # This is important, this is where the object permissions are checked
        contestant.reset_track_and_score()
        track_file = request.data.get("track_file", None)
        if not track_file:
            raise drf_exceptions.ValidationError("Missing track_file")
        import_gpx_track.apply_async(
            (
                contestant.pk,
                base64.decodebytes(bytes(track_file, "utf-8")).decode("utf-8"),
            )
        )
        return Response({}, status=status.HTTP_201_CREATED)


class ImportFCNavigationTask(ModelViewSet):
    """
    This is a shortcut to post a new navigation task to the tracking system. It requires the existence of a contest to
    which it will belong. The entire task with contestants and their associated times, crews, and aircraft, together
    with the route can be posted to the single endpoint.

    route_file is a utf-8 string that contains a base 64 encoded gpx route file of the format that FC exports. A new
    route object will be created every time this function is called, but it is possible to reuse routes if
    required. This is currently not supported through this endpoint, but this may change in the future.
    """

    queryset = NavigationTask.objects.all()
    serializer_class = ExternalNavigationTaskNestedTeamSerialiser
    permission_classes = [permissions.IsAuthenticated & NavigationTaskContestPermissions]

    metadata_class = ShowChoicesMetadata

    http_method_names = ["post"]

    lookup_key = "contest_pk"

    def get_serializer_context(self):
        context = super().get_serializer_context()
        try:
            contest = get_object_or_404(Contest, pk=self.kwargs.get(self.lookup_key))
            context.update({"contest": contest})
        except Http404:
            # This has to be handled below
            pass
        return context

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        serialiser = self.get_serializer(data=request.data)
        if serialiser.is_valid(raise_exception=True):
            serialiser.save()
            return Response(serialiser.data, status=status.HTTP_201_CREATED)
        return Response(serialiser.errors, status=status.HTTP_400_BAD_REQUEST)


class ImportFCNavigationTaskTeamId(ImportFCNavigationTask):
    """
    This is a shortcut to post a new navigation task to the tracking system. It requires the existence of a contest to
    which it will belong. The entire task with contestants and their associated times, crews, and aircraft, together
    with the route can be posted to the single endpoint.

    route_file is a utf-8 string that contains a base 64 encoded gpx route file of the format that FC exports. A new
    route object will be created every time this function is called, but it is possible to reuse routes if
    required. This is currently not supported through this endpoint, but this may change in the future.
    """

    serializer_class = ExternalNavigationTaskTeamIdSerialiser


########## Results service ##########
class TaskViewSet(ModelViewSet):
    queryset = Task.objects.all()
    permission_classes = [TaskContestPublicPermissions | permissions.IsAuthenticated & TaskContestPermissions]
    serializer_class = TaskSerialiser

    def get_queryset(self):
        contest_id = self.kwargs.get("contest_pk")
        return Task.objects.filter(contest_id=contest_id)

    def destroy(self, request, *args, **kwargs):
        task = self.get_object()
        if task.tasktest_set.filter(navigation_task__isnull=False).exists():
            raise drf_exceptions.ValidationError(
                "Cannot delete a task that is linked to a navigation task. Delete the navigation task instead."
            )
        return super().destroy(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        task = self.get_object()
        if task.tasktest_set.filter(navigation_task__isnull=False).exists():
            raise drf_exceptions.ValidationError(
                "Cannot modify a task that is linked to a navigation task. Modify the navigation task instead."
            )
        return super().update(request, *args, **kwargs)


_CONTEST_NESTED_PATH_PARAMETERS = [
    OpenApiParameter(name="contest_pk", type=OpenApiTypes.INT, location=OpenApiParameter.PATH),
]


@extend_schema_view(
    list=extend_schema(parameters=_CONTEST_NESTED_PATH_PARAMETERS),
    create=extend_schema(parameters=_CONTEST_NESTED_PATH_PARAMETERS),
    retrieve=extend_schema(parameters=_CONTEST_NESTED_PATH_PARAMETERS),
    update=extend_schema(parameters=_CONTEST_NESTED_PATH_PARAMETERS),
    partial_update=extend_schema(parameters=_CONTEST_NESTED_PATH_PARAMETERS),
    destroy=extend_schema(parameters=_CONTEST_NESTED_PATH_PARAMETERS),
)
class TaskTestViewSet(ModelViewSet):
    queryset = TaskTest.objects.all()
    permission_classes = [TaskTestContestPublicPermissions | permissions.IsAuthenticated & TaskTestContestPermissions]
    serializer_class = TaskTestSerialiser

    def get_queryset(self):
        contest_id = self.kwargs.get("contest_pk")
        return TaskTest.objects.filter(task__contest_id=contest_id)

    def destroy(self, request, *args, **kwargs):
        task_test = self.get_object()
        if task_test.navigation_task_id is not None:
            raise drf_exceptions.ValidationError(
                "Cannot delete a test that is linked to a navigation task. Delete the navigation task instead."
            )
        return super().destroy(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        task_test = self.get_object()
        if task_test.navigation_task_id is not None:
            raise drf_exceptions.ValidationError(
                "Cannot modify a test that is linked to a navigation task. Modify the navigation task instead."
            )
        return super().update(request, *args, **kwargs)


class HighlightedContestViewSet(ReadOnlyModelViewSet):
    queryset = HighlightedContest.objects.all()
    serializer_class = HighlightedContestSerialiser
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        return HighlightedContest.objects.filter(
            start_time__lte=now, finish_time__gte=now, contest__is_public=True
        ).select_related("contest")


class NewsletterSubscriberViewSet(ModelViewSet):
    queryset = NewsletterSubscriber.objects.all()
    serializer_class = NewsletterSubscriberSerialiser
    permission_classes = [permissions.AllowAny]
    http_method_names = ["post"]
