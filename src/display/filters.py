from django_filters import rest_framework as filters
from guardian.shortcuts import get_objects_for_user  # Keep this import if used elsewhere, otherwise remove

from display.models import Contest, NavigationTask
from display.services.contest_visibility import audience_contests


class NumberInFilter(filters.BaseInFilter, filters.NumberFilter):
    pass


class ContestFilter(filters.FilterSet):
    pks = NumberInFilter(field_name="pk", lookup_expr="in")
    start_time__gte = filters.DateTimeFilter(field_name="start_time", lookup_expr="gte")
    finish_time__lte = filters.DateTimeFilter(field_name="finish_time", lookup_expr="lte")
    start_time__lte = filters.DateTimeFilter(field_name="start_time", lookup_expr="lte")
    finish_time__gte = filters.DateTimeFilter(field_name="finish_time", lookup_expr="gte")

    is_featured = filters.BooleanFilter(field_name="is_featured")
    search = filters.CharFilter(field_name="name", lookup_expr="icontains")
    is_editor = filters.BooleanFilter(method="filter_is_editor")
    public_only = filters.BooleanFilter(method="filter_public_only")
    shared_only = filters.BooleanFilter(method="filter_shared_only")

    def filter_is_editor(self, queryset, name, value):
        if value:
            user = self.request.user
            if not user.is_authenticated:
                return queryset.none()
            
            # Use get_objects_for_user to get ONLY contests with explicit change permissions.
            # with_superuser=False is critical here to treat superusers as regular users.
            return get_objects_for_user(
                user, 
                "display.change_contest", 
                klass=queryset, 
                accept_global_perms=False, 
                with_superuser=False
            )
        return queryset

    def filter_public_only(self, queryset, name, value):
        if value:
            return queryset.filter(is_public=True)
        return queryset

    def filter_shared_only(self, queryset, name, value):
        if value:
            user = self.request.user
            if not user.is_authenticated:
                return queryset.none()
            
            if user.is_superuser:
                # For superusers, 'shared' means anything not public.
                return queryset.exclude(is_public=True)
                
            # For regular users, 'shared' means the private contests whose audience they are in.
            return queryset.filter(pk__in=audience_contests(user).values("pk")).exclude(is_public=True)
        return queryset

    class Meta:
        model = Contest
        fields = [
            "pks", 
            "start_time__gte", 
            "finish_time__lte", 
            "start_time__lte", 
            "finish_time__gte", 
            "is_featured",
            "search",
            "is_editor",
            "public_only",
            "shared_only"
        ]


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
