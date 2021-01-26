from string import Template

from crispy_forms.bootstrap import StrictButton
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Div, ButtonHolder, Submit, Button, Fieldset, Field
from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.forms import HiddenInput
from django.utils.safestring import mark_safe
from phonenumber_field.formfields import PhoneNumberField
from timezone_field import TimeZoneFormField

from display.map_plotter import A4, A3, N250_MAP, OSM_MAP
from display.models import NavigationTask, Contestant, Contest, Person, Crew, Aeroplane, Team, Club, \
    ContestTeam, TASK_TYPES, TrackScoreOverride

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

MAP_SIZES = (
    (A4, A4),
    (A3, A3)
)
SCALE_250 = 250
SCALE_200 = 200
SCALE_TO_FIT = 0
SCALES = (
    (SCALE_200, "1:200,000"),
    (SCALE_250, "1:250,000"),
    (SCALE_TO_FIT, "Fit page")
)

LANDSCAPE = 0
PORTRAIT = 1
ORIENTATIONS = (
    (LANDSCAPE, "Landscape"),
    (PORTRAIT, "Portrait")
)

MAP_SOURCES = (
    (OSM_MAP, "OSM"),
    (N250_MAP, "Norway 1:250,000")
)


class MapForm(forms.Form):
    size = forms.ChoiceField(choices=MAP_SIZES, initial=A4)
    zoom_level = forms.IntegerField(initial=12)
    orientation = forms.ChoiceField(choices=ORIENTATIONS, initial=LANDSCAPE)
    include_only_waypoints = forms.BooleanField(initial=False, required=False)
    scale = forms.ChoiceField(choices=SCALES, initial=SCALE_TO_FIT)
    map_source = forms.ChoiceField(choices=MAP_SOURCES, initial=OSM_MAP)
    dpi = forms.IntegerField(initial=300, min_value=100, max_value=1000)


class ContestantMapForm(forms.Form):
    size = forms.ChoiceField(choices=MAP_SIZES, initial=A4)
    zoom_level = forms.IntegerField(initial=12)
    orientation = forms.ChoiceField(choices=ORIENTATIONS, initial=LANDSCAPE)
    scale = forms.ChoiceField(choices=SCALES, initial=SCALE_TO_FIT)
    map_source = forms.ChoiceField(choices=MAP_SOURCES, initial=OSM_MAP)
    include_annotations = forms.BooleanField(required=False, initial=True)
    dpi = forms.IntegerField(initial=300, min_value=100, max_value=1000)


class PrecisionScoreOverrideForm(forms.Form):
    backtracking_penalty = forms.FloatField(required=False)

    def build_score_override(self, navigation_task: NavigationTask) -> TrackScoreOverride:
        return TrackScoreOverride.objects.create(navigation_task=navigation_task,
                                                 bad_course_penalty=self.cleaned_data["backtracking_penalty"])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.add_input(Submit("submit", "Submit"))


class ANRCorridorScoreOverrideForm(forms.Form):
    corridor_width = forms.FloatField(required=True)
    corridor_grace_time = forms.IntegerField(required=True)

    def build_score_override(self, navigation_task: NavigationTask) -> TrackScoreOverride:
        return TrackScoreOverride.objects.create(navigation_task=navigation_task,
                                                 corridor_width=self.cleaned_data["corridor_width"],
                                                 corridor_grace_time=self.cleaned_data["corridor_grace_time"])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.add_input(Submit("submit", "Submit"))


class TaskTypeForm(forms.Form):
    task_type = forms.ChoiceField(choices=TASK_TYPES,
                                  help_text="The type of the task. This determines how the route file is processed")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.add_input(Submit("submit", "Submit"))


class PrecisionImportRouteForm(forms.Form):
    file_type = forms.ChoiceField(choices=FILE_TYPES)
    file = forms.FileField(validators=[FileExtensionValidator(allowed_extensions=["kml", "csv", "gpx"])])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.add_input(Submit("submit", "Submit"))


class ANRCorridorImportRouteForm(forms.Form):
    file = forms.FileField(validators=[FileExtensionValidator(allowed_extensions=["kml"])])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.add_input(Submit("submit", "Submit"))


