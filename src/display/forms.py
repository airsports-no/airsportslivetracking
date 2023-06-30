from string import Template

import datetime

from crispy_forms.bootstrap import StrictButton
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Div, ButtonHolder, Submit, Fieldset, Field, HTML
from django import forms
from django.contrib.gis.forms import OSMWidget, LineStringField
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.forms import HiddenInput
from django.utils.safestring import mark_safe

from display.flight_order_and_maps.map_constants import (
    MAP_SIZES,
    ORIENTATIONS,
    LANDSCAPE,
    SCALES,
    SCALE_TO_FIT,
    A4,
    PORTRAIT,
)
from display.flight_order_and_maps.map_plotter_shared_utilities import get_map_choices
from display.models import (
    NavigationTask,
    Contestant,
    Contest,
    Person,
    Aeroplane,
    Team,
    Club,
    ContestTeam,
    EditableRoute,
    Scorecard,
    GateScore,
    FlightOrderConfiguration,
    UserUploadedMap,
)
from display.poker.poker_cards import PLAYING_CARDS

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


class MapForm(forms.Form):
    size = forms.ChoiceField(choices=MAP_SIZES, initial=A4)
    zoom_level = forms.IntegerField(initial=12)
    orientation = forms.ChoiceField(
        choices=ORIENTATIONS,
        initial=LANDSCAPE,
        help_text="WARNING: scale printing is currently only correct for landscape orientation",
    )
    plot_track_between_waypoints = forms.BooleanField(initial=True, required=False)
    include_meridians_and_parallels_lines = forms.BooleanField(
        initial=True,
        required=False,
        help_text="If true, navigation map is overlaid with meridians and parallels. Disable if map source already has this",
    )

    scale = forms.ChoiceField(choices=SCALES, initial=SCALE_TO_FIT)
    map_source = forms.ChoiceField(
        choices=[], help_text="Is overridden by user map source if set", required=False
    )
    user_map_source = forms.ModelChoiceField(UserUploadedMap.objects.all(), help_text="Overrides map source if set", required=False)
    dpi = forms.IntegerField(initial=300, min_value=100, max_value=1000)
    line_width = forms.FloatField(initial=0.5, min_value=0.1, max_value=10)
    colour = forms.CharField(initial="#0000ff", max_length=7, widget=forms.HiddenInput())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.fields["map_source"].choices = get_map_choices()



class ContestantMapForm(forms.Form):
    size = forms.ChoiceField(choices=MAP_SIZES, initial=A4)
    dpi = forms.IntegerField(initial=300, min_value=100, max_value=500)
    zoom_level = forms.IntegerField(initial=12)
    orientation = forms.ChoiceField(choices=ORIENTATIONS, initial=PORTRAIT)
    scale = forms.ChoiceField(choices=SCALES, initial=SCALE_TO_FIT)
    map_source = forms.ChoiceField(
        choices=[], help_text="Is overridden by user map source if set", required=False
    )
    user_map_source = forms.ModelChoiceField(UserUploadedMap.objects.all(), help_text="Overrides map source if set", required=False)

    include_annotations = forms.BooleanField(initial=True, required=False)
    plot_track_between_waypoints = forms.BooleanField(initial=True, required=False)
    include_meridians_and_parallels_lines = forms.BooleanField(
        initial=True,
        required=False,
        help_text="If true, navigation map is overlaid with meridians and parallels. Disable if map source already has this",
    )

    line_width = forms.FloatField(initial=0.5, min_value=0.1, max_value=10)
    minute_mark_line_width = forms.FloatField(initial=0.5, min_value=0.1, max_value=10)
    colour = forms.CharField(initial="#0000ff", max_length=7, widget=forms.HiddenInput())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.fields["map_source"].choices = get_map_choices()


class UserUploadedMapForm(forms.ModelForm):
    class Meta:
        model = UserUploadedMap
        exclude = ("thumbnail","unprotected", "minimum_zoom_level", "maximum_zoom_level")
        # widgets = {"map_file": FileInput(attrs={'accept': 'application/vnd.mapbox-vector-tile'})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Fieldset("User map", "name", "map_file"),
            Field("user", type="hidden"),
            ButtonHolder(Submit("submit", "Submit")),
        )


