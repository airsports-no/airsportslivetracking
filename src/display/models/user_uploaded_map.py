import os
from io import BytesIO
from pathlib import Path
from tempfile import NamedTemporaryFile

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils.text import slugify
from pymbtiles import MBtiles

from display.utilities.mbtiles_stitch import MBTilesHelper


def validate_file_size(value):
    filesize = value.size

    if filesize > 100 * 1024 * 1024:
        raise ValidationError(
            "You cannot upload file more than 100MB. Decrees the area of the map or include fewer zoom levels. Zoom level 12 is normally the best."
        )
    else:
        return value


LOCAL_MAP_FILE_CACHE = {}


def get_mbtiles_publish_root() -> Path:
    return Path(getattr(settings, "MBTILES_PUBLISH_ROOT", "/tilesets"))


class UserUploadedMap(models.Model):
    """
    A user uploaded map contains a mbtiles file that conserve tiles to be used as map backgrounds for navigation maps
    (flight orders) created by users with access to the user uploaded map object.
    """
    PROCESSING_PENDING = "pending"
    PROCESSING_READY = "ready"
    PROCESSING_FAILED = "failed"
    PROCESSING_STATUS_CHOICES = (
        (PROCESSING_PENDING, "Pending"),
        (PROCESSING_READY, "Ready"),
        (PROCESSING_FAILED, "Failed"),
    )

    user = models.ForeignKey("MyUser", on_delete=models.CASCADE)
    name = models.CharField(max_length=500)
    map_file = models.FileField(
        upload_to="user_uploaded_maps",
        validators=[FileExtensionValidator(allowed_extensions=["mbtiles"]), validate_file_size],
        help_text="File must be of type MBTILES. This can be generated for instance using MapTile Desktop",
        max_length=500,
    )
    thumbnail = models.ImageField(upload_to="map_thumbnails", blank=True, null=True, max_length=500)
    unprotected = models.BooleanField(default=False, help_text="If true, this map is globally available.")
    minimum_zoom_level = models.IntegerField(default=0)
    maximum_zoom_level = models.IntegerField(default=14)
    default_zoom_level = models.IntegerField(
        default=12,
        help_text="This zoom level is automatically selected when choosing the map in the flight order configuration "
        "or other map generation forms.",
    )
    attribution = models.TextField(
        default="",
        help_text="A short attribution text for the map source material (source and time of retrieval), e.g. 'Contains data from kartverket.no, 07/2023",
        max_length=100,
    )
    processing_status = models.CharField(
        max_length=16,
        choices=PROCESSING_STATUS_CHOICES,
        default=PROCESSING_PENDING,
    )
    processing_error = models.TextField(blank=True, default="")
    published_service_key = models.CharField(max_length=255, blank=True, default="")
    published_relative_path = models.CharField(max_length=500, blank=True, default="")
    published_at = models.DateTimeField(blank=True, null=True)
    minimum_longitude = models.FloatField(blank=True, null=True)
    minimum_latitude = models.FloatField(blank=True, null=True)
    maximum_longitude = models.FloatField(blank=True, null=True)
    maximum_latitude = models.FloatField(blank=True, null=True)

    def __str__(self):
        return self.name

    class Meta:
        unique_together = ("user", "name")

    @property
    def default_service_key(self) -> str:
        return f"user-uploaded-map-{self.pk}"

    @property
    def default_published_relative_path(self) -> str:
        if self.map_file and getattr(self.map_file, "name", ""):
            return self.map_file.name
        suffix = self.pk if self.pk else slugify(self.name) or "uploaded-map"
        return f"user_uploaded_maps/user-uploaded-map-{suffix}.mbtiles"

    @property
    def published_absolute_path(self) -> Path:
        relative_path = self.published_relative_path or self.default_published_relative_path
        return get_mbtiles_publish_root() / relative_path

    @property
    def canonical_source_exists(self) -> bool:
        return self.published_absolute_path.exists()

    @property
    def safe_map_file_size(self):
        if self.published_absolute_path.exists():
            return self.published_absolute_path.stat().st_size
        try:
            return self.map_file.size
        except (FileNotFoundError, OSError, ValueError):
            return None

    @property
    def safe_thumbnail_url(self):
        if not self.thumbnail:
            return None
        try:
            return self.thumbnail.url
        except (FileNotFoundError, OSError, ValueError):
            return None

    @property
    def bounds(self):
        if None in (self.minimum_longitude, self.minimum_latitude, self.maximum_longitude, self.maximum_latitude):
            return None
        return [self.minimum_longitude, self.minimum_latitude, self.maximum_longitude, self.maximum_latitude]

    def get_local_file_path(self) -> str:
        """
        Maps are stored in Google file storage. However, matplotlib/cartopy requires the files to be available locally.
        This function ensures that the file has been copied to the local file system and returns the path to it.
        Streams the file in chunks to avoid loading the entire (up to 100MB) mbtiles into memory at once.
        """
        if self.published_absolute_path.exists():
            return str(self.published_absolute_path)
        key = f"user_map_{self.map_file.name}"
        if temporary_path := LOCAL_MAP_FILE_CACHE.get(key):
            return temporary_path
        with NamedTemporaryFile(delete=False) as temporary_map:
            self.map_file.open("rb")
            try:
                for chunk in self.map_file.chunks():
                    temporary_map.write(chunk)
            finally:
                self.map_file.close()
            LOCAL_MAP_FILE_CACHE[key] = temporary_map.name
            return temporary_map.name

    def remove_uploaded_blob(self):
        if not self.map_file:
            return
        try:
            self.map_file.delete(save=False)
        except Exception:
            pass
        self.map_file = ""
        self.save(update_fields=["map_file"])

    def clear_local_file_path(self):
        """
        Clears the mbtiles file from the local file system
        """
        key = f"user_map_{self.map_file.name}"
        if local_path := LOCAL_MAP_FILE_CACHE.get(key):
            try:
                os.remove(local_path)
            except OSError:
                pass
            try:
                del LOCAL_MAP_FILE_CACHE[key]
            except KeyError:
                pass

    def create_thumbnail(self) -> tuple[BytesIO, int, int]:
        """
        Finds the smallest Zoom tile and returns this as a map thumbnail
        """
        local_path = self.get_local_file_path()
        with MBtiles(local_path) as src:
            helper = MBTilesHelper(src)
            minimum_zoom_level, maximum_zoom_level = helper.mbtiles.zoom_range()
            image = helper.stitch(4096)
            width, height = image.size
            image = image.resize((400, int(400 * height / width)))
            temporary_file = BytesIO()
            image.save(temporary_file, "PNG")
            return temporary_file, minimum_zoom_level, maximum_zoom_level

    def get_bounds(self) -> tuple[float, float, float, float]:
        local_path = self.get_local_file_path()
        with MBtiles(local_path) as src:
            helper = MBTilesHelper(src)
            return helper.bounds()
