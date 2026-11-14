import io
from unittest.mock import MagicMock, patch

from django.core.files.base import ContentFile
from django.core.management import call_command
from django.test import TestCase
from PIL import Image

from display.flight_order_and_maps.generate_flight_orders import generate_photo
from display.models import Photo, Route


def white_png(size=2000) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGBA", (size, size), (255, 255, 255, 255)).save(buffer, "PNG")
    return buffer.getvalue()


class GeneratedPhotoTest(TestCase):
    def test_nothing_is_printed_on_the_picture(self):
        """The photo's name used to be drawn in a corner; it could give away the order of the route."""
        figure = MagicMock()
        figure.savefig.side_effect = lambda target, *args, **kwargs: target.write(white_png())
        photo = Photo(name="Obs 3", latitude=60.0, longitude=11.0)
        waypoint = MagicMock(bearing_next=0)
        with (
            patch("display.flight_order_and_maps.generate_flight_orders.GoogleTiles"),
            patch("display.flight_order_and_maps.generate_flight_orders.Figure", return_value=figure),
        ):
            temporary_file = generate_photo(photo, waypoint, 350, 17)
        with Image.open(temporary_file.name) as image:
            image = image.convert("RGBA")
            # An untouched white picture: no text, not even a transparent cut-out of it
            self.assertEqual(image.getcolors(), [(image.width * image.height, (255, 255, 255, 255))])


class RegeneratePhotoImagesCommandTest(TestCase):
    def setUp(self):
        self.route = Route.objects.create(name="Route")
        self.generated = Photo.objects.create(name="Obs 1", route=self.route, latitude=60, longitude=11)
        self.generated.file.save("old.png", ContentFile(b"old"), save=True)
        self.uploaded = Photo.objects.create(name="Obs 2", route=self.route, latitude=60, longitude=11, uploaded=True)
        self.uploaded.file.save("own.png", ContentFile(b"own"), save=True)
        self.without_file = Photo.objects.create(name="Obs 3", route=self.route, latitude=60, longitude=11)

    def run_command(self, generate, *args):
        calls = []

        def fake_generate_image(photo, force=False):
            calls.append(photo.pk)
            return generate(photo)

        with patch.object(Photo, "generate_image", fake_generate_image):
            call_command("regenerate_photo_images", *args, stdout=io.StringIO(), stderr=io.StringIO())
        return calls

    def test_only_generated_pictures_are_made_again_and_the_old_file_goes(self):
        old_name = self.generated.file.name

        def generate(photo):
            photo.file.save("new.png", ContentFile(b"new"), save=True)
            return True

        calls = self.run_command(generate)
        self.assertEqual(calls, [self.generated.pk])
        self.generated.refresh_from_db()
        self.assertNotEqual(self.generated.file.name, old_name)
        self.assertEqual(self.generated.file.read(), b"new")
        self.assertFalse(self.generated.file.storage.exists(old_name))
        self.uploaded.refresh_from_db()
        self.assertEqual(self.uploaded.file.read(), b"own")

    def test_a_picture_that_could_not_be_made_again_is_kept(self):
        old_name = self.generated.file.name
        self.run_command(lambda photo: False)
        self.generated.refresh_from_db()
        self.assertEqual(self.generated.file.name, old_name)
        self.assertEqual(self.generated.file.read(), b"old")

    def test_a_dry_run_changes_nothing(self):
        self.assertEqual(self.run_command(lambda photo: True, "--dry-run"), [])
