import base64
import datetime
import logging

import dateutil
import phonenumbers
from django.core.exceptions import ObjectDoesNotExist
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import transaction
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django_countries.serializer_fields import CountryField
from django_countries.serializers import CountryFieldMixin
from guardian.shortcuts import assign_perm, get_objects_for_user
from rest_framework import serializers
from rest_framework.fields import MultipleChoiceField, SerializerMethodField
from rest_framework.exceptions import ValidationError
from rest_framework.relations import SlugRelatedField
from rest_framework_guardian.serializers import ObjectPermissionsAssignmentMixin
from timezone_field.rest_framework import TimeZoneSerializerField

from display.convert_flightcontest_gpx import create_precision_route_from_gpx
from display.models import (
    NavigationTask,
    Aeroplane,
    Team,
    Route,
    Contestant,
    ContestantTrack,
    Scorecard,
    Crew,
    Contest,
    ContestSummary,
    TaskTest,
    Task,
    TaskSummary,
    TeamTestScore,
    Person,
    Club,
    ContestTeam,
    TRACCAR,
    GateScoreOverride,
    TrackScoreOverride,
    GateScore,
    Prohibited,
    PlayingCard,
    TrackAnnotation,
    ScoreLogEntry,
    GateCumulativeScore, EditableRoute,
)
from display.waypoint import Waypoint

logger = logging.getLogger(__name__)


class MangledEmailField(serializers.Field):
    def to_representation(self, value):
        """
        Serialize the value's class name.
        """
        name, domain = value.split("@")
        levels = domain.split(".")
        return f"{name}@*****.{'.'.join(levels[1:])}"


class AeroplaneSerialiser(serializers.ModelSerializer):
    class Meta:
        model = Aeroplane
        fields = "__all__"


class PersonSignUpSerialiser(serializers.ModelSerializer):
    email = MangledEmailField(read_only=True)

    class Meta:
        model = Person
        fields = ("id", "first_name", "last_name", "email")


class PersonLtdSerialiser(serializers.ModelSerializer):
    class Meta:
        model = Person
        fields = ("first_name", "last_name", "picture")


class PersonSerialiser(CountryFieldMixin, serializers.ModelSerializer):
    country_flag_url = serializers.CharField(max_length=200, required=False, read_only=True)
    country = CountryField(required=False)
    # phone = PhoneNumberField(required=False)
    phone_country_prefix = serializers.CharField(
        max_length=5, required=False, help_text="International prefix for a phone number, e.g. +47"
    )
    phone_national_number = serializers.CharField(
        max_length=30, required=False, help_text="Actual phone number without international prefix"
    )

    def create(self, validated_data):
        country_prefix = validated_data.pop("phone_country_prefix", None)
        phone_national_number = validated_data.pop("phone_national_number", None)
        instance = super().create(validated_data)
        if country_prefix is not None and phone_national_number is not None:
            instance.phone = country_prefix + phone_national_number
            self.validate_phone(instance.phone)
            instance.save()
        return instance

    def update(self, instance, validated_data):
        country_prefix = validated_data.pop("phone_country_prefix", None)
        phone_national_number = validated_data.pop("phone_national_number", None)
        instance = super().update(instance, validated_data)
        if country_prefix is not None and phone_national_number is not None:
            instance.phone = country_prefix + phone_national_number
            self.validate_phone(instance.phone)
            instance.save()
        return instance

    def validate_phone(self, phone):
        if not phonenumbers.is_possible_number(phone):
            raise ValidationError(f"Phone number {phone} is not a possible number")
        if not phonenumbers.is_valid_number(phone):
            raise ValidationError(f"Phone number {phone} is not a valid number")

    class Meta:
        model = Person
        # fields = "__all__"
        exclude = ("phone",)


class ClubSerialiser(CountryFieldMixin, serializers.ModelSerializer):
    country_flag_url = serializers.CharField(max_length=200, required=False, read_only=True)
    country = CountryField(required=False)

    class Meta:
        model = Club
        fields = "__all__"


class CrewSerialiser(serializers.ModelSerializer):
    member1 = PersonSerialiser()
    member2 = PersonSerialiser(required=False)

    class Meta:
        model = Crew
        fields = "__all__"

    def create(self, validated_data):
        member1 = validated_data.pop("member1")
        member1_object = Person.get_or_create(
            member1["first_name"], member1["last_name"], member1.get("phone"), member1.get("email")
        )
        member2 = validated_data.pop("member2", None)
        member2_object = None
        if member2:
            member2_object = Person.get_or_create(
                member2["first_name"], member2["last_name"], member2.get("phone"), member2.get("email")
            )
        crew, _ = Crew.objects.get_or_create(member1=member1_object, member2=member2_object)
        return crew

    def update(self, instance, validated_data):
        return self.create(validated_data)


