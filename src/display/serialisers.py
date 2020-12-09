import base64

from rest_framework import serializers
from rest_framework.relations import SlugRelatedField
from rest_framework_guardian.serializers import ObjectPermissionsAssignmentMixin

from display.convert_flightcontest_gpx import create_track_from_gpx
from display.models import NavigationTask, Aeroplane, Team, Track, Contestant, ContestantTrack, Scorecard, Crew, Contest


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
    gate_line_infinite = serializers.JSONField()
    time_check = serializers.BooleanField()
    gate_check = serializers.BooleanField()
    end_curved = serializers.BooleanField()
    type = serializers.CharField(max_length=50)
    distance_next = serializers.FloatField()
    bearing_next = serializers.FloatField()
    is_procedure_turn = serializers.BooleanField()


class TrackSerialiser(serializers.ModelSerializer):
    waypoints = WaypointSerialiser(many=True)
    starting_line = WaypointSerialiser
    landing_gate = WaypointSerialiser
    takeoff_gate = WaypointSerialiser

    class Meta:
        model = Track
        fields = "__all__"


class AeroplaneSerialiser(serializers.ModelSerializer):
    class Meta:
        model = Aeroplane
        fields = "__all__"


class CrewSerialiser(serializers.ModelSerializer):
    class Meta:
        model = Crew
        fields = "__all__"


class TeamSerialiser(serializers.ModelSerializer):
    aeroplane = AeroplaneSerialiser()
    crew = CrewSerialiser()

    class Meta:
        model = Team
        fields = "__all__"


class ScorecardSerialiser(serializers.ModelSerializer):
    class Meta:
        model = Scorecard
        fields = ("name",)


class ContestantSerialiser(serializers.ModelSerializer):
    team = TeamSerialiser()
    gate_times = serializers.JSONField(
        help_text="Dictionary where the keys are gate names (must match the gate names in the track file) and the values are $date-time strings (with time zone)")
    scorecard = SlugRelatedField(slug_field="name", queryset=Scorecard.objects.all(),
                                 help_text="Reference to an existing scorecard name. Currently existing scorecards: {}".format(
                                     ", ".join(["'{}'".format(item) for item in Scorecard.objects.all()])))

    class Meta:
        model = Contestant
        # fields = "__all__"
        exclude = ("navigation_task",)


class NavigationTaskSerialiser(serializers.ModelSerializer):
    contestant_set = ContestantSerialiser(many=True, read_only=True)
    track = TrackSerialiser(read_only=True)

    class Meta:
        model = NavigationTask
        fields = "__all__"


class ContestantTrackSerialiser(serializers.ModelSerializer):
    """
    Used for output to the frontend
    """
    score_log = serializers.JSONField()
    score_per_gate = serializers.JSONField()
    contestant = ContestantSerialiser()

    class Meta:
        model = ContestantTrack
        fields = "__all__"


class ExternalNavigationTaskSerialiser(ObjectPermissionsAssignmentMixin, serializers.ModelSerializer):
    contestant_set = ContestantSerialiser(many=True)
    track_file = serializers.CharField(write_only=True, read_only=False, required=True,
                                       help_text="Base64 encoded gpx file")

    class Meta:
        model = NavigationTask
        exclude = ("track",)

    def get_permissions_map(self, created):
        user = self.context["request"].user
        return {
            "publish_navigationtask": [user],
            "delete_navigationtask": [user],
            "view_navigationtask": [user]
        }

    def validate_track_file(self, value):
        if value:
            try:
                base64.decodebytes(bytes(value, 'utf-8'))
            except Exception as e:
                raise serializers.ValidationError("track_file must be in a valid base64 string format.")
        return value

    def create(self, validated_data):
        contestant_set = validated_data.pop("contestant_set", None)
        track_file = validated_data.pop("track_file", None)
        track = create_track_from_gpx(validated_data["name"], base64.decodebytes(track_file))
        navigation_task = NavigationTask.objects.create(**validated_data, track=track, contest=self.context["contest"])
        for contestant_data in contestant_set:
            team_data = contestant_data.pop("team")
            aeroplane_data = team_data.pop("aeroplane")
            crew_data = team_data.pop("crew")
            aeroplane, _ = Aeroplane.objects.get_or_create(defaults=aeroplane_data,
                                                           registration=aeroplane_data["registration"])
            crew, _ = Crew.objects.get_or_create(**crew_data)
            team = Team.objects.get_or_create(crew=crew, aeroplane=aeroplane)
            Contestant.objects.create(**contestant_data, team=team)
        return navigation_task
