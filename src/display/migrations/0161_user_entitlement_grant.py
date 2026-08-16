import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('display', '0160_scorecard_speed_keeping_fields'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name='accessgrant',
            name='tier',
            field=models.CharField(choices=[('single_event', 'Single event'), ('annual_club_pass', 'Annual club pass')], help_text='Type of access entitlement. Always derived automatically from whether club or contest is set (see derive_tier()) - not directly editable in practice.', max_length=40),
        ),
        migrations.CreateModel(
            name='UserEntitlementGrant',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('kind', models.CharField(choices=[('task_type_group', 'Task-type group')], default='task_type_group', help_text="What kind of thing is being granted; determines how 'value' is interpreted.", max_length=40)),
                ('value', models.CharField(help_text="The kind-specific payload, e.g. a task-type group string such as 'cima' or 'cima:circle' for a task_type_group grant.", max_length=200)),
                ('expires_at', models.DateTimeField(blank=True, help_text='Optional expiry time after which this grant no longer applies. Leave empty for no automatic expiry.', null=True)),
                ('is_active', models.BooleanField(default=True, help_text='If false, this grant is ignored regardless of expiry.')),
                ('notes', models.TextField(blank=True, default='', help_text='Internal notes about why this grant was made.')),
                ('created_at', models.DateTimeField(auto_now_add=True, help_text='When this grant was created.')),
                ('updated_at', models.DateTimeField(auto_now=True, help_text='When this grant was last updated.')),
                ('granted_by', models.ForeignKey(blank=True, help_text='Backend user who created this grant.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='granted_user_entitlement_grants', to=settings.AUTH_USER_MODEL)),
                ('user', models.ForeignKey(help_text='User this entitlement is granted to.', on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ('-created_at',),
                'unique_together': {('user', 'kind', 'value')},
            },
        ),
    ]
