from .base import *


DEBUG = True

ALLOWED_HOSTS = [
    "127.0.0.1",
    "localhost",
    "192.168.1.7",
]


# Safety guard: development must never use the production database.
DEV_DATABASE_NAME = "delisky_bi_dev"
configured_database_name = str(DATABASES["default"]["NAME"]).strip()

if configured_database_name != DEV_DATABASE_NAME:
    raise RuntimeError(
        "Unsafe development database configuration: "
        f"expected '{DEV_DATABASE_NAME}', got '{configured_database_name}'."
    )
