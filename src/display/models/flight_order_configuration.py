from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models

from display.flight_order_and_maps.map_constants import MAP_SIZES, A4, ORIENTATIONS, PORTRAIT, SCALES, SCALE_TO_FIT
from display.flight_order_and_maps.map_plotter_shared_utilities import get_map_choices


class FlightOrderConfiguration(models.Model):
    """
    Stores the flight order configuration for a navigation task.
    """

    navigation_task = models.OneToOneField("NavigationTask", on_delete=models.CASCADE)
    document_size = models.CharField(choices=MAP_SIZES, default=A4, max_length=50)
    include_turning_point_images = models.BooleanField(
        default=True,
        help_text="Includes one or more pages with aerial photos of each turning point (turns in a anr corridor is not considered a turning point).",
    )
    map_include_meridians_and_parallels_lines = models.BooleanField(
        default=True,
        help_text="If true, navigation map is overlaid with meridians and parallels every 0.1 degrees. Disable if map source already has this",
    )
    map_dpi = models.IntegerField(default=300, validators=[MinValueValidator(100), MaxValueValidator(500)])
    map_zoom_level = models.IntegerField(default=12, choices=[(x, x) for x in range(1, 20)])
    map_orientation = models.CharField(choices=ORIENTATIONS, default=PORTRAIT, max_length=30)
    map_scale = models.IntegerField(choices=SCALES, default=SCALE_TO_FIT)
    map_source = models.CharField(choices=[], default="cyclosm", max_length=50, blank=True)
    map_user_source = models.ForeignKey(
        "UserUploadedMap",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        help_text="Overrides whatever is chosen in map source",
    )
    map_include_annotations = models.BooleanField(
        default=True,
        help_text="If this if set, the generated map will include minute marks and leg headings for the contestant so that no map preparation is necessary.",
    )
    map_plot_track_between_waypoints = models.BooleanField(
        default=True,
        help_text="For precision and Air Sport competition types this will draw a line between the waypoints of the track. Without this the precision map will only contain the waypoints, and the Air Sport maps will only contain the corridor without a centreline.",
    )
    map_line_width = models.FloatField(default=1, validators=[MinValueValidator(0.1), MaxValueValidator(10.0)])
    map_minute_mark_line_width = models.FloatField(
        default=1, validators=[MinValueValidator(0.1), MaxValueValidator(10.0)]
    )
    map_line_colour = models.CharField(default="#0000ff", max_length=7)
    turning_point_photos_meters_across = models.FloatField(
        default=1400,
        help_text="Approximately the number of meters on the ground that is covered by the turning point photo",
    )
    turning_point_photos_zoom_level = models.IntegerField(
        default=15,
        help_text="The tile zoom level used for generating turning point photos from google satellite imagery",
        validators=[MinValueValidator(1), MaxValueValidator(20)],
    )
    unknown_leg_photos_meters_across = models.FloatField(
        default=1400,
        help_text="Approximately the number of meters on the ground that is covered by the unknown leg photo",
    )
    unknown_leg_photos_zoom_level = models.IntegerField(
        default=15,
        help_text="The tile zoom level used for generating unknown leg photos from google satellite imagery",
        validators=[MinValueValidator(1), MaxValueValidator(20)],
    )
    photos_meters_across = models.FloatField(
        default=350,
        help_text="Approximately the number of meters on the ground that is covered by our observation photo",
    )
    photos_zoom_level = models.IntegerField(
        default=17,
        help_text="The tile zoom level used for generating photos from google satellite imagery",
        validators=[MinValueValidator(1), MaxValueValidator(20)],
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._meta.get_field("map_source").choices = get_map_choices()
