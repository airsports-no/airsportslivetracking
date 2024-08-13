from string import Template

import datetime
from typing import Optional

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, ButtonHolder, Submit, Fieldset, Field, HTML
from django import forms
from django.contrib.gis.forms import OSMWidget, LineStringField
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
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
from display.flight_order_and_maps.mbtiles_facade import get_map_details
from display.models import (
    NavigationTask,
    Contestant,
    Contest,
    Person,
    Team,
    ContestTeam,
    Scorecard,
    GateScore,
    FlightOrderConfiguration,
    UserUploadedMap,
)
from display.poker.poker_cards import PLAYING_CARDS
from display.utilities.country_code_utilities import get_country_code_from_location, CountryNotFoundException

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
    map_source = forms.ChoiceField(choices=[], help_text="Is overridden by user map source if set", required=False)
    user_map_source = forms.ModelChoiceField(
        UserUploadedMap.objects.all(), help_text="Overrides map source if set", required=False
    )
    zoom_level = forms.TypedChoiceField(initial=12, choices=[(x, x) for x in range(1, 15)], coerce=int, empty_value=12)
    dpi = forms.IntegerField(initial=300, min_value=100, max_value=1000)
    line_width = forms.FloatField(initial=0.5, min_value=0.1, max_value=10)
    colour = forms.CharField(initial="#0000ff", max_length=7, widget=forms.HiddenInput())

    def clean(self):
        cleaned_data = super().clean()
        validate_map_zoom_level(
            cleaned_data.get("map_source"), cleaned_data.get("user_uploaded_map"), cleaned_data.get("zoom_level")
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.fields["map_source"].choices = get_map_choices()


class ContestantMapForm(forms.Form):
    size = forms.ChoiceField(choices=MAP_SIZES, initial=A4)
    dpi = forms.IntegerField(initial=300, min_value=100, max_value=500)
    orientation = forms.ChoiceField(choices=ORIENTATIONS, initial=PORTRAIT)
    scale = forms.ChoiceField(choices=SCALES, initial=SCALE_TO_FIT)
    map_source = forms.ChoiceField(choices=[], help_text="Is overridden by user map source if set", required=False)
    user_map_source = forms.ModelChoiceField(
        UserUploadedMap.objects.all(), help_text="Overrides map source if set", required=False
    )
    zoom_level = forms.TypedChoiceField(coerce=int, initial=12, choices=[(i, i) for i in range(1, 15)])

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

    def clean(self):
        cleaned_data = super().clean()
        validate_map_zoom_level(
            cleaned_data.get("map_source"), cleaned_data.get("user_uploaded_map"), cleaned_data.get("zoom_level")
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.fields["map_source"].choices = get_map_choices()


class UserUploadedMapForm(forms.ModelForm):
    class Meta:
        model = UserUploadedMap
        exclude = ("thumbnail", "unprotected", "minimum_zoom_level", "maximum_zoom_level")
        # widgets = {"map_file": FileInput(attrs={'accept': 'application/vnd.mapbox-vector-tile'})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Fieldset("User map", "name", "default_zoom_level", "attribution", "map_file"),
            Field("user", type="hidden"),
            ButtonHolder(Submit("submit", "Submit")),
        )


def validate_map_zoom_level(map_source: str, user_uploaded_map: Optional[UserUploadedMap], zoom_level: int):
    if user_uploaded_map:
        if not user_uploaded_map.minimum_zoom_level <= zoom_level <= user_uploaded_map.maximum_zoom_level:
            raise ValidationError(
                f"The selected zoom level {zoom_level}  is not in the valid range [{user_uploaded_map.minimum_zoom_level}, "
                f"{user_uploaded_map.maximum_zoom_level}] for the  user uploaded map {user_uploaded_map.name}"
            )
    else:
        if map_source not in ("osm", "fc", "mto", "cyclosm"):
            map_details = get_map_details(map_source)
            min_zoom = map_details.get("minzoom", 12)
            max_zoom = map_details.get("maxzoom", 12)
            if not min_zoom <= zoom_level <= max_zoom:
                raise ValidationError(
                    f"The selected zoom level {zoom_level} is not in the valid range [{min_zoom}, "
                    f"{max_zoom}] for the map source {map_details['name']}"
                )


class FlightOrderConfigurationForm(forms.ModelForm):
    class Meta:
        model = FlightOrderConfiguration
        exclude = ("navigation_task", "document_size")

    def clean(self):
        cleaned_data = super().clean()
        validate_map_zoom_level(
            cleaned_data.get("map_source"), cleaned_data.get("map_user_source"), cleaned_data.get("map_zoom_level")
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["map_source"].choices = get_map_choices()
        print(self.fields["map_source"].choices)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
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
            HTML('<h3>Pick a colour for the map lines</h3><div id="picker" style="margin-bottom: 10px"></div>'),
            ButtonHolder(Submit("submit", "Submit"), Submit("cancel", "Cancel", css_class="btn-secondary")),
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
            "planning_time",
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
        exclude = ("contest_teams", "is_featured", "is_public", "latitude", "longitude", "country")

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
                "Contest location",
                # HTML(
                #     "If no position is given, position will be extracted from the starting position of the first task added to the contest"
                # ),
                # "latitude",
                # "longitude",
                # "country",
                "location",
            ),
            Fieldset("Publicity", "contest_website", "header_image", "logo"),
            Fieldset("Result service", "summary_score_sorting_direction", "autosum_scores"),
            ButtonHolder(Submit("submit", "Submit")),
        )

    def clean_finish_time(self):
        finish_time = self.cleaned_data["finish_time"]
        return finish_time + datetime.timedelta(hours=23, minutes=59)

    def clean(self):
        cleaned_data = super().clean()
        try:
            get_country_code_from_location(*[float(x) for x in cleaned_data["location"].split(",")])
        except CountryNotFoundException:
            raise ValidationError(
                f"The contest location {cleaned_data['location']} is not in a valid country",
                code="invalid",
            )
        except KeyError:
            raise ValidationError(f"Please select a valid location for the contest.", code="invalid")
        # except:
        #     pass
        return cleaned_data


