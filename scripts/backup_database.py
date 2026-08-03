import argparse
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

backup_settings_module = os.environ.get(
    "DELISKY_BACKUP_DJANGO_SETTINGS",
    "config.settings.development",
)

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    backup_settings_module,
)

import django

django.setup()

from django.conf import settings


def main():
    parser = argparse.ArgumentParser(
        description="Create a PostgreSQL backup for DELISKY BI."
    )

    parser.add_argument(
        "--output",
        required=True,
        help="Destination .dump file.",
    )

    parser.add_argument(
        "--pg-dump",
        required=True,
        help="Full path to pg_dump.exe.",
    )

    args = parser.parse_args()

    database = settings.DATABASES["default"]

    database_name = str(database.get("NAME") or "")
    database_user = str(database.get("USER") or "")
    database_password = str(database.get("PASSWORD") or "")
    database_host = str(database.get("HOST") or "127.0.0.1")
    database_port = str(database.get("PORT") or "5432")

    if not database_name:
        raise RuntimeError("Database NAME is empty.")

    if not database_user:
        raise RuntimeError("Database USER is empty.")

    if not os.path.isfile(args.pg_dump):
        raise FileNotFoundError(
            f"pg_dump not found: {args.pg_dump}"
        )

    output_path = Path(args.output).resolve()
    partial_path = output_path.with_name(
        f"{output_path.name}.partial"
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if output_path.exists():
        raise RuntimeError(
            f"Refusing to overwrite existing backup: {output_path}"
        )

    partial_path.unlink(missing_ok=True)

    env = os.environ.copy()
    env["PGPASSWORD"] = database_password

    command = [
        args.pg_dump,
        "--host",
        database_host,
        "--port",
        database_port,
        "--username",
        database_user,
        "--dbname",
        database_name,
        "--format=custom",
        "--no-password",
        "--no-owner",
        "--no-acl",
        "--file",
        str(partial_path),
    ]

    try:
        subprocess.run(
            command,
            env=env,
            check=True,
        )

        if not partial_path.is_file():
            raise RuntimeError(
                "pg_dump completed but backup file was not created."
            )

        if partial_path.stat().st_size <= 0:
            raise RuntimeError(
                "Backup file was created but is empty."
            )

        os.replace(
            partial_path,
            output_path,
        )
    except Exception:
        partial_path.unlink(missing_ok=True)
        raise

    print(f"BACKUP_CREATED={output_path}")
    print(f"BACKUP_SIZE={output_path.stat().st_size}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(
            f"BACKUP_DATABASE_ERROR={exc}",
            file=sys.stderr,
        )
        sys.exit(1)
