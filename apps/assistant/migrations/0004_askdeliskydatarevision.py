import uuid

from django.db import migrations, models


# Schema only. Optional revision triggers are explicitly provisioned.
class Migration(migrations.Migration):
    dependencies = [
        ("assistant", "0003_askdeliskyauditevent_scope"),
        ("imports", "0011_remove_importbatch_import_approved_opening_month_uniq_and_more"),
        ("fleet", "0006_add_truck_crew_assignment"),
        ("workforce", "0009_remove_legacy_capability_flags"),
    ]
    operations = [
        migrations.CreateModel(
            name="AskDeliskyDataRevision",
            fields=[
                ("id", models.PositiveSmallIntegerField(default=1, editable=False, primary_key=True, serialize=False)),
                ("token", models.UUIDField(default=uuid.uuid4, editable=False)),
            ],
        ),
    ]
