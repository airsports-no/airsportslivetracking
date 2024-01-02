from crispy_forms.bootstrap import StrictButton
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, ButtonHolder, Submit, HTML, Div, Field
from django import forms
from django.forms import HiddenInput

from display.forms import PictureWidget, kml_description
from display.models import EditableRoute, Contest, Aeroplane, Club
from display.utilities.navigation_task_type_definitions import NAVIGATION_TASK_TYPES


class TaskTypeForm(forms.Form):
    task_type = forms.ChoiceField(
        choices=NAVIGATION_TASK_TYPES,
        help_text="The type of the task. This determines how the route file is processed",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Fieldset(
                "Choose the task type from the drop-down list",
                "task_type",
            ),
            ButtonHolder(Submit("submit", "Submit")),
        )


class PrecisionImportRouteForm(forms.Form):
    internal_route = forms.ModelChoiceField(EditableRoute.objects.all(), required=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Fieldset("Route selection", "internal_route"),
            ButtonHolder(Submit("submit", "Submit")),
        )


class ANRCorridorImportRouteForm(forms.Form):
    rounded_corners = forms.BooleanField(
        required=False,
        initial=False,
        help_text="If checked, then the route will be rendered with nice rounded corners instead of pointy ones.",
    )
    internal_route = forms.ModelChoiceField(EditableRoute.objects.all(), required=True)
    corridor_width = forms.FloatField(required=True, help_text="The width of the ANR corridor in NM")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Fieldset("Route import", "internal_route", "rounded_corners", "corridor_width"),
            ButtonHolder(Submit("submit", "Submit")),
        )


class AirsportsImportRouteForm(forms.Form):
    rounded_corners = forms.BooleanField(
        required=False,
        initial=False,
        help_text="If checked, then the route will be rendered with nice rounded corners instead of pointy ones.",
    )
    internal_route = forms.ModelChoiceField(EditableRoute.objects.all(), required=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Fieldset(
                "Route import",
                "internal_route",
                "rounded_corners",
            ),
            kml_description,
            ButtonHolder(Submit("submit", "Submit")),
        )


class LandingImportRouteForm(forms.Form):
    internal_route = forms.ModelChoiceField(EditableRoute.objects.all(), required=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Fieldset("Route import", "internal_route"),
            ButtonHolder(Submit("submit", "Submit")),
        )


class ContestSelectForm(forms.Form):
    contest = forms.ModelChoiceField(
        Contest.objects.all(),
        required=False,
        help_text="Choose an existing contest for the new task. If no contest is chosen, you will be prompted to create a new one on the next screen",
    )
    task_type = forms.ChoiceField(
        choices=NAVIGATION_TASK_TYPES,
        help_text="The type of the task. This determines how the route is processed",
    )
    navigation_task_name = forms.CharField(max_length=200)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Fieldset("Create a navigation task from the route", "contest", "task_type", "navigation_task_name"),
            ButtonHolder(Submit("submit", "Submit")),
        )


rounded_corners_warning = HTML(
    """
<p style ="color:red">Using rounded corners will not look good with sharp corners or short legs. Each leg should be at least three or four times long as the width of the corridor, and the turn should be not much more than 90 degrees, especially if the corridor is wide.</p>
"""
)


class ANRCorridorParametersForm(forms.Form):
    rounded_corners = forms.BooleanField(
        required=False,
        initial=False,
        help_text="If checked, then the route will be rendered with nice rounded corners instead of pointy ones.",
    )
    corridor_width = forms.FloatField(required=True, help_text="The width of the ANR corridor in NM")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Fieldset("Route import", "rounded_corners", "corridor_width"),
            rounded_corners_warning,
            ButtonHolder(Submit("submit", "Submit")),
        )


class AirsportsParametersForm(forms.Form):
    rounded_corners = forms.BooleanField(
        required=False,
        initial=False,
        help_text="If checked, then the route will be rendered with nice rounded corners instead of pointy ones. This does not make sense if the corridor is very wide.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Fieldset(
                "Route import",
                "rounded_corners",
            ),
            rounded_corners_warning,
            ButtonHolder(Submit("submit", "Submit")),
        )


class Member1SearchForm(forms.Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Fieldset(
                "Find pilot",
                Div(
                    Div(
                        "person_id",
                        "first_name",
                        "last_name",
                        "phone",
                        "email",
                        "country_flag_display_field",
                        css_class="col-6",
                    ),
                    Div("picture_display_field", css_class="col-6"),
                    css_class="row",
                ),
            ),
            ButtonHolder(
                StrictButton("Create new pilot", css_class="btn btn-primary", type="submit"),
                StrictButton(
                    "Use existing pilot",
                    name="use_existing_pilot",
                    css_class="btn btn-primary",
                    css_id="use_existing",
                    type="submit",
                ),
            ),
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
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Fieldset(
                "Find co-pilot",
                Div(
                    Div(
                        "person_id",
                        "first_name",
                        "last_name",
                        "phone",
                        "email",
                        "country_flag_display_field",
                        css_class="col-6",
                    ),
                    Div(Field("picture_display_field", css_class="wizardImage"), css_class="col-6"),
                    css_class="row",
                ),
            ),
            ButtonHolder(
                StrictButton("Skip copilot", name="skip_copilot", css_class="btn btn-primary", type="submit"),
                StrictButton("Create new copilot", css_class="btn btn-primary", type="submit"),
                StrictButton(
                    "Use existing copilot",
                    name="use_existing_copilot",
                    css_class="btn btn-primary",
                    css_id="use_existing",
                    type="submit",
                ),
            ),
        )


class AeroplaneSearchForm(forms.ModelForm):
    picture_display_field = forms.ImageField(widget=PictureWidget, label="", required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["picture_display_field"].label = ""
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Div(
                Div("registration", "type", "colour", "picture", css_class="col-6"),
                Div(Field("picture_display_field", css_class="wizardImage"), css_class="col-6"),
                css_class="row",
            ),
            ButtonHolder(Submit("submit", "Submit")),
        )

    class Meta:
        model = Aeroplane
        fields = ("registration", "type", "colour", "picture")


class ClubSearchForm(forms.ModelForm):
    logo_display_field = forms.ImageField(widget=PictureWidget, label="", required=False)
    country_flag_display_field = forms.ImageField(widget=PictureWidget, label="", required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["logo_display_field"].label = ""
        self.fields["country_flag_display_field"].label = ""
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Div(
                Div("name", "logo", "country", "country_flag_display_field", css_class="col-6"),
                Div(Field("logo_display_field", css_class="wizardImage"), css_class="col-6"),
                css_class="row",
            ),
            ButtonHolder(Submit("submit", "Submit")),
        )

    class Meta:
        model = Club
        fields = "__all__"
