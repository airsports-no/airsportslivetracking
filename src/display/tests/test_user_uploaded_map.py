from io import BytesIO
from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from display.models.user_uploaded_map import UserUploadedMap
from display.tasks import process_user_uploaded_map


def _make_instance(user, default_zoom=12) -> UserUploadedMap:
    return UserUploadedMap.objects.create(
        user=user,
        name="test-map",
        map_file=SimpleUploadedFile("test.mbtiles", b"fake mbtiles bytes"),
        default_zoom_level=default_zoom,
    )


class ProcessUserUploadedMapTaskTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create(email="taskuser@example.com")

    def test_missing_map_does_not_raise(self):
        process_user_uploaded_map(999999)

    def test_successful_processing_marks_ready(self):
        instance = _make_instance(self.user, default_zoom=12)

        fake_png = BytesIO(b"\x89PNG\r\n\x1a\nfake")

        with patch.object(UserUploadedMap, "create_thumbnail", return_value=(fake_png, 10, 14)):
            process_user_uploaded_map(instance.pk)

        instance.refresh_from_db()
        self.assertEqual(instance.processing_status, UserUploadedMap.PROCESSING_READY)
        self.assertEqual(instance.processing_error, "")
        self.assertEqual(instance.minimum_zoom_level, 10)
        self.assertEqual(instance.maximum_zoom_level, 14)
        self.assertEqual(instance.default_zoom_level, 12)
        self.assertTrue(instance.thumbnail)

    def test_default_zoom_is_clamped_when_outside_range(self):
        instance = _make_instance(self.user, default_zoom=18)
        fake_png = BytesIO(b"\x89PNGfake")

        with patch.object(UserUploadedMap, "create_thumbnail", return_value=(fake_png, 10, 14)):
            process_user_uploaded_map(instance.pk)

        instance.refresh_from_db()
        self.assertEqual(instance.processing_status, UserUploadedMap.PROCESSING_READY)
        self.assertEqual(instance.default_zoom_level, 14)

    def test_failure_marks_failed_with_error(self):
        instance = _make_instance(self.user)

        with patch.object(UserUploadedMap, "create_thumbnail", side_effect=RuntimeError("corrupt mbtiles")):
            process_user_uploaded_map(instance.pk)

        instance.refresh_from_db()
        self.assertEqual(instance.processing_status, UserUploadedMap.PROCESSING_FAILED)
        self.assertIn("corrupt mbtiles", instance.processing_error)


class GetLocalFilePathStreamingTests(TestCase):
    """
    The old implementation called `self.map_file.read()` which loaded the entire (up to 100MB) mbtiles into
    memory in a single gunicorn request worker. This test guards against that regression by asserting we
    use the chunked iterator instead.
    """

    def setUp(self):
        self.user = get_user_model().objects.create(email="streamuser@example.com")

    def test_uses_chunks_not_full_read(self):
        instance = _make_instance(self.user)

        from display.models import user_uploaded_map as module
        module.LOCAL_MAP_FILE_CACHE.pop(f"user_map_{instance.map_file.name}", None)

        with patch.object(instance.map_file, "chunks", wraps=instance.map_file.chunks) as chunks_mock, \
             patch.object(instance.map_file, "read", wraps=instance.map_file.read) as read_mock:
            path = instance.get_local_file_path()
            self.addCleanup(instance.clear_local_file_path)

        self.assertTrue(path)
        chunks_mock.assert_called_once()
        read_mock.assert_not_called()
