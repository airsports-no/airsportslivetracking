from string import Template

import datetime
import json
from typing import Iterable, Optional

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, ButtonHolder, Submit, Fieldset, Field, HTML
from django import forms
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.utils.safestring import mark_safe
from django.utils.text import capfirst

from display.flight_order_and_maps.map_constants import (
    MAP_SIZES,
    ORIENTATIONS,
    LANDSCAPE,
    SCALES,
    SCALE_TO_FIT,
    A4,
    PORTRAIT,
)
from display.flight_order_and_maps.map_plotter_shared_utilities import (
    get_map_choices,
    get_available_map_source_choices_for_navigation_task,
    get_available_map_source_definitions_for_navigation_task,
    resolve_map_source_definition,
)
from display.flight_order_and_maps.mbtiles_facade import get_map_details

from display.models import (
    NavigationTask,
    Contestant,
    Contest,
    Person,
    Team,
    ContestTeam,
    Scorecard,
    FlightOrderConfiguration,
    UserUploadedMap,
    TokenType,
    UserTokenGrant,
    Club,
)

from display.models.scorecard_and_gate_score import DURATION_NORMALIZATION_POLICIES, SCORECARD_CONFIG_FIELDS
from display.models.user_uploaded_map import validate_file_size
from display.models.my_user import MyUser
from display.poker.poker_cards import PLAYING_CARDS
from display.utilities.country_code_utilities import get_country_code_from_location, CountryNotFoundException
from display.utilities.cima_task_type_definitions import (
    ANR_CATALOGUE,
    CONTRACT_NAVIGATION_TIME_CONTROLS,
    CURVE_NAVIGATION_TIME_ESTIMATION,
    DURATION,
    LIMITED_FUEL_TURNPOINT_HUNT,
    PRECISION_NAVIGATION,
    TURNPOINT_HUNT,
    CIRCLE,
    get_task_subtypes_for_family,
)
from display.services.task_type_visibility import can_user_see_cima_task_types, can_user_see_task_subtype
from display.utilities.navigation_task_type_definitions import ANR_CORRIDOR, NAVIGATION_TASK_TYPES, PRECISION

FILE_TYPE_CSV = "csv"
FILE_TYPE_FLIGHTCONTEST_GPX = "fcgpx"
FILE_TYPE_KML = "kml"
FILE_TYPES = (
    (FILE_TYPE_CSV, "CSV"),
    (FILE_TYPE_FLIGHTCONTEST_GPX, "FlightContest GPX file"),
    (FILE_TYPE_KML, "KML/KMZ file"),
)


class ShareForm(forms.Form):
    PUBLIC = "public"
    UNLISTED = "unlisted"
    PRIVATE = "private"
    PUBLICITY = (
        (PUBLIC, "Public, visible by all"),
        (UNLISTED, "Unlisted, requires direct link"),
        (PRIVATE, "Private, visible to users with permission"),
    )
    publicity = forms.ChoiceField(widget=forms.RadioSelect, choices=PUBLICITY)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = "form mt-4"
        self.helper.layout = Layout(
            Field("publicity"),
            ButtonHolder(Submit("submit", "Save")),
        )


class MapForm(forms.Form):
    size = forms.ChoiceField(choices=MAP_SIZES, initial=A4)
    orientation = forms.ChoiceField(
        choices=ORIENTATIONS,
        initial=LANDSCAPE,
        help_text="WARNING: scale printing is currently only correct for landscape orientation",
    )
    plot_track_between_waypoints = forms.BooleanField(
        initial=True,
        required=False,
        help_text="For precision and Air Sport competition types this will draw a line between the waypoints of the track. Without this the precision map will only contain the waypoints, and the Air Sport maps will only contain the corridor without a centreline.",
    )
    include_meridians_and_parallels_lines = forms.BooleanField(
        initial=True,
        required=False,
        help_text="If true, navigation map is overlaid with meridians and parallels every 0.1 degrees. Disable if map source already has this",
    )

    scale = forms.ChoiceField(choices=SCALES, initial=SCALE_TO_FIT)
    map_source = forms.ChoiceField(choices=[], required=False)
    include_openaip_overlay = forms.BooleanField(
        initial=False,
        required=False,
        help_text="Render OpenAIP on top of the selected map source.",
    )
    zoom_level = forms.TypedChoiceField(initial=12, choices=[(x, x) for x in range(1, 15)], coerce=int, empty_value=12)
    dpi = forms.IntegerField(initial=150, min_value=100, max_value=300)
    line_width = forms.FloatField(initial=0.5, min_value=0.1, max_value=10)
    colour = forms.CharField(initial="#0000ff", max_length=7, widget=forms.HiddenInput())

    def __init__(self, *args, **kwargs):
        self.redirect_url = kwargs.pop("redirect_url", "#")
        self.map_source_choices = kwargs.pop("map_source_choices", None)
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = "form mt-4"
        self.helper.layout = Layout(
            Fieldset(
                "Map details",
                "size",
                "orientation",
                "plot_track_between_waypoints",
                "include_meridians_and_parallels_lines",
                "scale",
                "map_source",
                "include_openaip_overlay",
                "zoom_level",
                "dpi",
                "line_width",
            ),
            Field("colour", type="hidden"),
            HTML(
                '<h5 class="text-lg font-semibold mt-4">Pick a colour for the route</h5><div id="picker" class="mx-auto mt-2" style="margin-bottom: 15px"></div>'
            ),
            HTML(
                """<div role="alert" class="alert alert-warning mt-4">
                <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-triangle-alert stroke-current shrink-0 h-6 w-6"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><path d="M12 9v4"/><path d="M12 17h.01"/></svg>
                <span><b>Caution:</b> Map generation may require several minutes. Using large zoom levels (e.g., above 12) with significant scales (e.g., 1:200,000 or higher) could result in an out of memory error. If this occurs, kindly decrease the zoom level (use a lower number).</span>
            </div>"""
            ),
            ButtonHolder(
                Submit("submit", "Submit"), HTML(f'<a href="{self.redirect_url}" class="btn btn-secondary">Back</a>')
            ),
        )
        self.fields["map_source"].choices = self.map_source_choices or get_map_choices()


