import base64

from guardian.shortcuts import assign_perm
from rest_framework import serializers
from rest_framework.relations import SlugRelatedField
from rest_framework_guardian.serializers import ObjectPermissionsAssignmentMixin

from display.convert_flightcontest_gpx import create_route_from_gpx
from display.models import NavigationTask, Aeroplane, Team, Route, Contestant, ContestantTrack, Scorecard, Crew, Contest
from display.waypoint import Waypoint


class ContestSerialiser(ObjectPermissionsAssignmentMixin, serializers.ModelSerializer):
    class Meta:
        model = Contest
        fields = "__all__"

    def get_permissions_map(self, created):
        user = self.context["request"].user
        return {
            "change_contest": [user],
            "delete_contest": [user],
            "publish_contest": [user],
            "view_contest": [user]
        }


class WaypointSerialiser(serializers.Serializer):
    def create(self, validated_data):
        pass

    def update(self, instance, validated_data):
        pass

    name = serializers.CharField(max_length=200)
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()
    elevation = serializers.FloatField()
    width = serializers.FloatField()
    gate_line = serializers.JSONField()
    time_check = serializers.BooleanField()
    gate_check = serializers.BooleanField()
    planning_test = serializers.BooleanField()
    end_curved = serializers.BooleanField()
    type = serializers.CharField(max_length=50)
    distance_next = serializers.FloatField()
    bearing_next = serializers.FloatField()
    is_procedure_turn = serializers.BooleanField()


class RouteSerialiser(serializers.ModelSerializer):
    waypoints = WaypointSerialiser(many=True)
    starting_line = WaypointSerialiser()
    landing_gate = WaypointSerialiser()
    takeoff_gate = WaypointSerialiser()

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
        waypoint.planning_test = waypoint_data["planning_test"]
        waypoint.end_curved = waypoint_data["end_curved"]
        waypoint.type = waypoint_data["type"]
        waypoint.distance_next = waypoint_data["distance_next"]
        waypoint.bearing_next = waypoint_data["bearing_next"]
        waypoint.is_procedure_turn = waypoint_data["is_procedure_turn"]

        # waypoint.inside_distance = waypoint_data["inside_distance"]
        # waypoint.outside_distance = waypoint_data["outside_distance"]
        return waypoint

    def create(self, validated_data):
        waypoints = []
        for waypoint_data in validated_data.pop("waypoints"):
            waypoints.append(self._create_waypoint(waypoint_data))
        route = Route.objects.create(waypoints=waypoints,
                                     starting_line=self._create_waypoint(validated_data.pop("starting_line")),
                                     landing_gate=self._create_waypoint(validated_data.pop("landing_gate")),
                                     takeoff_gate=self._create_waypoint(validated_data.pop("takeoff_gate")),
                                     **validated_data)
        return route

    def update(self, instance, validated_data):
        waypoints = []
        for waypoint_data in validated_data.pop("waypoints"):
            waypoints.append(self._create_waypoint(waypoint_data))
        instance.waypoints = waypoints
        instance.starting_line = self._create_waypoint(validated_data["starting_line"])
        instance.london_gate = self._create_waypoint(validated_data["landing_gate"])
        instance.takeoff_gate = self._create_waypoint(validated_data["takeoff_gate"])
        return instance


class AeroplaneSerialiser(serializers.ModelSerializer):
    class Meta:
        model = Aeroplane
        fields = "__all__"


class CrewSerialiser(serializers.ModelSerializer):
    class Meta:
        model = Crew
        fields = "__all__"


class TeamNestedSerialiser(serializers.ModelSerializer):
    aeroplane = AeroplaneSerialiser()
    crew = CrewSerialiser()

    class Meta:
        model = Team
        fields = "__all__"


class ScorecardSerialiser(serializers.ModelSerializer):
    class Meta:
        model = Scorecard
        fields = ("name",)


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


class TrackSerialiser(serializers.Serializer):
    def create(self, validated_data):
        pass

    def update(self, instance, validated_data):
        pass

    positions = PositionSerialiser(many=True)


