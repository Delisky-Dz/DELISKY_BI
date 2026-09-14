from pathlib import Path
from textwrap import dedent

ROOT = Path(__file__).resolve().parents[1]


def replace_method(relative_path, class_name, method_name, replacement):
    path = ROOT / relative_path
    text = path.read_text(encoding="utf-8-sig")
    lines = text.splitlines(keepends=True)

    class_index = None
    for index, line in enumerate(lines):
        if line.startswith(f"class {class_name}"):
            class_index = index
            break
    if class_index is None:
        raise RuntimeError(f"Class not found: {class_name}")

    class_end = len(lines)
    for index in range(class_index + 1, len(lines)):
        if lines[index].startswith("class "):
            class_end = index
            break

    def_index = None
    needle = f"    def {method_name}("
    for index in range(class_index + 1, class_end):
        if lines[index].startswith(needle):
            def_index = index
            break
    if def_index is None:
        raise RuntimeError(
            f"Method not found: {class_name}.{method_name}"
        )

    start = def_index
    cursor = def_index - 1
    while cursor > class_index and lines[cursor].strip():
        start = cursor
        cursor -= 1

    end = class_end
    for index in range(def_index + 1, class_end):
        line = lines[index]
        if line.startswith("    @") or line.startswith("    def "):
            end = index
            break

    while end > start and not lines[end - 1].strip():
        end -= 1

    new_source = dedent(replacement).strip("\n") + "\n\n"
    lines[start:end] = [new_source]
    path.write_text("".join(lines), encoding="utf-8")


# Ask DELISKY is now an independent manager tool page.
replace_method(
    "apps/dashboard/test_ask_delisky.py",
    "AskDeliskyUiTests",
    "test_dashboard_renders_assistant_with_filters",
    r'''
    def test_dashboard_renders_assistant_with_filters(self):
        response = self.client.get(
            reverse(
                "dashboard:manager_tool",
                args=("ask-delisky",),
            ),
            {
                "period_start": "2026-07-01",
                "period_end": "2026-07-20",
                "brand": str(self.brand.pk),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            "dashboard/manager_tool.html",
        )
        self.assertTemplateUsed(
            response,
            "dashboard/partials/ask_delisky.html",
        )

        html = response.content.decode("utf-8")
        self.assertIn("data-ask-delisky", html)
        self.assertIn("data-ask-delisky-form", html)
        self.assertIn('name="period_start"', html)
        self.assertIn('value="2026-07-01"', html)
        self.assertIn('value="2026-07-20"', html)
        self.assertIn(f'value="{self.brand.pk}"', html)
        self.assertIn("csrfmiddlewaretoken", html)
    ''',
)

replace_method(
    "apps/dashboard/test_ask_delisky.py",
    "AskDeliskyUiTests",
    "test_dashboard_renders_assistant_sidebar_link",
    r'''
    def test_dashboard_renders_assistant_sidebar_link(self):
        response = self.client.get(
            reverse("dashboard:manager_dashboard")
        )

        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        tool_url = reverse(
            "dashboard:manager_tool",
            args=("ask-delisky",),
        )
        self.assertIn(f'href="{tool_url}"', html)
        self.assertIn("Ask DELISKY", html)
        self.assertNotIn('id="ask-delisky-title"', html)
        self.assertNotIn("data-ask-delisky-form", html)
    ''',
)

# Marketing helper is also independent from the overview page.
replace_method(
    "apps/dashboard/test_marketing_helper.py",
    "MarketingHelperApiTests",
    "test_manager_dashboard_renders_both_ai_assistants",
    r'''
    def test_manager_dashboard_renders_both_ai_assistants(self):
        self.client.force_login(self.manager)

        dashboard = self.client.get(
            reverse("dashboard:manager_dashboard")
        )
        self.assertEqual(dashboard.status_code, 200)
        dashboard_html = dashboard.content.decode("utf-8")

        ask_url = reverse(
            "dashboard:manager_tool",
            args=("ask-delisky",),
        )
        marketing_url = reverse(
            "dashboard:manager_tool",
            args=("marketing-helper",),
        )
        self.assertIn(f'href="{ask_url}"', dashboard_html)
        self.assertIn(f'href="{marketing_url}"', dashboard_html)
        self.assertNotIn("data-ask-delisky", dashboard_html)
        self.assertNotIn("data-marketing-helper", dashboard_html)

        ask_page = self.client.get(ask_url)
        marketing_page = self.client.get(marketing_url)
        self.assertEqual(ask_page.status_code, 200)
        self.assertEqual(marketing_page.status_code, 200)
        self.assertIn(
            "data-ask-delisky",
            ask_page.content.decode("utf-8"),
        )
        self.assertIn(
            "data-marketing-helper",
            marketing_page.content.decode("utf-8"),
        )
    ''',
)