class ContestantMapForm(forms.Form):
    size = forms.ChoiceField(choices=MAP_SIZES, initial=A4)
    dpi = forms.IntegerField(initial=150, min_value=100, max_value=300)
    orientation = forms.ChoiceField(choices=ORIENTATIONS, initial=PORTRAIT)
    scale = forms.ChoiceField(choices=SCALES, initial=SCALE_TO_FIT)
    map_source = forms.ChoiceField(choices=[], required=False)
    include_openaip_overlay = forms.BooleanField(
        initial=False,
        required=False,
        help_text="Render OpenAIP on top of the selected map source.",
    )
    zoom_level = forms.TypedChoiceField(coerce=int, initial=12, choices=[(i, i) for i in range(1, 15)])

    include_annotations = forms.BooleanField(initial=True, required=False)
    include_contestant_declarations = forms.BooleanField(
        initial=True,
        required=False,
        help_text="If enabled, contestant-specific declaration route data will be rendered when available. Disable to render the generic task route.",
    )
    plot_track_between_waypoints = forms.BooleanField(initial=True, required=False)
    include_meridians_and_parallels_lines = forms.BooleanField(
        initial=True,
        required=False,
        help_text="If true, navigation map is overlaid with meridians and parallels. Disable if map source already has this",
    )

    line_width = forms.FloatField(initial=0.5, min_value=0.1, max_value=10)
    minute_mark_line_width = forms.FloatField(initial=0.5, min_value=0.1, max_value=10)
    colour = forms.CharField(initial="#0000ff", max_length=7, widget=forms.HiddenInput())

    def clean(self):
        cleaned_data = super().clean()
        validate_map_zoom_level(cleaned_data.get("map_source"), None, cleaned_data.get("zoom_level"))

    def __init__(self, *args, **kwargs):
        self.redirect_url = kwargs.pop("redirect_url", "#")
        self.map_source_choices = kwargs.pop("map_source_choices", None)
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = "form mt-4"
        self.helper.layout = Layout(
            Fieldset(
                "Map details",
                "size",
                "dpi",
                "orientation",
                "scale",
                "map_source",
                "include_openaip_overlay",
                "zoom_level",
                "include_annotations",
                "include_contestant_declarations",
                "plot_track_between_waypoints",
                "include_meridians_and_parallels_lines",
                "line_width",
                "minute_mark_line_width",
            ),
            Field("colour", type="hidden"),
            HTML(
                '<h5 class="text-lg font-semibold mt-4">Pick a colour for the route</h5><div id="picker" class="mx-auto mt-2" style="margin-bottom: 15px"></div>'
            ),
            HTML(
                """<div role="alert" class="alert alert-warning mt-4">
                <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-triangle-alert stroke-current shrink-0 h-6 w-6"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><path d="M12 9v4"/><path d="M12 17h.01"/></svg>
                <span><b>Caution:</b> Map generation may require several minutes. Using large zoom levels (e.g., above 12) with significant scales (e.g., 1:200,000 or higher) could result in an out of memory error. If this occurs, kindly decrease the zoom level (use a lower number).</span>
            </div>"""
            ),
            ButtonHolder(
                Submit("submit", "Submit"), HTML(f'<a href="{self.redirect_url}" class="btn btn-secondary">Back</a>')
            ),
        )
        self.fields["map_source"].choices = self.map_source_choices or get_map_choices()


class UserUploadedMapForm(forms.ModelForm):
    class Meta:
        model = UserUploadedMap
        exclude = (
            "thumbnail",
            "unprotected",
            "minimum_zoom_level",
            "maximum_zoom_level",
            "processing_status",
            "processing_error",
            "published_service_key",
            "published_relative_path",
            "published_at",
        )
        # widgets = {"map_file": FileInput(attrs={'accept': 'application/vnd.mapbox-vector-tile'})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = "form mt-4"
        self.helper.attrs = {"enctype": "multipart/form-data"}
        self.helper.layout = Layout(
            Fieldset("User map", "name", "default_zoom_level", "attribution", "map_file"),
            Field("user", type="hidden"),
            ButtonHolder(Submit("submit", "Submit")),
        )


def validate_map_zoom_level(map_source: str, user_uploaded_map: Optional[UserUploadedMap], zoom_level: int):
    source = resolve_map_source_definition(map_source, user_uploaded_map)
    min_zoom = source["min_zoom"]
    max_zoom = source["max_zoom"]
    if not min_zoom <= zoom_level <= max_zoom:
        raise ValidationError(
            f"The selected zoom level {zoom_level} is not in the valid range [{min_zoom}, "
            f"{max_zoom}] for the map source {source['label']}"
        )


