from django.db import migrations


def delete_stale_gate_scores(apps, schema_editor):
    GateScore = apps.get_model("display", "GateScore")
    GateScore.objects.filter(gate_type__in=["hidden_gate", "known_time_gate"]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('display', '0167_merge_20260824_1548'),
    ]

    operations = [
        migrations.RunPython(delete_stale_gate_scores, migrations.RunPython.noop),
    ]