class PictureWidget(forms.widgets.Widget):
    def render(self, name, value, attrs=None, renderer=None):
        html = Template("""<img id="{}" src="$link" class="wizardImage"/>""".format(name))
        return mark_safe(html.substitute(link=value))


class ImagePreviewWidget(forms.widgets.FileInput):
    def render(self, name, value, attrs=None, **kwargs):
        input_html = super().render(name, value, attrs=attrs, **kwargs)
        image_html = mark_safe(f'<br><br><img src="{value.url}"/>')
        return f"{input_html}{image_html}"


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
        self.fields["minutes_to_starting_point"].initial = self.navigation_task.minutes_to_starting_point
        self.fields["navigation_task"].initial = self.navigation_task
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Fieldset(
                "Contestant",
                "navigation_task",
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
                    "The below fields can mostly be left alone. Tracker start time and finished by time are calculated "
                    "automatically to ten minutes prior to the takeoff time with an assumed flight time of maximum two hours with "
                    "fixed start and five hours with adaptive start. Overwrite this as necessary."
                ),
                "tracking_device",
                "tracker_device_id",
                "tracker_start_time",
                "finished_by_time",
            ),
            ButtonHolder(Submit("submit", "Submit")),
        )

    class Meta:
        model = Contestant
        widgets = {"navigation_task": forms.HiddenInput()}
        fields = (
            "contestant_number",
            "team",
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
            "navigation_task",
        )


class ContestTeamOptimisationForm(forms.Form):
    contest_teams = forms.MultipleChoiceField(widget=forms.CheckboxSelectMultiple())
    first_takeoff_time = forms.DateTimeField()
    minutes_between_contestants_at_start = forms.FloatField(initial=5, help_text="The minimum spacing between takeoffs")
    minutes_between_contestants_at_finish = forms.FloatField(
        initial=2,
        help_text="The minimum spacing between aircraft as they cross the finish point (I.e. how close the second aircraft is allowed to get to the first aircraft",
    )
    minutes_for_aircraft_switch = forms.IntegerField(
        initial=30,
        help_text="If an aircraft is shared between competitors, how much time is required from the landing time to the next takeoff for the same aircraft.",
    )
    minutes_for_tracker_switch = forms.IntegerField(
        initial=15,
        help_text="If a tracker is shared between competitors, how much time is required from the landing time to the next takeoff for the same tracker.",
    )
    minutes_for_crew_switch = forms.IntegerField(
        initial=15,
        help_text="If a person is part of multiple crews, how much time does he/she require to jump from one crew to another.",
    )
    tracker_lead_time_minutes = forms.IntegerField(
        initial=15, help_text="How long before takeoff time should tracking of the contestant start"
    )
    optimise = forms.BooleanField(
        required=False,
        initial=True,
        help_text="Try to further optimise the schedule. This will take a maximum of 10 minutes. If a solution is not found within the time, the result will be a suboptimal solution. In that case, rerun the scheduler without this flag set",
    )


class AssignPokerCardForm(forms.Form):
    waypoint = forms.ChoiceField(choices=())
    playing_card = forms.ChoiceField(choices=[("random", "Random")] + PLAYING_CARDS, initial="random")


PERMISSIONS_CHOICE = [("nothing", "Nothing"), ("view", "View"), ("change", "Change"), ("delete", "Delete")]


class AddPermissionsForm(forms.Form):
    email = forms.EmailField()
    permission = forms.ChoiceField(choices=PERMISSIONS_CHOICE)


class ChangePermissionsForm(forms.Form):
    permission = forms.ChoiceField(choices=PERMISSIONS_CHOICE)


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
