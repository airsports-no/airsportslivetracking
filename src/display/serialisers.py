from rest_framework import serializers

from display.models import Contest, Aeroplane, Team, Track, Contestant, ContestantTrack


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
    aeroplane = AeroplaneSerialiser(read_only=True)

    class Meta:
        model = Team
        fields = "__all__"


class ContestantSerialiser(serializers.ModelSerializer):
    team = TeamSerialiser(read_only=True)
    gate_times = serializers.JSONField()

    class Meta:
        model = Contestant
        fields = "__all__"


class ContestSerialiser(serializers.ModelSerializer):
    contestant_set = ContestantSerialiser(many=True, read_only=True)
    track = TrackSerialiser(read_only=True)

    class Meta:
        model = Contest
        fields = "__all__"


class ContestantTrackSerialiser(serializers.ModelSerializer):
    score_log = serializers.JSONField()
    score_per_gate = serializers.JSONField()
    contestant = ContestantSerialiser()

    class Meta:
        model = ContestantTrack
        fields = "__all__"
