from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ("display", "0151_navigationtask_task_subtype_and_task_config"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CompiledNavigationTask",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("task_subtype", models.CharField(max_length=100)),
                ("compiled_payload", models.JSONField(default=dict)),
                ("source_signature", models.CharField(blank=True, default="", max_length=128)),
                ("compiled_at", models.DateTimeField(auto_now=True)),
                (
                    "compiled_family_route",
                    models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="display.route"),
                ),
                (
                    "navigation_task",
                    models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to="display.navigationtask"),
                ),
            ],
        ),
        migrations.CreateModel(
            name="ContestantTaskConfiguration",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("task_subtype", models.CharField(max_length=100)),
                ("declaration_payload", models.JSONField(default=dict)),
                ("compiled_effective_route_payload", models.JSONField(default=dict)),
                ("compiled_gate_times_payload", models.JSONField(default=dict)),
                ("validation_errors", models.JSONField(default=list)),
                ("is_valid", models.BooleanField(default=False)),
                ("is_locked", models.BooleanField(default=False)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "contestant",
                    models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to="display.contestant"),
                ),
                (
                    "updated_by",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL),
                ),
            ],
        ),
    ]
