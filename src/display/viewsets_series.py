"""REST API of series (see display/services/series.py for the rules and series_standings.py for the standings)."""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, permissions, serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from display.models import Contest, Series, SeriesContest
from display.services import series as series_rules
from display.services.series_standings import series_standings


class SeriesLegSerialiser(serializers.Serializer):
    contest_id = serializers.IntegerField(source="contest.pk", read_only=True)
    name = serializers.CharField(source="contest.name", read_only=True)
    start_time = serializers.DateTimeField(source="contest.start_time", read_only=True)
    is_public = serializers.BooleanField(source="contest.is_public", read_only=True)
    leg_number = serializers.IntegerField()
    weight = serializers.FloatField()


class SeriesSerialiser(serializers.ModelSerializer):
    can_manage = serializers.SerializerMethodField()
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
            "leg_count",
        )
        read_only_fields = ("id", "created_at", "can_manage", "leg_count")

    def get_can_manage(self, series) -> bool:
        return series_rules.can_manage(self.context["request"].user, series)

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
    http_method_names = ["get", "post", "patch", "delete"]
    pagination_class = None

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        queryset = series_rules.visible_series(self.request.user).distinct()
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

    def perform_destroy(self, instance):
        series_rules.delete_series(instance, self.request.user)

    @extend_schema(responses={200: None})
    @action(detail=True, methods=["get"])
    def standings(self, request, *args, **kwargs):
        """The ranking of the entrants over the legs of the series."""
        return Response(series_standings(self.get_object()))

    @extend_schema(request=AddLegSerialiser, responses={201: SeriesLegSerialiser})
    @action(detail=True, methods=["post"])
    def contests(self, request, *args, **kwargs):
        """Make a contest the user manages a leg of the series."""
        series = self.get_object()
        serialiser = self.get_serializer(data=request.data)
        serialiser.is_valid(raise_exception=True)
        data = serialiser.validated_data
        contest = get_object_or_404(Contest, pk=data["contest"])
        link = series_rules.add_contest(series, contest, request.user, data.get("leg_number"), data["weight"])
        return Response(SeriesLegSerialiser(link).data, status=status.HTTP_201_CREATED)

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
