from django.db import migrations

TABLE = "display_flightsummary"


def to_utf8mb4(apps, schema_editor):
    # The summaries are full of emojis, which need four bytes. The production database's default character set is the
    # three-byte utf8 of old, which new tables inherit, so saving a summary failed ("Incorrect string value").
    if schema_editor.connection.vendor != "mysql":
        return
    schema_editor.execute(f"ALTER TABLE {TABLE} CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")


class Migration(migrations.Migration):
    # MySQL cannot run DDL inside a transaction
    atomic = False

    dependencies = [
        ("display", "0213_flightsummary_style"),
    ]

    operations = [
        migrations.RunPython(to_utf8mb4, migrations.RunPython.noop),
    ]