class TeamNestedSerialiser(CountryFieldMixin, serializers.ModelSerializer):
    country_flag_url = serializers.CharField(max_length=200, required=False, read_only=True)
    aeroplane = AeroplaneSerialiser()
    country = CountryField(required=False)
    crew = CrewSerialiser()
    club = ClubSerialiser(required=False)

    class Meta:
        model = Team
        fields = "__all__"

    def create(self, validated_data):
        aeroplane, crew, club = self.nested_update(validated_data)
        team, _ = Team.objects.get_or_create(crew=crew, aeroplane=aeroplane, club=club, defaults=validated_data)
        return team

    def update(self, instance: Team, validated_data):
        instance.aeroplane, instance.crew, instance.club = self.nested_update(validated_data)
        instance.save()
        return instance

    @staticmethod
    def nested_update(validated_data):
        aeroplane_data = validated_data.pop("aeroplane")
        aeroplane_instance = Aeroplane.objects.filter(registration=aeroplane_data.get("registration")).first()
        aeroplane_serialiser = AeroplaneSerialiser(instance=aeroplane_instance, data=aeroplane_data)
        aeroplane_serialiser.is_valid(True)
        aeroplane = aeroplane_serialiser.save()
        crew_data = validated_data.pop("crew")
        crew_instance = Crew.objects.filter(pk=crew_data.get("id")).first()
        crew_serialiser = CrewSerialiser(instance=crew_instance, data=crew_data)
        crew_serialiser.is_valid(True)
        crew = crew_serialiser.save()
        club = None
        club_data = validated_data.pop("club", None)
        if club_data:
            club_instance = Club.objects.filter(name=club_data.get("name")).first()
            club_serialiser = ClubSerialiser(instance=club_instance, data=club_data)
            club_serialiser.is_valid(True)
            club = club_serialiser.save()
        return aeroplane, crew, club


class ContestSummaryNestedSerialiser(serializers.ModelSerializer):
    team = TeamNestedSerialiser()

    class Meta:
        model = ContestSummary
        fields = "__all__"


class NavigationTasksSummarySerialiser(serializers.ModelSerializer):
    class Meta:
        model = NavigationTask
        fields = ("pk", "name", "start_time", "finish_time", "tracking_link")


class NavigationTasksSummaryParticipationSerialiser(serializers.ModelSerializer):
    future_contestants = SerializerMethodField("get_future_contestants")

    class Meta:
        model = NavigationTask
        fields = ("pk", "name", "start_time", "finish_time", "tracking_link", "future_contestants")

    def get_future_contestants(self, navigation_task):
        person = get_object_or_404(Person, email=self.context["request"].user.email)
        future_contestants = navigation_task.contestant_set.filter(
            team__crew__member1=person, finished_by_time__gt=datetime.datetime.now(datetime.timezone.utc)
        )
        serialiser = ContestantSerialiser(future_contestants, many=True, read_only=True)
        return serialiser.data


class ContestSerialiser(ObjectPermissionsAssignmentMixin, serializers.ModelSerializer):
    time_zone = TimeZoneSerializerField(required=True)
    navigationtask_set = SerializerMethodField("get_visiblenavigationtasks")
    contestsummary_set = ContestSummaryNestedSerialiser(many=True, read_only=True)
    contest_team_count = serializers.IntegerField(read_only=True)
    share_string = serializers.CharField(read_only=True)

    class Meta:
        model = Contest
        fields = "__all__"

    def get_permissions_map(self, created):
        user = self.context["request"].user
        return {"change_contest": [user], "delete_contest": [user], "view_contest": [user]}

    def get_visiblenavigationtasks(self, contest):
        contests = get_objects_for_user(
            self.context["request"].user, "display.view_contest", klass=Contest, accept_global_perms=False
        )
        items = NavigationTask.objects.filter(
            Q(contest__in=contests) | Q(is_public=True, contest__is_public=True, is_featured=True)
        ).filter(contest_id=contest.pk)
        serialiser = NavigationTasksSummarySerialiser(items, many=True, read_only=True)
        return serialiser.data


class ContestParticipationSerialiser(ContestSerialiser):
    def get_visiblenavigationtasks(self, contest):
        contests = get_objects_for_user(
            self.context["request"].user, "display.view_contest", klass=Contest, accept_global_perms=False
        )
        items = (
            NavigationTask.objects.filter(
                Q(contest__in=contests) | Q(is_public=True, contest__is_public=True, is_featured=True)
            )
                .filter(contest_id=contest.pk)
                .filter(allow_self_management=True)
        )
        serialiser = NavigationTasksSummaryParticipationSerialiser(
            items, many=True, read_only=True, context={"request": self.context["request"]}
        )
        return serialiser.data


