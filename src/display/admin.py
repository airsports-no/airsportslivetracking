from django.contrib import admin

from django.contrib.auth import get_user_model
from django_use_email_as_username.admin import BaseUserAdmin
from guardian.admin import GuardedModelAdmin
from guardian.shortcuts import assign_perm

from display.services.token_assignment import revert_token_assignment_for_support
from display.models import (
    NavigationTask,
    Route,
    Aeroplane,
    Team,
    Contestant,
    ContestantTrack,
    Scorecard,
    GateScore,
    Contest,
    Crew,
    Person,
    Club,
    MyUser,
    EditableRoute,
    EmailMapLink,
    UserUploadedMap,
    NewsletterSubscriber,
    HighlightedContest,
    AccessGrant,
    ClubManagerMembership,
    TokenType,
    UserTokenGrant,
    ContestTokenAssignment,
)
from solo.admin import SingletonModelAdmin


class ContestantTrackInline(admin.TabularInline):
    model = ContestantTrack


class ContestantTrackAdmin(admin.ModelAdmin):
    inlines = (ContestantTrackInline,)
    search_fields = ["team__crew__member1__first_name", "team__crew__member1__last_name"]
    list_display = ["team", "takeoff_time", "navigation_task"]


class ContestantInline(admin.TabularInline):
    model = Contestant


class NavigationTaskAdmin(admin.ModelAdmin):
    inlines = (ContestantInline,)


class PersonAdmin(admin.ModelAdmin):
    readonly_fields = ("app_tracking_id", "simulator_tracking_id")

    def app_tracking_id(self, instance):
        return str(instance.app_tracking_id)

    def simulator_tracking_id(self, instance):
        return str(instance.simulator_tracking_id)

    app_tracking_id.short_description = "App tracking ID"
    simulator_tracking_id.short_description = "Simulator tracking ID"
    search_fields = ["first_name", "last_name", "email"]
    list_display = ("email", "first_name", "last_name")


class ContestTokenAssignmentInline(admin.TabularInline):
    model = ContestTokenAssignment
    extra = 0


class ContestAdmin(GuardedModelAdmin):
    list_display = (
        "name",
        "organizing_club",
        "created_by",
        "current_token_grant",
        "current_token_type",
        "start_time",
        "finish_time",
    )
    search_fields = ("name", "organizing_club__name", "created_by__email")
    inlines = (ContestTokenAssignmentInline,)

    def current_token_grant(self, obj):
        assignment = ContestTokenAssignment.objects.filter(contest=obj).select_related("token_grant").first()
        return assignment.token_grant if assignment else None

    def current_token_type(self, obj):
        assignment = ContestTokenAssignment.objects.filter(contest=obj).select_related("token_type").first()
        return assignment.token_type if assignment else None

    def save_model(self, request, obj, form, change):
        result = super().save_model(request, obj, form, change)
        assign_perm("change_contest", request.user, obj),
        assign_perm("delete_contest", request.user, obj),
        assign_perm("view_contest", request.user, obj),
        return result


class ClubManagerMembershipInline(admin.TabularInline):
    model = ClubManagerMembership
    extra = 0


class AccessGrantInline(admin.TabularInline):
    model = AccessGrant
    extra = 0
    fk_name = "club"
    exclude = ("created_by", "updated_by")

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


class ClubAdmin(admin.ModelAdmin):
    inlines = (ClubManagerMembershipInline, AccessGrantInline)
    search_fields = ("name",)
    list_display = ("name", "country")


class AccessGrantAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "tier",
        "status",
        "club",
        "contest",
        "contestant_limit",
        "task_type_groups",
        "starts_at",
        "expires_at",
    )
    list_filter = ("tier", "status")
    search_fields = ("club__name", "contest__name", "invoice_reference")
    exclude = ("created_by", "updated_by", "tier")
    readonly_fields = ("created_by", "updated_by", "derived_tier_display")
    fields = (
        "club",
        "contest",
        "derived_tier_display",
        "status",
        "starts_at",
        "expires_at",
        "contestant_limit",
        "task_type_groups",
        "notes",
        "invoice_reference",
        "created_by",
        "updated_by",
    )

    def derived_tier_display(self, obj):
        if obj and obj.pk:
            return obj.get_tier_display()
        if obj and obj.club_id:
            return AccessGrant.ANNUAL_CLUB_PASS.replace("_", " ").title()
        if obj and obj.contest_id:
            return AccessGrant.SINGLE_EVENT.replace("_", " ").title()
        return "Determined automatically after choosing club or contest"

    derived_tier_display.short_description = "Tier"

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


class ClubManagerMembershipAdmin(admin.ModelAdmin):
    list_display = ("club", "user", "role", "is_active")
    list_filter = ("role", "is_active")
    search_fields = ("club__name", "user__email")
    exclude = ("created_by", "updated_by")
    readonly_fields = ("created_by", "updated_by")

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


class TokenTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "contestant_limit", "task_type_groups", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name",)


class UserTokenGrantAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "token_type", "quantity_total", "quantity_consumed", "quantity_remaining")
    search_fields = ("user__email", "token_type__name", "purchase_reference")
    exclude = ("created_by", "updated_by")
    readonly_fields = ("created_by", "updated_by")

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


class ContestTokenAssignmentAdmin(admin.ModelAdmin):
    list_display = ("contest", "token_grant", "token_type", "assigned_by", "assigned_at")
    search_fields = ("contest__name", "token_grant__user__email", "token_type__name", "assigned_by__email")
    actions = ["revert_assignment_and_refund"]

    @admin.action(description="Revert assignment and refund token")
    def revert_assignment_and_refund(self, request, queryset):
        for assignment in queryset:
            revert_token_assignment_for_support(assignment, request.user)


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
admin.site.register(Club, ClubAdmin)
admin.site.register(EditableRoute, GuardedModelAdmin)
admin.site.register(EmailMapLink)
admin.site.register(UserUploadedMap, GuardedModelAdmin)
admin.site.register(AccessGrant, AccessGrantAdmin)
admin.site.register(ClubManagerMembership, ClubManagerMembershipAdmin)
admin.site.register(TokenType, TokenTypeAdmin)
admin.site.register(UserTokenGrant, UserTokenGrantAdmin)
admin.site.register(ContestTokenAssignment, ContestTokenAssignmentAdmin)


class NewsletterSubscriberAdmin(admin.ModelAdmin):
    list_display = ("email", "created_at", "is_active")
    search_fields = ["email"]


admin.site.register(NewsletterSubscriber, NewsletterSubscriberAdmin)


class HighlightedContestAdmin(admin.ModelAdmin):
    list_display = ("contest", "start_time", "finish_time")
    list_filter = ("contest", "start_time", "finish_time")
    search_fields = ("contest__name", "blurb")

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "contest":
            kwargs["queryset"] = Contest.objects.order_by("name")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    class Media:
        js = ("js/highlight_prefill.js",)


admin.site.register(HighlightedContest, HighlightedContestAdmin)