class AddUserUploadedMapPermissionsForm(forms.Form):
    email = forms.EmailField()
    change_useruploadedmap = forms.BooleanField(required=False, label="Modify map")
    view_useruploadedmap = forms.BooleanField(required=False, label="View and use map")
    delete_useruploadedmap = forms.BooleanField(required=False, label="Delete map")


class ChangeUserUploadedMapPermissionsForm(forms.Form):
    change_useruploadedmap = forms.BooleanField(required=False, label="Modify map")
    view_useruploadedmap = forms.BooleanField(required=False, label="View and use map")
    delete_useruploadedmap = forms.BooleanField(required=False, label="Delete map")


class FlightOrderConfigurationForm(forms.ModelForm):
    class Meta:
        model = FlightOrderConfiguration
        exclude = ("navigation_task", "document_size")


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["map_source"].choices = get_map_choices()
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Fieldset(
                "Flight order options",
                # "document_size",
                "include_turning_point_images",
            ),
            Fieldset(
                "Map options",
                "map_source",
                "map_user_source",
                "map_orientation",
                "map_zoom_level",
                "map_scale",
                "map_dpi",
                "map_include_annotations",
                "map_plot_track_between_waypoints",
                "map_include_meridians_and_parallels_lines",
                "map_line_width",
                "map_minute_mark_line_width",
            ),
            Field("map_line_colour", type="hidden"),
            HTML('<h3>Pick a colour for the map lines</h3><div id="picker" style="margin-bottom: 10px"></div>'),
            ButtonHolder(Submit("submit", "Submit"), Submit("cancel", "Cancel", css_class="btn-secondary")),
        )


class TaskTypeForm(forms.Form):
    task_type = forms.ChoiceField(
        choices=NavigationTask.NAVIGATION_TASK_TYPES,
        help_text="The type of the task. This determines how the route file is processed",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Fieldset(
                "Select the task type from the drop-down list",
                "task_type",
            ),
            ButtonHolder(Submit("submit", "Submit")),
        )


