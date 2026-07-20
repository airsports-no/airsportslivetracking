# Generated manually for historical usage accounting
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('display', '0144_tokentype_alter_accessgrant_tier_usertokengrant_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='ContestUsageLedger',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('kind', models.CharField(choices=[('contestant_started', 'Contestant started'), ('task_started', 'Task started')], max_length=40)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('contest', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='display.contest')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('contestant', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='display.contestant')),
                ('navigation_task', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='display.navigationtask')),
            ],
            options={
                'ordering': ('-created_at',),
            },
        ),
        migrations.AddConstraint(
            model_name='contestusageledger',
            constraint=models.UniqueConstraint(condition=models.Q(kind='contestant_started'), fields=('contest', 'contestant', 'kind'), name='unique_contestant_started_usage'),
        ),
        migrations.AddConstraint(
            model_name='contestusageledger',
            constraint=models.UniqueConstraint(condition=models.Q(kind='task_started'), fields=('contest', 'navigation_task', 'kind'), name='unique_task_started_usage'),
        ),
    ]
