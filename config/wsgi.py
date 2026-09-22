"""
WSGI config for config project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application


PRODUCTION_SETTINGS_MODULE = "config.settings.production"
configured_settings_module = os.environ.get(
    "DJANGO_SETTINGS_MODULE"
)

if (
    configured_settings_module
    and configured_settings_module
    != PRODUCTION_SETTINGS_MODULE
):
    raise RuntimeError(
        "Unsafe WSGI settings configuration: "
        f"expected '{PRODUCTION_SETTINGS_MODULE}', "
        f"got '{configured_settings_module}'."
    )

os.environ["DJANGO_SETTINGS_MODULE"] = (
    PRODUCTION_SETTINGS_MODULE
)

application = get_wsgi_application()
