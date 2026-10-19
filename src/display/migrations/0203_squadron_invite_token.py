from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("display", "0202_squadrons"),
    ]

    operations = [
        migrations.AddField(
            model_name="squadron",
            name="invite_token",
            field=models.CharField(
                blank=True,
                help_text="Anybody logged in who opens the squadron's invite link with this token can join as a member. Empty: the link is off.",
                max_length=64,
                null=True,
                unique=True,
            ),
        ),
    ]
