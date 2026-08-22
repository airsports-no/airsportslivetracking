from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("display", "0142_flightorderconfiguration_map_include_openaip_overlay"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="contest",
            name="created_by",
            field=models.ForeignKey(blank=True, null=True, on_delete=models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name="contest",
            name="organizing_club",
            field=models.ForeignKey(blank=True, null=True, on_delete=models.deletion.SET_NULL, to="display.club"),
        ),
        migrations.CreateModel(
            name="ClubManagerMembership",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("role", models.CharField(choices=[("owner", "Owner"), ("manager", "Manager")], default="manager", max_length=20)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("club", models.ForeignKey(on_delete=models.deletion.CASCADE, to="display.club")),
                ("user", models.ForeignKey(on_delete=models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={"unique_together": {("club", "user")}},
        ),
        migrations.CreateModel(
            name="AccessGrant",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("tier", models.CharField(choices=[("free", "Free"), ("single_event", "Single event"), ("annual_club_pass", "Annual club pass"), ("manual_override", "Manual override")], max_length=40)),
                ("status", models.CharField(choices=[("draft", "Draft"), ("active", "Active"), ("expired", "Expired"), ("cancelled", "Cancelled")], default="draft", max_length=20)),
                ("starts_at", models.DateTimeField(blank=True, null=True)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("contestant_limit", models.IntegerField(blank=True, null=True)),
                ("task_limit", models.IntegerField(blank=True, null=True)),
                ("notes", models.TextField(blank=True, default="")),
                ("invoice_reference", models.CharField(blank=True, default="", max_length=200)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("club", models.ForeignKey(blank=True, null=True, on_delete=models.deletion.CASCADE, to="display.club")),
                ("contest", models.ForeignKey(blank=True, null=True, on_delete=models.deletion.CASCADE, to="display.contest")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=models.deletion.SET_NULL, related_name="created_access_grants", to=settings.AUTH_USER_MODEL)),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=models.deletion.SET_NULL, related_name="updated_access_grants", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("-created_at",)},
        ),
    ]