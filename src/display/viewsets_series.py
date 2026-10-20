"""REST API of series (see display/services/series.py for the rules and series_standings.py for the standings)."""

import csv

from django.http import Http404, HttpResponse
from django.utils.text import slugify
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, permissions, serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from display.models import Contest, MyUser, Series, SeriesContest, SeriesContestRequest
from display.serialisers import ContestPermissionGrantCreateSerialiser
from display.services import series as series_rules
from display.services.people_search import user_identities
from display.services.series_permissions import (
    list_series_permission_grants,
    remove_series_permission_grant,
    set_series_permission_level,
)
from display.services.series_standings import series_standings


def csv_safe(value: str) -> str:
    """Names are typed in by users: a spreadsheet would run one that starts like a formula."""
    return "'" + value if value[:1] in ("=", "+", "-", "@", "\t", "\r") else value


class SeriesLegSerialiser(serializers.Serializer):
    contest_id = serializers.IntegerField(source="contest.pk", read_only=True)
    name = serializers.CharField(source="contest.name", read_only=True)
    start_time = serializers.DateTimeField(source="contest.start_time", read_only=True)
    is_public = serializers.BooleanField(source="contest.is_public", read_only=True)
    leg_number = serializers.IntegerField()
    weight = serializers.FloatField()


class SeriesSerialiser(serializers.ModelSerializer):
    can_manage = serializers.SerializerMethodField()
    can_delete = serializers.SerializerMethodField()
    leg_count = serializers.SerializerMethodField()

    class Meta:
        model = Series
        fields = (
            "id",
            "name",
            "description",
            "is_public",
            "scoring_method",
            "entrant_identity",
            "best_results_counted",
            "points_table",
            "created_at",
            "can_manage",
            "can_delete",
            "leg_count",
        )
        read_only_fields = ("id", "created_at", "can_manage", "can_delete", "leg_count")

    def get_can_manage(self, series) -> bool:
        return series_rules.can_manage(self.context["request"].user, series)

    def get_can_delete(self, series) -> bool:
        user = self.context["request"].user
        return bool(user and user.is_authenticated and user.has_perm("display.delete_series", series))

    def get_leg_count(self, series) -> int:
        return series.seriescontest_set.count()


class SeriesDetailSerialiser(SeriesSerialiser):
    legs = serializers.SerializerMethodField()

    class Meta(SeriesSerialiser.Meta):
        fields = SeriesSerialiser.Meta.fields + ("legs",)
        read_only_fields = fields

    def get_legs(self, series) -> list:
        links = series.seriescontest_set.select_related("contest")
        return SeriesLegSerialiser(links, many=True).data


class SeriesRequestSerialiser(serializers.ModelSerializer):
    series_id = serializers.IntegerField(source="series.pk", read_only=True)
    series_name = serializers.CharField(source="series.name", read_only=True)
    contest_id = serializers.IntegerField(source="contest.pk", read_only=True)
    contest_name = serializers.CharField(source="contest.name", read_only=True)
    requested_by_name = serializers.SerializerMethodField()
    can_answer = serializers.SerializerMethodField()
    can_cancel = serializers.SerializerMethodField()

    class Meta:
        model = SeriesContestRequest
        fields = (
            "id",
            "series_id",
            "series_name",
            "contest_id",
            "contest_name",
            "from_side",
            "status",
            "requested_by_name",
            "created_at",
            "can_answer",
            "can_cancel",
        )
        read_only_fields = fields

    def get_requested_by_name(self, request) -> str:
        user = request.requested_by
        return f"{user.first_name} {user.last_name}".strip() if user else ""

    def get_can_answer(self, request) -> bool:
        return series_rules.can_answer(request, self.context["request"].user)

    def get_can_cancel(self, request) -> bool:
        return series_rules.can_cancel(request, self.context["request"].user)


class EnrolSerialiser(serializers.Serializer):
    series = serializers.IntegerField()
    contest = serializers.IntegerField()


def enrolment_response(outcome, request) -> Response:
    """201 with the leg when the contest was added at once, 202 with the request when the other side must answer."""
    if isinstance(outcome, SeriesContest):
        return Response(SeriesLegSerialiser(outcome).data, status=status.HTTP_201_CREATED)
    return Response(
        SeriesRequestSerialiser(outcome, context={"request": request}).data, status=status.HTTP_202_ACCEPTED
    )


class AddLegSerialiser(serializers.Serializer):
    contest = serializers.IntegerField()
    leg_number = serializers.IntegerField(required=False, min_value=0)
    weight = serializers.FloatField(required=False, default=1)


class UpdateLegSerialiser(serializers.Serializer):
    leg_number = serializers.IntegerField(required=False, min_value=0)
    weight = serializers.FloatField(required=False)


class SeriesViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    GenericViewSet,
):
    """The series the user can see: the public ones, and the ones they manage."""

    serializer_class = SeriesSerialiser
    http_method_names = ["get", "post", "put", "patch", "delete"]
    pagination_class = None

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        # Includes every series of a contest the user manages, also private ones, so a leg can always see it and leave it
        queryset = series_rules.visible_series(self.request.user)
        contest = self.request.query_params.get("contest")
        if contest and contest.isdigit():
            queryset = queryset.filter(contests=int(contest))
        queryset = queryset.distinct()
        if self.request.query_params.get("managed", "").lower() == "true" and self.request.user.is_authenticated:
            queryset = queryset.filter(pk__in=[s.pk for s in queryset if series_rules.can_manage(self.request.user, s)])
        return queryset

    def get_serializer_class(self):
        if self.action == "retrieve":
            return SeriesDetailSerialiser
        if self.action == "contests":
            return AddLegSerialiser
        if self.action == "contest":
            return UpdateLegSerialiser
        return SeriesSerialiser

    def create(self, request, *args, **kwargs):
        serialiser = self.get_serializer(data=request.data)
        serialiser.is_valid(raise_exception=True)
        series = series_rules.create_series(request.user, **serialiser.validated_data)
        return Response(SeriesSerialiser(series, context={"request": request}).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        series = self.get_object()
        serialiser = self.get_serializer(series, data=request.data, partial=True)
        serialiser.is_valid(raise_exception=True)
        series = series_rules.update_series(series, request.user, **serialiser.validated_data)
        return Response(SeriesSerialiser(series, context={"request": request}).data)

    def update(self, request, *args, **kwargs):
        # PUT is only allowed for the permissions routes; the series itself is changed with PATCH, through the rules
        return self.partial_update(request, *args, **kwargs)

    def perform_destroy(self, instance):
        series_rules.delete_series(instance, self.request.user)

    @staticmethod
    def _cache_headers(series: Series, response):
        if series.is_public:
            # The same for everybody, and it changes as the legs are scored.
            # s-maxage=60: the CDN shields the origin by caching for a minute. max-age=0: browsers always check.
            response["Cache-Control"] = "public, max-age=0, s-maxage=60, stale-while-revalidate=600"
        else:
            response["Cache-Control"] = "private, no-cache"
        return response

    def _grant(self, user: MyUser, level: str) -> dict:
        return {"user_id": user.pk, **user_identities([user])[user.pk], "level": level}

    @extend_schema(request=ContestPermissionGrantCreateSerialiser, responses={200: None, 201: None})
    @action(detail=True, methods=["get", "post"], url_path="permissions")
    def permission_grants(self, request, *args, **kwargs):
        """Who may see (view), run (change) or delete (delete) the series; those who run it can change that."""
        series = self.get_object()
        series_rules.require_manager(request.user, series)
        if request.method == "GET":
            return Response(list_series_permission_grants(series))
        serialiser = ContestPermissionGrantCreateSerialiser(data=request.data)
        serialiser.is_valid(raise_exception=True)
        target_user = serialiser.context["target_user"]
        level = serialiser.validated_data["level"]
        set_series_permission_level(series, target_user, level, request.user)
        return Response(self._grant(target_user, level), status=status.HTTP_201_CREATED)

    @extend_schema(request=ContestPermissionGrantCreateSerialiser, responses={200: None, 204: None})
    @action(detail=True, methods=["put", "delete"], url_path=r"permissions/(?P<user_pk>\d+)")
    def permission_detail(self, request, user_pk=None, *args, **kwargs):
        series = self.get_object()
        series_rules.require_manager(request.user, series)
        target_user = get_object_or_404(MyUser, pk=user_pk)
        if request.method == "DELETE":
            remove_series_permission_grant(series, target_user, request.user)
            return Response(status=status.HTTP_204_NO_CONTENT)
        serialiser = ContestPermissionGrantCreateSerialiser(data={**request.data, "identifier": str(user_pk)})
        serialiser.is_valid(raise_exception=True)
        level = serialiser.validated_data["level"]
        set_series_permission_level(series, target_user, level, request.user)
        return Response(self._grant(target_user, level))

    @extend_schema(responses={200: None})
    @action(detail=True, methods=["get"])
    def standings(self, request, *args, **kwargs):
        """The ranking of the entrants over the legs of the series."""
        series = self.get_object()
        return self._cache_headers(series, Response(series_standings(series)))

    @extend_schema(responses={200: None})
    @action(detail=True, methods=["get"], url_path="standings-csv")
    def standings_csv(self, request, *args, **kwargs):
        """The standings as a CSV file: rank, entrant, club, the place in each leg and the total."""
        series = self.get_object()
        response = HttpResponse(
            content_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{slugify(series.name) or "series"}_standings.csv"'},
        )
        standings = series_standings(series)
        writer = csv.writer(response)
        writer.writerow(["Rank", "Name", "Club", *[csv_safe(leg["name"]) for leg in standings["legs"]], "Total"])
        for row in standings["rows"]:
            cells = {cell["contest_id"]: cell for cell in row["legs"]}
            places = []
            for leg in standings["legs"]:
                cell = cells[leg["contest_id"]]
                text = {"ranked": str(cell["placement"]), "no_result": "no result", "absent": "not in it"}[
                    cell["status"]
                ]
                places.append(text if cell["counted"] else f"({text})")
            writer.writerow(
                [row["rank"], csv_safe(row["entrant"]["name"]), csv_safe(row["entrant"]["club"]), *places, row["total"]]
            )
        return self._cache_headers(series, response)

    @extend_schema(request=AddLegSerialiser, responses={201: SeriesLegSerialiser, 202: None})
    @action(detail=True, methods=["post"])
    def contests(self, request, *args, **kwargs):
        """
        Make a contest a leg of the series. Somebody who manages both adds it at once; otherwise the managers of the other
        side get a request to answer.
        """
        series = self.get_object()
        serialiser = self.get_serializer(data=request.data)
        serialiser.is_valid(raise_exception=True)
        data = serialiser.validated_data
        contest = get_object_or_404(Contest, pk=data["contest"])
        if "leg_number" in data or data["weight"] != 1:
            # Choosing the number and weight of the leg is for somebody who manages both
            link = series_rules.add_contest(series, contest, request.user, data.get("leg_number"), data["weight"])
            return Response(SeriesLegSerialiser(link).data, status=status.HTTP_201_CREATED)
        return enrolment_response(series_rules.request_enrolment(series, contest, request.user), request)

    @extend_schema(request=UpdateLegSerialiser, responses={200: SeriesLegSerialiser, 204: None})
    @action(detail=True, methods=["patch", "delete"], url_path=r"contests/(?P<contest_pk>\d+)")
    def contest(self, request, contest_pk=None, *args, **kwargs):
        series = self.get_object()
        link = get_object_or_404(
            SeriesContest.objects.select_related("contest", "series"), series=series, contest_id=contest_pk
        )
        if request.method == "DELETE":
            series_rules.remove_contest(link, request.user)
            return Response(status=status.HTTP_204_NO_CONTENT)
        serialiser = self.get_serializer(data=request.data)
        serialiser.is_valid(raise_exception=True)
        link = series_rules.update_leg(link, request.user, **serialiser.validated_data)
        return Response(SeriesLegSerialiser(link).data)

    @extend_schema(responses={200: None})
    @action(detail=True, methods=["get"], url_path="addable-contests")
    def addable_contests(self, request, *args, **kwargs):
        """The contests the user manages that can still be added to the series."""
        series = self.get_object()
        if not request.user.is_authenticated:
            return Response([])
        contests = series_rules.addable_contests(series, request.user)[:200]
        return Response(
            [{"id": c.pk, "name": c.name, "start_time": c.start_time, "is_public": c.is_public} for c in contests]
        )


class SeriesRequestViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, GenericViewSet):
    """The requests for contests to join series that involve the user, to answer or to take back."""

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = SeriesRequestSerialiser
    pagination_class = None

    def get_queryset(self):
        queryset = series_rules.requests_for(self.request.user)
        series, contest = self.request.query_params.get("series"), self.request.query_params.get("contest")
        if series and series.isdigit():
            queryset = queryset.filter(series_id=int(series))
        if contest and contest.isdigit():
            queryset = queryset.filter(contest_id=int(contest))
        return queryset

    def get_serializer_class(self):
        return EnrolSerialiser if self.action == "create" else SeriesRequestSerialiser

    @extend_schema(request=EnrolSerialiser, responses={201: SeriesLegSerialiser, 202: SeriesRequestSerialiser})
    def create(self, request, *args, **kwargs):
        serialiser = self.get_serializer(data=request.data)
        serialiser.is_valid(raise_exception=True)
        series = get_object_or_404(Series, pk=serialiser.validated_data["series"])
        # A series the user cannot see does not exist for them, unless they manage it
        if not (series_rules.can_view(request.user, series) or series_rules.can_manage(request.user, series)):
            raise Http404
        contest = get_object_or_404(Contest, pk=serialiser.validated_data["contest"])
        return enrolment_response(series_rules.request_enrolment(series, contest, request.user), request)

    @extend_schema(request=None, responses={200: SeriesLegSerialiser})
    @action(detail=True, methods=["post"])
    def accept(self, request, pk=None, *args, **kwargs):
        link = series_rules.accept_request(self.get_object(), request.user)
        return Response(SeriesLegSerialiser(link).data)

    @extend_schema(request=None, responses={204: None})
    @action(detail=True, methods=["post"])
    def decline(self, request, pk=None, *args, **kwargs):
        series_rules.decline_request(self.get_object(), request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(request=None, responses={204: None})
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None, *args, **kwargs):
        series_rules.cancel_request(self.get_object(), request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)
