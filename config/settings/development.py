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


# Safety guard: development tests must use their own database.
DEV_TEST_DATABASE_NAME = "test_delisky_bi_dev"
DATABASES["default"]["TEST"]["NAME"] = DEV_TEST_DATABASE_NAME


# DEV-only deterministic context cache; production retains uncached behavior.
ASK_DELISKY_CONTEXT_CACHE_ENABLED = True

# Measured cold local Ask inference: 126.277 s. Allow headroom without
# changing the shared/Marketing timeout. The Ask-specific environment key
# takes precedence in the provider factory and is available to future hosts.
ASK_DELISKY_REQUEST_TIMEOUT_SECONDS = 180
