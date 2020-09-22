from rest_framework import serializers

from display.models import Contest, Aeroplane, Team, Track, Contestant, ContestantTrack


class TrackSerialiser(serializers.ModelSerializer):
    waypoints = serializers.JSONField()
    starting_line = serializers.JSONField()

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

    class Meta:
        model = ContestantTrack
        fields = "__all__"