class FlightOrderConfigurationForm(forms.ModelForm):
    class Meta:
        model = FlightOrderConfiguration
        exclude = ("navigation_task",)

    def clean_map_source(self):
        map_source = self.cleaned_data.get("map_source")
        if not map_source:
            return map_source

        valid_map_sources = {choice[0] for choice in self.fields["map_source"].choices}
        if map_source not in valid_map_sources:
            raise ValidationError("Select a valid choice. That choice is not one of the available choices.")

        return map_source

    def clean(self):
        cleaned_data = super().clean()
        if "map_source" in self.errors or not cleaned_data.get("map_source"):
            return cleaned_data

        validate_map_zoom_level(cleaned_data.get("map_source"), None, cleaned_data.get("map_zoom_level"))
        return cleaned_data

    def __init__(self, *args, **kwargs):
        self.map_source_choices = kwargs.pop("map_source_choices", None)
        super().__init__(*args, **kwargs)
        self.fields["map_source"].choices = self.map_source_choices or get_map_choices()
        self.instance._meta.get_field("map_source").choices = self.fields["map_source"].choices
        self.helper = FormHelper()
        self.helper.layout = Layout(
            HTML(
                """<div role="alert" class="alert alert-warning mt-4">
                <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-triangle-alert stroke-current shrink-0 h-6 w-6"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><path d="M12 9v4"/><path d="M12 17h.01"/></svg>
                <span><b>Caution:</b> Map generation may require several minutes. Using large zoom levels (e.g., above 12) with significant scales (e.g., 1:200,000 or higher) could result in an out of memory error. If this occurs, kindly decrease the zoom level (use a lower number). Be sure to test map generation when changing the values here.</span>
            </div>"""
            ),
            Fieldset(
                "Map options",
                "document_size",
                "map_source",
                "map_orientation",
                "map_zoom_level",
                "map_scale",
                "map_dpi",
                "map_include_annotations",
                "map_include_contestant_declarations",
                "map_plot_track_between_waypoints",
                "map_include_meridians_and_parallels_lines",
                "map_include_openaip_overlay",
                "map_line_width",
                "map_minute_mark_line_width",
            ),
            Fieldset(
                "Turning point photo options",
                "include_turning_point_images",
                "turning_point_photos_meters_across",
                "turning_point_photos_zoom_level",
            ),
            Fieldset(
                "Unknown leg photo options",
                HTML(
                    "Unknown leg photos are included automatically if unknown legs are present in the route. These are created through the route editor."
                ),
                "unknown_leg_photos_meters_across",
                "unknown_leg_photos_zoom_level",
            ),
            Fieldset(
                "Observation photo options",
                HTML(
                    "If the route includes photo markers, these will be included on one or more separate pages sorted according to name"
                ),
                "photos_meters_across",
                "photos_zoom_level",
            ),
            Field("map_line_colour", type="hidden"),
            HTML(
                '<h3>Pick a colour for the map lines</h3><div id="picker" class="mx-auto mt-4" style="margin-bottom: 10px"></div>'
            ),
            ButtonHolder(Submit("submit", "Submit"), Submit("cancel", "Cancel", css_class="btn-secondary")),
        )


class NavigationTaskForm(forms.ModelForm):
    task_subtype = forms.ChoiceField(required=False, choices=[])

    class Meta:
        model = NavigationTask
        fields = (
            "name",
            "start_time",
            "finish_time",
            "display_background_map",
            "display_secrets",
            "minutes_to_starting_point",
            "planning_time",
            "original_scorecard",
            "task_subtype",
            "minutes_to_landing",
            "wind_speed",
            "wind_direction",
            "allow_self_management",
            "calculation_delay_minutes",
        )

    def __init__(self, *args, **kwargs):
        task_family = kwargs.pop("task_family", None)
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        self.fields["original_scorecard"].queryset = Scorecard.get_originals()
        instance = getattr(self, "instance", None)
        if instance and instance.pk:
            self.fields["original_scorecard"].disabled = True

        subtype_choices = [("", "---------")]
        family_labels = dict(NAVIGATION_TASK_TYPES)
        subtype_families = [task_family] if task_family else [PRECISION, ANR_CORRIDOR]
        for family in subtype_families:
            family_subtypes = [
                (item.key, item.display_name)
                for item in get_task_subtypes_for_family(family)
                if can_user_see_task_subtype(user, task_type=family, task_subtype=item.key)
            ]
            if family_subtypes:
                subtype_choices.append((family_labels.get(family, family), family_subtypes))
        self.fields["task_subtype"].choices = subtype_choices

        datetime_widget = forms.DateTimeInput(attrs={"type": "datetime-local", "step": "60"}, format="%Y-%m-%dT%H:%M")
        self.fields["start_time"].widget = datetime_widget
        self.fields["finish_time"].widget = datetime_widget

        self.helper = FormHelper()
        self.helper.layout = Layout(
            Fieldset(
                "Navigation task details",
                "name",
                "start_time",
                "finish_time",
                "original_scorecard",
                "task_subtype",
                "allow_self_management",
                "planning_time",
            ),
            Fieldset("Wind", "wind_speed", "wind_direction"),
            Fieldset("Getting to and from the track", "minutes_to_starting_point", "minutes_to_landing"),
            Fieldset(
                "Display control",
                "display_background_map",
                "display_secrets",
                "calculation_delay_minutes",
            ),
            ButtonHolder(Submit("submit", "Submit")),
        )

    def save(self, commit=True):
        instance = super().save(commit=False)
        if commit:
            instance.save()
        return instance


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
    initial_token_grant = forms.ModelChoiceField(queryset=UserTokenGrant.objects.none(), required=False)

    class Meta:
        model = Contest
        exclude = ("contest_teams", "is_featured", "is_public", "latitude", "longitude", "country")

    def __init__(self, *args, **kwargs):
        token_grant_queryset = kwargs.pop("token_grant_queryset", UserTokenGrant.objects.none())
        managed_club_queryset = kwargs.pop("managed_club_queryset", Club.objects.none())
        super().__init__(*args, **kwargs)
        self.fields["initial_token_grant"].queryset = token_grant_queryset.filter(
            quantity_total__gt=models.F("quantity_consumed")
        )
        self.fields["initial_token_grant"].label = "Initial token grant (optional)"
        self.fields[
            "initial_token_grant"
        ].help_text = "Assign a token immediately when creating the contest. Spent tokens are never restored."
        self.fields["organizing_club"].queryset = managed_club_queryset
        self.fields["organizing_club"].required = False
        datetime_widget = forms.DateTimeInput(attrs={"type": "datetime-local", "step": "60"}, format="%Y-%m-%dT%H:%M")
        self.fields["start_time"].widget = datetime_widget
        self.fields["finish_time"].widget = datetime_widget
        self.helper = FormHelper()
        self.helper.form_class = "form"
        self.helper.attrs = {"enctype": "multipart/form-data"}
        self.helper.layout = Layout(
            Fieldset(
                "Contest details",
                "name",
                "time_zone",
                "start_time",
                "finish_time",
                "organizing_club",
                "initial_token_grant",
            ),
            Fieldset(
                "Contest location",
                "location",
            ),
            Fieldset("Publicity", "contest_website", "header_image", "logo"),
            Fieldset("Result service", "summary_score_sorting_direction", "autosum_scores"),
            ButtonHolder(Submit("submit", "Submit")),
        )

    def clean(self):
        cleaned_data = super().clean()
        location = cleaned_data.get("location")
        if not location:
            raise ValidationError("Please select a valid location for the contest.", code="invalid")

        try:
            lat, lon = [float(x) for x in location.split(",")]
            country_code = get_country_code_from_location(lat, lon)
            cleaned_data["country_code"] = country_code
        except (ValueError, TypeError):
            raise ValidationError("Invalid location format. Expected 'latitude,longitude'.", code="invalid")
        except CountryNotFoundException:
            raise ValidationError(
                f"The contest location {location} is not in a valid country",
                code="invalid",
            )
        return cleaned_data


