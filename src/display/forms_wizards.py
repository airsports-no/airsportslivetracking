from crispy_forms.bootstrap import StrictButton
from crispy_forms.helper import FormHelper
from crispy_forms.layout import HTML, ButtonHolder, Div, Field, Fieldset, Layout, Submit
from django import forms
from django.forms import HiddenInput
from phonenumber_field.formfields import PhoneNumberField

from display.forms import PictureWidget, kml_description
from display.models import Aeroplane, Club, Contest, EditableRoute
from display.services.route_compatibility import get_compatible_task_subtypes
from display.services.task_type_visibility import can_user_see_cima_task_types, can_user_see_task_subtype
from display.utilities.cima_task_type_definitions import LEGACY_DEFAULT_SUBTYPE_BY_FAMILY, TASK_SUBTYPE_DEFINITIONS
from display.utilities.navigation_task_type_definitions import NAVIGATION_TASK_TYPES


def _task_template_choices(user=None, editable_route=None):
    """
    Build the grouped (Legacy/CIMA) task_template choices for the task-type picker.

    When `editable_route` is given, choices are additionally hard-filtered to task subtypes the
    route's authored content actually satisfies (display.services.route_compatibility) - this is
    the canonical, non-bypassable gate; user-permission filtering (CIMA visibility) is layered on
    top of it.
    """
    compatible = set(get_compatible_task_subtypes(editable_route)) if editable_route is not None else None
    grouped = {"Legacy": [], "CIMA": []}
    for key, label in NAVIGATION_TASK_TYPES:
        if compatible is not None and LEGACY_DEFAULT_SUBTYPE_BY_FAMILY.get(key) not in compatible:
            continue
        grouped["Legacy"].append((key, label))
    for definition in TASK_SUBTYPE_DEFINITIONS.values():
        if definition.key.startswith("legacy_"):
            continue
        if not can_user_see_task_subtype(user, task_subtype=definition.key):
            continue
        if compatible is not None and definition.key not in compatible:
            continue
        grouped["CIMA"].append((definition.key, definition.display_name))
    return [(group, choices) for group, choices in grouped.items() if choices]


def _normalize_task_template_selection(value):
    if not value:
        return None, None
    if value in dict(NAVIGATION_TASK_TYPES):
        return value, ""
    definition = TASK_SUBTYPE_DEFINITIONS.get(value)
    if definition is None:
        raise forms.ValidationError("Select a valid task type.")
    return definition.coarse_family, definition.key


class TaskTypeForm(forms.Form):
    task_template = forms.ChoiceField(
        choices=(),
        help_text="Choose either a legacy task family or a specific CIMA task.",
    )
    task_type = forms.ChoiceField(
        choices=NAVIGATION_TASK_TYPES,
        help_text="The type of the task. This determines how the route file is processed",
        required=False,
        widget=HiddenInput(),
    )
    task_subtype = forms.CharField(required=False, widget=HiddenInput())

    def clean(self):
        cleaned_data = super().clean()
        task_type, task_subtype = _normalize_task_template_selection(cleaned_data.get("task_template"))
        cleaned_data["task_type"] = task_type
        cleaned_data["task_subtype"] = task_subtype
        return cleaned_data

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        self.visible_cima = can_user_see_cima_task_types(user)
        self.fields["task_template"].choices = _task_template_choices(user)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Fieldset(
                "Choose the task type",
                "task_template",
                "task_type",
                "task_subtype",
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
        Contest.objects.all().order_by("name"),
        required=False,
        help_text="Choose an existing contest for the new task. If no contest is chosen, you will be prompted to create a new one on the next screen",
    )
    task_template = forms.ChoiceField(
        choices=(),
        help_text="Choose either a legacy task family or a specific CIMA task.",
    )
    task_type = forms.ChoiceField(
        choices=NAVIGATION_TASK_TYPES,
        help_text="The type of the task. This determines how the route is processed",
        required=False,
        widget=HiddenInput(),
    )
    task_subtype = forms.CharField(required=False, widget=HiddenInput())
    navigation_task_name = forms.CharField(max_length=200)

    def clean(self):
        cleaned_data = super().clean()
        task_type, task_subtype = _normalize_task_template_selection(cleaned_data.get("task_template"))
        cleaned_data["task_type"] = task_type
        cleaned_data["task_subtype"] = task_subtype
        return cleaned_data

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        editable_route = kwargs.pop("editable_route", None)
        super().__init__(*args, **kwargs)
        self.visible_cima = can_user_see_cima_task_types(user)
        self.fields["task_template"].choices = _task_template_choices(user, editable_route=editable_route)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Fieldset(
                "Create a navigation task from the route",
                "contest",
                "task_template",
                "task_type",
                "task_subtype",
                "navigation_task_name",
            ),
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
