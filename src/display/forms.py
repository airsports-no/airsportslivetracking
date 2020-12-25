from string import Template

from crispy_forms.bootstrap import StrictButton
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Div, ButtonHolder, Submit, Button, Fieldset, Field
from django import forms
from django.core.exceptions import ValidationError
from django.forms import HiddenInput
from django.utils.safestring import mark_safe
from phonenumber_field.formfields import PhoneNumberField

from display.models import NavigationTask, Contestant, Contest, Person, Crew, Aeroplane, Team, Club

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
        exclude = ("teams",)


class PictureWidget(forms.widgets.Widget):
    def render(self, name, value, attrs=None, renderer=None):
        print(name)
        print(attrs)
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
        if Person.objects.filter(phone=phone).exists():
            raise ValidationError("Phone number must be unique")
        return phone

    def clean_email(self):
        email = self.cleaned_data["email"]
        if Person.objects.filter(email=email).exists():
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
