from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from apps.assistant.context_cache import clear_context_cache
from apps.assistant.revision_tracking import configure_tracking, tracking_installed


class Command(BaseCommand):
    help = "Explicitly enable/disable optional Ask context revision triggers."

    def add_arguments(self, parser):
        actions = parser.add_mutually_exclusive_group(required=True)
        actions.add_argument("--enable", action="store_true")
        actions.add_argument("--disable", action="store_true")
        actions.add_argument("--status", action="store_true")

    def handle(self, *args, **options):
        if connection.vendor != "postgresql":
            raise CommandError("Context tracking requires PostgreSQL.")
        if options["status"]:
            self.stdout.write("enabled" if tracking_installed() else "disabled")
            return
        if options["enable"] and not getattr(
            settings, "ASK_DELISKY_CONTEXT_CACHE_ENABLED", False,
        ):
            raise CommandError("Enablement requires ASK_DELISKY_CONTEXT_CACHE_ENABLED.")
        configure_tracking(enabled=options["enable"])
        clear_context_cache()
        self.stdout.write("enabled" if options["enable"] else "disabled")
