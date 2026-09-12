from django.db import migrations, models
from django.db.models import Count


def _dedupe_by_field(apps, model_name, field_name):
    """
    Merge rows that share the same `field_name` value, keeping the earliest (lowest pk) row and
    repointing every foreign key that referenced a duplicate onto the kept row before deleting the
    duplicate. Matches the exact-string-equality uniqueness already enforced (racily, without a DB
    constraint) by Aeroplane.validate()/Club.validate() via their pre_save signals - see
    display.signals.validate_aeroplane/validate_club.

    Uses Model._meta.related_objects (as of this migration's historical model state) to discover
    every referencing relation generically, rather than hand-listing them - this is what protects
    against silently orphaning or cascade-deleting rows in an FK relation added after this
    migration was written but before it runs (e.g. Team.aeroplane/Team.club, plus
    ClubManagerMembership.club, AccessGrant.club, and Contest.organizing_club for Club, some of
    which CASCADE and would otherwise destroy those rows outright on a plain delete).
    """
    Model = apps.get_model("display", model_name)

    duplicate_values = list(Model.objects.values(field_name).annotate(n=Count("id")).filter(n__gt=1))
    if not duplicate_values:
        return

    print(f"\n  Found {len(duplicate_values)} duplicate {model_name}.{field_name} value(s) to merge.")

    for group in duplicate_values:
        value = group[field_name]
        matching = Model.objects.filter(**{field_name: value}).order_by("pk")
        keep = matching.first()
        extras = list(matching.exclude(pk=keep.pk))
        if not extras:
            continue
        print(
            f"  {model_name}.{field_name}={value!r}: merging {len(extras)} duplicate(s) "
            f"(pks={[extra.pk for extra in extras]}) into pk={keep.pk}"
        )
        for extra in extras:
            for related in Model._meta.related_objects:
                related_model = related.related_model
                fk_field_name = related.field.name
                related_model.objects.filter(**{fk_field_name: extra.pk}).update(**{fk_field_name: keep.pk})
            extra.delete()


def dedupe_aeroplanes_and_clubs(apps, schema_editor):
    _dedupe_by_field(apps, "Aeroplane", "registration")
    _dedupe_by_field(apps, "Club", "name")


def noop_reverse(apps, schema_editor):
    # Merged duplicate rows are not reconstructible - intentionally one-directional, matching
    # 0169_dedupe_playingcard_and_idempotency_constraint.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("display", "0177_navigationtask_display_navi_is_publ_4d1ba7_idx_and_more"),
    ]

    operations = [
        migrations.RunPython(dedupe_aeroplanes_and_clubs, noop_reverse),
        migrations.AlterField(
            model_name="aeroplane",
            name="registration",
            field=models.CharField(max_length=20, unique=True),
        ),
        migrations.AlterField(
            model_name="club",
            name="name",
            field=models.CharField(max_length=200, unique=True),
        ),
    ]