# Main dashboard is filter-first and no longer calls the monolithic builder.
replace_method(
    "apps/dashboard/tests.py",
    "ManagerDashboardViewFilterTests",
    "test_empty_filters_call_dashboard_service",
    r'''
    @patch("apps.dashboard.views.build_manager_dashboard")
    def test_empty_filters_call_dashboard_service(
        self,
        mocked_build_dashboard,
    ):
        response = self.client.get(self.dashboard_url())

        self.assertEqual(response.status_code, 200)
        mocked_build_dashboard.assert_not_called()
        self.assertFalse(response.context["filter_requested"])
        self.assertIsNone(response.context["overview_summary"])
    ''',
)

replace_method(
    "apps/dashboard/tests.py",
    "ManagerDashboardViewFilterTests",
    "test_valid_filters_are_passed_to_service",
    r'''
    @patch("apps.dashboard.views.build_manager_dashboard")
    def test_valid_filters_are_passed_to_service(
        self,
        mocked_build_dashboard,
    ):
        response = self.client.get(
            self.dashboard_url(),
            {
                "run": "1",
                "period_start": "2026-07-01",
                "period_end": "2026-07-20",
                "brand": str(self.active_brand.pk),
            },
        )

        self.assertEqual(response.status_code, 200)
        mocked_build_dashboard.assert_not_called()
        self.assertTrue(response.context["filter_requested"])
        self.assertEqual(
            response.context["filter_form"].cleaned_data[
                "period_start"
            ],
            date(2026, 7, 1),
        )
        self.assertEqual(
            response.context["filter_form"].cleaned_data[
                "period_end"
            ],
            date(2026, 7, 20),
        )
        self.assertEqual(
            response.context["filter_form"].cleaned_data[
                "brand"
            ],
            self.active_brand,
        )
    ''',
)

replace_method(
    "apps/dashboard/tests.py",
    "ManagerDashboardTemplateTests",
    "test_dashboard_uses_expected_template_and_context",
    r'''
    def test_dashboard_uses_expected_template_and_context(self):
        response = self.client.get(self.dashboard_url())

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            "dashboard/manager_dashboard.html",
        )
        self.assertTemplateUsed(
            response,
            "dashboard/partials/welcome_state.html",
        )
        self.assertIsInstance(
            response.context["filter_form"],
            ManagerDashboardFilterForm,
        )
        self.assertFalse(response.context["filter_requested"])
        self.assertIsNone(response.context["overview_summary"])
    ''',
)

replace_method(
    "apps/dashboard/tests.py",
    "ManagerDashboardTemplateTests",
    "test_invalid_filter_renders_errors_without_result",
    r'''
    def test_invalid_filter_renders_errors_without_result(self):
        response = self.client.get(
            self.dashboard_url(),
            {
                "run": "1",
                "period_start": "2026-07-20",
                "period_end": "2026-07-01",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertTemplateUsed(
            response,
            "dashboard/manager_dashboard.html",
        )
        self.assertIsNone(response.context["overview_summary"])
        self.assertTrue(response.context["filter_requested"])
        self.assertIn(
            "تاريخ النهاية لا يمكن أن يسبق تاريخ البداية.",
            response.context[
                "filter_form"
            ].non_field_errors(),
        )
        self.assertContains(
            response,
            "تعذر تطبيق الفلتر",
            status_code=400,
        )
    ''',
)

# Overview summary now comes from lightweight sales + visit aggregations.
replace_method(
    "apps/dashboard/tests.py",
    "ManagerDashboardSummaryViewTests",
    "test_summary_is_presented_and_added_to_context",
    r'''
    @patch(
        "apps.dashboard.manager_views.present_brand_sales_chart",
        return_value=(),
    )
    @patch(
        "apps.dashboard.manager_views.present_sales_timeline",
        return_value=None,
    )
    @patch("apps.dashboard.manager_views.aggregate_pos_visits")
    @patch("apps.dashboard.manager_views.aggregate_sales")
    def test_summary_is_presented_and_added_to_context(
        self,
        aggregate_sales,
        aggregate_pos_visits,
        present_sales_timeline,
        present_brand_sales_chart,
    ):
        aggregate_sales.return_value = SimpleNamespace(
            overall=SimpleNamespace(
                total_sales=Decimal("1200.00"),
                sale_record_count=4,
                positive_sale_record_count=3,
            ),
            by_worker=(),
            by_brand=(),
            by_date=(),
        )
        aggregate_pos_visits.return_value = SimpleNamespace(
            overall=SimpleNamespace(
                total_record_count=5,
                visited_record_count=3,
                not_visited_record_count=2,
            ),
            by_brand_client=(),
        )

        response = self.client.get(
            self.dashboard_url(),
            {"run": "1"},
        )

        self.assertEqual(response.status_code, 200)
        summary = response.context["overview_summary"]
        self.assertEqual(summary.total_sales, Decimal("1200.00"))
        self.assertEqual(summary.sale_record_count, 4)
        self.assertEqual(summary.visit_success_percentage, Decimal("60"))
        present_sales_timeline.assert_called_once()
        present_brand_sales_chart.assert_called_once()
    ''',
)

