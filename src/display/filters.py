from django.db.models import Q
from django_filters import rest_framework as filters
from guardian.shortcuts import get_objects_for_user # New import

from display.models import Contest, NavigationTask


class NumberInFilter(filters.BaseInFilter, filters.NumberFilter):
    pass


class ContestFilter(filters.FilterSet):
    pks = NumberInFilter(field_name="pk", lookup_expr="in")
    start_time__gte = filters.DateTimeFilter(field_name="start_time", lookup_expr="gte")
    finish_time__lte = filters.DateTimeFilter(field_name="finish_time", lookup_expr="lte")
    is_editor = filters.BooleanFilter(method='filter_is_editor') # New filter

    class Meta:
        model = Contest
        fields = ["pks", "start_time__gte", "finish_time__lte", "is_editor"] # Updated fields

    def filter_is_editor(self, queryset, name, value):
        if value:
            # If is_editor=True, return contests where the user has display.change_contest permission
            return queryset.filter(pk__in=get_objects_for_user(self.request.user, 'display.change_contest').values_list('pk', flat=True))
        else:
            # If is_editor=False, return contests where the user does NOT have display.change_contest permission
            return queryset.exclude(pk__in=get_objects_for_user(self.request.user, 'display.change_contest').values_list('pk', flat=True))


class NavigationTaskFilter(filters.FilterSet):
    pks = NumberInFilter(field_name="pk", lookup_expr="in")
    start_time__gte = filters.DateTimeFilter(field_name="contest__start_time", lookup_expr="gte")
    finish_time__lte = filters.DateTimeFilter(field_name="contest__finish_time", lookup_expr="lte")

    class Meta:
        model = NavigationTask
        fields = ["pks", "start_time__gte", "finish_time__lte"]
