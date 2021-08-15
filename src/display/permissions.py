from guardian.mixins import PermissionRequiredMixin
from rest_framework import permissions
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import SAFE_METHODS

from display.models import Contest



class ContestPermissionsWithoutObjects(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in ['POST']:
            return request.user.has_perm('display.add_contest')
        if request.method in ['PUT', 'PATCH']:
            return request.user.has_perm('display.change_contest')
        if request.method in ['DELETE']:
            return request.user.has_perm('display.delete_contest')
        return request.method in SAFE_METHODS


class ContestPermissions(ContestPermissionsWithoutObjects):

    def has_object_permission(self, request, view, obj):
        if request.method in ['GET']:
            return request.user.has_perm('display.view_contest', obj)
        if request.method in ['POST']:
            return request.user.has_perm('display.add_contest', obj)
        if request.method in ['PUT', 'PATCH']:
            return request.user.has_perm('display.change_contest', obj)
        if request.method in ['DELETE']:
            return request.user.has_perm('display.delete_contest', obj)
        return False


class EditableRoutePermission(ContestPermissionsWithoutObjects):
    def has_object_permission(self, request, view, obj):
        if request.method in ['GET']:
            return request.user.has_perm('display.view_editableroute', obj)
        if request.method in ['POST']:
            return request.user.has_perm('display.add_editableroute', obj)
        if request.method in ['PUT', 'PATCH']:
            return request.user.has_perm('display.change_editableroute', obj)
        if request.method in ['DELETE']:
            return request.user.has_perm('display.delete_editableroute', obj)
        return False

class OrganiserPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.has_perm("display.add_contest")


class ContestModificationPermissions(permissions.BasePermission):
    def has_permission(self, request, view):
        return True

    def has_object_permission(self, request, view, obj):
        return request.user.has_perm('display.change_contest', obj)


class ContestPublicPermissions(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.method in SAFE_METHODS

    def has_object_permission(self, request, view, obj):
        if request.method in ['GET']:
            return obj.is_public
        return False


class ContestPublicModificationPermissions(permissions.BasePermission):
    def has_permission(self, request, view):
        return True

    def has_object_permission(self, request, view, obj):
        return obj.is_public or request.user.has_perm('display.change_contest', obj)


class TaskTestContestPublicPermissions(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.method in SAFE_METHODS

    def has_object_permission(self, request, view, obj):
        if request.method in ['GET']:
            return obj.task.contest.is_public
        return False


class TaskContestPublicPermissions(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.method in SAFE_METHODS

    def has_object_permission(self, request, view, obj):
        if request.method in ['GET']:
            return obj.contest.is_public
        return False


class TeamContestPublicPermissions(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.method in SAFE_METHODS

    def has_object_permission(self, request, view, obj):
        pk = view.kwargs.get("contest_pk")
        contest = get_object_or_404(Contest, pk=pk)
        if request.method in ['GET']:
            return contest.is_public
        return False


class NavigationTaskPublicPermissions(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.method in SAFE_METHODS

    def has_object_permission(self, request, view, obj):
        if request.method in ['GET']:
            return obj.is_public and obj.contest.is_public
        return False


class NavigationTaskPublicPutPermissions(permissions.BasePermission):
    def has_permission(self, request, view):
        return True

    def has_object_permission(self, request, view, obj):
        if request.method in ['GET', "PUT"]:
            return obj.is_public and obj.contest.is_public
        return False


class ContestantPublicPermissions(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.method in SAFE_METHODS

    def has_object_permission(self, request, view, obj):
        if request.method in ['GET']:
            return obj.navigation_task.is_public and obj.navigation_task.contest.is_public
        return False


class TeamContestPermissions(permissions.BasePermission):
    def has_permission(self, request, view):
        pk = view.kwargs.get("contest_pk")
        if not pk:
            return True
        contest = get_object_or_404(Contest, pk=pk)
        return request.user.has_perm("display.change_contest", contest)

    def has_object_permission(self, request, view, obj):
        pk = view.kwargs.get("contest_pk")
        contest = get_object_or_404(Contest, pk=pk)
        if request.method in ['GET']:
            return request.user.has_perm('view_contest', contest)
        if request.method in ['POST']:
            return request.user.has_perm('add_contest', contest)
        if request.method in ['PUT', 'PATCH']:
            return request.user.has_perm('change_contest', contest)
        if request.method in ['DELETE']:
            return request.user.has_perm('delete_contest', contest)
        return False


class ChangeContestKeyPermissions(permissions.BasePermission):
    def has_permission(self, request, view):
        pk = view.kwargs.get("id")
        if not pk:
            return False
        contest = get_object_or_404(Contest, pk=pk)
        return request.user.has_perm("display.change_contest", contest)


class TaskContestPermissions(permissions.BasePermission):
    def has_permission(self, request, view):
        pk = view.kwargs.get("contest_pk")
        if not pk:
            return True
        contest = get_object_or_404(Contest, pk=pk)
        return request.user.has_perm("display.change_contest", contest)

    def has_object_permission(self, request, view, obj):
        if request.method in ['GET']:
            return request.user.has_perm('view_contest', obj.contest)
        if request.method in ['POST']:
            return request.user.has_perm('add_contest', obj.contest)
        if request.method in ['PUT', 'PATCH']:
            return request.user.has_perm('change_contest', obj.contest)
        if request.method in ['DELETE']:
            return request.user.has_perm('delete_contest', obj.contest)
        return False


class TaskTestContestPermissions(permissions.BasePermission):
    def has_permission(self, request, view):
        pk = view.kwargs.get("contest_pk")
        if not pk:
            return True
        contest = get_object_or_404(Contest, pk=pk)
        return request.user.has_perm("display.change_contest", contest)

    def has_object_permission(self, request, view, obj):
        if request.method in ['GET']:
            return request.user.has_perm('view_contest', obj.task.contest)
        if request.method in ['POST']:
            return request.user.has_perm('add_contest', obj.task.contest)
        if request.method in ['PUT', 'PATCH']:
            return request.user.has_perm('change_contest', obj.task.contest)
        if request.method in ['DELETE']:
            return request.user.has_perm('delete_contest', obj.task.contest)
        return False


class ContestTeamContestPermissions(permissions.BasePermission):
    def has_permission(self, request, view):
        pk = view.kwargs.get("contest_pk")
        if not pk:
            return True
        contest = get_object_or_404(Contest, pk=pk)
        return request.user.has_perm("display.change_contest", contest)

    def has_object_permission(self, request, view, obj):
        if request.method in ['GET']:
            return request.user.has_perm('view_contest', obj.contest)
        if request.method in ['POST']:
            return request.user.has_perm('add_contest', obj.contest)
        if request.method in ['PUT', 'PATCH']:
            return request.user.has_perm('change_contest', obj.contest)
        if request.method in ['DELETE']:
            return request.user.has_perm('delete_contest', obj.contest)
        return False


class NavigationTaskContestPermissions(permissions.BasePermission):
    def has_permission(self, request, view):
        pk = view.kwargs.get("contest_pk")
        if not pk:
            return True
        contest = get_object_or_404(Contest, pk=pk)
        return request.user.has_perm("display.change_contest", contest)

    def has_object_permission(self, request, view, obj):
        if request.method in ['GET']:
            return request.user.has_perm('view_contest', obj.contest)
        if request.method in ['POST']:
            return request.user.has_perm('add_contest', obj.contest)
        if request.method in ['PUT', 'PATCH']:
            return request.user.has_perm('change_contest', obj.contest)
        if request.method in ['DELETE']:
            return request.user.has_perm('delete_contest', obj.contest)
        return False


class NavigationTaskSelfManagementPermissions(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.allow_self_management


class ContestantNavigationTaskContestPermissions(permissions.BasePermission):
    def has_permission(self, request, view):
        pk = view.kwargs.get("contest_pk")
        if not pk:
            return True
        contest = get_object_or_404(Contest, pk=pk)
        return request.user.has_perm("display.change_contest", contest)

    def has_object_permission(self, request, view, obj):
        if request.method in ['GET']:
            return request.user.has_perm('view_contest', obj.navigation_task.contest)
        if request.method in ['POST']:
            return request.user.has_perm('add_contest', obj.navigation_task.contest)
        if request.method in ['PUT', 'PATCH']:
            return request.user.has_perm('change_contest', obj.navigation_task.contest)
        if request.method in ['DELETE']:
            return request.user.has_perm('delete_contest', obj.navigation_task.contest)
        return False


class RoutePermissions(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in ['GET']:
            return request.user.has_perm('view_route', obj.navigation_task)
        if request.method in ['POST']:
            return request.user.has_perm('add_route', obj.navigation_task)
        if request.method in ['PUT', 'PATCH']:
            return request.user.has_perm('change_route', obj.navigation_task)
        if request.method in ['DELETE']:
            return request.user.has_perm('delete_route', obj.navigation_task)
        return False