class SelfManagementSerialiser(serializers.Serializer):
    starting_point_time = serializers.DateTimeField()
    contest_team = serializers.PrimaryKeyRelatedField(queryset=ContestTeam.objects.all())
    adaptive_start = serializers.BooleanField(required=False)
    wind_speed = serializers.FloatField(validators=[MaxValueValidator(40), MinValueValidator(0)])
    wind_direction = serializers.FloatField(validators=[MaxValueValidator(360), MinValueValidator(0)])


class WaypointSerialiser(serializers.Serializer):
    def create(self, validated_data):
        pass

    def update(self, instance, validated_data):
        pass

    name = serializers.CharField(max_length=200)
    latitude = serializers.FloatField(help_text="degrees")
    longitude = serializers.FloatField(help_text="degrees")
    elevation = serializers.FloatField(help_text="Metres above MSL")
    width = serializers.FloatField(help_text="Width of the gate in NM")
    gate_line = serializers.JSONField(
        help_text="Coordinates that describe the starting point and finish point of the gate line, e.g. [[lat1,lon2],[lat2,lon2]"
    )
    time_check = serializers.BooleanField()
    gate_check = serializers.BooleanField()
    end_curved = serializers.BooleanField()
    type = serializers.CharField(max_length=50, help_text="The type of the gate (tp, sp, fp, to, ldg, secret)")
    distance_next = serializers.FloatField(help_text="Distance to the next gate (NM)")
    distance_previous = serializers.FloatField(help_text="Distance from the previous gate (NM)")
    bearing_next = serializers.FloatField(help_text="True track to the next gate (degrees)")
    bearing_from_previous = serializers.FloatField(help_text="True track from the previous gates to this")
    procedure_turn_points = serializers.JSONField(
        help_text="Curve that describes the procedure turn (read-only)", required=False, read_only=True
    )
    is_procedure_turn = serializers.BooleanField()
    outside_distance = serializers.FloatField(
        help_text="The distance at which we leave the gate vicinity", read_only=True, required=False
    )
    inside_distance = serializers.FloatField(
        help_text="The distance at which we enter the gate vicinity", read_only=True, required=False
    )

    left_corridor_line = serializers.JSONField(required=False)
    right_corridor_line = serializers.JSONField(required=False)


class ProhibitedSerialiser(serializers.ModelSerializer):
    path = serializers.JSONField()

    class Meta:
        model = Prohibited
        fields = "__all__"


class RouteSerialiser(serializers.ModelSerializer):
    waypoints = WaypointSerialiser(many=True)
    landing_gate = WaypointSerialiser(required=False, help_text="Optional landing gate")
    takeoff_gate = WaypointSerialiser(required=False, help_text="Optional takeoff gate")
    prohibited_set = ProhibitedSerialiser(many=True, required=False)

    class Meta:
        model = Route
        fields = "__all__"

    @staticmethod
    def _create_waypoint(waypoint_data) -> Waypoint:
        waypoint = Waypoint(waypoint_data["name"])
        waypoint.latitude = waypoint_data["latitude"]
        waypoint.longitude = waypoint_data["longitude"]
        waypoint.elevation = waypoint_data["elevation"]
        waypoint.gate_line = waypoint_data["gate_line"]
        waypoint.width = waypoint_data["width"]
        waypoint.time_check = waypoint_data["time_check"]
        waypoint.gate_check = waypoint_data["gate_check"]
        waypoint.end_curved = waypoint_data["end_curved"]
        waypoint.type = waypoint_data["type"]
        waypoint.distance_next = waypoint_data["distance_next"]
        waypoint.distance_previous = waypoint_data["distance_previous"]
        waypoint.bearing_next = waypoint_data["bearing_next"]
        waypoint.bearing_from_previous = waypoint_data["bearing_from_previous"]
        waypoint.is_procedure_turn = waypoint_data["is_procedure_turn"]

        # waypoint.inside_distance = waypoint_data["inside_distance"]
        # waypoint.outside_distance = waypoint_data["outside_distance"]
        return waypoint

    def create(self, validated_data):
        waypoints = []
        for waypoint_data in validated_data.pop("waypoints"):
            waypoints.append(self._create_waypoint(waypoint_data))
        route = Route.objects.create(
            waypoints=waypoints,
            landing_gate=self._create_waypoint(validated_data.pop("landing_gate")),
            takeoff_gate=self._create_waypoint(validated_data.pop("takeoff_gate")),
            **validated_data,
        )
        return route

    def update(self, instance, validated_data):
        waypoints = []
        for waypoint_data in validated_data.pop("waypoints"):
            waypoints.append(self._create_waypoint(waypoint_data))
        instance.waypoints = waypoints
        instance.landing_gate = self._create_waypoint(validated_data.get("landing_gate"))
        instance.takeoff_gate = self._create_waypoint(validated_data.get("takeoff_gate"))
        return instance