kml_description = HTML(
    """
            <p>The KML must contain at least the following:
            <ol>
            <li>route: A path with the name "route" which makes up the route that should be flown.</li>
            </ol>
            The KML file can optionally also include:
            <ol>
            <li>to: A path with the name "to" that defines the takeoff gate. This is typically located across the runway</li>
            <li>ldg: A path with the name "ldg" that defines the landing gate. This is typically located across the runway. It can be at the same location as the take of gate, but it must be a separate path</li>
            <li>prohibited: Zero or more polygons with the name "prohibited_*" where '*' can be replaced with an arbitrary text. These polygons describe prohibited zones either in an ANR context, or can be used to mark airspace that should not be infringed, for instance. Prohibited zones incur a fixed penalty for each entry.</li>
            <li>penalty: Zero or more polygons with the name "penalty_*" where '*' can be replaced with an arbitrary text. These polygons describe penalty zones Where points are added for each second spent inside the zone.</li>
            <li>info: Zero or more polygons with the name "info_*" where '*' can be replaced with an arbitrary text. These polygons Are for information only and not give any penalties. Can be used to indicate RMZ with frequency information, for instance</li>
            </ol>
            </p>
            """
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


class NavigationTaskForm(forms.ModelForm):
    class Meta:
        model = NavigationTask
        fields = (
            "name",
            "start_time",
            "finish_time",
            "display_background_map",
            "display_secrets",
            "minutes_to_starting_point",
            "original_scorecard",
            "minutes_to_landing",
            "wind_speed",
            "wind_direction",
            "allow_self_management",
            "score_sorting_direction",
            "calculation_delay_minutes",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["original_scorecard"].queryset = Scorecard.get_originals()
        instance = getattr(self, "instance", None)
        if instance and instance.pk:
            self.fields["original_scorecard"].disabled = True
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Fieldset(
                "Navigation task details",
                "name",
                "start_time",
                "finish_time",
                "original_scorecard",
                "allow_self_management",
                "score_sorting_direction",
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


class ContestSelectForm(forms.Form):
    contest = forms.ModelChoiceField(
        Contest.objects.all(),
        required=False,
        help_text="Choose an existing contest for the new task. If no contest is chosen, you will be prompted to create a new one on the next screen",
    )
    task_type = forms.ChoiceField(
        choices=NavigationTask.NAVIGATION_TASK_TYPES,
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


class ContestForm(forms.ModelForm):
    class Meta:
        model = Contest
        exclude = ("contest_teams", "is_featured", "is_public")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Fieldset(
                "Contest details",
                "name",
                "time_zone",
                "start_time",
                "finish_time",
            ),
            Fieldset(
                "Contest location (optional)",
                HTML(
                    "If no position is given, position will be extracted from the starting position of the first task added to the contest"
                ),
                "latitude",
                "longitude",
                "country",
            ),
            Fieldset("Publicity", "contest_website", "header_image", "logo"),
            Fieldset("Result service", "summary_score_sorting_direction", "autosum_scores"),
            ButtonHolder(Submit("submit", "Submit")),
        )

    def clean_finish_time(self):
        start_time = self.cleaned_data.get("start_time")
        finish_time = self.cleaned_data.get("finish_time")
        if start_time == finish_time:
            return finish_time + datetime.timedelta(days=1)
        else:
            return finish_time


class PictureWidget(forms.widgets.Widget):
    def render(self, name, value, attrs=None, renderer=None):
        html = Template("""<img id="{}" src="$link" class="wizardImage"/>""".format(name))
        return mark_safe(html.substitute(link=value))


class ImagePreviewWidget(forms.widgets.FileInput):
    def render(self, name, value, attrs=None, **kwargs):
        input_html = super().render(name, value, attrs=attrs, **kwargs)
        image_html = mark_safe(f'<br><br><img src="{value.url}"/>')
        return f"{input_html}{image_html}"


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


class PersonPictureForm(forms.ModelForm):
    # picture = forms.ImageField(widget=ImagePreviewWidget)
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
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


class PersonForm(forms.ModelForm):
    # picture = forms.ImageField(widget=ImagePreviewWidget)
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
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


class TeamForm(forms.ModelForm):
    logo = forms.ImageField(widget=ImagePreviewWidget, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["crew"].disabled = True
        self.fields["aeroplane"].disabled = True
        self.fields["club"].disabled = True
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Fieldset("Team", "crew", "aeroplane", "club", "country", "logo"), ButtonHolder(Submit("submit", "Submit"))
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


class TrackingDataForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Fieldset("Team contest information", "air_speed", "tracking_device"),
            Fieldset(
                "Optional tracking information if not using the official Air Sports Live Tracking app",
                "tracker_device_id",
            ),
            ButtonHolder(Submit("submit", "Submit")),
        )

    class Meta:
        model = ContestTeam
        fields = ("air_speed", "tracker_device_id", "tracking_device")


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


class ContestantForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self.navigation_task = kwargs.pop("navigation_task")  # type: NavigationTask

        super().__init__(*args, **kwargs)
        self.fields["team"].queryset = self.navigation_task.contest.contest_teams.all()
        self.fields["contestant_number"].initial = (
            max([item.contestant_number for item in self.navigation_task.contestant_set.all()]) + 1
            if self.navigation_task.contestant_set.all().count() > 0
            else 1
        )
        self.fields["wind_speed"].initial = self.navigation_task.wind_speed
        self.fields["wind_direction"].initial = self.navigation_task.wind_direction
        self.fields["wind_direction"].initial = self.navigation_task.wind_direction
        # self.fields["tracking_device_id"].required = False

    class Meta:
        model = Contestant
        fields = (
            "contestant_number",
            "team",
            "tracker_start_time",
            "tracking_device",
            "tracker_device_id",
            "takeoff_time",
            "adaptive_start",
            "finished_by_time",
            "minutes_to_starting_point",
            "air_speed",
            "wind_direction",
            "wind_speed",
        )


class ContestTeamOptimisationForm(forms.Form):
    contest_teams = forms.MultipleChoiceField(widget=forms.CheckboxSelectMultiple())
    first_takeoff_time = forms.DateTimeField()
    minutes_between_contestants = forms.FloatField(initial=5)
    minutes_for_aircraft_switch = forms.IntegerField(initial=30)
    minutes_for_tracker_switch = forms.IntegerField(initial=15)
    minutes_for_crew_switch = forms.IntegerField(initial=15)
    tracker_lead_time_minutes = forms.IntegerField(initial=15)
    # optimise = forms.BooleanField(required=False, initial=False, help_text="Try to further optimise the schedule")


class AssignPokerCardForm(forms.Form):
    waypoint = forms.ChoiceField(choices=())
    playing_card = forms.ChoiceField(choices=[("random", "Random")] + PLAYING_CARDS, initial="random")


class AddContestPermissionsForm(forms.Form):
    email = forms.EmailField()
    change_contest = forms.BooleanField(required=False)
    view_contest = forms.BooleanField(required=False)
    delete_contest = forms.BooleanField(required=False)


class ChangeContestPermissionsForm(forms.Form):
    change_contest = forms.BooleanField(required=False)
    view_contest = forms.BooleanField(required=False)
    delete_contest = forms.BooleanField(required=False)


class AddEditableRoutePermissionsForm(forms.Form):
    email = forms.EmailField()
    change_editableroute = forms.BooleanField(required=False, label="Change route")
    view_editableroute = forms.BooleanField(required=False, label="View route")
    delete_editableroute = forms.BooleanField(required=False, label="Delete route")


class ChangeEditableRoutePermissionsForm(forms.Form):
    change_editableroute = forms.BooleanField(required=False, label="Change route")
    view_editableroute = forms.BooleanField(required=False, label="View route")
    delete_editableroute = forms.BooleanField(required=False, label="Delete route")


class RouteCreationForm(forms.Form):
    route = LineStringField(widget=OSMWidget(attrs={"map_width": 800, "map_height": 500}))


class GPXTrackImportForm(forms.Form):
    track_file = forms.FileField(validators=[FileExtensionValidator(allowed_extensions=["gpx"])], required=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Fieldset(
                "GPX Track upload",
                "track_file",
            ),
            ButtonHolder(Submit("submit", "Submit")),
        )


class ScorecardForm(forms.ModelForm):
    corridor_width = forms.FloatField()

    class Meta:
        model = Scorecard
        exclude = ("name", "original", "included_fields", "calculator", "task_type", "use_procedure_turns", "free_text")

    def __init__(self, *args, **kwargs):
        instance = kwargs.get("instance", None)
        if instance:
            kwargs["initial"] = {"corridor_width": instance.corridor_width}
        super().__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.layout = Layout(
            *[
                Fieldset(*[field for field in block if field != "corridor_width"])
                for block in self.instance.included_fields
            ],
            *[
                Field(key, type="hidden")
                for key in self.fields.keys()
                if key not in self.instance.visible_fields or key == "corridor_width"
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


class GateScoreForm(forms.ModelForm):
    class Meta:
        model = GateScore
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
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


class ScorecardFormSetHelper(FormHelper):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.form_method = "post"
        self.render_required_fields = True


class ImportRouteForm(forms.Form):
    """Used to import routes as editable route."""

    name = forms.CharField(help_text="The name the route should be saved as.")
    file = forms.FileField(
        help_text="Route file to import. File type is inferred from the file suffix. Supported files are .csv, .kml, .kmz, and FlightContest .gpx. Note that the imported route does not respect the Flight Contest pre-calculated gate lines. Gate lines are calculated by airsports."
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
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
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Fieldset("User selection", "email", "send_email"),
            ButtonHolder(Submit("submit", "Submit")),
        )