class PictureWidget(forms.widgets.Widget):
    def render(self, name, value, attrs=None, renderer=None):
        html = Template("""<img id="{}" src="$link" class="wizardImage"/>""".format(name))
        return mark_safe(html.substitute(link=value))


class ImagePreviewWidget(forms.widgets.FileInput):
    def render(self, name, value, attrs=None, **kwargs):
        if attrs is None:
            attrs = {}
        attrs["class"] = (attrs.get("class", "") + " file-input file-input-bordered w-full max-w-xs").strip()
        input_html = super().render(name, value, attrs=attrs, **kwargs)
        if value and hasattr(value, "url"):
            image_html = mark_safe(
                f'<div class="mt-4"><img src="{value.url}" class="max-w-[200px] max-h-[200px] rounded-lg shadow-md object-cover"/></div>'
            )
            return mark_safe(f"<div>{input_html}{image_html}</div>")
        return input_html


class PersonPictureForm(forms.ModelForm):
    picture = forms.ImageField(widget=ImagePreviewWidget)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = "form mt-4"
        self.helper.attrs = {"enctype": "multipart/form-data"}
        self.helper.layout = Layout(
            Fieldset(
                "Upload picture",
                "picture",
            ),
            ButtonHolder(Submit("submit", "Upload")),
        )

    class Meta:
        model = Person
        fields = ("picture",)


class TrackingDataForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = "form mt-4"
        self.helper.attrs = {"enctype": "multipart/form-data"}
        self.helper.layout = Layout(
            Fieldset("Team contest information", "air_speed", "tracking_service", "tracking_device"),
            Fieldset(
                "Optional tracking information if not using the official Air Sports Live Tracking app",
                "tracker_device_id",
            ),
            ButtonHolder(Submit("submit", "Submit")),
        )

    class Meta:
        model = ContestTeam
        fields = ("air_speed", "tracking_service", "tracker_device_id", "tracking_device")