class GateScoreOverrideSerialiser(serializers.ModelSerializer):
    for_gate_types = serializers.JSONField(
        help_text='List of gates types (eg. ["tp", "secret", "sp"]) that should be overridden (all lower case)'
    )

    class Meta:
        model = GateScoreOverride
        fields = "__all__"


class TrackScoreOverrideSerialiser(serializers.ModelSerializer):
    class Meta:
        model = TrackScoreOverride
        fields = "__all__"


class ContestTeamSerialiser(serializers.ModelSerializer):
    class Meta:
        model = ContestTeam
        fields = "__all__"

    def validate_team(self, team: Team):
        if not team.crew.member1.has_user and (not team.crew.member2 or not team.crew.member2.has_user):
            raise ValidationError(f"The team {team} is not tied to any registered user")


class SignupSerialiser(serializers.Serializer):
    def update(self, instance, validated_data):
        request = self.context["request"]
        contest = self.context["contest"]  # type: Contest

        contest_team = validated_data["contest_team"]
        original_team = contest_team.team
        teams = ContestTeam.objects.filter(
            Q(team__crew__member1=request.user.pk) | Q(team__crew__member2=request.user.pk), contest=contest
        ).exclude(pk=contest_team.pk)
        if teams.exists():
            raise ValidationError(
                f"You are already signed up to the contest {contest} in a different team: f{[str(item) for item in teams]}"
            )
        if validated_data["copilot_id"]:
            teams = ContestTeam.objects.filter(
                Q(team__crew__member1=validated_data["copilot_id"])
                | Q(team__crew__member2=validated_data["copilot_id"]),
                contest=contest,
            ).exclude(pk=contest_team.pk)
            if teams.exists():
                raise ValidationError(
                    f"The co-pilot is already signed up to the contest {contest} in a different team: f{[str(item) for item in teams]}"
                )

        team = Team.get_or_create_from_signup(
            self.context["request"].user,
            validated_data["copilot_id"],
            validated_data["aircraft_registration"],
            validated_data["club_name"],
        )
        new_contest_team = contest.replace_team(original_team, team, {"air_speed": validated_data["airspeed"]})

        return new_contest_team

    def create(self, validated_data):
        request = self.context["request"]
        team = Team.get_or_create_from_signup(
            self.context["request"].user,
            validated_data["copilot_id"],
            validated_data["aircraft_registration"],
            validated_data["club_name"],
        )

        contest = self.context["contest"]
        if ContestTeam.objects.filter(contest=contest, team=team).exists():
            raise ValidationError(f"Team {team} is already registered for contest {contest}")
        teams = ContestTeam.objects.filter(
            Q(team__crew__member1_id=request.user.pk) | Q(team__crew__member2_id=request.user.pk), contest=contest
        )
        if teams.exists():
            raise ValidationError(
                f"You are already signed up to the contest {contest} in a different team: f{[str(item) for item in teams]}"
            )
        if validated_data["copilot_id"]:
            teams = ContestTeam.objects.filter(
                Q(team__crew__member1=validated_data["copilot_id"])
                | Q(team__crew__member2=validated_data["copilot_id"]),
                contest=contest,
            )
            if teams.exists():
                raise ValidationError(
                    f"The co-pilot is already signed up to the contest {contest} in a different team: f{[str(item) for item in teams]}"
                )
        return contest.replace_team(None, team, {"air_speed": validated_data["airspeed"]})

    aircraft_registration = serializers.CharField()
    club_name = serializers.CharField()
    copilot_id = serializers.PrimaryKeyRelatedField(queryset=Person.objects.all(), required=False, allow_null=True)
    airspeed = serializers.FloatField()
    contest_team = serializers.PrimaryKeyRelatedField(queryset=ContestTeam.objects.all(), required=False)

    def validate_copilot_id(self, value):
        request = self.context["request"]
        my_person = Person.objects.get(email=request.user.email)
        if my_person == value:
            raise ValidationError("You cannot choose yourself as co-pilot")
        return value


class ContestTeamManagementSerialiser(serializers.ModelSerializer):
    contest = ContestParticipationSerialiser(read_only=True)
    team = TeamNestedSerialiser(read_only=True)
    can_edit = serializers.BooleanField(read_only=True)

    class Meta:
        model = ContestTeam
        fields = "__all__"


