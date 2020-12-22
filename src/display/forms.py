from django import forms
from phonenumber_field.formfields import PhoneNumberField

from display.models import NavigationTask, Contestant, Contest, Person, Crew, Aeroplane, Team

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
    (FILE_TYPE_CSV, "CSV"),
    (FILE_TYPE_FLIGHTCONTEST_GPX, "FlightContest GPX file"),
    (FILE_TYPE_KML, "KML file")
)


class ImportRouteForm(forms.Form):
    name = forms.CharField(max_length=100, label="Route name")
    file_type = forms.ChoiceField(choices=FILE_TYPES)
    file = forms.FileField()


class WaypointForm(forms.Form):
    name = forms.CharField(max_length=200)
    width = forms.FloatField(help_text="Width of the gate in NM", initial=1)
    latitude = forms.FloatField(help_text="degrees")
    longitude = forms.FloatField(help_text="degrees")
    time_check = forms.BooleanField(required=False, initial=True)
    gate_check = forms.BooleanField(required=False, initial=True)
    type = forms.ChoiceField(initial=TURNPOINT, choices=GATES_TYPES)


class NavigationTaskForm(forms.ModelForm):
    class Meta:
        model = NavigationTask
        fields = ("name", "start_time", "finish_time", "is_public")


class ContestForm(forms.ModelForm):
    class Meta:
        model = Contest
        fields = "__all__"


class ContestantForm(forms.ModelForm):
    pilot_first_name = forms.CharField()
    pilot_last_name = forms.CharField()
    pilot_phone = PhoneNumberField(required=False)
    pilot_email = forms.EmailField(required=False)

    copilot_first_name = forms.CharField(required=False)
    copilot_last_name = forms.CharField(required=False)
    copilot_phone = PhoneNumberField(required=False)
    copilot_email = forms.EmailField(required=False)

    aircraft_registration = forms.CharField()

    class Meta:
        model = Contestant
        fields = (
            "contestant_number", "tracker_start_time", "tracking_service", "traccar_device_name", "takeoff_time",
            "finished_by_time",
            "minutes_to_starting_point", "air_speed", "wind_direction", "wind_speed", "scorecard")

    def save(self, commit=True):
        contestant = super().save(commit=False)
        member1 = Person.get_or_create(self.cleaned_data["pilot_first_name"], self.cleaned_data["pilot_last_name"],
                                       self.cleaned_data["pilot_phone"], self.cleaned_data["pilot_email"])
        member2 = Person.get_or_create(self.cleaned_data["copilot_first_name"], self.cleaned_data["copilot_last_name"],
                                       self.cleaned_data["copilot_phone"], self.cleaned_data["copilot_email"])
        crew, _ = Crew.objects.get_or_create(member1=member1, member2=member2)
        aircraft, _ = Aeroplane.objects.get_or_create(registration=self.cleaned_data["aircraft_registration"])
        team, _ = Team.objects.get_or_create(crew=crew, aeroplane=aircraft)
        contestant.team = team
        if commit:
            contestant.save()
        return contestant