class WaypointFormHelper(FormHelper):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_input(Submit("submit", "Submit"))
        self.template = "bootstrap/table_inline_formset.html"


class WaypointForm(forms.Form):
    name = forms.CharField(max_length=200)
    width = forms.FloatField(initial=1)
    latitude = forms.FloatField(help_text="degrees", widget=forms.HiddenInput())
    longitude = forms.FloatField(help_text="degrees", widget=forms.HiddenInput())
    time_check = forms.BooleanField(required=False, initial=True)
    gate_check = forms.BooleanField(required=False, initial=True)
    type = forms.ChoiceField(initial=TURNPOINT, choices=GATES_TYPES)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        print(self.initial)


class NavigationTaskForm(forms.ModelForm):
    class Meta:
        model = NavigationTask
        fields = ("name", "start_time", "finish_time", "is_public", "scorecard")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.add_input(Submit("submit", "Submit"))


# class BasicScoreOverrideForm(forms.ModelForm):
#     for_gate_types = forms.MultipleChoiceField(initial=[TURNPOINT, SECRETPOINT, STARTINGPOINT, FINISHPOINT],
#                                                choices=GATES_TYPES)
#
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         if self.instance:
#             # print("Setting initial:|{}".format( self.instance.for_gate_types))
#             self.initial["for_gate_types"] = self.instance.for_gate_types
#
#     class Meta:
#         model = BasicScoreOverride
#         exclude = ("navigation_task",)
#
#     def save(self, commit=True):
#         instance = super().save(commit=False)
#         # print(self.cleaned_data["for_gate_types"])
#         instance.for_gate_types = self.cleaned_data["for_gate_types"]
#         if commit:
#             instance.save()
#         # print(instance.for_gate_types)
#         return instance


class ContestForm(forms.ModelForm):
    class Meta:
        model = Contest
        exclude = ("contest_teams",)


class PictureWidget(forms.widgets.Widget):
    def render(self, name, value, attrs=None, renderer=None):
        html = Template("""<img id="{}" src="$link" class="wizardImage"/>""".format(name))
        return mark_safe(html.substitute(link=value))


class ImagePreviewWidget(forms.widgets.FileInput):
    def render(self, name, value, attrs=None, **kwargs):
        input_html = super().render(name, value, attrs=attrs, **kwargs)
        image_html = mark_safe(f'<br><br><img src="{value.url}"/>')
        return f'{input_html}{image_html}'


class Member1SearchForm(forms.Form):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Fieldset("Find pilot",
                     Div(
                         Div("person_id", "first_name", "last_name", "phone", "email",
                             "country_flag_display_field",
                             css_class="col-6"),
                         Div("picture_display_field", css_class="col-6"),
                         css_class="row")
                     ),
            ButtonHolder(
                StrictButton("Create new pilot",
                             css_class='button white', type="submit"),
                StrictButton("Use existing pilot", name='use_existing_pilot',
                             css_class='button white', css_id="use_existing", type="submit")
            )
        )

    person_id = forms.IntegerField(required=False, widget=HiddenInput())
    first_name = forms.CharField(required=False)
    last_name = forms.CharField(required=False)
    email = forms.CharField(required=False)
    phone = forms.CharField(required=False)
    picture_display_field = forms.ImageField(widget=PictureWidget, label="", required=False)
    country_flag_display_field = forms.ImageField(widget=PictureWidget, label="", required=False)


class Member2SearchForm(Member1SearchForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Fieldset("Find co-pilot",
                     Div(
                         Div("person_id", "first_name", "last_name", "phone", "email",
                             "country_flag_display_field",
                             css_class="col-6"),
                         Div(Field("picture_display_field", css_class="wizardImage"), css_class="col-6"),
                         css_class="row")
                     ),
            ButtonHolder(
                StrictButton("Skip copilot", name='skip_copilot',
                             css_class='button white', type="submit"),
                StrictButton("Create new copilot",
                             css_class='button white', type="submit"),
                StrictButton("Use existing copilot", name='use_existing_copilot',
                             css_class='button white', css_id="use_existing", type="submit")
            )
        )


