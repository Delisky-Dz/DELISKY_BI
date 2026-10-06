from contextlib import ExitStack
from datetime import date
from html.parser import HTMLParser
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from .models import DistributionBrand, ImportBatch, ImportReportType


class NavigationParser(HTMLParser):
    def __init__(self, content):
        super().__init__()
        self.links = []
        self.feed(content)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a" and "side-link" in attrs.get("class", "").split():
            self.links.append(attrs)


class AccountantNavigationTests(TestCase):
    sections = {
        "opening_stock": "opening_stock_upload_form",
        "chargement": "raw_upload_formset",
        "items_detail": "items_detail_upload_form",
        "items": "items_upload_form",
        "sales": "sales_upload_formset",
    }

    @classmethod
    def setUpTestData(cls):
        call_command("seed_roles", stdout=StringIO())
        users = get_user_model()
        cls.accountant = users.objects.create_user(username="navigation-accountant")
        cls.accountant.groups.add(Group.objects.get(name="Accountant"))
        cls.manager = users.objects.create_user(username="navigation-manager")
        cls.manager.groups.add(Group.objects.get(name="Manager"))
        cls.superuser = users.objects.create_superuser(username="navigation-admin", email="admin@example.com")
        cls.inactive = users.objects.create_user(username="navigation-inactive", is_active=False)
        cls.inactive.groups.add(Group.objects.get(name="Accountant"))
        cls.staff = users.objects.create_user(username="navigation-staff", is_staff=True)
        cls.brand = DistributionBrand.objects.create(code="BIFA", name="BIFA")
        cls.batch = ImportBatch.objects.create(
            uploaded_by=cls.accountant,
            brand=cls.brand, report_type=ImportReportType.SALES,
            period_start=date(2026, 7, 1), period_end=date(2026, 7, 7),
            original_filename="Sales_BIFA_2026-07-01_2026-07-07.xlsx",
            file_size_bytes=128, file_sha256="a" * 64, content_sha256="b" * 64,
        )

    def routes(self):
        return ["accountant_home", "batch_list", "standard_upload"] + [
            f"raw_{section}_upload" for section in self.sections
        ]

    def assert_active(self, response, route):
        links = NavigationParser(response.content.decode()).links
        active = [link for link in links if "is-active" in link["class"].split()]
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0]["href"], reverse(f"imports:{route}"))
        self.assertEqual(active[0].get("aria-current"), "page")
        self.assertTrue(all("#" not in link["href"] for link in links))

    def test_accountant_and_superuser_can_open_each_page(self):
        for user in (self.accountant, self.superuser):
            self.client.force_login(user)
            for route in self.routes():
                with self.subTest(user=user.username, route=route):
                    response = self.client.get(reverse(f"imports:{route}"))
                    self.assertEqual(response.status_code, 200)
                    self.assert_active(response, route)
                    self.assertContains(response, 'dir="rtl"')
                    for theme in ("light", "system", "dark"):
                        self.assertContains(response, f'data-theme-option="{theme}"')

    def test_unauthorized_get_and_post_remain_restricted(self):
        for user, expected in ((None, 302), (self.manager, 403), (self.staff, 403), (self.inactive, 302)):
            self.client.logout()
            if user:
                self.client.force_login(user)
            for route in self.routes():
                for method in (self.client.get, self.client.post):
                    with self.subTest(user=user, route=route, method=method.__name__):
                        response = method(reverse(f"imports:{route}"))
                        self.assertEqual(response.status_code, expected)

    def test_landing_does_not_construct_forms_or_query_import_history(self):
        self.client.force_login(self.accountant)
        with ExitStack() as stack:
            for form in ("ImportUploadForm", "RawOpeningStockUploadForm", "RawChargementUploadFormSet", "RawItemsDetailUploadForm", "RawItemsUploadForm", "RawSalesUploadFormSet"):
                stack.enter_context(patch(f"apps.imports.views.{form}", side_effect=AssertionError("Landing built an upload form")))
            with CaptureQueriesContext(connection) as queries:
                response = self.client.get(reverse("imports:accountant_home"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'enctype="multipart/form-data"')
        self.assertNotContains(response, 'id="recent-batches"')
        self.assertFalse(any('imports_' in query["sql"] for query in queries))

    def test_each_upload_get_and_invalid_post_only_render_own_form(self):
        self.client.force_login(self.accountant)
        for section, key in self.sections.items():
            route = f"raw_{section}_upload"
            for method in (self.client.get, self.client.post):
                with self.subTest(section=section, method=method.__name__):
                    response = method(reverse(f"imports:{route}"))
                    self.assertEqual(response.status_code, 200)
                    self.assert_active(response, route)
                    self.assertTemplateUsed(response, f"imports/partials/{section}_upload.html")
                    self.assertIn(key, response.context)
                    self.assertContains(response, f'id="raw-{section.replace("_", "-")}-form"')
                    for other, other_key in self.sections.items():
                        if other != section:
                            self.assertNotIn(other_key, response.context)
                            self.assertNotContains(response, f'id="raw-{other.replace("_", "-")}-form"')
                    self.assertNotIn("upload_form", response.context)
                    self.assertNotContains(response, 'id="recent-batches"')

    def test_standard_upload_legacy_post_keeps_errors_and_active_section(self):
        self.client.force_login(self.accountant)
        for route in ("accountant_home", "standard_upload"):
            response = self.client.post(reverse(f"imports:{route}"), {})
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context["upload_form"].errors)
            self.assert_active(response, "standard_upload")
            self.assertTemplateUsed(response, "imports/partials/standard_upload.html")

    def test_batches_are_paginated_and_detail_marks_history_active(self):
        self.client.force_login(self.accountant)
        for index in range(21):
            ImportBatch.objects.create(
                uploaded_by=self.accountant,
                brand=self.brand, report_type=ImportReportType.SALES,
                period_start=date(2026, 7, 1), period_end=date(2026, 7, 7),
                original_filename=f"history-{index}.xlsx", file_size_bytes=128,
                file_sha256=f"{index:064x}", content_sha256=f"{index:064x}",
            )
        first = self.client.get(reverse("imports:batch_list"))
        second = self.client.get(reverse("imports:batch_list"), {"page": 2})
        self.assertEqual(len(first.context["recent_batches"]), 20)
        self.assertEqual(len(second.context["recent_batches"]), 2)
        self.assertEqual(first.context["batch_total"], 22)
        self.assertContains(second, self.batch.original_filename)
        self.assertNotContains(first, 'enctype="multipart/form-data"')
        detail = self.client.get(reverse("imports:batch_detail", args=[self.batch.pk]))
        self.assert_active(detail, "batch_list")
        self.assertContains(detail, "العودة إلى سجل الدفعات")

    def test_all_sidebar_destinations_resolve_for_accountant(self):
        self.client.force_login(self.accountant)
        response = self.client.get(reverse("imports:accountant_home"))
        for link in NavigationParser(response.content.decode()).links:
            with self.subTest(url=link["href"]):
                page = self.client.get(link["href"])
                self.assertEqual(page.status_code, 200)
                active = [
                    item for item in NavigationParser(page.content.decode()).links
                    if "is-active" in item["class"].split()
                ]
                self.assertEqual([item["href"] for item in active], [link["href"]])
