import base64
import datetime
import logging

from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Q, Count
from django.http import Http404
from guardian.shortcuts import get_objects_for_user
from rest_framework import status, permissions, mixins
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet, ModelViewSet, ReadOnlyModelViewSet
import rest_framework.exceptions as drf_exceptions

from display.tasks import (
    import_gpx_track,
    generate_and_maybe_notify_flight_order,
)

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
)
from display.serialisers import (
    NavigationTasksSummarySerialiser,
    ContestTeamManagementSerialiser,
    PersonSerialiser,
    EditableRouteSerialiser,
    ContestFrontEndSerialiser,
    ContestTeamNestedSerialiser,
    ContestSummaryWithoutReferenceSerialiser,
    TaskSummaryWithoutReferenceSerialiser,
    TeamTestScoreWithoutReferenceSerialiser,
    ContestResultsDetailsSerialiser,
    OngoingNavigationSerialiser,
    SignupSerialiser,
    SharingSerialiser,
    ContestSerialiserWithResults,
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
)
from display.utilities.show_slug_choices import ShowChoicesMetadata
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
    def my_participating_contests(self, request, *args, **kwargs):
        available_contests = Contest.visible_contests_for_user(request.user).filter(
            finish_time__gte=datetime.datetime.now(datetime.timezone.utc)
        )
        # for authorisation
        _ = self.get_object()
        contest_teams = (
            ContestTeam.objects.filter(
                Q(team__crew__member1=self.get_object()) | Q(team__crew__member2=self.get_object()),
                contest__in=available_contests,
            )
            .order_by("contest__start_time")
            .distinct()
        )
        teams = []
        for team in contest_teams:
            team.can_edit = team.team.crew.member1 == self.get_object()
            teams.append(team)
        return Response(ContestTeamManagementSerialiser(teams, many=True, context={"request": request}).data)

    @action(detail=False, methods=["patch"])
    def partial_update_profile(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update_profile(request, *args, **kwargs)

    @action(detail=False, methods=["get"])
    def retrieve_profile(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def get_current_sim_navigation_task(self, request, *args, **kwargs):
        person = self.get_object()
        contestant, _ = Contestant.get_contestant_for_device_at_time(
            person.simulator_tracking_id, datetime.datetime.now(datetime.timezone.utc)
        )
        if not contestant:
            raise Http404
        return Response(NavigationTasksSummarySerialiser(instance=contestant.navigation_task).data)

    @action(detail=False, methods=["get"])
    def get_current_app_navigation_task(self, request, *args, **kwargs):
        person = self.get_object()
        contestant, _ = Contestant.get_contestant_for_device_at_time(
            person.simulator_tracking_id, datetime.datetime.now(datetime.timezone.utc)
        )
        if not contestant:
            raise Http404
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


class ContestFrontEndViewSet(mixins.ListModelMixin, GenericViewSet):
    """
    Internal endpoint to drive the contest list front end
    """

    queryset = Contest.objects.all()
    serializer_class = ContestFrontEndSerialiser

    permission_classes = [(permissions.IsAuthenticated & ContestPermissions)]

    def get_queryset(self):
        return (
            get_objects_for_user(
                self.request.user,
                "display.view_contest",
                klass=self.queryset,
                accept_global_perms=False,
            )
            .annotate(Count("navigationtask", distinct=True))
            .order_by("name")
        )


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
        "results": ContestSerialiserWithResults,
    }
    default_serialiser_class = ContestSerialiser
    lookup_url_kwarg = "pk"

    permission_classes = [ContestPublicPermissions | (permissions.IsAuthenticated & ContestPermissions)]

    def get_serializer_class(self):
        return self.serializer_classes.get(self.action, self.default_serialiser_class)

    def get_queryset(self):
        return (
            get_objects_for_user(
                self.request.user,
                "display.view_contest",
                klass=self.queryset,
                accept_global_perms=False,
            )
            | self.queryset.filter(is_public=True, is_featured=True)
        ).prefetch_related("navigationtask_set", "contest_teams")

    @action(detail=True, methods=["get"], url_path=r"contest_team_for_team/(?P<team_id>\d+)")
    def contest_team_for_team(self, request, team_id, **kwargs):
        """Get the ContestTeam that matches the Team id"""
        return Response(
            ContestTeamSerialiser(instance=ContestTeam.objects.get(contest=self.get_object(), team=team_id)).data
        )

    @action(detail=False, methods=["get"])
    def results(self, request, *args, **kwargs):
        """
        Get contests with ContestResults. Used by the main page in the results service, ContestSummaryResultsTable.
        This data replaces the original contest data in the redux storage, so it must use a serialiser that includes
        all the original data.
        """
        data = self.get_serializer_class()(self.get_queryset(), many=True, context={"request": self.request}).data
        return Response(data)

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
        navigation_tasks = (
            NavigationTask.get_visible_navigation_tasks(self.request.user)
            .filter(
                contestant__contestanttrack__calculator_started=True,
                contestant__contestanttrack__calculator_finished=False,
                contestant__finished_by_time__gt=datetime.datetime.now(datetime.timezone.utc),
            )
            .distinct()
        )
        data = self.get_serializer_class()(navigation_tasks, many=True, context={"request": self.request}).data
        return Response(data)

    @action(detail=True, methods=["get"])
    def results_details(self, request, *args, **kwargs):
        """
        Retrieve the full list of contest summaries, tasks summaries, and individual test results for the contest
        """
        contest = self.get_object()
        contest.permission_change_contest = request.user.has_perm("display.change_contest", contest)
        serialiser = ContestResultsDetailsSerialiser(contest)
        return Response(serialiser.data)

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
                f"You are currently participating in at least one navigation task. Cancel all flights before you can withdraw from the contest"
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
        return context


class TeamViewSet(ModelViewSet):
    queryset = Team.objects.all()
    serializer_class = TeamNestedSerialiser
    permission_classes = [permissions.IsAuthenticated & OrganiserPermission]

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

    permission_classes = [
        NavigationTaskPublicPermissions | (permissions.IsAuthenticated & NavigationTaskContestPermissions)
    ]

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
        methods=["put", "delete"],
        permission_classes=[
            permissions.IsAuthenticated
            & NavigationTaskSelfManagementPermissions
            & (NavigationTaskPublicPutDeletePermissions | NavigationTaskContestPermissions)
        ],
    )
    def contestant_self_registration(self, request, *args, **kwargs):
        navigation_task = self.get_object()  # type: NavigationTask
        if request.method == "PUT":
            serialiser = self.get_serializer(data=request.data)
            serialiser.is_valid(raise_exception=True)
            contest_team = serialiser.validated_data["contest_team"]
            if contest_team.team.crew.member1.email != request.user.email:
                raise drf_exceptions.ValidationError("You cannot add a team where you are not the pilot")
            starting_point_time = serialiser.validated_data["starting_point_time"].astimezone(
                navigation_task.contest.time_zone
            )  # type: datetime
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
            final_time = contestant.get_final_gate_time()
            if final_time is None:
                final_time = starting_point_time
            if adaptive_start:
                # Properly account for how final time is created when adaptive start is active
                final_time = (
                    starting_point_time
                    + datetime.timedelta(hours=1)
                    + datetime.timedelta(
                        hours=final_time.hour,
                        minutes=final_time.minute,
                        seconds=final_time.second,
                    )
                )
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
            return Response(status=status.HTTP_201_CREATED)
        elif request.method == "DELETE":
            my_contestants = navigation_task.contestant_set.filter(team__crew__member1__email=request.user.email)
            # Delete all contestants that have not started yet where I am the pilot
            my_contestants.filter(
                contestanttrack__calculator_started=False,
            ).delete()
            # If the contestant has not reached the takeoff time, delete the contestant
            my_contestants.filter(
                takeoff_time__gte=datetime.datetime.now(datetime.timezone.utc),
            ).delete()
            # Terminate ongoing contestants where the time has passed the takeoff time
            for c in my_contestants.filter(
                finished_by_time__gt=datetime.datetime.now(datetime.timezone.utc),
                contestanttrack__calculator_started=True,
            ):
                # We know the takeoff time is in the past, so we can freely set it to now.
                c.finished_by_time = datetime.datetime.now(datetime.timezone.utc)
                c.save()
                c.request_calculator_termination()
            return Response(status=status.HTTP_204_NO_CONTENT)

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


