from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("display", "0199_drop_legacy_firebase_tables"),
    ]

    operations = [
        migrations.AddField(
            model_name="contestant",
            name="mock_positions_at",
            field=models.DateTimeField(
                blank=True,
                editable=False,
                help_text="When the phone app first sent a position that the phone itself reported as simulated (a fake-GPS app). The "
                "positions are used as usual; organizers see a warning.",
                null=True,
            ),
        ),
    ]