class ContestTeamNestedSerialiser(serializers.ModelSerializer):
    team = TeamNestedSerialiser()

    class Meta:
        model = ContestTeam
        fields = "__all__"


class ScorecardSerialiser(serializers.ModelSerializer):
    task_type = MultipleChoiceField(read_only=True, choices=NavigationTask.NAVIGATION_TASK_TYPES)

    class Meta:
        model = Scorecard
        fields = ("name", "task_type")


class GateScoreSerialiser(serializers.ModelSerializer):
    class Meta:
        model = GateScore
        fields = "__all__"


class ScorecardNestedSerialiser(serializers.ModelSerializer):
    class Meta:
        model = Scorecard
        fields = "__all__"


class PositionSerialiser(serializers.Serializer):
    """
    {
        "0": {
            "time": "2015-01-01T07:15:54Z",
            "altitude": 177.7005608388,
            "battery_level": 1,
            "contestant": "310",
            "course": 0,
            "device_id": "2017_101",
            "latitude": 48.10305,
            "longitude": 16.93245,
            "navigation_task": "31",
            "speed": 0
        }
    }
    """

    def create(self, validated_data):
        pass

    def update(self, instance, validated_data):
        pass

    latitude = serializers.FloatField()
    longitude = serializers.FloatField()
    altitude = serializers.FloatField()
    time = serializers.DateTimeField()
    progress = serializers.FloatField()
    device_id = serializers.CharField()
    position_id = serializers.IntegerField()


class GpxTrackSerialiser(serializers.Serializer):
    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    track_file = serializers.CharField(write_only=True, required=True, help_text="Base64 encoded gpx track file")

    def validate_track_file(self, value):
        if value:
            try:
                base64.decodebytes(bytes(value, "utf-8"))
            except Exception as e:
                raise ValidationError("track_file must be in a valid base64 string format.")
        return value


class ContestantTrackWithTrackPointsSerialiser(serializers.ModelSerializer):
    """
    Used for output to the frontend
    """

    track = PositionSerialiser(many=True, read_only=True)

    class Meta:
        model = ContestantTrack
        fields = "__all__"


class PlayingCardSerialiser(serializers.ModelSerializer):
    class Meta:
        model = PlayingCard
        fields = "__all__"


class SharingSerialiser(serializers.Serializer):
    def create(self, validated_data):
        pass

    def update(self, instance, validated_data):
        pass

    PUBLIC = "public"
    PRIVATE = "private"
    UNLISTED = "unlisted"
    VISIBILITIES = ((PUBLIC, "Public"), (PRIVATE, "Private"), (UNLISTED, "Unlisted"))
    visibility = serializers.ChoiceField(choices=VISIBILITIES)


class ContestantTrackSerialiser(serializers.ModelSerializer):
    """
    Used for output to the frontend
    """

    contest_summary = serializers.FloatField(read_only=True, required=False)

    class Meta:
        model = ContestantTrack
        fields = "__all__"


class ContestantSerialiser(serializers.ModelSerializer):
    class Meta:
        model = Contestant
        exclude = ("navigation_task", "predefined_gate_times")

    gate_score_override = GateScoreOverrideSerialiser(required=False, many=True)
    track_score_override = TrackScoreOverrideSerialiser(required=False)
    gate_times = serializers.JSONField(
        help_text="Dictionary where the keys are gate names (must match the gate names in the route file) and the values are $date-time strings (with time zone)"
    )
    default_map_url = SerializerMethodField("get_default_map_url")

    def get_default_map_url(self, contestant):
        return reverse("contestant_default_map", kwargs={"pk": contestant.pk})

    def create(self, validated_data):
        try:
            navigation_task = self.context["navigation_task"]
        except KeyError:
            raise Http404("Navigation task not found")
        validated_data["navigation_task"] = navigation_task
        gate_times = validated_data.pop("gate_times", {})
        track_score_override_data = validated_data.pop("track_score_override", None)
        gate_score_override_data = validated_data.pop("gate_score_override", None)
        contestant = Contestant.objects.create(**validated_data)
        contestant.predefined_gate_times = {key: dateutil.parser.parse(value) for key, value in gate_times.items()}
        contestant.save()
        if not ContestTeam.objects.filter(contest=contestant.navigation_task.contest, team=contestant.team).exists():
            ContestTeam.objects.create(
                contest=contestant.navigation_task.contest,
                team=contestant.team,
                tracker_device_id=contestant.tracker_device_id,
                tracking_service=contestant.tracking_service,
                air_speed=contestant.air_speed,
            )
        if track_score_override_data is not None:
            track_override = TrackScoreOverride.objects.create(**track_score_override_data)
            contestant.track_score_override = track_override
        contestant.save()
        if gate_score_override_data is not None and len(gate_score_override_data) > 0:
            for item in gate_score_override_data:
                contestant.gate_score_override.add(GateScoreOverride.objects.create(**item))

        return contestant

    def update(self, instance, validated_data):
        ContestTeam.objects.filter(contest=instance.navigation_task.contest, team=instance.team).delete()
        gate_times = validated_data.pop("gate_times", {})
        track_score_override_data = validated_data.pop("track_score_override", None)
        gate_score_override_data = validated_data.pop("gate_score_override", None)
        Contestant.objects.filter(pk=instance.pk).update(**validated_data)
        instance.refresh_from_db()
        instance.predefined_gate_times = {key: dateutil.parser.parse(value) for key, value in gate_times.items()}
        instance.save()

        if not ContestTeam.objects.filter(contest=instance.navigation_task.contest, team=instance.team).exists():
            ContestTeam.objects.create(
                contest=instance.navigation_task.contest,
                team=instance.team,
                tracker_device_id=instance.tracker_device_id,
                tracking_service=instance.tracking_service,
                air_speed=instance.air_speed,
            )
        if track_score_override_data is not None:
            track_override = TrackScoreOverride.objects.create(**track_score_override_data)
            instance.track_score_override = track_override
        instance.save()
        if gate_score_override_data is not None and len(gate_score_override_data) > 0:
            for item in gate_score_override_data:
                instance.gate_score_override.add(GateScoreOverride.objects.create(**item))
        return instance


