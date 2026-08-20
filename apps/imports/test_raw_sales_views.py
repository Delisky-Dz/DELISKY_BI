from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from apps.imports.models import ImportSourceSystem


class RawSalesAccountantViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()

        accountant_group = Group.objects.create(
            name="Accountant"
        )

        cls.accountant = user_model.objects.create_user(
            username="raw-sales-accountant-view",
            password="test-pass-123",
            is_active=True,
        )
        cls.accountant.groups.add(
            accountant_group
        )

        manager_group = Group.objects.create(
            name="Manager"
        )

        cls.manager = user_model.objects.create_user(
            username="raw-sales-manager-view",
            password="test-pass-123",
            is_active=True,
        )
        cls.manager.groups.add(
            manager_group
        )

        cls.source_system = (
            ImportSourceSystem.objects.create(
                code="AIO_WEB",
                name="AIO-WEB",
                is_active=True,
            )
        )

    def login_accountant(self):
        self.client.force_login(
            self.accountant
        )

    def make_upload(self, filename):
        return SimpleUploadedFile(
            filename,
            b"temporary-test-content",
            content_type=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
        )

    @patch(
        "apps.imports.views."
        "create_raw_sales_multi_import_reviews"
    )
    def test_valid_sales_formset_calls_multi_file_service(
        self,
        multi_review_mock,
    ):
        self.login_accountant()

        multi_review_mock.return_value = SimpleNamespace(
            files=(),
            succeeded_count=1,
            failed_count=0,
        )

        response = self.client.post(
            reverse(
                "imports:raw_sales_upload"
            ),
            data={
                "sales-TOTAL_FORMS": "1",
                "sales-INITIAL_FORMS": "0",
                "sales-MIN_NUM_FORMS": "1",
                "sales-MAX_NUM_FORMS": "20",
                "sales-0-source_system": (
                    self.source_system.pk
                ),
                "sales-0-period_start": (
                    "2026-08-01"
                ),
                "sales-0-period_end": (
                    "2026-08-18"
                ),
                "sales-0-source_file": (
                    self.make_upload(
                        "VAN2-NITA.xlsx"
                    )
                ),
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        multi_review_mock.assert_called_once()

        args = multi_review_mock.call_args.args
        kwargs = multi_review_mock.call_args.kwargs

        requests = tuple(args[0])

        self.assertEqual(
            len(requests),
            1,
        )

        item = requests[0]

        self.assertEqual(
            item.source_system_code,
            "AIO_WEB",
        )
        self.assertEqual(
            item.period_start.isoformat(),
            "2026-08-01",
        )
        self.assertEqual(
            item.period_end.isoformat(),
            "2026-08-18",
        )
        self.assertEqual(
            item.original_filename,
            "VAN2-NITA.xlsx",
        )
        self.assertEqual(
            item.source.name,
            "VAN2-NITA.xlsx",
        )

        self.assertEqual(
            kwargs["uploaded_by"],
            self.accountant,
        )
        self.assertEqual(
            kwargs["reviewed_by"],
            self.accountant,
        )

    @patch(
        "apps.imports.views."
        "create_raw_sales_multi_import_reviews"
    )
    def test_invalid_sales_formset_does_not_call_service(
        self,
        multi_review_mock,
    ):
        self.login_accountant()

        response = self.client.post(
            reverse(
                "imports:raw_sales_upload"
            ),
            data={
                "sales-TOTAL_FORMS": "1",
                "sales-INITIAL_FORMS": "0",
                "sales-MIN_NUM_FORMS": "1",
                "sales-MAX_NUM_FORMS": "20",
                "sales-0-source_system": (
                    self.source_system.pk
                ),
                "sales-0-period_start": (
                    "2026-08-01"
                ),
                "sales-0-period_end": (
                    "2026-08-18"
                ),
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        multi_review_mock.assert_not_called()

        formset = response.context[
            "sales_upload_formset"
        ]

        self.assertFalse(
            formset.is_valid()
        )
        self.assertIn(
            "source_file",
            formset.forms[0].errors,
        )

    def test_anonymous_sales_upload_redirects_to_login(self):
        response = self.client.post(
            reverse(
                "imports:raw_sales_upload"
            ),
            data={},
        )

        self.assertEqual(
            response.status_code,
            302,
        )

    def test_manager_cannot_use_sales_upload_endpoint(self):
        self.client.force_login(
            self.manager
        )

        response = self.client.post(
            reverse(
                "imports:raw_sales_upload"
            ),
            data={},
        )

        self.assertEqual(
            response.status_code,
            403,
        )

    def test_accountant_home_renders_sales_multi_file_form(self):
        self.login_accountant()

        response = self.client.get(
            reverse(
                "imports:accountant_home"
            )
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertIn(
            "sales_upload_formset",
            response.context,
        )

        self.assertContains(
            response,
            'action="'
            + reverse(
                "imports:raw_sales_upload"
            )
            + '"',
        )

        self.assertContains(
            response,
            'name="sales-TOTAL_FORMS"',
        )
        self.assertContains(
            response,
            'id="sales-form-list"',
        )
        self.assertContains(
            response,
            'id="sales-add-file"',
        )
        self.assertContains(
            response,
            'id="sales-empty-form-template"',
        )

    @patch(
        "apps.imports.views."
        "create_raw_sales_multi_import_reviews"
    )
    def test_sales_result_renders_reviewed_and_blocked_batches(
        self,
        multi_review_mock,
    ):
        self.login_accountant()

        reviewed_batch = SimpleNamespace(
            id=301,
            status="REVIEWED",
            brand=SimpleNamespace(
                code="DELISKY",
            ),
        )

        blocked_batch = SimpleNamespace(
            id=302,
            status="BLOCKED",
            brand=SimpleNamespace(
                code="NITA",
            ),
        )

        multi_review_mock.return_value = SimpleNamespace(
            files=(
                SimpleNamespace(
                    filename="VAN2-DELISKY.xlsx",
                    succeeded=True,
                    batch=reviewed_batch,
                    error_code=None,
                    error_message=None,
                ),
                SimpleNamespace(
                    filename="VAN2-NITA.xlsx",
                    succeeded=True,
                    batch=blocked_batch,
                    error_code=None,
                    error_message=None,
                ),
            ),
            succeeded_count=2,
            failed_count=0,
        )

        response = self.client.post(
            reverse(
                "imports:raw_sales_upload"
            ),
            data={
                "sales-TOTAL_FORMS": "1",
                "sales-INITIAL_FORMS": "0",
                "sales-MIN_NUM_FORMS": "1",
                "sales-MAX_NUM_FORMS": "20",
                "sales-0-source_system": (
                    self.source_system.pk
                ),
                "sales-0-period_start": (
                    "2026-08-01"
                ),
                "sales-0-period_end": (
                    "2026-08-18"
                ),
                "sales-0-source_file": (
                    self.make_upload(
                        "VAN2-DELISKY.xlsx"
                    )
                ),
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertContains(
            response,
            reverse(
                "imports:batch_detail",
                args=[reviewed_batch.id],
            ),
        )

        self.assertContains(
            response,
            reverse(
                "imports:batch_detail",
                args=[blocked_batch.id],
            ),
        )

        self.assertContains(
            response,
            "VAN2-DELISKY.xlsx",
        )
        self.assertContains(
            response,
            "VAN2-NITA.xlsx",
        )

    @patch(
        "apps.imports.views."
        "create_raw_sales_multi_import_reviews"
    )
    def test_failed_sales_file_renders_error_code(
        self,
        multi_review_mock,
    ):
        self.login_accountant()

        multi_review_mock.return_value = SimpleNamespace(
            files=(
                SimpleNamespace(
                    filename="VAN1-DELISKY.xlsx",
                    succeeded=False,
                    batch=None,
                    error_code="sale_outside_period",
                    error_message=(
                        "Sale date is outside period."
                    ),
                ),
            ),
            succeeded_count=0,
            failed_count=1,
        )

        response = self.client.post(
            reverse(
                "imports:raw_sales_upload"
            ),
            data={
                "sales-TOTAL_FORMS": "1",
                "sales-INITIAL_FORMS": "0",
                "sales-MIN_NUM_FORMS": "1",
                "sales-MAX_NUM_FORMS": "20",
                "sales-0-source_system": (
                    self.source_system.pk
                ),
                "sales-0-period_start": (
                    "2026-08-01"
                ),
                "sales-0-period_end": (
                    "2026-08-18"
                ),
                "sales-0-source_file": (
                    self.make_upload(
                        "VAN1-DELISKY.xlsx"
                    )
                ),
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )
        self.assertContains(
            response,
            "sale_outside_period",
        )
