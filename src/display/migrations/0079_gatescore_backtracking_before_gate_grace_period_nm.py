# Generated by Django 3.2.12 on 2022-02-14 07:00

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('display', '0078_auto_20220213_1028'),
    ]

    operations = [
        migrations.AddField(
            model_name='gatescore',
            name='backtracking_before_gate_grace_period_nm',
            field=models.FloatField(default=0),
        ),
    ]