class OngoingNavigationSerialiser(serializers.ModelSerializer):
    contest = ContestSerialiser(read_only=True)
    active_contestants = SerializerMethodField("get_active_contestants")

    class Meta:
        model = NavigationTask
        fields = ("pk", "name", "start_time", "finish_time", "tracking_link", "active_contestants", "contest")

    def get_active_contestants(self, navigation_task):
        future_contestants = navigation_task.contestant_set.filter(
            contestanttrack__calculator_started=True,
            contestanttrack__calculator_finished=False
        )
        serialiser = ContestantSerialiser(future_contestants, many=True, read_only=True)
        return serialiser.data


class ContestantNestedTeamSerialiser(ContestantSerialiser):
    """
    Contestants. When putting or patching, note that the entire team has to be specified for it to be changed.
    Otherwise changes will be ignored.
    """

    team = TeamNestedSerialiser()

    class Meta:
        model = Contestant
        exclude = ("navigation_task", "predefined_gate_times")

    def create(self, validated_data):
        team_data = validated_data.pop("team")
        team_serialiser = TeamNestedSerialiser(data=team_data)
        team_serialiser.is_valid(True)
        team = team_serialiser.save()
        validated_data["team"] = team
        return super().create(validated_data)

    def update(self, instance, validated_data):
        team_data = validated_data.pop("team", None)
        if team_data:
            try:
                team_instance = Team.objects.get(pk=team_data.get("id"))
            except ObjectDoesNotExist:
                team_instance = None
            team_serialiser = TeamNestedSerialiser(instance=team_instance, data=team_data)
            team_serialiser.is_valid(True)
            team = team_serialiser.save()
            validated_data.update({"team": team.pk})
        return super().update(instance, validated_data)


class ContestantNestedTeamSerialiserWithContestantTrack(ContestantNestedTeamSerialiser):
    contestanttrack = ContestantTrackSerialiser(read_only=True)


