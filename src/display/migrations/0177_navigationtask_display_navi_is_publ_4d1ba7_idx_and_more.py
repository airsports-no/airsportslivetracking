# Generated manually (see commit message): adds composite indexes on
# (is_public, is_featured) for Contest and NavigationTask, which had no index
# on either boolean field despite being the filter driving a query called
# ~475,000 times (Cloud SQL Query Insights), scanning ~3100 rows to return 1.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("display", "0176_merge_20260905_0655"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="navigationtask",
            index=models.Index(fields=["is_public", "is_featured"], name="display_navi_is_publ_4d1ba7_idx"),
        ),
        migrations.AddIndex(
            model_name="contest",
            index=models.Index(fields=["is_public", "is_featured"], name="display_cont_is_publ_9a3f2e_idx"),
        ),
    ]