class PersonForm(forms.ModelForm):
    # picture = forms.ImageField(widget=ImagePreviewWidget)
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Fieldset(
                "Create new person",
                "first_name",
                "last_name",
                "phone",
                "email",
                "country",
                "picture",
                "biography"
            ),
            ButtonHolder(
                Submit("submit", "Submit")
            )
        )

    def clean_phone(self):
        phone = self.cleaned_data["phone"]
        if phone is not None and len(phone) > 0 and Person.objects.filter(phone=phone).exists():
            raise ValidationError("Phone number must be unique")
        return phone

    def clean_email(self):
        email = self.cleaned_data["email"]
        if email is not None and len(email) > 0 and Person.objects.filter(email=email).exists():
            raise ValidationError("E-mail must be unique")
        return email

    class Meta:
        model = Person
        fields = "__all__"


class TeamForm(forms.ModelForm):
    logo = forms.ImageField(widget=ImagePreviewWidget, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["crew"].disabled = True
        self.fields["aeroplane"].disabled = True
        self.fields["club"].disabled = True
        self.helper = FormHelper()
        self.helper.layout = Layout(Fieldset(
            "Team", "crew", "aeroplane", "club", "country", "logo"),
            ButtonHolder(
                Submit("submit", "Submit")
            )
        )

    class Meta:
        model = Team
        fields = "__all__"


class AeroplaneSearchForm(forms.ModelForm):
    picture_display_field = forms.ImageField(widget=PictureWidget, label="", required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["picture_display_field"].label = ""
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Div(
                Div("registration", "type", "colour", "picture", css_class="col-6"),
                Div(Field("picture_display_field", css_class="wizardImage"), css_class="col-6"),
                css_class="row"
            ),
            ButtonHolder(
                Submit("submit", "Submit")
            )
        )

    class Meta:
        model = Aeroplane
        fields = ("registration", "type", "colour", "picture")


class AeroplaneForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    class Meta:
        model = Aeroplane
        fields = "__all__"


class TrackingDataForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(Fieldset(
            "Team contest information", "air_speed", "tracker_device_id", "tracking_service"),
            ButtonHolder(
                Submit("submit", "Submit")
            )
        )

    class Meta:
        model = ContestTeam
        fields = ("air_speed", "tracker_device_id", "tracking_service")


class ClubSearchForm(forms.ModelForm):
    logo_display_field = forms.ImageField(widget=PictureWidget, label="", required=False)
    country_flag_display_field = forms.ImageField(widget=PictureWidget, label="", required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["logo_display_field"].label = ""
        self.fields["country_flag_display_field"].label = ""
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Div(
                Div("name", "logo", "country", "country_flag_display_field", css_class="col-6"),
                Div(Field("logo_display_field", css_class="wizardImage"), css_class="col-6"),
                css_class="row"
            ),
            ButtonHolder(
                Submit("submit", "Submit")
            )
        )

    class Meta:
        model = Club
        fields = "__all__"


class ContestantForm(forms.ModelForm):
    # pilot_first_name = forms.CharField()
    # pilot_last_name = forms.CharField()
    # pilot_phone = PhoneNumberField(required=False)
    # pilot_email = forms.EmailField(required=False)
    #
    # copilot_first_name = forms.CharField(required=False)
    # copilot_last_name = forms.CharField(required=False)
    # copilot_phone = PhoneNumberField(required=False)
    # copilot_email = forms.EmailField(required=False)
    #
    # aircraft_registration = forms.CharField()
    def __init__(self, *args, **kwargs):
        self.navigation_task = kwargs.pop("navigation_task")  # type: NavigationTask

        super().__init__(*args, **kwargs)
        self.fields["team"].queryset = self.navigation_task.contest.contest_teams.all()
        self.fields["contestant_number"].initial = max([item.contestant_number for item in
                                                        self.navigation_task.contestant_set.all()]) + 1 if self.navigation_task.contestant_set.all().count() > 0 else 1
        # self.fields["tracking_device_id"].required = False

    class Meta:
        model = Contestant
        fields = (
            "contestant_number", "team", "tracker_start_time", "tracking_service", "tracker_device_id",
            "takeoff_time",
            "finished_by_time",
            "minutes_to_starting_point", "air_speed", "wind_direction", "wind_speed")
