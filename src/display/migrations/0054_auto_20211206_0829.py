# Generated by Django 3.2.9 on 2021-12-06 08:29

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('display', '0053_auto_20211126_1123'),
    ]

    operations = [
        migrations.AddField(
            model_name='contestantreceivedposition',
            name='calculator_received_time',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='contestantreceivedposition',
            name='processor_received_time',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='contestantreceivedposition',
            name='server_time',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='contestantreceivedposition',
            name='websocket_transmitted_time',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='navigationtask',
            name='scorecard',
            field=models.ForeignKey(help_text='Reference to an existing scorecard name. Currently existing scorecards: <function NavigationTask.<lambda> at 0x7fe7d8266280>', on_delete=django.db.models.deletion.PROTECT, to='display.scorecard'),
        ),
    ]
