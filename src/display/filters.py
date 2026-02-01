from django_filters import rest_framework as filters
from guardian.shortcuts import get_objects_for_user  # Keep this import if used elsewhere, otherwise remove

from display.models import Contest, NavigationTask


class NumberInFilter(filters.BaseInFilter, filters.NumberFilter):
    pass


class ContestFilter(filters.FilterSet):
    pks = NumberInFilter(field_name="pk", lookup_expr="in")
    start_time__gte = filters.DateTimeFilter(field_name="start_time", lookup_expr="gte")
    finish_time__lte = filters.DateTimeFilter(field_name="finish_time", lookup_expr="lte")
    start_time__lte = filters.DateTimeFilter(field_name="start_time", lookup_expr="lte")
    finish_time__gte = filters.DateTimeFilter(field_name="finish_time", lookup_expr="gte")

    is_featured = filters.BooleanFilter(field_name="is_featured")

    class Meta:
        model = Contest
        fields = ["pks", "start_time__gte", "finish_time__lte", "start_time__lte", "finish_time__gte", "is_featured"]


class NavigationTaskFilter(filters.FilterSet):
    pks = NumberInFilter(field_name="pk", lookup_expr="in")
    start_time__gte = filters.DateTimeFilter(field_name="contest__start_time", lookup_expr="gte")
    finish_time__lte = filters.DateTimeFilter(field_name="contest__finish_time", lookup_expr="lte")
    start_time__lte = filters.DateTimeFilter(field_name="contest__start_time", lookup_expr="lte")
    finish_time__gte = filters.DateTimeFilter(field_name="contest__finish_time", lookup_expr="gte")
    is_featured = filters.BooleanFilter(field_name="is_featured")

    class Meta:
        model = NavigationTask
        fields = ["pks", "start_time__gte", "finish_time__lte", "start_time__lte", "finish_time__gte", "is_featured"]
