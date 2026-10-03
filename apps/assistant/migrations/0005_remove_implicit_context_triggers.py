from django.db import migrations


# Frozen cleanup for databases that applied the original pre-release 0004.
# Fresh databases now create only the idle revision table in 0004. Optional
# triggers belong to an explicit operator command, never migration settings.
SOURCE_TABLES = (
    "imports_distributionbrand", "imports_importbatch", "imports_importrow",
    "fleet_truck", "fleet_truckcrewassignment", "workforce_worker",
)


def remove_implicit_tracking(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    for table in SOURCE_TABLES:
        schema_editor.execute(
            "DROP TRIGGER IF EXISTS ask_delisky_context_changed ON "
            + schema_editor.quote_name(table)
        )
    schema_editor.execute("DROP FUNCTION IF EXISTS assistant_bump_context_revision()")


class Migration(migrations.Migration):
    dependencies = [("assistant", "0004_askdeliskydatarevision")]
    # Reversal also cleans up explicit tracking before 0004 can drop its table.
    operations = [
        migrations.RunPython(remove_implicit_tracking, remove_implicit_tracking),
    ]