replace_method(
    "apps/dashboard/tests.py",
    "ManagerDashboardSummaryViewTests",
    "test_summary_cards_are_rendered",
    r'''
    @patch(
        "apps.dashboard.manager_views.present_brand_sales_chart",
        return_value=(),
    )
    @patch(
        "apps.dashboard.manager_views.present_sales_timeline",
        return_value=None,
    )
    @patch("apps.dashboard.manager_views.aggregate_pos_visits")
    @patch("apps.dashboard.manager_views.aggregate_sales")
    def test_summary_cards_are_rendered(
        self,
        aggregate_sales,
        aggregate_pos_visits,
        present_sales_timeline,
        present_brand_sales_chart,
    ):
        aggregate_sales.return_value = SimpleNamespace(
            overall=SimpleNamespace(
                total_sales=Decimal("1200.00"),
                sale_record_count=4,
                positive_sale_record_count=3,
            ),
            by_worker=(),
            by_brand=(),
            by_date=(),
        )
        aggregate_pos_visits.return_value = SimpleNamespace(
            overall=SimpleNamespace(
                total_record_count=5,
                visited_record_count=3,
                not_visited_record_count=2,
            ),
            by_brand_client=(),
        )

        response = self.client.get(
            self.dashboard_url(),
            {"run": "1"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            "dashboard/partials/manager_overview_core.html",
        )
        self.assertContains(response, "إجمالي المبيعات")
        self.assertContains(response, "1200.00")
        self.assertContains(response, "نسبة نجاح الزيارة")
        self.assertContains(response, "60.0")
        self.assertContains(response, "المنتجات غير المباعة")
    ''',
)

replace_method(
    "apps/dashboard/tests.py",
    "ManagerDashboardTemplateStructureTests",
    "test_dashboard_uses_base_and_summary_partials",
    r'''
    def test_dashboard_uses_base_and_summary_partials(self):
        response = self.client.get(
            reverse("dashboard:manager_dashboard")
        )

        self.assertEqual(response.status_code, 200)
        for template_name in (
            "dashboard/base.html",
            "dashboard/manager_dashboard.html",
            "dashboard/partials/manager_sidebar_navigation.html",
            "dashboard/partials/filter_form.html",
            "dashboard/partials/welcome_state.html",
        ):
            self.assertTemplateUsed(response, template_name)

        for legacy_template in (
            "dashboard/partials/sales_summary.html",
            "dashboard/partials/visits_summary.html",
            "dashboard/partials/workers_summary.html",
            "dashboard/partials/attention_summary.html",
            "dashboard/partials/truck_status.html",
        ):
            self.assertTemplateNotUsed(response, legacy_template)
    ''',
)

# Coverage and quality moved to the follow-up section.
replace_method(
    "apps/dashboard/tests.py",
    "ManagerDashboardCoverageAndQualityViewTests",
    "test_coverage_and_quality_are_added_to_context",
    r'''
    def test_coverage_and_quality_are_added_to_context(self):
        response = self.client.get(self.dashboard_url())

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("coverage", response.context)
        self.assertNotIn("data_quality", response.context)

        html = response.content.decode("utf-8")
        coverage_url = reverse(
            "dashboard:manager_section",
            args=("follow-up", "coverage"),
        )
        quality_url = reverse(
            "dashboard:manager_section",
            args=("follow-up", "data-quality"),
        )
        self.assertIn(f'href="{coverage_url}"', html)
        self.assertIn(f'href="{quality_url}"', html)
    ''',
)

