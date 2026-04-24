import base64
from collections import OrderedDict
import datetime
import logging
import hashlib
import json
import csv

from django.core.cache import cache
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Q, Prefetch
from django.http import Http404, HttpResponse, StreamingHttpResponse
from django.core.serializers.json import DjangoJSONEncoder
from django.utils.cache import add_never_cache_headers, patch_response_headers
from guardian.shortcuts import get_objects_for_user
from rest_framework import status, permissions
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.pagination import CursorPagination
from rest_framework.viewsets import GenericViewSet, ModelViewSet, ReadOnlyModelViewSet
import rest_framework.exceptions as drf_exceptions
from urllib import parse

from django_filters.rest_framework import DjangoFilterBackend

from display.filters import ContestFilter, NavigationTaskFilter
from display.tasks import (
    import_gpx_track,
    generate_and_maybe_notify_flight_order,
)
from display.contestant_scheduling.schedule_contestants import schedule_and_create_contestants
import dateutil.parser

from display.models import (
    Person,
    Contest,
    ContestTeam,
    Contestant,
    EditableRoute,
    NavigationTask,
    ContestSummary,
    TaskSummary,
    TeamTestScore,
    Team,
    Scorecard,
    Route,
    Aeroplane,
    Club,
    ANOMALY,
    Task,
    TaskTest,
)
from display.permissions import (
    EditableRoutePermission,
    ContestPermissions,
    ContestPublicPermissions,
    ContestPublicModificationPermissions,
    OrganiserPermission,
    ContestTeamContestPermissions,
    NavigationTaskPublicPermissions,
    NavigationTaskContestPermissions,
    NavigationTaskSelfManagementPermissions,
    NavigationTaskPublicPutDeletePermissions,
    RoutePermissions,
    ContestantPublicPermissions,
    ContestantNavigationTaskContestPermissions,
    TaskContestPublicPermissions,
    TaskContestPermissions,
    TaskTestContestPublicPermissions,
    TaskTestContestPermissions,
    TeamPermissions,
)
from display.serialisers import (
    ContestantTrackSerialiser,
    NavigationTaskNestedTeamRouteSerialiserNestedContest,
    NavigationTasksSummarySerialiser,
    ContestTeamManagementSerialiser,
    PersonSerialiser,
    EditableRouteSerialiser,
    ContestTeamNestedSerialiser,
    ContestSummaryWithoutReferenceSerialiser,
    TaskSummaryWithoutReferenceSerialiser,
    TeamTestScoreWithoutReferenceSerialiser,
    ContestResultsDetailsSerialiser,
    OngoingNavigationSerialiser,
    SignupSerialiser,
    SharingSerialiser,
    ContestSerialiser,
    ContestTeamSerialiser,
    TeamNestedSerialiser,
    ScorecardNestedSerialiser,
    SelfManagementSerialiser,
    NavigationTaskEditableRoutReferenceSerialiser,
    NavigationTaskNestedTeamRouteSerialiser,
    RouteSerialiser,
    AeroplaneSerialiser,
    ClubSerialiser,
    ContestantSerialiser,
    ContestantTrackWithTrackPointsSerialiser,
    GpxTrackSerialiser,
    ContestantNestedTeamSerialiserWithContestantTrack,
    ExternalNavigationTaskNestedTeamSerialiser,
    ExternalNavigationTaskTeamIdSerialiser,
    GateCumulativeScoreSerialiser,
    PlayingCardSerialiser,
    PositionSerialiser,
    TrackAnnotationSerialiser,
    ScoreLogEntrySerialiser,
    TaskSerialiser,
    TaskTestSerialiser,
    ContestantNestedTeamSerialiser,
    FutureContestantNestedTeamSerialiser,
)
from display.utilities.show_slug_choices import ShowChoicesMetadata
from display.utilities.tracking_definitions import TrackingService
from websocket_channels import WebsocketFacade, generate_contestant_data_block