class NavigationTaskNestedTeamRouteSerialiser(serializers.ModelSerializer):
    contestant_set = ContestantNestedTeamSerialiserWithContestantTrack(many=True, read_only=True)
    gate_score_override = GateScoreOverrideSerialiser(required=False, many=True)
    track_score_override = TrackScoreOverrideSerialiser(required=False)
    scorecard_data = serializers.SerializerMethodField()
    scorecard = SlugRelatedField(
        slug_field="name",
        queryset=Scorecard.objects.all(),
        required=False,
        help_text="Reference to an existing scorecard name. Currently existing scorecards: {}".format(
            lambda: ", ".join(["'{}'".format(item) for item in Scorecard.objects.all()])
        ),
    )
    actual_rules = serializers.JSONField(read_only=True)
    display_contestant_rank_summary = serializers.BooleanField(read_only=True)
    share_string = serializers.CharField(read_only=True)
    route = RouteSerialiser()
    contest = serializers.PrimaryKeyRelatedField(read_only=True)

    def get_scorecard_data(self, navigation_task):
        return ScorecardSerialiser(instance=navigation_task.scorecard).data

    class Meta:
        model = NavigationTask
        fields = "__all__"

    def create(self, validated_data):
        user = self.context["request"].user
        track_score_override_data = validated_data.pop("track_score_override", None)
        gate_score_override_data = validated_data.pop("gate_score_override", None)
        contestant_set = validated_data.pop("contestant_set", [])
        try:
            validated_data["contest"] = self.context["contest"]
        except KeyError:
            raise Http404("Contest not found")

        route = validated_data.pop("route", None)
        route_serialiser = RouteSerialiser(data=route)
        route_serialiser.is_valid(raise_exception=True)
        route = route_serialiser.save()
        assign_perm("view_route", user, route)
        assign_perm("delete_route", user, route)
        assign_perm("change_route", user, route)
        track_override = None
        if track_score_override_data is not None:
            track_override = TrackScoreOverride.objects.create(**track_score_override_data)
        navigation_task = NavigationTask.objects.create(
            **validated_data, track_score_override=track_override, route=route
        )
        if gate_score_override_data is not None and len(gate_score_override_data) > 0:
            for item in gate_score_override_data:
                navigation_task.gate_score_override.add(GateScoreOverride.objects.create(**item))

        for contestant_data in contestant_set:
            contestant_serialiser = ContestantNestedTeamSerialiser(
                data=contestant_data, context={"navigation_task": navigation_task}
            )
            contestant_serialiser.is_valid(True)
            contestant_serialiser.save()
        return navigation_task


class ExternalNavigationTaskNestedTeamSerialiser(serializers.ModelSerializer):
    contestant_set = ContestantNestedTeamSerialiser(many=True)
    scorecard = SlugRelatedField(
        slug_field="name",
        queryset=Scorecard.objects.all(),
        required=True,
        help_text="Reference to an existing scorecard name. Currently existing scorecards: {}".format(
            lambda: ", ".join(["'{}'".format(item) for item in Scorecard.objects.all()])
        ),
    )
    gate_score_override = GateScoreOverrideSerialiser(required=False, many=True)
    track_score_override = TrackScoreOverrideSerialiser(required=False)
    route_file = serializers.CharField(write_only=True, required=True, help_text="Base64 encoded gpx file")
    internal_serialiser = ContestantNestedTeamSerialiser

    class Meta:
        model = NavigationTask
        exclude = ("route", "contest")

    def validate_route_file(self, value):
        if value:
            try:
                base64.decodebytes(bytes(value, "utf-8"))
            except Exception as e:
                raise ValidationError("route_file must be in a valid base64 string format.")
        return value

    def create(self, validated_data):
        with transaction.atomic():
            contestant_set = validated_data.pop("contestant_set", [])
            route_file = validated_data.pop("route_file", None)
            track_score_override_data = validated_data.pop("track_score_override", None)
            gate_score_override_data = validated_data.pop("gate_score_override", None)
            try:
                route = create_precision_route_from_gpx(
                    base64.decodebytes(route_file.encode("utf-8")), validated_data["scorecard"].use_procedure_turns
                )
            except Exception as e:
                raise ValidationError("Failed building route from provided GPX: {}".format(e))
            user = self.context["request"].user
            try:
                validated_data["contest"] = self.context["contest"]
            except KeyError:
                raise Http404("Contest not found")

            validated_data["route"] = route
            assign_perm("view_route", user, route)
            assign_perm("delete_route", user, route)
            assign_perm("change_route", user, route)
            print(self.context)
            track_override = None
            if track_score_override_data is not None:
                track_override = TrackScoreOverride.objects.create(**track_score_override_data)
            navigation_task = NavigationTask.objects.create(**validated_data, track_score_override=track_override)
            if gate_score_override_data is not None and len(gate_score_override_data) > 0:
                for item in gate_score_override_data:
                    navigation_task.gate_score_override.add(GateScoreOverride.objects.create(**item))
            for contestant_data in contestant_set:
                if isinstance(contestant_data["team"], Team):
                    contestant_data["team"] = contestant_data["team"].pk

            contestant_serialiser = self.internal_serialiser(
                data=contestant_set, many=True, context={"navigation_task": navigation_task}
            )
            contestant_serialiser.is_valid(True)
        contestant_serialiser.save()
        return navigation_task


class ExternalNavigationTaskTeamIdSerialiser(ExternalNavigationTaskNestedTeamSerialiser):
    """
    Does not provide team data input, only team ID for each contestant.
    """

    contestant_set = ContestantSerialiser(many=True)
    internal_serialiser = ContestantSerialiser

    class Meta:
        model = NavigationTask
        exclude = ("route", "contest")


class TrackAnnotationSerialiser(serializers.ModelSerializer):
    class Meta:
        model = TrackAnnotation
        fields = "__all__"


