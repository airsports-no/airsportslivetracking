from django.contrib import admin

# Register your models here.
from django.contrib.auth import get_user_model
from django.contrib.auth.models import User
from django_use_email_as_username.admin import BaseUserAdmin
from guardian.admin import GuardedModelAdmin
from guardian.shortcuts import assign_perm

from display.models import NavigationTask, Route, Aeroplane, Team, Contestant, TraccarCredentials, ContestantTrack, \
    Scorecard, \
    GateScore, Contest, Crew, Person, Club, MyUser
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


class PersonAdmin(admin.ModelAdmin):
    readonly_fields = ("app_tracking_id", "simulator_tracking_id")

    def app_tracking_id(self, instance):
        return str(instance.app_tracking_id)

    def simulator_tracking_id(self, instance):
        return str(instance.simulator_tracking_id)

    app_tracking_id.short_description = "App tracking ID"
    simulator_tracking_id.short_description = "Simulator tracking ID"


class ContestAdmin(GuardedModelAdmin):
    def save_model(self, request, obj, form, change):
        result = super().save_model(request, obj, form, change)
        assign_perm("change_contest", request.user, obj),
        assign_perm("delete_contest", request.user, obj),
        assign_perm("view_contest", request.user, obj),
        return result


# admin.site.unregister(User)
admin.site.register(get_user_model(), BaseUserAdmin)
admin.site.register(NavigationTask, NavigationTaskAdmin)
admin.site.register(Scorecard)
admin.site.register(Route)
admin.site.register(Contest, ContestAdmin)
admin.site.register(GateScore)
admin.site.register(Aeroplane)
admin.site.register(Team)
admin.site.register(Crew)
admin.site.register(Contestant, ContestantTrackAdmin)
admin.site.register(Person, PersonAdmin)
admin.site.register(Club)