logger = logging.getLogger(__name__)


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
        contestants = Contestant.get_contestant_for_device_at_time(
            TrackingService.TRACCAR, person.simulator_tracking_id, datetime.datetime.now(datetime.timezone.utc)
        )
        if not contestants:
            raise Http404
        contestant, _ = contestants[0]
        return Response(NavigationTasksSummarySerialiser(instance=contestant.navigation_task).data)

    @action(detail=False, methods=["get"])
    def get_current_app_navigation_task(self, request, *args, **kwargs):
        person = self.get_object()
        contestants = Contestant.get_contestant_for_device_at_time(
            TrackingService.TRACCAR, person.simulator_tracking_id, datetime.datetime.now(datetime.timezone.utc)
        )
        if not contestants:
            raise Http404
        contestant, _ = contestants[0]
        return Response(NavigationTasksSummarySerialiser(instance=contestant.navigation_task).data)

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

    def get_queryset(self):
        return get_objects_for_user(
            self.request.user,
            "display.view_editableroute",
            klass=self.queryset,
            accept_global_perms=False,
        ).order_by("name")

    def perform_update(self, serializer):
        super().perform_update(serializer)
        self.get_object().update_thumbnail()

    def perform_create(self, serializer):
        super().perform_create(serializer)
        try:
            serializer.instance.thumbnail.save(
                serializer.instance.name + "_thumbnail.png",
                ContentFile(serializer.instance.create_thumbnail().getvalue()),
                save=True,
            )
        except:
            logger.exception("Failed creating editable route thumbnail")


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
        version = cache.get("contest_list_version", 1)

        # ETag based on global version and object ID
        etag = f'"{version}-contest-{instance.pk}"'
        if request.META.get("HTTP_IF_NONE_MATCH") == etag:
            return Response(status=status.HTTP_304_NOT_MODIFIED)

        response = super().retrieve(request, *args, **kwargs)

        response["ETag"] = etag
        if instance.is_public and instance.is_featured:
            response["Cache-Control"] = "public, max-age=60, s-maxage=3600, stale-while-revalidate=86400"
        else:
            response["Cache-Control"] = "private, no-cache"
        return response

    permission_classes = [ContestPublicPermissions | (permissions.IsAuthenticated & ContestPermissions)]
    filter_backends = [DjangoFilterBackend]
    filterset_class = ContestFilter

    def list(self, request, *args, **kwargs):
        public_only = request.query_params.get("public_only", "false").lower() == "true"
        user_id = "global" if public_only else (request.user.id if request.user.is_authenticated else "anon")
        params = request.query_params.dict()
        sorted_params = json.dumps(params, sort_keys=True)
        params_hash = hashlib.md5(sorted_params.encode("utf-8")).hexdigest()

        version = cache.get("contest_list_version", 1)

        # 1. ETag check (Browser/CDN level validation)
        # The ETag represents a specific version of a specific query
        etag = f'"{version}-{params_hash}"'
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
        if public_only:
            # Public data can be cached by CDN and shared between users.
            # s-maxage=3600: CDN caches for 1 hour
            # stale-while-revalidate=86400: Serve stale data while fetching fresh in background
            response["Cache-Control"] = "public, max-age=60, s-maxage=3600, stale-while-revalidate=86400"
        else:
            # Private data must NOT be cached by CDN or shared.
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

        return queryset.prefetch_related(
            "navigationtask_set__route__prohibited_set",
            "contestteam_set__team__crew__member1",
        ).order_by("-start_time")

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
        if serialiser.is_valid():
            if serialiser.validated_data["visibility"] == serialiser.PUBLIC:
                contest.make_public()
            elif serialiser.validated_data["visibility"] == serialiser.PRIVATE:
                contest.make_private()
            elif serialiser.validated_data["visibility"] == serialiser.UNLISTED:
                contest.make_unlisted()
        return Response(serialiser.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"])
    def ongoing_navigation(self, request, *args, **kwargs):
        version = cache.get("contest_list_version", 1)
        etag = f'"{version}-ongoing"'
        if request.META.get("HTTP_IF_NONE_MATCH") == etag:
            return Response(status=status.HTTP_304_NOT_MODIFIED)

        # Synchronize with OngoingNavigationSerialiser definition of 'active'
        navigation_tasks = (
            NavigationTask.get_visible_navigation_tasks(self.request.user)
            .filter(
                contestant__contestanttrack__calculator_started=True,
                contestant__contestanttrack__calculator_finished=False,
            )
            .distinct()
        )

        # Optimize N+1
        active_contestants_prefetch = Prefetch(
            "contestant_set",
            queryset=Contestant.objects.filter(
                contestanttrack__calculator_started=True, contestanttrack__calculator_finished=False
            ).select_related("team__crew__member1", "team__aeroplane", "contestanttrack"),
            to_attr="prefetched_active_contestants",
        )

        navigation_tasks = navigation_tasks.prefetch_related("contest", active_contestants_prefetch)

        data = self.get_serializer_class()(navigation_tasks, many=True, context={"request": self.request}).data
        response = Response(data)
        response["ETag"] = etag
        # This is a public-facing list of live tasks, safe to cache at edge but revalidate often
        response["Cache-Control"] = "public, max-age=30, s-maxage=60, stale-while-revalidate=300"
        return response

    @action(detail=True, methods=["get"])
    def results_details(self, request, *args, **kwargs):
        """
        Retrieve the full list of contest summaries, tasks summaries, and individual test results for the contest
        """
        contest = self.get_object()
        version = cache.get("contest_list_version", 1)
        etag = f'"{version}-results-{contest.pk}"'
        if request.META.get("HTTP_IF_NONE_MATCH") == etag:
            return Response(status=status.HTTP_304_NOT_MODIFIED)

        contest.permission_change_contest = request.user.has_perm("display.change_contest", contest)
        serialiser = ContestResultsDetailsSerialiser(contest)
        response = Response(serialiser.data)
        response["ETag"] = etag
        if contest.is_public and contest.is_featured:
            response["Cache-Control"] = "public, max-age=60, s-maxage=3600, stale-while-revalidate=86400"
        else:
            response["Cache-Control"] = "private, no-cache"
        return response

    @action(detail=True, methods=["get"])
    def results_csv(self, request, *args, **kwargs):
        """
        Download contest results as CSV
        """
        contest = self.get_object()
        version = cache.get("contest_list_version", 1)
        etag = f'"{version}-results-csv-{contest.pk}"'
        if request.META.get("HTTP_IF_NONE_MATCH") == etag:
            return Response(status=status.HTTP_304_NOT_MODIFIED)

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
        response["ETag"] = etag
        if contest.is_public and contest.is_featured:
            response["Cache-Control"] = "public, max-age=60, s-maxage=3600, stale-while-revalidate=86400"
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
        contest_teams = ContestTeam.objects.filter(contest=pk)
        return Response(ContestTeamNestedSerialiser(contest_teams, many=True).data)

    @action(detail=True, methods=["put"])
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

    @action(detail=True, methods=["put"])
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

    @action(detail=True, methods=["put"])
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

    @action(detail=True, methods=["post"])
    def team_results_delete(self, request, *args, **kwargs):
        contest = self.get_object()
        team_id = request.data["team_id"]
        ContestTeam.objects.filter(contest=contest, team__pk=team_id).delete()
        ContestSummary.objects.filter(contest=contest, team__pk=team_id).delete()
        ws = WebsocketFacade()
        ws.transmit_contest_results(request.user, contest)
        ws.transmit_teams(contest)
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
        serialiser.is_valid()
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
        version = cache.get("contest_list_version", 1)

        # ETag based on global version and object ID
        etag = f'"{version}-navtask-{instance.pk}"'
        if request.META.get("HTTP_IF_NONE_MATCH") == etag:
            return Response(status=status.HTTP_304_NOT_MODIFIED)

        response = super().retrieve(request, *args, **kwargs)

        response["ETag"] = etag
        if instance.is_public and instance.contest.is_public and instance.is_featured:
            response["Cache-Control"] = "public, max-age=60, s-maxage=3600, stale-while-revalidate=86400"
        else:
            response["Cache-Control"] = "private, no-cache"
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
            serialiser.is_valid()
            serialiser.save()
            return Response(serialiser.data, status=status.HTTP_200_OK)
        else:
            serialiser = self.get_serializer(instance=navigation_task.scorecard)
            return Response(serialiser.data, status=status.HTTP_200_OK)

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[permissions.IsAuthenticated & NavigationTaskContestPermissions],
    )
    def schedule_contestants(self, request, pk=None, **kwargs):
        navigation_task = self.get_object()
        data = request.data

        try:
            contest_teams_pks = data.get("contest_teams", [])

            first_takeoff_time = dateutil.parser.parse(data.get("first_takeoff_time"))
            if first_takeoff_time.tzinfo is None:
                first_takeoff_time = first_takeoff_time.replace(tzinfo=navigation_task.contest.time_zone)

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
            )

            if success:
                return Response({"status": "success", "messages": messages})
            else:
                return Response({"status": "error", "messages": messages}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.exception("Scheduling failed")
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

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
        try:
            my_contestant = get_object_or_404(navigation_task.contestant_set, pk=kwargs["contestant_id"])
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
        if serialiser.is_valid():
            if serialiser.validated_data["visibility"] == serialiser.PUBLIC:
                navigation_task.make_public()
            elif serialiser.validated_data["visibility"] == serialiser.PRIVATE:
                navigation_task.make_private()
            elif serialiser.validated_data["visibility"] == serialiser.UNLISTED:
                navigation_task.make_unlisted()
        return Response(serialiser.data, status=status.HTTP_200_OK)


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


class ClubViewSet(ModelViewSet):
    queryset = Club.objects.all()
    serializer_class = ClubSerialiser
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get"]


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

    return data


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
        contests = get_objects_for_user(
            self.request.user,
            "display.change_contest",
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
            serialiser.save()
            return Response(serialiser.data)
        return Response(serialiser.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["put", "patch"])
    def update_with_team(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @action(detail=True, methods=["get"])
    def score_data(self, request, *args, **kwargs):
        """
        Used by the front end to load initial data
        """
        contestant = self.get_object()  # This is important, this is where the object permissions are checked

        # ETag based on contestant's track version
        etag = f'"{contestant.pk}-{contestant.track_version}-scores"'
        if request.META.get("HTTP_IF_NONE_MATCH") == etag:
            return Response(status=status.HTTP_304_NOT_MODIFIED)

        response = Response(generate_score_data(contestant.pk))
        response["ETag"] = etag

        # Cache-Control:
        # If public, cache at edge but revalidate (stale-while-revalidate)
        # If private, don't cache at edge.
        is_public = contestant.navigation_task.is_public and contestant.navigation_task.contest.is_public
        if is_public:
            response["Cache-Control"] = "public, max-age=60, s-maxage=3600, stale-while-revalidate=86400"
        else:
            response["Cache-Control"] = "private, no-cache"

        return response

    @action(detail=True, methods=["get"], url_path=r"slice/(?P<minute_index>\d+)")
    def slice(self, request, minute_index, **kwargs):
        contestant = self.get_object()
        minute_index = int(minute_index)
        count = int(request.query_params.get("count", 1))

        # Enforce alignment for multi-minute chunks to ensure CDN cache hit consistency.
        # e.g. If count=15, minute_index must be 0, 15, 30, 45...
        if count > 1 and minute_index % count != 0:
            return Response(
                {
                    "detail": f"Multi-minute slices must be aligned to the count. {minute_index} is not a multiple of {count}."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ETag includes the count to distinguish between single minutes and chunks
        etag = f'"{contestant.pk}-{contestant.track_version}-{minute_index}-c{count}"'
        if request.META.get("HTTP_IF_NONE_MATCH") == etag:
            return Response(status=status.HTTP_304_NOT_MODIFIED)

        start_window = datetime.datetime.fromtimestamp(minute_index * 60, tz=datetime.timezone.utc)
        end_window = start_window + datetime.timedelta(seconds=60 * count)

        positions = contestant.contestantreceivedposition_set.filter(
            time__gte=start_window, time__lt=end_window
        ).values("time", "latitude", "longitude", "speed", "course", "altitude", "progress", "interpolated")

        response = Response(list(positions))
        response["ETag"] = etag

        now = datetime.datetime.now(datetime.timezone.utc)
        if end_window < now - datetime.timedelta(minutes=1):
            # Completed historical chunk - cache for a long time
            response["Cache-Control"] = "public, max-age=60, s-maxage=31536000, stale-while-revalidate=86400"
        else:
            # Active or future chunk - cache for a short time
            response["Cache-Control"] = "public, max-age=5, must-revalidate"

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
        yield '{"id":' + json.dumps(ct.id) + ',"score":' + json.dumps(
            float(ct.score)
        ) + ',"current_state":' + json.dumps(ct.current_state) + ',"current_leg":' + json.dumps(
            ct.current_leg
        ) + ',"last_gate":' + json.dumps(
            ct.last_gate
        ) + ',"last_gate_time_offset":' + json.dumps(
            ct.last_gate_time_offset
        ) + ',"passed_starting_gate":' + json.dumps(
            ct.passed_starting_gate
        ) + ',"passed_finish_gate":' + json.dumps(
            ct.passed_finish_gate
        ) + ',"calculator_finished":' + json.dumps(
            ct.calculator_finished
        ) + ',"calculator_started":' + json.dumps(
            ct.calculator_started
        ) + ',"contestant":' + json.dumps(
            ct.contestant_id
        ) + ',"track":['

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

    @action(detail=True, methods=["get"])
    def score(self, request, pk=None, **kwargs):
        """
        Returns the score for the contestant
        """
        contestant = self.get_object()  # This is important, this is where the object permissions are checked
        return Response(generate_score_data(contestant.pk))

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
            # Use streaming to avoid memory spikes
            positions_qs = position_data.values(
                "time", "latitude", "longitude", "speed", "course", "altitude", "progress", "interpolated"
            )
            response = StreamingHttpResponse(
                self._stream_positions_json(positions_qs, contestant), content_type="application/json"
            )

        return response

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
        return response

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


class TaskTestViewSet(ModelViewSet):
    queryset = TaskTest.objects.all()
    permission_classes = [TaskTestContestPublicPermissions | permissions.IsAuthenticated & TaskTestContestPermissions]
    serializer_class = TaskTestSerialiser

    def get_queryset(self):
        contest_id = self.kwargs.get("contest_pk")
        return TaskTest.objects.filter(task__contest_id=contest_id)
