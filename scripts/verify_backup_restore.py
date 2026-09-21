import argparse
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import psycopg
from psycopg import sql


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Restore a DELISKY PostgreSQL custom-format backup into a "
            "temporary database, verify core schema metadata, then remove it."
        )
    )
    parser.add_argument(
        "--backup",
        required=True,
        help="Path to the .dump archive to verify.",
    )
    parser.add_argument(
        "--settings",
        default="config.settings.production",
        help="Django settings module used to obtain PostgreSQL credentials.",
    )
    parser.add_argument(
        "--expected-source-database",
        required=True,
        help=(
            "Exact database name expected both from Django settings and "
            "from the archive header."
        ),
    )
    parser.add_argument(
        "--pg-restore",
        default=r"C:\Program Files\PostgreSQL\18\bin\pg_restore.exe",
        help="Path to pg_restore.",
    )
    return parser.parse_args()


def archive_database_name(pg_restore, backup_path):
    result = subprocess.run(
        [
            str(pg_restore),
            "--list",
            str(backup_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    match = re.search(
        r"^;\s+dbname:\s*(.+?)\s*$",
        result.stdout,
        flags=re.MULTILINE,
    )

    if match is None:
        raise RuntimeError(
            "Unable to read source database name from archive header."
        )

    return match.group(1).strip()


def safe_restore_database_name(expected_database):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    name = (
        f"{expected_database}_restore_verify_"
        f"{timestamp}_{os.getpid()}"
    )

    if len(name) > 63:
        raise RuntimeError(
            "Generated restore verification database name is too long."
        )

    required_prefix = f"{expected_database}_restore_verify_"

    if name == expected_database or not name.startswith(required_prefix):
        raise RuntimeError("Unsafe restore verification database name.")

    return name


def connection_params(database):
    return {
        "host": str(database.get("HOST") or "127.0.0.1"),
        "port": str(database.get("PORT") or "5432"),
        "user": str(database.get("USER") or ""),
        "password": str(database.get("PASSWORD") or ""),
    }


def drop_database(admin_connection, database_name):
    with admin_connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT pg_terminate_backend(pid)
            FROM pg_stat_activity
            WHERE datname = %s
              AND pid <> pg_backend_pid()
            """,
            (database_name,),
        )
        cursor.execute(
            sql.SQL("DROP DATABASE IF EXISTS {}").format(
                sql.Identifier(database_name)
            )
        )


def main():
    args = parse_args()

    backup_path = Path(args.backup).resolve()
    pg_restore = Path(args.pg_restore).resolve()
    expected_database = args.expected_source_database.strip()

    if not expected_database:
        raise RuntimeError("Expected source database name is empty.")

    if not backup_path.is_file():
        raise FileNotFoundError(
            f"Backup archive not found: {backup_path}"
        )

    if backup_path.stat().st_size <= 0:
        raise RuntimeError("Backup archive is empty.")

    if not pg_restore.is_file():
        raise FileNotFoundError(
            f"pg_restore not found: {pg_restore}"
        )

    os.environ["DJANGO_SETTINGS_MODULE"] = args.settings

    import django

    django.setup()

    from django.conf import settings

    database = settings.DATABASES["default"]
    configured_database = str(
        database.get("NAME") or ""
    ).strip()

    if configured_database != expected_database:
        raise RuntimeError(
            "Unsafe restore settings database: "
            f"expected '{expected_database}', "
            f"got '{configured_database}'."
        )

    archive_database = archive_database_name(
        pg_restore,
        backup_path,
    )

    if archive_database != expected_database:
        raise RuntimeError(
            "Unsafe restore archive database: "
            f"expected '{expected_database}', "
            f"got '{archive_database}'."
        )

    params = connection_params(database)

    if not params["user"]:
        raise RuntimeError("Database USER is empty.")

    restore_database = safe_restore_database_name(
        expected_database
    )

    print(f"SETTINGS_DATABASE={configured_database}")
    print(f"ARCHIVE_DATABASE={archive_database}")
    print(f"RESTORE_DATABASE={restore_database}")
    print(f"BACKUP_ARCHIVE={backup_path}")

    admin = psycopg.connect(
        dbname="postgres",
        **params,
    )
    admin.autocommit = True

    created = False

    try:
        drop_database(
            admin,
            restore_database,
        )

        with admin.cursor() as cursor:
            cursor.execute(
                sql.SQL("CREATE DATABASE {}").format(
                    sql.Identifier(restore_database)
                )
            )

        created = True

        env = os.environ.copy()
        env["PGPASSWORD"] = params["password"]

        restore_command = [
            str(pg_restore),
            "--host",
            params["host"],
            "--port",
            params["port"],
            "--username",
            params["user"],
            "--dbname",
            restore_database,
            "--no-owner",
            "--no-acl",
            str(backup_path),
        ]

        restore_result = subprocess.run(
            restore_command,
            env=env,
        )

        print(
            "PG_RESTORE_EXIT="
            f"{restore_result.returncode}"
        )

        if restore_result.returncode != 0:
            raise RuntimeError(
                "Backup restore command failed."
            )

        restored = psycopg.connect(
            dbname=restore_database,
            **params,
        )

        try:
            with restored.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT COUNT(*)
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                      AND table_type = 'BASE TABLE'
                    """
                )
                public_tables = cursor.fetchone()[0]

                cursor.execute(
                    "SELECT COUNT(*) FROM django_migrations"
                )
                migration_count = cursor.fetchone()[0]

                cursor.execute(
                    """
                    SELECT extname
                    FROM pg_extension
                    ORDER BY extname
                    """
                )
                extensions = [
                    row[0]
                    for row in cursor.fetchall()
                ]
        finally:
            restored.close()

        if public_tables <= 0:
            raise RuntimeError(
                "Restored database has no public base tables."
            )

        if migration_count <= 0:
            raise RuntimeError(
                "Restored database has no Django migrations."
            )

        print(f"PUBLIC_TABLES={public_tables}")
        print(
            "DJANGO_MIGRATIONS="
            f"{migration_count}"
        )
        print(
            "EXTENSIONS="
            f"{','.join(extensions)}"
        )
        print("RESTORE_TEST_RESULT=PASS")
    finally:
        if created:
            drop_database(
                admin,
                restore_database,
            )
            print(
                "RESTORE_TEST_DATABASE_REMOVED=True"
            )

        admin.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(
            f"RESTORE_TEST_ERROR={exc}",
            file=sys.stderr,
        )
        sys.exit(1)
