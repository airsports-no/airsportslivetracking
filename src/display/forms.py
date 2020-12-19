from django import forms

from display.models import NavigationTask, Contestant, Contest

TURNPOINT = "tp"
STARTINGPOINT = "sp"
FINISHPOINT = "fp"
SECRETPOINT = "secret"
TAKEOFF_GATE = "to"
LANDING_GATE = "ldg"
GATES_TYPES = (
    (TURNPOINT, "Turning point"),
    (STARTINGPOINT, "Starting point"),
    (FINISHPOINT, "Finish point"),
    (SECRETPOINT, "Secret point"),
    (TAKEOFF_GATE, "Takeoff gate"),
    (LANDING_GATE, "Landing gate")
)

FILE_TYPE_CSV = "csv"
FILE_TYPE_FLIGHTCONTEST_GPX = "fcgpx"
FILE_TYPE_KML = "kml"
FILE_TYPES = (
    (FILE_TYPE_CSV, "csv"),
    (FILE_TYPE_FLIGHTCONTEST_GPX, "FlightContest GPX file"),
    (FILE_TYPE_KML, "KML file")
)


class ImportRouteForm(forms.Form):
    name = forms.CharField(max_length=100)
    file_type = forms.ChoiceField(choices=FILE_TYPES)
    file = forms.FileField()


class WaypointForm(forms.Form):
    name = forms.CharField(max_length=200)
    width = forms.FloatField(help_text="Width of the gate in NM", initial=1)
    latitude = forms.FloatField(help_text="degrees")
    longitude = forms.FloatField(help_text="degrees")
    time_check = forms.BooleanField(required=False)
    gate_check = forms.BooleanField(required=False)
    type = forms.ChoiceField(initial=TURNPOINT, choices=GATES_TYPES)
    is_procedure_turn = forms.BooleanField(required=False)


class NavigationTaskForm(forms.ModelForm):
    class Meta:
        model = NavigationTask
        fields = ("name", "start_time", "finish_time", "is_public")


class ContestForm(forms.ModelForm):
    class Meta:
        model = Contest
        fields = "__all__"


class ContestantForm(forms.ModelForm):
    class Meta:
        model = Contestant
        fields = (
            "contestant_number", "team", "tracker_start_time", "traccar_device_name", "takeoff_time",
            "finished_by_time",
            "minutes_to_starting_point", "air_speed", "wind_direction", "wind_speed", "scorecard")
