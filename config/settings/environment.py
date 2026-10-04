"""Strict parsers for opt-in deployment settings."""
import os

from django.core.exceptions import ImproperlyConfigured


def boolean_environment(name, *, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized not in {"true", "false"}:
        raise ImproperlyConfigured(f"{name} must be 'true' or 'false'.")
    return normalized == "true"
