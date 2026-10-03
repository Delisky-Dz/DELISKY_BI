import os

from .base import *


DEBUG = False

TURNSTILE_ENABLED = True

ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("DJANGO_ALLOWED_HOSTS", "").split(",")
    if host.strip()
]

CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin.strip()
]

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True

STATIC_ROOT = BASE_DIR / "staticfiles"

# Production static files
MIDDLEWARE.insert(
    1,
    "whitenoise.middleware.WhiteNoiseMiddleware",
)

MIDDLEWARE.insert(
    1,
    "config.middleware.ProductionHostSeparationMiddleware",
)

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# Safety guard: production must never use a non-production database.
PRODUCTION_DATABASE_NAME = "delisky_bi"
configured_database_name = str(DATABASES["default"]["NAME"]).strip()

if configured_database_name != PRODUCTION_DATABASE_NAME:
    raise RuntimeError(
        "Unsafe production database configuration: "
        f"expected '{PRODUCTION_DATABASE_NAME}', got '{configured_database_name}'."
    )
