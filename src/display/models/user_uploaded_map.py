import os
from io import BytesIO
from tempfile import NamedTemporaryFile

from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models
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


class UserUploadedMap(models.Model):
    """
    A user uploaded map contains a mbtiles file that conserve tiles to be used as map backgrounds for navigation maps
    (flight orders) created by users with access to the user uploaded map object.
    """
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

    def __str__(self):
        return self.name

    class Meta:
        unique_together = ("user", "name")

    def get_local_file_path(self) -> str:
        """
        Maps are stored in Google file storage. However, matplotlib/cartopy requires the files to be available locally.
        This function ensures that the file has been copied to the local file system and returns the path to it.
        """
        key = f"user_map_{self.map_file.name}"
        if temporary_path := LOCAL_MAP_FILE_CACHE.get(key):
            return temporary_path
        else:
            with NamedTemporaryFile(delete=False) as temporary_map:
                temporary_map.write(self.map_file.read())
                LOCAL_MAP_FILE_CACHE[key] = temporary_map.name
                return temporary_map.name

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
