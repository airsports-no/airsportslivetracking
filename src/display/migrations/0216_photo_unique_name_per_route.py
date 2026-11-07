from django.db import migrations, models
from django.db.models import Count


def choose_photo_to_keep(photos):
    """The copy that stays: a real photo before a decoy, the organiser's own upload, one that has a picture, the oldest."""
    return min(photos, key=lambda photo: (photo.is_decoy, not photo.uploaded, not photo.file, photo.pk))


def merge_duplicate_photos(apps, schema_editor):
    """
    A route could get two photos of one name when two requests for its photos came at once (the photos are made when they
    are first asked for, which takes long for a route with many), and the next request then failed for good ("returned more
    than one Photo"). The registrations of observations are moved to the copy that stays before the others are removed:
    they are cleared when their photo is deleted.
    """
    Photo = apps.get_model("display", "Photo")
    PhotoObservation = apps.get_model("display", "PhotoObservation")
    groups = Photo.objects.values("route_id", "name").annotate(copies=Count("id")).filter(copies__gt=1)
    for group in list(groups):
        photos = list(Photo.objects.filter(route_id=group["route_id"], name=group["name"]))
        keep = choose_photo_to_keep(photos)
        others = [photo for photo in photos if photo.pk != keep.pk]
        PhotoObservation.objects.filter(photo__in=others).update(photo=keep)
        Photo.objects.filter(pk__in=[photo.pk for photo in others]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("display", "0215_flightorderconfiguration_randomize_observation_photos"),
    ]

    operations = [
        migrations.RunPython(merge_duplicate_photos, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="photo",
            constraint=models.UniqueConstraint(fields=("route", "name"), name="display_photo_unique_name_per_route"),
        ),
    ]
