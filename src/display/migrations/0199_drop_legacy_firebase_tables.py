from django.db import migrations


class Migration(migrations.Migration):
    """
    The drf_firebase_auth package was removed (see display/authentication.py) but its two tables stayed behind, with a
    database-level foreign key to the user that made deleting any user fail. Nothing reads them. IF EXISTS, so that a
    database that never had them (a fresh one) is fine.
    """

    dependencies = [
        ("display", "0198_remove_person_is_public_last_seen"),
    ]

    operations = [
        migrations.RunSQL(
            sql=[
                "DROP TABLE IF EXISTS drf_firebase_auth_firebaseuserprovider",
                "DROP TABLE IF EXISTS drf_firebase_auth_firebaseuser",
            ],
            # The data is gone for good; nothing needs the tables back
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