replace_method(
    "apps/dashboard/tests.py",
    "ManagerDashboardCoverageAndQualityViewTests",
    "test_coverage_and_quality_partials_are_rendered",
    r'''
    def test_coverage_and_quality_partials_are_rendered(self):
        response = self.client.get(self.dashboard_url())

        self.assertEqual(response.status_code, 200)
        self.assertTemplateNotUsed(
            response,
            "dashboard/partials/coverage_summary.html",
        )
        self.assertTemplateNotUsed(
            response,
            "dashboard/partials/data_quality_summary.html",
        )
        self.assertContains(response, "التغطية الزمنية")
        self.assertContains(response, "جودة البيانات")
        self.assertContains(
            response,
            reverse(
                "dashboard:manager_section",
                args=("follow-up", "coverage"),
            ),
        )
    ''',
)

# Seller rankings/cards are independent sections and must not be built on overview load.
replace_method(
    "apps/dashboard/tests.py",
    "ManagerDashboardWorkerRankingViewTests",
    "test_rankings_use_one_worker_lookup_and_render",
    r'''
    @patch("apps.dashboard.views.Worker.objects.filter")
    def test_rankings_use_one_worker_lookup_and_render(
        self,
        mocked_worker_filter,
    ):
        response = self.client.get(self.dashboard_url())

        self.assertEqual(response.status_code, 200)
        mocked_worker_filter.assert_not_called()
        rankings_url = reverse(
            "dashboard:manager_section",
            args=("sellers", "rankings"),
        )
        self.assertContains(response, rankings_url)
        self.assertTemplateNotUsed(
            response,
            "dashboard/partials/worker_rankings.html",
        )
    ''',
)

replace_method(
    "apps/dashboard/tests.py",
    "ManagerDashboardWorkerRankingViewTests",
    "test_empty_rankings_do_not_query_workers",
    r'''
    @patch("apps.dashboard.views.Worker.objects.filter")
    def test_empty_rankings_do_not_query_workers(
        self,
        mocked_worker_filter,
    ):
        response = self.client.get(self.dashboard_url())

        self.assertEqual(response.status_code, 200)
        mocked_worker_filter.assert_not_called()
        self.assertNotIn("lowest_sales_workers", response.context)
        self.assertNotIn("highest_visit_workers", response.context)
        self.assertNotIn("most_not_sold_workers", response.context)
    ''',
)

replace_method(
    "apps/dashboard/tests.py",
    "ManagerDashboardWorkerCardViewTests",
    "test_worker_cards_use_shared_lookups_and_render",
    r'''
    @patch("apps.dashboard.views._load_brands_by_id")
    @patch("apps.dashboard.views._load_workers_by_id")
    def test_worker_cards_use_shared_lookups_and_render(
        self,
        mocked_load_workers,
        mocked_load_brands,
    ):
        response = self.client.get(self.dashboard_url())

        self.assertEqual(response.status_code, 200)
        mocked_load_workers.assert_not_called()
        mocked_load_brands.assert_not_called()
        card_url = reverse(
            "dashboard:manager_section",
            args=("sellers", "card"),
        )
        self.assertContains(response, card_url)
        self.assertTemplateNotUsed(
            response,
            "dashboard/partials/worker_cards.html",
        )
    ''',
)

replace_method(
    "apps/dashboard/tests.py",
    "ManagerDashboardWorkerCardViewTests",
    "test_empty_cards_and_rankings_skip_lookups",
    r'''
    @patch("apps.dashboard.views._load_brands_by_id")
    @patch("apps.dashboard.views._load_workers_by_id")
    def test_empty_cards_and_rankings_skip_lookups(
        self,
        mocked_load_workers,
        mocked_load_brands,
    ):
        response = self.client.get(self.dashboard_url())

        self.assertEqual(response.status_code, 200)
        mocked_load_workers.assert_not_called()
        mocked_load_brands.assert_not_called()
        self.assertNotIn("worker_cards", response.context)
        self.assertTemplateNotUsed(
            response,
            "dashboard/partials/worker_cards.html",
        )
    ''',
)

replace_method(
    "apps/dashboard/tests.py",
    "HighestVisitManagerDashboardConditionTests",
    "test_highest_visit_workers_can_show_rankings",
    r'''
    def test_highest_visit_workers_can_show_rankings(self):
        from pathlib import Path

        template_path = (
            Path(__file__).resolve().parent
            / "templates"
            / "dashboard"
            / "manager_sellers.html"
        )
        template_text = template_path.read_text(
            encoding="utf-8"
        )

        self.assertIn("item == 'visits'", template_text)
        self.assertIn("seller_rows", template_text)
        self.assertNotIn(
            "highest_visit_workers or highest_non_visit_workers",
            (
                Path(__file__).resolve().parent
                / "templates"
                / "dashboard"
                / "manager_dashboard.html"
            ).read_text(encoding="utf-8"),
        )
    ''',
)

# Remove this one-shot migration script in the same commit produced by CI.
Path(__file__).unlink()