def cached_generate_data(contestant_pk) -> dict:
    return _generate_data(contestant_pk)


def _generate_data(contestant_pk):
    contestant = get_object_or_404(Contestant, pk=contestant_pk)  # type: Contestant
    logger.debug("Fetching track for {} {}".format(contestant.pk, contestant))
    # Do not include track if we have not started a calculator yet
    position_data = (
        contestant.get_track()
        if hasattr(contestant, "contestanttrack") and contestant.contestanttrack.calculator_started
        else []
    )
    if len(position_data) > 0:
        global_latest_time = position_data[-1].time
    else:
        global_latest_time = datetime.datetime(2016, 1, 1, tzinfo=datetime.timezone.utc)
    progress = 0
    for index, item in enumerate(position_data):
        if index % 30 == 0:
            progress = contestant.calculate_progress(item.time, ignore_finished=True)
        item.progress = progress
    logger.debug(
        "Completed generating data {} {} with {} positions".format(contestant.pk, contestant, len(position_data))
    )
    data = generate_contestant_data_block(
        contestant,
        positions=PositionSerialiser(position_data, many=True).data,
        annotations=TrackAnnotationSerialiser(contestant.trackannotation_set.all(), many=True).data,
        log_entries=ScoreLogEntrySerialiser(contestant.scorelogentry_set.filter(type=ANOMALY), many=True).data,
        latest_time=global_latest_time,
        gate_scores=GateCumulativeScoreSerialiser(contestant.gatecumulativescore_set.all(), many=True).data,
        playing_cards=PlayingCardSerialiser(contestant.playingcard_set.all(), many=True).data,
        include_contestant_track=True,
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
    def initial_track_data(self, request, *args, **kwargs):
        """
        Used by the front end to load initial data
        """
        contestant = self.get_object()  # This is important, this is where the object permissions are checked
        return Response(cached_generate_data(contestant.pk))

    @action(detail=True, methods=["get"])
    def track(self, request, pk=None, **kwargs):
        """
        Returns the GPS track for the contestant
        """
        contestant = self.get_object()  # This is important, this is where the object permissions are checked
        contestant_track = contestant.contestanttrack

        position_data = contestant.get_track()
        contestant_track.track = position_data
        serialiser = ContestantTrackWithTrackPointsSerialiser(contestant_track)
        return Response(serialiser.data)

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
