"""Development-only read-only context/HTML benchmark (no PDF/browser timing)."""
from contextlib import ExitStack
from statistics import median
from time import perf_counter
from unittest.mock import patch

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.template.loader import render_to_string

from apps.dashboard import manager_print as report
from apps.dashboard.forms import ManagerDashboardFilterForm


class Command(BaseCommand):
    help = "Measure meeting report stages against development data, read only."

    def add_arguments(self, parser):
        parser.add_argument("--period-start", required=True)
        parser.add_argument("--period-end", required=True)
        parser.add_argument("--brand", default="")
        parser.add_argument("--samples", type=int, default=3)

    def handle(self, *args, **options):
        if (not settings.DEBUG or connection.vendor != "postgresql"
                or connection.settings_dict["NAME"] != "delisky_bi_dev"):
            raise CommandError("Requires the PostgreSQL development database and DEBUG.")
        if options["samples"] < 1:
            raise CommandError("samples must be positive")
        form = ManagerDashboardFilterForm(data={
            "period_start": options["period_start"], "period_end": options["period_end"],
            "brand": options["brand"],
        })
        stages = (
            ("index building", report.overview, "build_truck_code_index"),
            ("index building", report.overview, "build_assignment_index"),
            ("sales aggregation", report.overview, "aggregate_sales"),
            ("POS aggregation", report.overview, "aggregate_pos_visits"),
            ("seller presentation", report.sellers, "_build_seller_rows"),
            ("seller presentation", report.sellers, "_rank_sellers"),
            ("seller presentation", report.sellers, "_lowest_sales"),
            ("seller presentation", report.sellers, "_present_not_sold_groups"),
            ("client analytics", report.clients, "_previous_period"),
            ("client analytics", report.clients, "_trend_rows"),
            ("client analytics", report.clients, "_stopped_clients"),
            ("client analytics", report.clients, "_declining_clients"),
            ("client analytics", report.clients, "_visited_without_sales"),
            ("client analytics", report.clients, "_client_visit_rows"),
            ("client analytics", report.clients, "_top_clients"),
            ("product source analytics", report.follow, "_build_product_sources"),
            ("truck analytics", report.fleet, "_status_rows"),
            ("truck analytics", report.follow, "determine_truck_operational_status"),
            ("coverage/data-quality", report.follow, "_data_quality"),
            ("coverage/data-quality", report.follow, "_exclusion_summary"),
            ("coverage/data-quality", report.follow, "_source_status_rows"),
        )
        samples = {preset: [] for preset in report.PRESETS}
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION READ ONLY")
            if not form.is_valid():
                raise CommandError(str(form.errors))
            for iteration in range(options["samples"] + 1):
                for preset in (("quick", "full") if iteration % 2 else ("full", "quick")):
                    timings = {label: 0.0 for label, _, _ in stages}
                    def measure(label, function):
                        def wrapped(*args, **kwargs):
                            start = perf_counter()
                            try:
                                return function(*args, **kwargs)
                            finally:
                                timings[label] += perf_counter() - start
                        return wrapped
                    with ExitStack() as stack:
                        for label, module, name in stages:
                            stack.enter_context(patch.object(module, name, measure(label, getattr(module, name))))
                        start = perf_counter()
                        context = report.build_print_context(form, selected_sections=report.PRESETS[preset])
                        render_start = perf_counter()
                        render_to_string("dashboard/manager_meeting_print.html", context)
                        timings["template rendering"] = perf_counter() - render_start
                        timings["total"] = perf_counter() - start
                    if iteration:
                        samples[preset].append(timings)
        self.stdout.write(f"Current-period sales records={context['overview_summary'].sale_record_count}; "
                          f"POS records={context['overview_summary'].pos_record_count}; "
                          f"samples per preset={options['samples']}")
        self.stdout.write("Development context + HTML; one warmup; stage medians in seconds. "
                          "Inclusive stages overlap: coverage includes product/truck work; "
                          "sales includes previous-period sales when clients selected. "
                          "Total includes remaining orchestration; PDF/browser excluded.")
        for preset, results in samples.items():
            self.stdout.write(preset + " " + "; ".join(
                f"{label}={median(row[label] for row in results):.6f}"
                for label in results[0]))