class ScoreLogEntrySerialiser(serializers.ModelSerializer):
    class Meta:
        model = ScoreLogEntry
        fields = "__all__"


class GateCumulativeScoreSerialiser(serializers.ModelSerializer):
    class Meta:
        model = GateCumulativeScore
        fields = "__all__"


########## Results service ##########
########## Write data ##########


########## Fetch data #############
class TeamTestScoreSerialiser(serializers.ModelSerializer):
    class Meta:
        model = TeamTestScore
        fields = "__all__"


class TaskSummarySerialiser(serializers.ModelSerializer):
    class Meta:
        model = TaskSummary
        fields = "__all__"


class TaskTestNestedSerialiser(serializers.ModelSerializer):
    teamtestscore_set = TeamTestScoreSerialiser(many=True)

    class Meta:
        model = TaskTest
        fields = "__all__"


class TaskNestedSerialiser(serializers.ModelSerializer):
    tasktest_set = TaskTestNestedSerialiser(many=True)
    tasksummary_set = TaskSummarySerialiser(many=True)

    class Meta:
        model = Task
        fields = "__all__"


# Details entry
class ContestResultsDetailsSerialiser(serializers.ModelSerializer):
    contestsummary_set = ContestSummaryNestedSerialiser(many=True)
    task_set = TaskNestedSerialiser(many=True)
    time_zone = TimeZoneSerializerField(required=True)
    permission_change_contest = serializers.BooleanField(read_only=True)

    class Meta:
        model = Contest
        fields = "__all__"


# Team summary entry
class TeamResultsSummarySerialiser(serializers.ModelSerializer):
    contestsummary_set = ContestSummaryNestedSerialiser(many=True)

    class Meta:
        model = Team
        fields = "__all__"


######################  write data #####################
class ContestSummaryWithoutReferenceSerialiser(serializers.ModelSerializer):
    contest = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = ContestSummary
        fields = "__all__"

    def create(self, validated_data):
        try:
            validated_data["contest"] = self.context["contest"]
        except KeyError:
            raise Http404("Contest not found")

        return ContestSummary.objects.create(**validated_data)


class TaskSummaryWithoutReferenceSerialiser(serializers.ModelSerializer):
    task = serializers.PrimaryKeyRelatedField(queryset=Task.objects.all())

    class Meta:
        model = TaskSummary
        fields = "__all__"


class TeamTestScoreWithoutReferenceSerialiser(serializers.ModelSerializer):
    task_test = serializers.PrimaryKeyRelatedField(queryset=TaskTest.objects.all(), required=True)

    class Meta:
        model = TeamTestScore
        fields = "__all__"


# TODO: Not used?
class TaskTestWithoutReferenceNestedSerialiser(serializers.ModelSerializer):
    teamtestscore_set = TeamTestScoreWithoutReferenceSerialiser(many=True)
    task = serializers.PrimaryKeyRelatedField(queryset=Task.objects.all())

    class Meta:
        model = TaskTest
        fields = "__all__"


class TaskWithoutReferenceNestedSerialiser(serializers.ModelSerializer):
    tasktest_set = TaskTestWithoutReferenceNestedSerialiser(many=True)
    tasksummary_set = TaskSummaryWithoutReferenceSerialiser(many=True)

    class Meta:
        model = Task
        exclude = ("contest",)

    def create(self, validated_data):
        task_test_data = validated_data.pop("tasktest_set", [])
        task_summary_data = validated_data.pop("tasksummary_set", [])
        try:
            validated_data["contest"] = self.context["contest"]
        except KeyError:
            raise Http404("Contest not found")

        task = Task.objects.create(**validated_data)
        for item in task_summary_data:
            item["task"] = task
            TaskSummary.objects.create(**item)
        for task_test_data in task_test_data:
            task_test_data["task"] = task
            team_test_score_data = task_test_data.pop("teamtestscore_set", [])
            task_test = TaskTest.objects.create(**task_test_data)
            for i in team_test_score_data:
                i["task_test"] = task_test
                TeamTestScore.objects.create(**i)
        return task


class TaskSerialiser(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = "__all__"


class TaskTestSerialiser(serializers.ModelSerializer):
    class Meta:
        model = TaskTest
        fields = "__all__"


class EditableRouteSerialiser(ObjectPermissionsAssignmentMixin, serializers.ModelSerializer):
    route = serializers.JSONField()

    class Meta:
        model = EditableRoute
        fields = "__all__"

    def get_permissions_map(self, created):
        user = self.context["request"].user
        return {"change_editableroute": [user], "delete_editableroute": [user], "view_editableroute": [user]}
