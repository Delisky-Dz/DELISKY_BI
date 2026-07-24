from django.db import migrations
from django.db.models import Q


SEQUENCE_NAME = "workforce_worker_code_seq"


def create_sequence_and_backfill(
    apps,
    schema_editor,
):
    connection = schema_editor.connection

    if connection.vendor != "postgresql":
        raise RuntimeError(
            "Worker code sequence requires PostgreSQL."
        )

    Worker = apps.get_model(
        "workforce",
        "Worker",
    )

    database_alias = connection.alias
    table_name = schema_editor.quote_name(
        Worker._meta.db_table
    )

    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            CREATE SEQUENCE IF NOT EXISTS
            {SEQUENCE_NAME}
            START WITH 1
            INCREMENT BY 1
            MINVALUE 1
            NO CYCLE
            """
        )

        cursor.execute(
            f"""
            SELECT COALESCE(
                MAX(
                    CAST(
                        SUBSTRING(
                            employee_code
                            FROM '^DW-([0-9]+)$'
                        )
                        AS BIGINT
                    )
                ),
                0
            )
            FROM {table_name}
            WHERE employee_code
                ~ '^DW-[0-9]+$'
            """
        )

        maximum_code = (
            cursor.fetchone()[0] or 0
        )

        if maximum_code:
            cursor.execute(
                f"""
                SELECT setval(
                    '{SEQUENCE_NAME}',
                    %s,
                    true
                )
                """,
                [maximum_code],
            )
        else:
            cursor.execute(
                f"""
                SELECT setval(
                    '{SEQUENCE_NAME}',
                    1,
                    false
                )
                """
            )

        worker_ids = list(
            Worker.objects.using(
                database_alias
            )
            .filter(
                Q(employee_code__isnull=True)
                | Q(employee_code="")
            )
            .order_by("pk")
            .values_list(
                "pk",
                flat=True,
            )
        )

        for worker_id in worker_ids:
            cursor.execute(
                f"""
                SELECT nextval(
                    '{SEQUENCE_NAME}'
                )
                """
            )

            sequence_value = (
                cursor.fetchone()[0]
            )

            generated_code = (
                f"DW-{sequence_value:05d}"
            )

            Worker.objects.using(
                database_alias
            ).filter(
                pk=worker_id
            ).update(
                employee_code=generated_code
            )


def remove_sequence(
    apps,
    schema_editor,
):
    if (
        schema_editor.connection.vendor
        == "postgresql"
    ):
        with (
            schema_editor.connection.cursor()
            as cursor
        ):
            cursor.execute(
                f"""
                DROP SEQUENCE IF EXISTS
                {SEQUENCE_NAME}
                """
            )


class Migration(migrations.Migration):
    dependencies = [
        (
            "workforce",
            "0001_initial",
        ),
    ]

    operations = [
        migrations.RunPython(
            create_sequence_and_backfill,
            remove_sequence,
        ),
    ]
