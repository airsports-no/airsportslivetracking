from authemail.admin import EmailUserAdmin, SignupCodeAdmin, PasswordResetCodeAdmin, EmailChangeCodeAdmin, \
    SignupCodeInline, PasswordResetCodeInline, EmailChangeCodeInline
from authemail.models import SignupCode, PasswordResetCode, EmailChangeCode
from django.contrib import admin

# Register your models here.
from django.contrib.auth import get_user_model
from guardian.admin import GuardedModelAdmin
from guardian.shortcuts import assign_perm

from display.models import NavigationTask, Route, Aeroplane, Team, Contestant, TraccarCredentials, ContestantTrack, \
    Scorecard, \
    GateScore, Contest, Crew, Person, Club
from solo.admin import SingletonModelAdmin

admin.site.register(TraccarCredentials, SingletonModelAdmin)


class ContestantTrackInline(admin.TabularInline):
    model = ContestantTrack


class ContestantTrackAdmin(admin.ModelAdmin):
    inlines = (
        ContestantTrackInline,
    )


class ContestantInline(admin.TabularInline):
    model = Contestant


# class ScorecardInLine(admin.TabularInline):
#     model = Scorecard


# class GateScoreInLine(admin.TabularInline):
#     model = GateScore


# class ScorecardAdmin(admin.ModelAdmin):
# inlines = (
#     GateScoreInLine,
# )

class NavigationTaskAdmin(admin.ModelAdmin):
    inlines = (
        ContestantInline,
    )


class HasAddPermissionsMixing:
    def has_add_permission(self, request, obj=None):
        return False


class SignupCodeAdminPermission(HasAddPermissionsMixing, SignupCodeAdmin):
    pass


class PasswordResetCodeAdminPermission(HasAddPermissionsMixing, PasswordResetCodeAdmin):
    pass


class EmailChangeCodeAdminPermission(HasAddPermissionsMixing, EmailChangeCodeAdmin):
    pass


class SignupCodeInlinePermission(HasAddPermissionsMixing, SignupCodeInline):
    pass


class PasswordResetCodeInlinePermission(HasAddPermissionsMixing, PasswordResetCodeInline):
    pass


class EmailChangeCodeInlinePermission(HasAddPermissionsMixing, EmailChangeCodeInline):
    pass


class ContestAdmin(GuardedModelAdmin):
    def save_model(self, request, obj, form, change):
        result = super().save_model(request, obj, form, change)
        assign_perm("change_contest", request.user, obj),
        assign_perm("delete_contest", request.user, obj),
        assign_perm("view_contest", request.user, obj),
        return result

class MyEmailUserAdmin(EmailUserAdmin):
    inlines = [SignupCodeInlinePermission, EmailChangeCodeInlinePermission, PasswordResetCodeInlinePermission]


class MyUserAdmin(MyEmailUserAdmin, HasAddPermissionsMixing):
    fieldsets = (
        (None, {'fields': ('email', 'password', 'person')}),
        ('Personal Info', {'fields': ('first_name', 'last_name')}),
        ('Permissions', {'fields': ('is_active', 'is_staff',
                                    'is_superuser', 'is_verified',
                                    'groups')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')})
    )


admin.site.unregister(SignupCode)
admin.site.unregister(PasswordResetCode)
admin.site.unregister(EmailChangeCode)

admin.site.register(SignupCode, SignupCodeAdminPermission)
admin.site.register(PasswordResetCode, PasswordResetCodeAdminPermission)
admin.site.register(EmailChangeCode, EmailChangeCodeAdminPermission)

admin.site.unregister(get_user_model())
admin.site.register(get_user_model(), MyUserAdmin)
admin.site.register(NavigationTask, NavigationTaskAdmin)
admin.site.register(Scorecard)
admin.site.register(Route)
admin.site.register(Contest, ContestAdmin)
admin.site.register(GateScore)
admin.site.register(Aeroplane)
admin.site.register(Team)
admin.site.register(Crew)
admin.site.register(Contestant, ContestantTrackAdmin)
admin.site.register(Person)
admin.site.register(Club)