class ContestantTrackWithTrackPointsSerialiser(serializers.ModelSerializer):
    """
    Used for output to the frontend
    """
    score_log = serializers.JSONField()
    score_per_gate = serializers.JSONField()
    track = PositionSerialiser(many=True)

    class Meta:
        model = ContestantTrack
        fields = "__all__"


class ContestantTrackSerialiser(serializers.ModelSerializer):
    """
    Used for output to the frontend
    """
    score_log = serializers.JSONField()
    score_per_gate = serializers.JSONField()

    class Meta:
        model = ContestantTrack
        fields = "__all__"


class ContestantNestedSerialiser(serializers.ModelSerializer):
    team = TeamNestedSerialiser()
    gate_times = serializers.JSONField(
        help_text="Dictionary where the keys are gate names (must match the gate names in the route file) and the values are $date-time strings (with time zone)")
    scorecard = SlugRelatedField(slug_field="name", queryset=Scorecard.objects.all(),
                                 help_text="Reference to an existing scorecard name. Currently existing scorecards: {}".format(
                                     ", ".join(["'{}'".format(item) for item in Scorecard.objects.all()])))
    contestanttrack = ContestantTrackSerialiser(required=False)

    class Meta:
        model = Contestant
        exclude = ("navigation_task", "predefined_gate_times")


class ContestantSerialiser(serializers.ModelSerializer):
    gate_times = serializers.JSONField(
        help_text="Dictionary where the keys are gate names (must match the gate names in the route file) and the values are $date-time strings (with time zone)")
    scorecard = SlugRelatedField(slug_field="name", queryset=Scorecard.objects.all(),
                                 help_text="Reference to an existing scorecard name. Currently existing scorecards: {}".format(
                                     ", ".join(["'{}'".format(item) for item in Scorecard.objects.all()])))

    class Meta:
        model = Contestant
        exclude = ("predefined_gate_times",)


class NavigationTaskSerialiser(serializers.ModelSerializer):
    class Meta:
        model = NavigationTask
        fields = "__all__"


class NavigationTaskNestedSerialiser(serializers.ModelSerializer):
    contestant_set = ContestantNestedSerialiser(many=True, read_only=True)
    route = RouteSerialiser(read_only=True)

    class Meta:
        model = NavigationTask
        fields = "__all__"


class ExternalNavigationTaskNestedSerialiser(ObjectPermissionsAssignmentMixin, serializers.ModelSerializer):
    contestant_set = ContestantNestedSerialiser(many=True)
    route_file = serializers.CharField(write_only=True, read_only=False, required=True,
                                       help_text="Base64 encoded gpx file")

    class Meta:
        model = NavigationTask
        exclude = ("route",)

    def get_permissions_map(self, created):
        user = self.context["request"].user
        return {
            "publish_navigationtask": [user],
            "delete_navigationtask": [user],
            "view_navigationtask": [user]
        }

    def validate_route_file(self, value):
        if value:
            try:
                base64.decodebytes(bytes(value, 'utf-8'))
            except Exception as e:
                raise serializers.ValidationError("route_file must be in a valid base64 string format.")
        return value

    def create(self, validated_data):
        contestant_set = validated_data.pop("contestant_set", None)
        route_file = validated_data.pop("route_file", None)
        route = create_route_from_gpx(validated_data["name"], base64.decodebytes(route_file.encode("utf-8")))
        user = self.context["request"].user
        assign_perm("view_route", user, route)
        assign_perm("delete_route", user, route)
        assign_perm("change_route", user, route)
        print(self.context)
        navigation_task = NavigationTask.objects.create(**validated_data, route=route, contest=self.context["contest"])
        for contestant_data in contestant_set:
            team_data = contestant_data.pop("team")
            aeroplane_data = team_data.pop("aeroplane")
            crew_data = team_data.pop("crew")
            aeroplane, _ = Aeroplane.objects.get_or_create(defaults=aeroplane_data,
                                                           registration=aeroplane_data["registration"])
            crew, _ = Crew.objects.get_or_create(**crew_data)
            team, _ = Team.objects.get_or_create(crew=crew, aeroplane=aeroplane)
            Contestant.objects.create(**contestant_data, team=team, navigation_task=navigation_task)
        return navigation_task
