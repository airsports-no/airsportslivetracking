import logging
import typing
from typing import Optional

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.db import models
from django_countries.fields import CountryField
from guardian.shortcuts import assign_perm, get_objects_for_user, get_users_with_perms
from location_field.models.plain import PlainLocationField
from timezone_field import TimeZoneField

from display.utilities.country_code_utilities import get_country_code_from_location, CountryNotFoundException
from display.utilities.tracking_definitions import (
    TRACCAR,
    TRACKING_SERVICES,
    TRACKING_PILOT_AND_COPILOT,
    TRACKING_DEVICES,
    TRACKING_DEVICE,
    TRACKING_COPILOT,
    TRACKING_PILOT,
)

if typing.TYPE_CHECKING:
    from display.models import Team

logger = logging.getLogger(__name__)


class ContestTeam(models.Model):
    contest = models.ForeignKey("Contest", on_delete=models.CASCADE)
    team = models.ForeignKey("Team", on_delete=models.CASCADE)
    air_speed = models.FloatField(default=70, help_text="The planned airspeed for the contestant")
    tracking_service = models.CharField(
        default=TRACCAR,
        choices=TRACKING_SERVICES,
        max_length=30,
        help_text="Supported tracking services: {}".format(TRACKING_SERVICES),
    )
    tracking_device = models.CharField(
        default=TRACKING_PILOT_AND_COPILOT,
        choices=TRACKING_DEVICES,
        max_length=30,
        help_text="The device used for tracking the team",
    )
    tracker_device_id = models.CharField(
        max_length=100,
        help_text="ID of physical tracking device that will be brought into the plane. Leave empty if official Air Sports Live Tracking app is used. Note that only a single tracker is to be used per plane.",
        blank=True,
        null=True,
    )

    class Meta:
        unique_together = ("contest", "team")

    def clean(self):
        if self.tracking_device == TRACKING_DEVICE and (
            self.tracker_device_id is None or len(self.tracker_device_id) == 0
        ):
            raise ValidationError(
                f"Tracking device is set to {self.get_tracking_device_display()}, but no tracker device ID is supplied"
            )
        try:
            if self.tracking_device == TRACKING_COPILOT and self.team.crew.member2 is None:
                raise ValidationError(
                    f"Tracking device is set to {self.get_tracking_device_display()}, but there is no copilot"
                )
        except ObjectDoesNotExist:
            pass

    def __str__(self):
        return str(self.team)

    def get_tracker_id(self) -> str:
        if self.tracking_device == TRACKING_DEVICE:
            return self.tracker_device_id
        if self.tracking_device in (TRACKING_PILOT, TRACKING_PILOT_AND_COPILOT):
            return self.team.crew.member1.app_tracking_id
        if self.tracking_device == TRACKING_COPILOT:
            return self.team.crew.member2.app_tracking_id
        logger.error(
            f"ContestTeam {self.team} for contest {self.contest} does not have a tracker ID for tracking device {self.tracking_device}"
        )
        return ""


