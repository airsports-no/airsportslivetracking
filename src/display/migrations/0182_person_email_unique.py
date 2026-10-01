from django.db import migrations, models
from django.db.models import Count


def dedupe_person_emails(apps, schema_editor):
    """
    Person.email had no DB-level uniqueness constraint, so a get_or_create race could leave two
    Person rows sharing an email (see Sentry PYTHON-DJANGO-1Q). For each duplicated, non-blank
    email, keep the oldest row and repoint any Crew/ContestUsageLedger references to it before
    deleting the rest, so the AlterField below can add the constraint safely.

    Blank emails are left alone: unlike a real address, a shared blank email doesn't mean two
    Person rows are the same physical person, so merging them could wrongly conflate two
    unrelated people.
    """
    Person = apps.get_model("display", "Person")
    Crew = apps.get_model("display", "Crew")
    ContestUsageLedger = apps.get_model("display", "ContestUsageLedger")

    duplicate_emails = (
        Person.objects.exclude(email="")
        .values("email")
        .annotate(total=Count("id"))
        .filter(total__gt=1)
        .values_list("email", flat=True)
    )
    for email in duplicate_emails:
        survivor, *duplicates = Person.objects.filter(email=email).order_by("pk")
        for duplicate in duplicates:
            Crew.objects.filter(member1=duplicate).update(member1=survivor)
            Crew.objects.filter(member2=duplicate).update(member2=survivor)
            for ledger in ContestUsageLedger.objects.filter(pilot=duplicate):
                # Mirrors ContestUsageLedger's unique_contest_pilot_started_usage /
                # unique_task_pilot_started_usage conditional constraints. Those use a Q()
                # condition, which MySQL (this project's production database) does not support
                # on unique constraints - Django silently skips creating them there - so this
                # can't rely on catching an IntegrityError and must check for the conflict itself.
                if ledger.kind == "contest_pilot_started":
                    conflict = ContestUsageLedger.objects.filter(
                        contest_id=ledger.contest_id, pilot=survivor, kind=ledger.kind
                    ).exists()
                elif ledger.kind == "task_pilot_started":
                    conflict = ContestUsageLedger.objects.filter(
                        contest_id=ledger.contest_id,
                        navigation_task_id=ledger.navigation_task_id,
                        pilot=survivor,
                        kind=ledger.kind,
                    ).exists()
                else:
                    conflict = False
                if conflict:
                    # Survivor already has a ledger row for the same usage event - the
                    # duplicate's row is then just a redundant record of it.
                    ledger.delete()
                else:
                    ledger.pilot = survivor
                    ledger.save(update_fields=["pilot"])
            duplicate.delete()


class Migration(migrations.Migration):
    dependencies = [
        ("display", "0181_merge_20260917_1701"),
    ]

    operations = [
        migrations.RunPython(dedupe_person_emails, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="person",
            name="email",
            field=models.EmailField(max_length=254, unique=True),
        ),
    ]
