import datetime
import typing

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, IntegrityError
from django.db.models import Q
from django.urls import reverse
from geopy import Nominatim
from guardian.shortcuts import get_objects_for_user, get_users_with_perms

from display.fields.my_pickled_object_field import MyPickledObjectField
from display.utilities.navigation_task_type_definitions import (
    POKER,
    PRECISION,
    ANR_CORRIDOR,
    AIRSPORTS,
    AIRSPORT_CHALLENGE,
)

if typing.TYPE_CHECKING:
    from display.models import UserUploadedMap


class NavigationTask(models.Model):
    """
    The navigation task model stores information about task visibility, with a reference to the containing contest, a
    Route, and a scorecard.
    """

    DESCENDING = "desc"
    ASCENDING = "asc"
    SORTING_DIRECTION = ((DESCENDING, "Highest score is best"), (ASCENDING, "Lowest score is best"))
    name = models.CharField(max_length=200)
    contest = models.ForeignKey("Contest", on_delete=models.CASCADE)
    route = models.OneToOneField("Route", on_delete=models.PROTECT)
    original_scorecard = models.ForeignKey(
        "Scorecard",
        on_delete=models.PROTECT,
        help_text=f"Reference to an existing scorecard",
        related_name="navigation_task_original",
    )
    scorecard = models.OneToOneField(
        "Scorecard",
        on_delete=models.SET_NULL,
        null=True,
        help_text="The actual scorecard used for this task. The scorecard may be modified, since it must be a copy of original_scorecard.",
        related_name="navigation_task_override",
    )
    editable_route = models.ForeignKey("EditableRoute", on_delete=models.SET_NULL, null=True, blank=True)
    score_sorting_direction = models.CharField(
        default=ASCENDING,
        choices=SORTING_DIRECTION,
        help_text="Whether the lowest (ascending) or highest (descending) score is the best result",
        max_length=50,
        blank=True,
    )
    start_time = models.DateTimeField(
        help_text="The start time of the navigation test. Not really important, but nice to have"
    )
    finish_time = models.DateTimeField(
        help_text="The finish time of the navigation test. Not really important, but nice to have"
    )
    is_public = models.BooleanField(
        default=False,
        help_text="The navigation test is only viewable by unauthenticated users or users without object permissions if this is True",
    )
    is_featured = models.BooleanField(
        default=False,
        help_text="A featured navigation is visible to all (if public). Otherwise a direct link is required to access it",
    )

    wind_speed = models.FloatField(
        default=0,
        help_text="The navigation test wind speed. This is used to calculate gate times if these are not predefined.",
        validators=[MaxValueValidator(40), MinValueValidator(0)],
    )
    wind_direction = models.FloatField(
        default=0,
        help_text="The navigation test wind direction. This is used to calculate gate times if these are not predefined.",
        validators=[MaxValueValidator(360), MinValueValidator(0)],
    )
    minutes_to_starting_point = models.FloatField(
        default=5,
        help_text="The number of minutes from the take-off time until the starting point",
    )
    minutes_to_landing = models.FloatField(
        default=30,
        help_text="The number of minutes from the finish point to the contestant should have landed",
    )
    planning_time = models.IntegerField(
        default=30,
        help_text="The number of minutes each team has for planning the navigation task. This is only used for populating the planning time: in the starting table timeline.",
    )
    display_background_map = models.BooleanField(
        default=True,
        help_text="If checked the online tracking map shows the mapping background. Otherwise the map will be blank.",
    )
    display_secrets = models.BooleanField(
        default=True,
        help_text="If checked secret gates will be displayed on the map. Otherwise the map will only include gates that"
        " are not secret, and also not display annotations related to the secret gates.",
    )
    allow_self_management = models.BooleanField(
        default=False,
        help_text="If checked, authenticated users will be allowed to set up themselves as a contestant after having registered for the contest.",
    )
    calculation_delay_minutes = models.FloatField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Number of minutes processions and scores should be delayed before they are made available on the tracking map.",
    )
    _nominatim = MyPickledObjectField(default=dict, help_text="Used to hold response from geolocation service")

    def _geo_reference(self):
        """
        Perform a reverse geolocation lookup based on latitude, longitude and stores the raw result with the navigation
        task object
        """
        if location := self.route.get_location():
            geolocator = Nominatim(user_agent="airsports.no")
            self._nominatim = geolocator.reverse(f"{location[0]},{location[1]}").raw
            self.save()

    @property
    def country_code(self) -> str:
        if len(self._nominatim) == 0:
            self._geo_reference()
        return self._nominatim.get("address", {}).get("country_code", "")

    @property
    def country_name(self) -> str:
        if len(self._nominatim) == 0:
            self._geo_reference()
        return self._nominatim.get("address", {}).get("country", "")

    @classmethod
    def create(cls, **kwargs) -> "NavigationTask":
        task = cls.objects.create(**kwargs)
        task.assign_scorecard_from_original(force=False)
        return task

    @classmethod
    def get_visible_navigation_tasks(cls, user: User):
        """
        Retrieve all navigation tasks that either are public or where the user has view permissions to the contest
        """
        from display.models import Contest

        contests = get_objects_for_user(user, "display.view_contest", klass=Contest, accept_global_perms=False)
        return NavigationTask.objects.filter(
            Q(contest__in=contests) | Q(is_public=True, contest__is_public=True, is_featured=True)
        )

    def get_available_user_maps(self) -> set["UserUploadedMap"]:
        """
        Retrieve all user uploaded maps for which the user has view permissions.
        """
        from display.models import UserUploadedMap

        users = get_users_with_perms(self.contest, attach_perms=True)
        maps = set(UserUploadedMap.objects.filter(unprotected=True))
        for user in users:
            maps.update(
                get_objects_for_user(
                    user, "display.view_useruploadedmap", klass=UserUploadedMap, accept_global_perms=False
                )
            )
        return UserUploadedMap.objects.filter(pk__in=(item.pk for item in maps))

    # @property
    # def is_landscaped_best(self)->bool:

    @property
    def is_poker_run(self) -> bool:
        return POKER in self.scorecard.task_type

    @property
    def tracking_link(self) -> str:
        """
        URL for the online tracking map
        """
        return reverse("frontend_view_map", kwargs={"pk": self.pk})

    @property
    def everything_public(self):
        return self.is_public and self.contest.is_public and self.is_featured

    @property
    def share_string(self):
        if self.is_public and self.is_featured:
            return "Public"
        elif self.is_public and not self.is_featured:
            return "Unlisted"
        else:
            return "Private"

    @property
    def display_contestant_rank_summary(self):
        """
        Returns true if the number of task objects for the contest for this navigation task is greater than 1
        :return:
        """
        from display.models import Task

        return Task.objects.filter(contest=self.contest).count() > 1

    @property
    def earliest_takeoff_time(self) -> datetime.datetime:
        """
        Return the first takeoff time for any contestant in the navigation task or the navigation task start time
        """
        try:
            return self.contestant_set.all().order_by("takeoff_time")[0].takeoff_time
        except IndexError:
            return self.start_time

    @property
    def latest_finished_by_time(self) -> datetime.datetime:
        """
        Return the latest finished by time for any contestant in a navigation task or the navigation task finish time
        """
        try:
            return self.contestant_set.all().order_by("-finished_by_time")[0].finished_by_time
        except IndexError:
            return self.finish_time

    @property
    def duration(self) -> datetime.timedelta:
        return self.latest_finished_by_time - self.earliest_takeoff_time

    class Meta:
        ordering = ("start_time", "finish_time")

    def user_has_change_permissions(self, user: User) -> bool:
        """
        Returns true if the user is allowed to modify the contest of the navigation task
        """
        return user.is_superuser or user.has_perm("display.change_contest", self.contest)

    def __str__(self):
        return "{}: {}".format(self.name, self.start_time.strftime("%Y-%m-%d"))

    def assign_scorecard_from_original(self, force: bool = False):
        """
        Makes a copy of original_scorecard and saves it as the new scorecard after deleting the old one.

        :force: If true, override scorecard. Otherwise only overwrite if it does not already exist
        """
        if not self.scorecard or force:
            if self.scorecard:
                self.scorecard.delete()
            self.scorecard = self.original_scorecard.copy(self.pk)
            self.save(update_fields=("scorecard",))

    def refresh_editable_route(self):
        """
        Create a new Route object to replace the old from the navigation tasks editable route. Typically used when the
        editable rout has been updated and the user wants to update the navigation task without creating a new one.
        Requires that there are no contestants in the navigation task.
        :return:
        """
        if self.contestant_set.all().count() > 0:
            raise ValidationError("Cannot refresh the route as long as they are contestants")
        if self.editable_route is None:
            raise ValidationError("There is no route to refresh")
        route = None
        if self.scorecard.calculator in (PRECISION, POKER):
            route = self.editable_route.create_precision_route(self.route.use_procedure_turns, self.scorecard)
        elif self.scorecard.calculator == ANR_CORRIDOR:
            route = self.editable_route.create_anr_route(
                self.route.rounded_corners, self.route.corridor_width, self.scorecard
            )
        elif self.scorecard.calculator in (AIRSPORTS, AIRSPORT_CHALLENGE):
            route = self.editable_route.create_airsports_route(self.route.rounded_corners, self.scorecard)
        if route:
            old_route = self.route
            self.route = route
            self.save()
            old_route.delete()

    def make_public(self):
        """
        Makes the navigation task public. If the contest is private or unvested, make it public as well.
        """
        self.is_public = True
        self.is_featured = True
        self.save()
        self.contest.make_public()

    def make_unlisted(self):
        """
        Makes the navigation task unlisted. It is accessible by anyone with a direct link, but it is not listed
        anywhere. Makes the contest at least unlisted as well.
        """
        self.is_public = True
        self.is_featured = False
        self.contest.is_public = True
        self.save()
        self.contest.save()

    def make_private(self):
        """
        Makes the navigation task private so that it is only viewable by viewers with view permissions on the contest.
        """
        self.is_public = False
        self.is_featured = False
        self.save()

    def create_results_service_test(self):
        """
        Creates a special Task and TaskTest  that is linked to the navigation task. Any scoring updates performed in
        the navigation tasks are automatically updated in the associated TaskTest.
        """
        from display.models import Task, TaskTest

        task, _ = Task.objects.get_or_create(
            contest=self.contest,
            name=f"Navigation task {self.name}",
            defaults={
                "summary_score_sorting_direction": Task.ASCENDING,
                "heading": self.name,
            },
        )
        TaskTest.objects.filter(task=task, name="Navigation").delete()
        test = TaskTest.objects.create(
            task=task,
            name="Navigation",
            heading="Navigation",
            sorting=TaskTest.ASCENDING,
            index=0,
            navigation_task=self,
        )
        return test
