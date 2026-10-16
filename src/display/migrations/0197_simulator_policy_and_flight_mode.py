from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('display', '0196_clientnotification'),
    ]

    operations = [
        migrations.AddField(
            model_name='contestant',
            name='blocked_positions_at',
            field=models.DateTimeField(blank=True, editable=False, help_text='When positions were first ignored because of the simulator policy or the flight mode (the positions themselves are not kept).', null=True),
        ),
        migrations.AddField(
            model_name='contestant',
            name='flight_mode',
            field=models.CharField(blank=True, choices=[('real', 'Real aircraft'), ('simulator', 'Flight simulator')], help_text="What the pilot declared when registering: a real aircraft or a flight simulator. Positions of the other kind are ignored. Empty for flights registered before this existed: then only the task's simulator policy decides.", max_length=20, null=True),
        ),
        migrations.AddField(
            model_name='navigationtask',
            name='simulator_policy',
            field=models.CharField(choices=[('not_allowed', 'Not allowed: simulator flights are ignored'), ('allowed', 'Allowed: simulator flights count, and are marked as simulator flights'), ('simulator_only', 'Simulator only: real flights (tracker or app) are ignored')], default='not_allowed', help_text='Whether flights flown in a flight simulator are accepted. Positions that the policy does not accept are ignored and never scored. Changes take effect within about a minute.', max_length=20),
        ),
        # Every existing task keeps ignoring simulator flights: AddField's default is "not_allowed".
    ]
