# Generated by Django 4.1.7 on 2023-07-18 12:25

from django.db import migrations


def update_location(apps, schema_editor):
    db_alias = schema_editor.connection.alias
    Contest = apps.get_model("display", "Contest")
    for contest in Contest.objects.all():
        contest.location = f"{contest.latitude}, {contest.longitude}"
        contest.save()


class Migration(migrations.Migration):
    dependencies = [
        ("display", "0102_contest_location"),
    ]

    operations = [
        migrations.RunPython(update_location),
    ]
