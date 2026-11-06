import logging

from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand

from display.models import Photo

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Generates the satellite pictures of the route photos again. They used to have the photo's name printed on "
        "them, which could give away the order of the route; the pictures are made without it now, but the ones "
        "already stored keep the name. The organisers' own uploaded pictures are not touched, and a picture that cannot "
        "be generated again (no satellite imagery) is left as it was."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--navigation-task",
            type=int,
            action="append",
            dest="navigation_task_ids",
            help="Only the photos of this navigation task. Repeat for more.",
        )
        parser.add_argument(
            "--dry-run", action="store_true", help="Only list the photos that would be generated again."
        )
        parser.add_argument("--limit", type=int, default=None, help="At most this many photos.")

    def handle(self, *args, **options):
        photos = Photo.objects.filter(uploaded=False).exclude(file="").exclude(file=None).order_by("pk")
        if options["navigation_task_ids"]:
            photos = photos.filter(route__navigationtask__pk__in=options["navigation_task_ids"])
        if options["limit"]:
            photos = photos[: options["limit"]]
        done = failed = 0
        for photo in photos.select_related("route"):
            if options["dry_run"]:
                self.stdout.write(f"Would generate photo {photo.pk} ({photo.name}) again")
                continue
            old_name = photo.file.name
            try:
                # It logs and gives up when there is no imagery: the old picture is still the photo's then
                generated = photo.generate_image(force=True)
            except Exception:
                logger.exception(f"Could not generate photo {photo.pk} again")
                generated = False
            if not generated:
                failed += 1
                self.stderr.write(f"Photo {photo.pk} ({photo.name}) could not be generated again, kept as it was")
                continue
            # Storage that does not overwrite gives the new picture a name of its own
            if photo.file.name != old_name:
                default_storage.delete(old_name)
            done += 1
            self.stdout.write(f"Generated photo {photo.pk} ({photo.name}) again")
        self.stdout.write(self.style.SUCCESS(f"{done} generated again, {failed} kept as they were"))
