"""Explicitly provisioned context revision tracking, not a migration default."""

from django.db import connection, transaction

from .models import AskDeliskyDataRevision


SOURCE_TABLES = (
    "imports_distributionbrand", "imports_importbatch", "imports_importrow",
    "fleet_truck", "fleet_truckcrewassignment", "workforce_worker",
)
TRIGGER_NAME = "ask_delisky_context_changed"
FUNCTION_NAME = "assistant_bump_context_revision"


def tracking_installed():
    """Verify every source on each revision read; missing tracking fails closed."""
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT c.relname FROM pg_trigger t
            JOIN pg_class c ON c.oid = t.tgrelid
            JOIN pg_proc p ON p.oid = t.tgfoid
            WHERE t.tgname = %s AND p.proname = %s
              AND t.tgenabled IN ('O', 'A') AND t.tgtype = 60
              AND pg_table_is_visible(c.oid)
              AND current_setting('session_replication_role') = 'origin'
        """, [TRIGGER_NAME, FUNCTION_NAME])
        return {row[0] for row in cursor.fetchall()} == set(SOURCE_TABLES)


def configure_tracking(*, enabled):
    """Atomic operator action; rotate the token even after untracked edits.

    Source table locks close the installation gap. This is never invoked by
    application startup, migrations or ordinary requests.
    """
    with transaction.atomic(), connection.cursor() as cursor:
        tables = ", ".join(connection.ops.quote_name(t) for t in SOURCE_TABLES)
        cursor.execute(f"LOCK TABLE {tables} IN SHARE ROW EXCLUSIVE MODE")
        for table in SOURCE_TABLES:
            cursor.execute(
                f'DROP TRIGGER IF EXISTS {TRIGGER_NAME} ON '
                + connection.ops.quote_name(table)
            )
        cursor.execute(f"DROP FUNCTION IF EXISTS {FUNCTION_NAME}()")
        if enabled:
            cursor.execute(f"""
                CREATE FUNCTION {FUNCTION_NAME}() RETURNS trigger
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
                cursor.execute(f"""
                    CREATE TRIGGER {TRIGGER_NAME}
                    AFTER INSERT OR UPDATE OR DELETE OR TRUNCATE
                    ON {connection.ops.quote_name(table)} FOR EACH STATEMENT
                    EXECUTE FUNCTION {FUNCTION_NAME}();
                """)
        import uuid
        AskDeliskyDataRevision.objects.update_or_create(
            pk=1, defaults={"token": uuid.uuid4()},
        )
