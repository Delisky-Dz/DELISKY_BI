import uuid

from django.db import migrations, models


# All database relations read by the manager insights/context path. Keep this
# list in sync if that path gains a new data source. Authentication/audit/rate
# limit writes deliberately do not invalidate deterministic analytics.
SOURCE_TABLES = (
    "imports_distributionbrand",
    "imports_importbatch",
    "imports_importrow",
    "fleet_truck",
    "fleet_truckcrewassignment",
    "workforce_worker",
)


def install_revision_triggers(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute("""
        CREATE FUNCTION assistant_bump_context_revision() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            INSERT INTO assistant_askdeliskydatarevision (id, token)
            VALUES (1, gen_random_uuid())
            ON CONFLICT (id) DO UPDATE SET token = EXCLUDED.token;
            RETURN NULL;
        END;
        $$;
    """)
    for table in SOURCE_TABLES:
        schema_editor.execute(f"""
            CREATE TRIGGER ask_delisky_context_changed
            AFTER INSERT OR UPDATE OR DELETE OR TRUNCATE
            ON {schema_editor.quote_name(table)}
            FOR EACH STATEMENT
            EXECUTE FUNCTION assistant_bump_context_revision();
        """)


def remove_revision_triggers(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    for table in SOURCE_TABLES:
        schema_editor.execute(
            "DROP TRIGGER IF EXISTS ask_delisky_context_changed ON "
            + schema_editor.quote_name(table)
        )
    schema_editor.execute("DROP FUNCTION IF EXISTS assistant_bump_context_revision()")


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
        migrations.RunPython(install_revision_triggers, remove_revision_triggers),
    ]