class PersonForm(forms.ModelForm):
    picture = forms.ImageField(widget=ImagePreviewWidget, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = "form mt-4"
        self.helper.attrs = {"enctype": "multipart/form-data"}
        self.helper.layout = Layout(
            Fieldset(
                "Create new person", "first_name", "last_name", "phone", "email", "country", "picture", "biography"
            ),
            ButtonHolder(Submit("submit", "Submit")),
        )

    def clean_phone(self):
        phone = self.cleaned_data["phone"]
        if phone is not None and len(phone) > 0:
            existing = Person.objects.filter(phone=phone)
            if self.instance is not None:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise ValidationError("Phone number must be unique")
        return phone

    class Meta:
        model = Person
        fields = "__all__"


DECLARATION_SLOT_COUNT = 4


def _local_datetime_to_utc_iso(value):
    if value in (None, ""):
        return None
    dt = value if isinstance(value, datetime.datetime) else datetime.datetime.fromisoformat(str(value))
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt.astimezone(datetime.timezone.utc).isoformat()


def _catalogue_turnpoint_choices(navigation_task):
    editable_route = navigation_task.editable_route
    if editable_route is None:
        return []
    choices = []
    for item in editable_route.get_catalogue_turnpoints():
        name = item.get("properties", {}).get("name")
        if name and name not in {"SP", "MP", "FP"}:
            choices.append((name, name))
    return choices


def _known_time_gate_names(navigation_task):
    editable_route = navigation_task.editable_route
    if editable_route is None:
        return []
    result = []
    for item in editable_route.get_known_time_gates():
        name = item.get("properties", {}).get("name")
        if name:
            result.append(name)
    return result


class ContestantForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self.navigation_task = kwargs.pop("navigation_task")
        super().__init__(*args, **kwargs)
        if not can_user_see_cima_task_types(getattr(self.navigation_task.contest, "created_by", None)):
            pass
        self.fields["team"].queryset = self.navigation_task.contest.contest_teams.all()
        self.fields["contestant_number"].initial = (
            max([item.contestant_number for item in self.navigation_task.contestant_set.all()]) + 1
            if self.navigation_task.contestant_set.all().count() > 0
            else 1
        )
        self.fields["wind_speed"].initial = self.navigation_task.wind_speed
        self.fields["wind_direction"].initial = self.navigation_task.wind_direction
        self.fields["wind_direction"].initial = self.navigation_task.wind_direction

        datetime_widget = forms.DateTimeInput(attrs={"type": "datetime-local", "step": "60"}, format="%Y-%m-%dT%H:%M")
        self.fields["takeoff_time"].widget = datetime_widget
        self.fields["tracker_start_time"].widget = datetime_widget
        self.fields["finished_by_time"].widget = datetime_widget

        self.helper = FormHelper()
        self.helper.attrs = {"enctype": "multipart/form-data"}
        layout_items = [
            Fieldset(
                "Contestant",
                "contestant_number",
                "team",
                "takeoff_time",
                "adaptive_start",
                "minutes_to_starting_point",
                "air_speed",
                "wind_direction",
                "wind_speed",
            ),
            Fieldset(
                "Tracking",
                HTML(
                    "The below fields can mostly be left alone. Tracker start time and finished by time are calculated automatically to ten minutes prior to the takeoff time with an assumed flight time of maximum two hours with fixed start and five hours with adaptive start. Overwrite this as necessary."
                ),
                "tracking_service",
                "tracking_device",
                "tracker_device_id",
                "tracker_start_time",
                "finished_by_time",
            ),
        ]
        self.helper.layout = Layout(*layout_items, ButtonHolder(Submit("submit", "Submit")))

    def clean(self):
        return super().clean()

    def get_declaration_payload(self):
        return {}

    class Meta:
        model = Contestant
        fields = (
            "contestant_number",
            "team",
            "tracking_service",
            "tracking_device",
            "tracker_device_id",
            "takeoff_time",
            "adaptive_start",
            "tracker_start_time",
            "finished_by_time",
            "minutes_to_starting_point",
            "air_speed",
            "wind_direction",
            "wind_speed",
        )


class ContestantQuickAddForm(forms.Form):
    contest_team = forms.ModelChoiceField(queryset=ContestTeam.objects.none(), label="Team")
    starting_point_time = forms.DateTimeField(
        label="Time at starting point",
        widget=forms.DateTimeInput(attrs={"type": "datetime-local", "step": "60"}, format="%Y-%m-%dT%H:%M"),
        help_text="The time the contestant is expected to cross the starting point",
    )
    adaptive_start = forms.BooleanField(required=False, initial=False, label="Adaptive start")

    def __init__(self, *args, **kwargs):
        self.navigation_task = kwargs.pop("navigation_task")
        super().__init__(*args, **kwargs)
        self.fields["contest_team"].queryset = self.navigation_task.contest.contestteam_set.all()
        task_start_local = timezone.localtime(
            self.navigation_task.start_time,
            timezone=self.navigation_task.contest.time_zone,
        )
        one_hour_from_now = timezone.localtime() + datetime.timedelta(hours=1)
        self.fields["starting_point_time"].initial = max(one_hour_from_now, task_start_local)

        declaration_fields = []

        self.helper = FormHelper()
        layout_items = [
            Fieldset(
                "Quick Add Contestant",
                "contest_team",
                "starting_point_time",
                "adaptive_start",
            )
        ]
        if declaration_fields:
            layout_items.append(Fieldset("Task-specific declaration", *declaration_fields))
        self.helper.layout = Layout(*layout_items, ButtonHolder(Submit("submit", "Create")))

    def clean(self):
        return super().clean()

    def get_declaration_payload(self):
        return {}


from django import forms
from django.db.models import QuerySet
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, Submit, HTML, ButtonHolder, Row, Column
from django.utils.translation import gettext_lazy as _
from .models import Contestant, ContestTeam, NavigationTask, ContestantTrack


class BatchContestantUpdateForm(forms.Form):
    contestant_ids = forms.MultipleChoiceField(
        widget=forms.CheckboxSelectMultiple,
        required=True,
        label="Contestants",
    )
    update_wind = forms.BooleanField(required=False, label="Update wind speed/direction")
    wind_speed = forms.FloatField(required=False, min_value=0, max_value=40, label="Wind speed (knots)")
    wind_direction = forms.FloatField(required=False, min_value=0, max_value=360, label="Wind direction (°)")
    shift_times = forms.BooleanField(required=False, label="Shift contestant times")
    time_shift_minutes = forms.FloatField(required=False, label="Shift by (minutes, use negative to move earlier)")

    def __init__(self, *args, navigation_task=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.navigation_task = navigation_task
        if navigation_task:
            from display.utilities.calculator_running_utilities import is_calculator_running, is_dispatch_pending

            choices = []
            for c in navigation_task.contestant_set.select_related("contestanttrack").order_by("takeoff_time"):
                # Exclude only contestants whose calculator is *currently* running - not merely
                # ones whose calculator has ever started. calculator_started is set once at
                # dispatch and never reverts to False on a normal finish, so filtering on it
                # instead would permanently lock out batch time edits (e.g. fixing a wrong
                # takeoff time) for any contestant who has already flown. See GH #29.
                currently_running = is_calculator_running(c.pk) or is_dispatch_pending(c.pk)
                if not currently_running:
                    choices.append((str(c.pk), str(c)))
            self.fields["contestant_ids"].choices = choices

        self.helper = FormHelper()
        self.helper.layout = Layout(
            Fieldset(
                "Select Contestants",
                "contestant_ids",
            ),
            Fieldset(
                "Operation: Update Wind",
                "update_wind",
                Row(
                    Column("wind_speed", css_class="form-group col-md-6 mb-0"),
                    Column("wind_direction", css_class="form-group col-md-6 mb-0"),
                ),
            ),
            Fieldset(
                "Operation: Shift Times",
                "shift_times",
                "time_shift_minutes",
            ),
            ButtonHolder(Submit("submit", "Apply Changes", css_class="btn-primary")),
        )

    def clean(self):
        cd = super().clean()
        if cd.get("update_wind"):
            if cd.get("wind_speed") is None:
                self.add_error("wind_speed", "Wind speed is required when updating wind.")
            if cd.get("wind_direction") is None:
                self.add_error("wind_direction", "Wind direction is required when updating wind.")
        if cd.get("shift_times") and cd.get("time_shift_minutes") is None:
            self.add_error("time_shift_minutes", "Shift amount is required when shifting times.")
        if not cd.get("update_wind") and not cd.get("shift_times"):
            raise forms.ValidationError("Please select at least one operation (update wind or shift times).")
        return cd


class ContestantRecalculateWithStartTimeForm(forms.Form):
    starting_point_time = forms.DateTimeField(
        label="New time at starting point",
        widget=forms.DateTimeInput(attrs={"type": "datetime-local", "step": "1"}, format="%Y-%m-%dT%H:%M:%S"),
        help_text="The time the contestant is expected to cross the starting point",
    )

    def __init__(self, *args, **kwargs):
        self.contestant = kwargs.pop("contestant")
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Fieldset(
                "Update Starting Point Time and Recalculate",
                "starting_point_time",
            ),
            HTML(
                "<p class='text-error font-bold mb-4'>Warning: This will delete the current contestant and create a new one with the same positions but updated timing. All current scores for this contestant will be lost.</p>"
            ),
            ButtonHolder(Submit("submit", "Recalculate")),
        )


class AssignPokerCardForm(forms.Form):
    waypoint = forms.ChoiceField(choices=())
    playing_card = forms.ChoiceField(choices=[("random", "Random")] + PLAYING_CARDS, initial="random")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = "form"
        self.helper.layout = Layout(
            Fieldset(
                "Assign Poker Card",
                "waypoint",
                "playing_card",
            ),
            ButtonHolder(Submit("submit", "Assign")),
        )


PERMISSIONS_CHOICE = [("nothing", "Nothing"), ("view", "View"), ("change", "Change"), ("delete", "Delete")]


class AddPermissionsForm(forms.Form):
    email = forms.EmailField()
    permission = forms.ChoiceField(choices=PERMISSIONS_CHOICE)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = "form mt-4"
        self.helper.layout = Layout(
            Fieldset(
                "Add Permission",
                "email",
                "permission",
            ),
            ButtonHolder(Submit("submit", "Add")),
        )


class ChangePermissionsForm(forms.Form):
    permission = forms.ChoiceField(choices=PERMISSIONS_CHOICE)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = "form mt-4"
        self.helper.layout = Layout(
            Fieldset(
                "Change Permission",
                "permission",
            ),
            ButtonHolder(Submit("submit", "Update")),
        )


class GPXTrackImportForm(forms.Form):
    track_file = forms.FileField(validators=[FileExtensionValidator(allowed_extensions=["gpx"])], required=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = "form mt-4"
        self.helper.attrs = {"enctype": "multipart/form-data"}
        self.helper.layout = Layout(
            Fieldset(
                "GPX Track upload",
                "track_file",
            ),
            ButtonHolder(Submit("submit", "Submit")),
        )


class ScorecardForm(forms.ModelForm):
    corridor_width = forms.FloatField()

    # Phase 2 of the scorecard-system review roadmap moved these 26 fields off of real
    # Scorecard columns and onto Scorecard.config (see ConfigField in
    # models/scorecard_and_gate_score.py). ModelForm's `exclude`-based auto-introspection
    # (construct_instance(), django/forms/models.py) only ever applies real model fields to
    # the instance on save - a plain (name-matching) declared field here would validate but
    # then be silently dropped, exactly like this form's pre-existing `corridor_width` (never
    # applied by construct_instance() either, applied manually - see save() below). Declared
    # explicitly, with save() below applying them, so the organizer-facing form keeps
    # actually writing what it lets you edit.
    backtracking_penalty = forms.FloatField()
    backtracking_bearing_difference = forms.FloatField()
    backtracking_grace_time_seconds = forms.FloatField()
    backtracking_maximum_penalty = forms.FloatField()
    prohibited_zone_penalty = forms.FloatField()
    prohibited_zone_grace_time = forms.FloatField()
    prohibited_zone_maximum = forms.FloatField()
    penalty_zone_grace_time = forms.FloatField()
    penalty_zone_penalty_per_second = forms.FloatField()
    penalty_zone_maximum = forms.FloatField()
    corridor_grace_time = forms.IntegerField()
    corridor_outside_penalty = forms.FloatField()
    corridor_maximum_penalty = forms.FloatField()
    corridor_maximum_penalty_is_per_leg = forms.BooleanField(required=False)
    anr_route_to_sp_penalty = forms.FloatField()
    anr_route_from_fp_penalty = forms.FloatField()
    compulsory_timing_tolerance_seconds = forms.IntegerField()
    maximum_task_duration_minutes = forms.IntegerField(required=False)
    maximum_task_duration_penalty = forms.FloatField()
    fuel_deadline_penalty = forms.FloatField()
    duration_normalization_policy = forms.ChoiceField(choices=DURATION_NORMALIZATION_POLICIES, required=False)
    duration_residual_fuel_required = forms.BooleanField(required=False)
    circle_radius_min_m = forms.FloatField()
    circle_radius_max_m = forms.FloatField()
    speed_keeping_tolerance_kt = forms.FloatField()
    speed_keeping_penalty_per_kt = forms.FloatField()
    # min_value=0: see the matching comment in admin.py's ScorecardAdminForm.
    turnpoint_hunt_sequence_bonus = forms.FloatField(min_value=0)

    class Meta:
        model = Scorecard
        # Phase 2e of the scorecard-system review roadmap dropped the legacy_* columns for
        # real (migration 0174) - no longer anything to exclude by name here.
        exclude = (
            "name",
            "original",
            "included_fields",
            "calculator",
            "task_type",
            "use_procedure_turns",
            "free_text",
            "config",
        )

    def save(self, commit=True):
        instance = super().save(commit=False)
        # See the class docstring comment above the declared fields: construct_instance()
        # only ever applies real model fields, so these 26 config-backed ones need applying
        # by hand.
        for field_name in SCORECARD_CONFIG_FIELDS:
            setattr(instance, field_name, self.cleaned_data[field_name])
        if commit:
            instance.save()
        return instance

    def __init__(self, *args, **kwargs):
        instance = kwargs.get("instance", None)
        if instance:
            # Only corridor_width used to need this - it isn't a model field at all. Now
            # that the 26 SCORECARD_CONFIG_FIELDS are declared form fields backed by
            # ConfigField properties rather than real model fields too, ModelForm's usual
            # instance-to-initial-data path (model_to_dict(), which only looks at real model
            # fields) can't see them either - without this, editing an existing scorecard
            # would render every one of them blank instead of its current value.
            initial = {"corridor_width": instance.corridor_width}
            initial.update({field: getattr(instance, field) for field in SCORECARD_CONFIG_FIELDS})
            initial.update(kwargs.get("initial") or {})
            kwargs["initial"] = initial
        super().__init__(*args, **kwargs)

        # ModelForm auto-generates a field's .label from the model field's verbose_name
        # (fields_for_model(), django/forms/models.py) - for a field with no explicit
        # verbose_name, Django defaults that to capfirst(name.replace("_", " ")). The 26
        # SCORECARD_CONFIG_FIELDS declared above aren't model fields, so they never go
        # through that path and keep label=None. Rendering through a BoundField (plain
        # template display) falls back to a pretty name anyway, masking this - but
        # views.py's _extract_values_from_form() (used by the scorecard detail page) reads
        # form.fields[name].label directly, so without this every one of these 26 rows
        # showed "None:" as its label instead of e.g. "Backtracking penalty".
        for field_name in SCORECARD_CONFIG_FIELDS:
            self.fields[field_name].label = capfirst(field_name.replace("_", " "))

        # __init__ runs on every construction, including every POST to the scorecard
        # override page - self.instance.included_fields is a live list stored in
        # Scorecard.config (see the included_fields property), so appending here
        # unconditionally added another copy of the matching block on every save of a
        # navigation task with one of these subtypes, growing without bound. Guard each
        # append with a check for whether a block with that title is already present.
        existing_block_titles = {block[0] for block in self.instance.included_fields}

        def _append_block_once(block: list) -> None:
            if block[0] not in existing_block_titles:
                self.instance.included_fields.append(block)
                existing_block_titles.add(block[0])

        navigation_task = getattr(self.instance, "navigation_task_override", None)
        if navigation_task and navigation_task.task_subtype in (TURNPOINT_HUNT, LIMITED_FUEL_TURNPOINT_HUNT):
            _append_block_once(
                [
                    "Turnpoint hunt configuration",
                    "compulsory_timing_tolerance_seconds",
                    "maximum_task_duration_minutes",
                    "maximum_task_duration_penalty",
                    "fuel_deadline_penalty",
                ]
            )
        if navigation_task and navigation_task.task_subtype == ANR_CATALOGUE:
            _append_block_once(
                [
                    "ANR catalogue configuration",
                    "anr_route_to_sp_penalty",
                    "anr_route_from_fp_penalty",
                ]
            )
        if navigation_task and navigation_task.task_subtype == DURATION:
            _append_block_once(
                [
                    "Duration configuration",
                    "duration_normalization_policy",
                    "duration_residual_fuel_required",
                ]
            )
        if navigation_task and navigation_task.task_subtype == CIRCLE:
            _append_block_once(
                [
                    "Circle configuration",
                    "circle_radius_min_m",
                    "circle_radius_max_m",
                ]
            )

        self.helper = FormHelper()
        self.helper.form_class = "form mt-4"
        self.helper.layout = Layout(
            Fieldset("Score sorting direction", "score_sorting_direction"),
            *[
                Fieldset(*[field for field in block if field != "corridor_width"])
                for block in self.instance.included_fields
            ],
            *[
                Field(key, type="hidden")
                for key in self.fields.keys()
                if (key not in self.instance.visible_fields and key != "score_sorting_direction")
                or key == "corridor_width"
            ],
            ButtonHolder(
                Submit("submit", "Submit"),
                Submit(
                    "cancel",
                    "Cancel",
                    css_class="btn-danger",
                ),
            ),
        )


class GateScoreForm(forms.Form):
    # Phase 2e of the scorecard-system review roadmap: GateScore is no longer a database
    # table - this form is bound to a Scorecard + gate_type (GateScoreForm(scorecard=...,
    # gate_type=...)) instead of a GateScore instance, and reads/writes
    # Scorecard.config["gates"][gate_type] via GateScoreValue
    # (models/scorecard_and_gate_score.py). Same 11 editable fields the previous ModelForm's
    # fields="__all__" ended up exposing once id/scorecard/gate_type were hidden by
    # views.py's visible_fields-based pop loop downstream - those three were never meant to
    # be user-editable, so they're not declared here either.
    extended_gate_width = forms.FloatField(required=False)
    bad_crossing_extended_gate_penalty = forms.FloatField(required=False)
    graceperiod_before = forms.FloatField(required=False)
    graceperiod_after = forms.FloatField(required=False)
    maximum_penalty = forms.FloatField(required=False)
    penalty_per_second = forms.FloatField(required=False)
    missed_penalty = forms.FloatField(required=False)
    missed_procedure_turn_penalty = forms.FloatField(required=False)
    backtracking_after_steep_gate_grace_period_seconds = forms.FloatField(required=False)
    backtracking_before_gate_grace_period_nm = forms.FloatField(required=False)
    backtracking_after_gate_grace_period_nm = forms.FloatField(required=False)

    def __init__(self, *args, scorecard, gate_type, **kwargs):
        self.scorecard = scorecard
        self.gate_type = gate_type
        # self.instance (not a Django/ModelForm convention here, just matching that naming so
        # _extract_values_from_form() - shared with ScorecardForm - keeps working unchanged):
        # a GateScoreValue has every field name below as a plain attribute, plus
        # included_fields/visible_fields/get_gate_type_display(), same as GateScore used to.
        self.instance = scorecard.get_gate_scorecard(gate_type)
        initial = dict(kwargs.get("initial") or {})
        for field_name in self.base_fields:
            initial.setdefault(field_name, getattr(self.instance, field_name))
        kwargs["initial"] = initial
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = "form mt-4"
        self.helper.layout = Layout(
            *[Fieldset(*block) for block in self.instance.included_fields],
            *[Field(key, type="hidden") for key in self.fields.keys() if key not in self.instance.visible_fields],
            ButtonHolder(
                Submit("submit", "Submit"),
                Submit(
                    "cancel",
                    "Cancel",
                    css_class="btn-danger",
                ),
            ),
        )

    def save(self):
        # Every field here is required=False and none of GateScoreValue's fields declare a
        # None default (all 11 have real numeric defaults, models/scorecard_and_gate_score.py)
        # - so a cleared numeric input's None must never be merged in, or it would permanently
        # overwrite the configured value with None on every future read of this gate.
        cleaned_values = {
            field_name: value for field_name, value in self.cleaned_data.items() if value is not None
        }
        gates = self.scorecard.config.setdefault("gates", {})
        gates.setdefault(self.gate_type, {}).update(cleaned_values)
        self.scorecard.save(update_fields=["config"])


class ScorecardFormSetHelper(FormHelper):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.form_method = "post"
        self.render_required_fields = True


kml_description = HTML(
    """
<p>The KML must contain at least the following:</p>
<ol class="list-decimal list-inside mb-2">
    <li><strong>route</strong>: A path with the name "route" which makes up the route that should be flown.</li>
</ol>
<p>The KML file can optionally also include:</p>
<ol class="list-decimal list-inside space-y-1">
    <li><strong>to</strong>: A path with the name "to" that defines the takeoff gate. This is typically located across the runway.</li>
    <li><strong>ldg</strong>: A path with the name "ldg" that defines the landing gate. This is typically located across the runway. It can be at the same location as the take off gate, but it must be a separate path.</li>
    <li><strong>prohibited</strong>: Zero or more polygons with the name "prohibited_*" where '*' can be replaced with an arbitrary text. These polygons describe prohibited zones either in an ANR context, or can be used to mark airspace that should not be infringed, for instance. Prohibited zones incur a fixed penalty for each entry.</li>
    <li><strong>penalty</strong>: Zero or more polygons with the name "penalty_*" where '*' can be replaced with an arbitrary text. These polygons describe penalty zones where points are added for each second spent inside the zone.</li>
    <li><strong>info</strong>: Zero or more polygons with the name "info_*" where '*' can be replaced with an arbitrary text. These polygons are for information only and not give any penalties. Can be used to indicate RMZ with frequency information, for instance.</li>
</ol>
    """
)


class ImportRouteForm(forms.Form):
    """Used to import routes as editable route."""

    name = forms.CharField(help_text="The name the route should be saved as.")
    file = forms.FileField(
        help_text="Route file to import. File type is inferred from the file suffix. Supported files are .csv, .kml, .kmz, and FlightContest .gpx. Note that the imported route does not respect the Flight Contest pre-calculated gate lines. Gate lines are calculated by airsports."
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Fieldset("Route import", "name", "file"),
            kml_description,
            ButtonHolder(Submit("submit", "Submit")),
        )


class DeleteUserForm(forms.Form):
    email = forms.EmailField(help_text="The e-mail of the user you wish to delete")
    send_email = forms.BooleanField(
        help_text="Should we automatically send a deletion acknowledgement email to the user", required=False
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Fieldset("User selection", "email", "send_email"),
            ButtonHolder(Submit("submit", "Submit")),
        )


class SignUpForm(forms.Form):
    first_name = forms.CharField(max_length=255)
    last_name = forms.CharField(max_length=255)
    email = forms.EmailField(max_length=255)
    country = forms.ChoiceField(choices=[])
    password = forms.CharField(widget=forms.PasswordInput)
    password_confirm = forms.CharField(widget=forms.PasswordInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["country"].choices = Person._meta.get_field("country").choices
        self.helper = FormHelper()
        self.helper.form_class = "form"
        self.helper.layout = Layout(
            Fieldset(
                "Personal Information",
                "first_name",
                "last_name",
                "email",
                "country",
            ),
            Fieldset(
                "Security",
                "password",
                "password_confirm",
            ),
            ButtonHolder(Submit("submit", "Sign Up")),
        )

    def clean_email(self):
        email = self.cleaned_data.get("email", "").lower()
        return email

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        password_confirm = cleaned_data.get("password_confirm")

        if password and password_confirm and password != password_confirm:
            self.add_error("password_confirm", "Passwords do not match.")

        return cleaned_data


class ImportContestTeamForm(forms.Form):
    contest = forms.ModelChoiceField(queryset=Contest.objects.all())

    def __init__(self, available_contests: Iterable[Contest], *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["contest"].queryset = available_contests
        self.helper = FormHelper()
        self.helper.form_class = "form"
        self.helper.layout = Layout(
            Fieldset("Import Teams", "contest"),
            ButtonHolder(Submit("submit", "Import")),
        )
