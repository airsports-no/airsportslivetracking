from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('display', '0161_user_entitlement_grant'),
    ]

    operations = [
        migrations.AddField(
            model_name='editableroute',
            name='updated_at',
            field=models.DateTimeField(auto_now=True, help_text="When this editable route's content was last saved.", null=True),
        ),
    ]
