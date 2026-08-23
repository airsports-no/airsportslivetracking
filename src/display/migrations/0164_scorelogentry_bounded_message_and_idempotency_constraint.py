from django.db import migrations, models


class Migration(migrations.Migration):
    # NOTE: `makemigrations` also detects a large amount of unrelated
    # pre-existing model/migration drift across other apps (help_text
    # additions etc. that were never captured in a migration). That drift
    # predates this change and is deliberately not included here - this
    # migration only touches ScoreLogEntry.

    dependencies = [
        ("display", "0163_dedupe_scorelogentry_and_correct_totals"),
    ]

    operations = [
        migrations.AlterField(
            model_name="scorelogentry",
            name="message",
            field=models.CharField(default="", max_length=255),
        ),
        migrations.AlterUniqueTogether(
            name="scorelogentry",
            unique_together={("contestant", "time", "gate", "message", "points", "planned", "actual", "type")},
        ),
    ]
