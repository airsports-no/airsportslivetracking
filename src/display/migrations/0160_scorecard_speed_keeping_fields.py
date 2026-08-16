from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('display', '0159_photo_decoy_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='scorecard',
            name='speed_keeping_penalty_per_kt',
            field=models.FloatField(default=1, help_text='Penalty per knot of speed deviation beyond the tolerance on a known-circuit leg'),
        ),
        migrations.AddField(
            model_name='scorecard',
            name='speed_keeping_tolerance_kt',
            field=models.FloatField(default=5, help_text='Allowed deviation (in knots) from the declared speed on a known-circuit leg before a speed-keeping penalty applies'),
        ),
    ]