class Contest(models.Model):
    DESCENDING = "desc"
    ASCENDING = "asc"
    SORTING_DIRECTION = ((DESCENDING, "Highest score is best"), (ASCENDING, "Lowest score is best"))
    summary_score_sorting_direction = models.CharField(
        default=ASCENDING,
        choices=SORTING_DIRECTION,
        help_text="Whether the lowest (ascending) or highest (descending) score is the best result",
        max_length=50,
        blank=True,
    )
    autosum_scores = models.BooleanField(
        default=True,
        help_text="If true, contest summary points for a team will be updated with the new sum when any task is updated",
    )
    name = models.CharField(max_length=100, unique=True)
    time_zone = TimeZoneField()
    location = PlainLocationField(
        based_fields=["city"],
        zoom=7,
        help_text="Text field with latitude, longitude (two comma-separated numbers). Select the location using the embedded map.",
    )
    start_time = models.DateTimeField(
        help_text="The start time of the contest. Used for sorting. All navigation tasks should ideally be within this time interval."
    )
    finish_time = models.DateTimeField(
        help_text="The finish time of the contest. Used for sorting. All navigation tasks should ideally be within this time interval."
    )
    contest_teams = models.ManyToManyField("Team", blank=True, through=ContestTeam)
    is_public = models.BooleanField(
        default=False,
        help_text="A public contest is visible to people who are not logged and does not require special privileges",
    )
    is_featured = models.BooleanField(
        default=False,
        help_text="A featured contest is visible to all (if it is public). If it is not featured, a direct link is required to access it.",
    )
    contest_website = models.CharField(help_text="URL to contest website", blank=True, default="", max_length=300)
    header_image = models.ImageField(
        null=True,
        blank=True,
        help_text="Nice image that is shown on top of the event information on the map.",
    )
    logo = models.ImageField(
        null=True,
        blank=True,
        help_text="Quadratic logo that is shown next to the event in the event list",
    )
    country = CountryField(
        blank=True,
        null=True,
        help_text="Optional, if omitted country will be inferred from latitude and longitude if they are provided.",
    )

    @property
    def latitude(self) -> float:
        return float(self.location.split(",")[0])

    @property
    def longitude(self) -> float:
        return float(self.location.split(",")[1])

    @property
    def country_flag_url(self):
        if self.country:
            return "/static/flags/3x2/" + str(self.country) + ".svg"
        return None

    @property
    def share_string(self):
        if self.is_public and self.is_featured:
            return "Public"
        elif self.is_public and not self.is_featured:
            return "Unlisted"
        else:
            return "Private"

    def __str__(self):
        return self.name

    class Meta:
        ordering = ("-start_time", "-finish_time")

    @property
    def country_codes(self) -> set[str]:
        return set([navigation_task.country_code for navigation_task in self.navigationtask_set.all()])

    @property
    def country_names(self) -> set[str]:
        return set([navigation_task.country_name for navigation_task in self.navigationtask_set.all()])

    def validate_and_set_country(self):
        try:
            self.country = get_country_code_from_location(self.latitude, self.longitude)
        except CountryNotFoundException:
            raise ValidationError(
                "The contest location %(location)s is not in a valid country",
                params={"location": self.location},
                code="invalid",
            )
        # except:
        #     pass

    def initialise(self, user: "MyUser"):
        self.start_time = self.start_time.replace(tzinfo=self.time_zone)
        self.finish_time = self.finish_time.replace(tzinfo=self.time_zone)
        self.save()
        assign_perm("delete_contest", user, self)
        assign_perm("view_contest", user, self)
        assign_perm("add_contest", user, self)
        assign_perm("change_contest", user, self)

    def replace_team(self, old_team: Optional["Team"], new_team: "Team", tracking_data: dict) -> ContestTeam:
        """
        Whenever a ContestTeam is modified, we need to update all navigation tasks, contest summaries, tasks summaries,
        and team test scores.
        """
        from display.models import Contestant, ContestSummary, TaskSummary, TeamTestScore

        ContestTeam.objects.filter(contest=self, team=old_team).delete()
        ContestTeam.objects.filter(contest=self, team=new_team).delete()
        ct = ContestTeam.objects.create(contest=self, team=new_team, **tracking_data)
        Contestant.objects.filter(navigation_task__contest=self, team=old_team).update(team=new_team)
        ContestSummary.objects.filter(contest=self, team=old_team).update(team=new_team)
        TaskSummary.objects.filter(task__contest=self, team=old_team).update(team=new_team)
        TeamTestScore.objects.filter(task_test__task__contest=self, team=old_team).update(team=new_team)
        return ct

    def make_public(self):
        self.is_public = True
        self.is_featured = True
        self.save()

    def make_private(self):
        self.is_public = False
        self.is_featured = False
        self.navigationtask_set.all().update(is_featured=False, is_public=False)
        self.save()

    def make_unlisted(self):
        self.is_public = True
        self.is_featured = False
        self.navigationtask_set.all().update(is_featured=False)
        self.save()

    @classmethod
    def visible_contests_for_user(cls, user: User):
        return get_objects_for_user(
            user, "display.view_contest", klass=Contest, accept_global_perms=False
        ) | Contest.objects.filter(is_public=True)

    @property
    def contest_team_count(self):
        return self.contest_teams.all().count()

    @property
    def editors(self) -> list:
        users = get_users_with_perms(self, attach_perms=True)
        return [user for user, permissions in users.items() if "change_contest" in permissions]
