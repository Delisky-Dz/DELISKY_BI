from contextlib import ExitStack
from time import perf_counter
from statistics import median
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.http import QueryDict
from django.test import TestCase, SimpleTestCase
from django.urls import reverse

from . import manager_print as report
from apps.imports.models import DistributionBrand


class SelectionValidationTests(SimpleTestCase):
    def test_presets(self):
        self.assertEqual(report.requested_sections(QueryDict('preset=quick')),
                         {'overview', 'sellers', 'visits', 'actions'})
        self.assertEqual(report.requested_sections(QueryDict()), set(report.SECTION_IDS))

    def test_manual_comma_or_repeated_sections(self):
        for query in ('preset=manual&sections=overview,sellers',
                      'preset=manual&sections=overview&sections=sellers'):
            self.assertEqual(report.requested_sections(QueryDict(query)), {'overview', 'sellers'})

    def test_reject_invalid_or_empty_selection(self):
        for query in ('preset=evil', 'preset=manual', 'preset=manual&sections=overview,evil'):
            with self.subTest(query=query), self.assertRaises(ValueError):
                report.requested_sections(QueryDict(query))


class SelectivePrintTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = get_user_model().objects.create_user(username='selective-manager')
        cls.manager.groups.add(Group.objects.get_or_create(name='Manager')[0])
        cls.other = get_user_model().objects.create_user(username='selective-other')
        cls.brand = DistributionBrand.objects.create(code='TEST', name='Test brand')

    def setUp(self):
        self.client.force_login(self.manager)
        self.filters = dict(period_start='2026-08-27', period_end='2026-10-22',
                            brand=str(self.brand.pk), run='1')
        self.url = reverse('dashboard:manager_print_generate')

    def generate(self, sections, **options):
        return self.client.get(self.url, {**self.filters, 'preset': 'manual',
                                          'sections': sections, **options})

    def test_configuration_is_lazy_and_preserves_filters(self):
        with patch.object(report.overview, 'aggregate_sales') as sales, \
             patch.object(report.follow, '_data_quality') as quality, \
             patch.object(report, 'build_print_context') as build:
            response = self.client.get(reverse('dashboard:manager_print'), self.filters)
            self.assertEqual(response.status_code, 200)
            sales.assert_not_called()
            quality.assert_not_called()
            build.assert_not_called()
        for text in ('إعداد تقرير الاجتماع', 'إنشاء التقرير', 'اجتماع سريع', 'اجتماع كامل',
                     'تخصيص يدوي', 'name="run" value="1"', 'name="period_start" value="2026-08-27"',
                     'name="period_end" value="2026-10-22"', 'name="brand" value="'+str(self.brand.pk)+'"'):
            self.assertContains(response, text)
        self.assertContains(response, 'type="checkbox" name="sections"', count=10)
        self.assertContains(response, 'name="preset" value="full" checked')
        self.assertContains(response, 'name="auto_skip" value="1" checked')
        self.assertIn('no-store', response.headers['Cache-Control'])

    def test_permissions_on_configuration_and_generation(self):
        for url in (self.url, reverse('dashboard:manager_print')):
            with patch.object(report, 'build_print_context') as build:
                self.client.force_login(self.other)
                self.assertEqual(self.client.get(url, self.filters).status_code, 403)
                self.client.logout()
                self.assertEqual(self.client.get(url, self.filters).status_code, 302)
                build.assert_not_called()

    def test_overview_and_sellers_never_invoke_unselected_heavy_modules(self):
        forbidden = ((report.clients, '_previous_period'), (report.clients, '_top_clients'),
                     (report.clients, '_client_visit_rows'), (report.follow, '_data_quality'),
                     (report.follow, '_build_product_sources'), (report.follow, '_source_status_rows'), (report.fleet, '_status_rows'),
                     (report.fleet, '_slow_moving_rows'), (report.sellers, '_present_not_sold_groups'))
        with ExitStack() as stack:
            mocks = [stack.enter_context(patch.object(module, name, side_effect=AssertionError(name)))
                     for module, name in forbidden]
            response = self.generate('overview,sellers', auto_skip='0')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context['render_sections'], ['overview', 'sellers'])
            self.assertEqual(response.context['overview_summary'].total_sales, 0)
            self.assertContains(response, '<span>01</span>')
            self.assertContains(response, '<span>02</span>')
            self.assertNotContains(response, '<span>03</span>')
            for mock in mocks:
                mock.assert_not_called()

    def test_each_section_can_generate_alone(self):
        for section in report.SECTION_IDS:
            with self.subTest(section=section):
                response = self.generate(section, auto_skip='0')
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context['render_sections'], [section])
                self.assertContains(response, '<span>01</span>')
                self.assertNotContains(response, '<span>02</span>')

    def test_products_only_does_not_build_sales_visits_clients_or_quality(self):
        with patch.object(report.overview, 'aggregate_sales', side_effect=AssertionError('sales')), \
             patch.object(report.overview, 'aggregate_pos_visits', side_effect=AssertionError('visits')), \
             patch.object(report.follow, '_data_quality', side_effect=AssertionError('quality')), \
             patch.object(report.clients, '_previous_period', side_effect=AssertionError('clients')):
            self.assertEqual(self.generate('unsold,product_alerts').status_code, 200)

    def test_sales_only_skips_visit_and_seller_builders(self):
        with patch.object(report.overview, 'aggregate_pos_visits', side_effect=AssertionError('visits')), \
             patch.object(report.sellers, '_build_seller_rows', side_effect=AssertionError('sellers')):
            self.assertEqual(self.generate('sales').status_code, 200)

    def test_unsold_only_skips_other_product_presenters(self):
        with patch.object(report.fleet, '_slow_moving_rows', side_effect=AssertionError('slow')), \
             patch.object(report.follow, '_gap_rows', side_effect=AssertionError('gaps')):
            self.assertEqual(self.generate('unsold').status_code, 200)

    def test_quick_skips_quality_and_large_tables_but_loads_action_dependencies(self):
        with patch.object(report.follow, '_data_quality', side_effect=AssertionError('quality')), \
             patch.object(report.follow, '_build_product_sources', wraps=report.follow._build_product_sources) as products, \
             patch.object(report.fleet, '_status_rows', wraps=report.fleet._status_rows) as trucks:
            response = self.client.get(self.url, {**self.filters, 'preset': 'quick', 'auto_skip': '0'})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context['selected_sections'], set(report.PRESETS['quick']))
            products.assert_called_once()
            trucks.assert_called_once()
            self.assertNotContains(response, 'coverage-quality')
            self.assertNotContains(response, 'أعلى 10 زبائن بالمبيعات')

    def test_full_reuses_base_aggregations(self):
        with patch.object(report.follow, 'aggregate_sales', side_effect=AssertionError('duplicate sales')), \
             patch.object(report.follow, 'aggregate_pos_visits', side_effect=AssertionError('duplicate visits')), \
             patch.object(report.follow, '_build_product_sources', wraps=report.follow._build_product_sources) as products:
            response = self.client.get(self.url, {**self.filters, 'preset': 'full'})
            self.assertEqual(response.status_code, 200)
            products.assert_called_once()

    def test_empty_sections_skip_by_default_and_render_when_disabled(self):
        for auto_skip, expected in (('1', []), ('0', ['clients', 'unsold', 'product_alerts', 'actions'])):
            response = self.generate('clients,unsold,product_alerts,actions', auto_skip=auto_skip)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context['render_sections'], expected)
            if auto_skip == '1':
                self.assertNotContains(response, 'class="report-section')

    def test_first_selected_section_does_not_force_a_header_only_page(self):
        from pathlib import Path
        css = (Path(__file__).parent / 'static/dashboard/css/manager_print.css').read_text()
        self.assertIn('.meeting-report main > .page-section:first-child { break-before: auto; }', css)

    def test_zero_executive_kpis_remain(self):
        response = self.generate('overview')
        self.assertEqual(response.context['render_sections'], ['overview'])
        self.assertContains(response, 'إجمالي المبيعات')
        self.assertContains(response, '<strong>0.00</strong>')
        self.assertIsNone(response.context['overview_summary'].visit_success_percentage)

    def test_bad_selection_rejected_before_analytics(self):
        with patch.object(report, 'build_print_context') as build:
            for sections in ('overview,unknown', '', '__class__'):
                self.assertEqual(self.generate(sections).status_code, 400)
            build.assert_not_called()

    def test_detail_ignores_selection_parameters(self):
        response = self.client.get(reverse('dashboard:manager_print_detail'),
                                   {**self.filters, 'preset': 'invalid', 'sections': 'unknown'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'هذا تقرير تفصيلي وقد يحتوي عددًا كبيرًا من الصفحات.')
        self.assertNotIn('selected_sections', response.context)

    def test_development_generation_timings(self):
        from datetime import date
        from apps.fleet.models import Truck, TruckCrewAssignment
        from apps.workforce.models import Worker
        from apps.imports.models import ImportBatch, ImportBatchStatus, ImportReportType, ImportRow, ImportRowStatus

        # Synthetic approved fixtures live exclusively in Django's disposable test DB.
        trucks = []
        for i in range(5):
            truck = Truck.objects.create(internal_code=f"BENCH-{i}",
                                         registration_number=f"BENCH-REG-{i}", brand="Test", model="Test")
            worker = Worker.objects.create(employee_code=f"BENCH-{i}", first_name="Test", last_name=str(i))
            TruckCrewAssignment.objects.create(truck=truck, worker=worker,
                crew_role=TruckCrewAssignment.CrewRole.SELLER, is_primary_seller=True,
                start_date=date(2026, 8, 27), end_date=date(2026, 10, 22))
            trucks.append(truck)
        for report_index, report_type in enumerate((ImportReportType.SALES, ImportReportType.POS,
                ImportReportType.ITEMS, ImportReportType.OPENING_STOCK, ImportReportType.CHARGEMENT)):
            batch = ImportBatch.objects.create(brand=self.brand, report_type=report_type,
                period_start=date(2026, 8, 27),
                period_end=date(2026, 8, 27) if report_type == ImportReportType.OPENING_STOCK else date(2026, 10, 22),
                original_filename=f"benchmark-{report_type}.xlsx", worksheet_name="Sheet1", file_size_bytes=100,
                file_sha256=f"{report_index+1:064x}", content_sha256=f"{report_index+100:064x}",
                status=ImportBatchStatus.APPROVED, total_rows=200, accepted_rows=200, uploaded_by=self.manager)
            rows = []
            for i in range(200):
                van = trucks[i % 5].internal_code
                data = dict(van=van, van_normalized=van.casefold(), client=f"Client {i % 40}",
                            client_normalized=f"client {i % 40}")
                if report_type == ImportReportType.SALES:
                    data.update(sale_datetime="2026-09-01T10:00:00", total=str((i+1)*10))
                elif report_type == ImportReportType.POS:
                    data.update(visit_date="2026-09-01", ignoration_message="absent" if i % 3 else None,
                                ignoration_cause=None)
                else:
                    data.update(article=f"Product {i % 30}", article_normalized=f"product {i % 30}",
                                total_units=str(i % 2 if report_type == ImportReportType.ITEMS else 10))
                rows.append(ImportRow(batch=batch, excel_row_number=i+2, status=ImportRowStatus.ACCEPTED,
                    raw_data={}, cleaned_data=data, issues=[], row_sha256=f"{report_index*1000+i+1:064x}"))
            ImportRow.objects.bulk_create(rows)
        # End-to-end Django test-client timings, 1,000 approved synthetic rows.
        # Alternating order, warmup, medians; informational, no speed assertion.
        samples = {'quick': [], 'full': []}
        for iteration in range(8):
            for preset in (('quick', 'full') if iteration % 2 else ('full', 'quick')):
                start = perf_counter()
                response = self.client.get(self.url, {**self.filters, 'preset': preset})
                elapsed = perf_counter() - start
                self.assertEqual(response.status_code, 200)
                if iteration:
                    samples[preset].append(elapsed)
        self.assertEqual(response.context['overview_summary'].sale_record_count, 200)
        self.assertEqual(response.context['overview_summary'].pos_record_count, 200)
        print('SELECTIVE_PRINT_BENCHMARK 1000 synthetic rows, 5 sellers/trucks; 7 warm samples; '
              + '; '.join(f'{key} median={median(values):.6f}s' for key, values in samples.items()))
