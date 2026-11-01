from html.parser import HTMLParser
from urllib.parse import parse_qs, urlsplit

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from apps.imports.models import DistributionBrand
from .manager_sales import SALES_TABS
from .manager_sections import SECTION_ITEMS


class PrintLinkParser(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.links = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a" and attrs.get("id") == "manager-print-action":
            self.links.append(attrs)


class ManagerPrintActionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = get_user_model().objects.create_user(username="print-action-manager")
        cls.manager.groups.add(Group.objects.get_or_create(name="Manager")[0])
        cls.brand = DistributionBrand.objects.create(code="BIFA", name="BIFA")

    def setUp(self):
        self.client.force_login(self.manager)
        self.filters = {
            "run": "1", "period_start": "2026-08-27",
            "period_end": "2026-10-22", "brand": str(self.brand.pk),
        }

    def analysis_urls(self):
        yield reverse("dashboard:manager_dashboard")
        for tab in SALES_TABS:
            yield reverse("dashboard:manager_sales", args=[tab])
        for section, items in SECTION_ITEMS.items():
            for item in items:
                yield reverse("dashboard:manager_section", args=[section, item])

    def test_print_action_on_every_analysis_page_preserves_filters(self):
        for url in self.analysis_urls():
            with self.subTest(url=url):
                response = self.client.get(url, self.filters)
                self.assertEqual(response.status_code, 200)
                links = PrintLinkParser(response.content.decode()).links
                self.assertEqual(len(links), 1)
                link = links[0]
                self.assertEqual(link["target"], "_blank")
                self.assertEqual(link["rel"], "noopener")
                parsed = urlsplit(link["href"])
                self.assertEqual(parsed.path, reverse("dashboard:manager_print"))
                self.assertEqual(parse_qs(parsed.query), {
                    key: [value] for key, value in self.filters.items()
                })
                self.assertContains(response, "طباعة التقرير")
                self.assertTemplateUsed(response, "dashboard/partials/manager_print_action.html")

    def test_no_print_action_before_run_or_with_invalid_filters(self):
        for url in self.analysis_urls():
            for data, status in (
                ({}, 200),
                ({key: value for key, value in self.filters.items() if key != "run"}, 200),
                ({**self.filters, "run": "0"}, 200),
                ({**self.filters, "period_end": "2026-01-01"}, 400),
                ({**self.filters, "period_start": "invalid"}, 400),
                ({**self.filters, "brand": "999999"}, 400),
            ):
                with self.subTest(url=url, data=data):
                    response = self.client.get(url, data)
                    self.assertEqual(response.status_code, status)
                    self.assertEqual(PrintLinkParser(response.content.decode()).links, [])
                    self.assertNotContains(response, "طباعة التقرير", status_code=status)

    def test_all_brands_print_action(self):
        filters = {**self.filters, "brand": ""}
        for url in self.analysis_urls():
            with self.subTest(url=url):
                response = self.client.get(url, filters)
                self.assertEqual(response.status_code, 200)
                link, = PrintLinkParser(response.content.decode()).links
                query = parse_qs(urlsplit(link["href"]).query)
                self.assertNotIn("brand", query)
                self.assertEqual(query["run"], ["1"])
                self.assertEqual(query["period_start"], [filters["period_start"]])
                self.assertEqual(query["period_end"], [filters["period_end"]])

    def test_ai_tools_do_not_show_print_action(self):
        for tool in ("ask-delisky", "marketing-helper"):
            with self.subTest(tool=tool):
                response = self.client.get(reverse("dashboard:manager_tool", args=[tool]), self.filters)
                self.assertEqual(response.status_code, 200)
                self.assertNotContains(response, "طباعة التقرير")
                self.assertTemplateNotUsed(response, "dashboard/partials/manager_print_action.html")
