from crispy_forms.bootstrap import StrictButton
from crispy_forms.helper import FormHelper
from crispy_forms.layout import ButtonHolder, Div, Field, Fieldset, Layout, Submit
from django import forms
from django.forms import HiddenInput
from phonenumber_field.formfields import PhoneNumberField

from display.forms import PictureWidget
from display.models import Aeroplane, Club

# These three are no longer used in this module (their only callers, TaskTypeForm and
# ContestSelectForm, were removed once NewNavigationTaskWizard/RouteToTaskWizard were replaced by
# the React nav-task-creation flow) - kept as re-exports because existing tests still import them
# from here (display.forms_wizards._task_template_choices etc.) rather than from
# display.services.task_templates directly.
from display.services.task_templates import (  # noqa: F401
    no_compatible_task_types_message as _no_compatible_task_types_message,
)
from display.services.task_templates import (  # noqa: F401
    normalize_task_template_selection as _normalize_task_template_selection,
)
from display.services.task_templates import (  # noqa: F401
    task_template_choices as _task_template_choices,
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
    phone = PhoneNumberField(required=False)
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
