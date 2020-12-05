from django.contrib import admin

# Register your models here.
from display.models import Contest, Track, Aeroplane, Team, Contestant, TraccarCredentials, ContestantTrack, Scorecard, \
    GateScore
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

class ContestAdmin(admin.ModelAdmin):
    inlines = (
        ContestantInline,
    )


admin.site.register(Contest, ContestAdmin)
admin.site.register(Scorecard)
admin.site.register(Track)
admin.site.register(GateScore)
admin.site.register(Aeroplane)
admin.site.register(Team)
admin.site.register(Contestant, ContestantTrackAdmin)
