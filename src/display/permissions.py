from rest_framework import permissions


class ContestPermissions(permissions.BasePermission):
    # def has_permission(self, request, view):
    #     if request.method in ['POST']:
    #         return request.user.has_perm('add_contest')
    #     return False

    def has_object_permission(self, request, view, obj):
        if request.method in ['GET']:
            return request.user.has_perm('view_contest', obj) or obj.is_public
        if request.method in ['POST']:
            return request.user.has_perm('add_contest', obj) or request.user.has_perm('add_contest')
        if request.method in ['PUT', 'PATCH']:
            return request.user.has_perm('change_contest', obj)
        if request.method in ['DELETE']:
            return request.user.has_perm('delete_contest', obj)
        return False


class NavigationTaskPermissions(permissions.BasePermission):
    # def has_permission(self, request, view):
    #     if request.method in ['POST']:
    #         return request.user.has_perm('add_navigationtask')
    #     return False

    def has_object_permission(self, request, view, obj):
        if request.method in ['GET']:
            return request.user.has_perm('view_navigationtask', obj) or obj.is_public
        if request.method in ['POST']:
            return request.user.has_perm('add_navigationtask', obj) or request.user.has_perm('add_navigationtask')
        if request.method in ['PUT', 'PATCH']:
            return request.user.has_perm('change_navigationtask', obj)
        if request.method in ['DELETE']:
            return request.user.has_perm('delete_navigationtask', obj)
        return False
