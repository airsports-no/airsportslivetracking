from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("display", "0194_simulatorquickstart_registration_defaults"),
    ]

    operations = [
        migrations.AlterField(
            model_name="mobileappactivity",
            name="platform",
            field=models.CharField(
                choices=[("android", "Android"), ("ios", "iOS"), ("msfs", "MSFS client")], max_length=10
            ),
        ),
        migrations.AlterField(
            model_name="mobileappactivity",
            name="app_build",
            field=models.CharField(
                blank=True, default="", help_text="Android versionCode / iOS build number / MSFS client build.", max_length=20
            ),
        ),
    ]
