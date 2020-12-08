import base64

from rest_framework import serializers
from rest_framework.fields import FileField, DateTimeField, CharField
from rest_framework.relations import SlugRelatedField

from display.models import Contest, Aeroplane, Team, Track, Contestant, ContestantTrack, Scorecard
from display.show_slug_choices import ChoicesSlugRelatedField


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


class TeamSerialiser(serializers.ModelSerializer):
    aeroplane = SlugRelatedField(slug_field="registration", queryset=Aeroplane.objects.all())

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
        exclude = ("contest",)


class ContestSerialiser(serializers.ModelSerializer):
    contestant_set = ContestantSerialiser(many=True, read_only=True)
    track = TrackSerialiser(read_only=True)

    class Meta:
        model = Contest
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


class ExternalContestSerialiser(serializers.ModelSerializer):
    contestant_set = ContestantSerialiser(many=True)
    track_file = serializers.CharField(write_only=True, read_only=False, required=True,
                                       help_text="Base64 encoded gpx file")

    class Meta:
        model = Contest
        exclude = ("track",)

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

        vdes_message = VdesMessage.objects.create(**validated_data, producer_mmsi=producer_mmsi)
        if destination_data:
            dest = [VdesDestination(vdes_message=vdes_message, **item) for item in destination_data]
            VdesDestination.objects.bulk_create(dest)
        VdesMessageStatus.objects.create(vdes_message=vdes_message)
