from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import (
    SimpleUploadedFile,
)
from django.test import TestCase
from django.urls import reverse


class RawItemsDetailAccountantViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()

        accountant_group = Group.objects.create(
            name="Accountant"
        )
        cls.accountant = user_model.objects.create_user(
            username="items-detail-accountant",
            password="test-pass-123",
            is_active=True,
        )
        cls.accountant.groups.add(accountant_group)

        manager_group = Group.objects.create(
            name="Manager"
        )
        cls.manager = user_model.objects.create_user(
            username="items-detail-manager",
            password="test-pass-123",
            is_active=True,
        )
        cls.manager.groups.add(manager_group)

    def make_upload(self, filename):
        return SimpleUploadedFile(
            filename,
            b"temporary-items-detail-content",
            content_type=(
                "application/vnd.openxmlformats-"
                "officedocument.spreadsheetml.sheet"
            ),
        )

    def login_accountant(self):
        self.client.force_login(self.accountant)

    @patch(
        "apps.imports.views."
        "create_raw_items_detail_multi_import_reviews"
    )
    def test_valid_detail_form_calls_multi_service(
        self,
        multi_review_mock,
    ):
        self.login_accountant()

        multi_review_mock.return_value = (
            SimpleNamespace(
                files=(),
                succeeded_count=2,
                failed_count=0,
            )
        )

        response = self.client.post(
            reverse(
                "imports:raw_items_detail_upload"
            ),
            data={
                "period_start": "2026-04-04",
                "period_end": "2026-08-26",
                "bifa_file": self.make_upload(
                    "BIFA_Items_DETAIL_2026-04-04_to_2026-08-26.xlsx"
                ),
                "aio_file": self.make_upload(
                    "AIO_Items_DETAIL_2026-04-04_to_2026-08-26.xlsx"
                ),
            },
        )

        self.assertEqual(response.status_code, 200)
        multi_review_mock.assert_called_once()

        requests = tuple(
            multi_review_mock.call_args.args[0]
        )
        self.assertEqual(len(requests), 2)

        self.assertEqual(
            requests[0].source_system_code,
            "BIFA_MILA",
        )
        self.assertEqual(
            requests[1].source_system_code,
            "AIO_WEB",
        )
        self.assertEqual(
            requests[0].period_start.isoformat(),
            "2026-04-04",
        )
        self.assertEqual(
            requests[0].period_end.isoformat(),
            "2026-08-26",
        )
        self.assertEqual(
            multi_review_mock.call_args.kwargs[
                "uploaded_by"
            ],
            self.accountant,
        )
        self.assertEqual(
            multi_review_mock.call_args.kwargs[
                "reviewed_by"
            ],
            self.accountant,
        )

    @patch(
        "apps.imports.views."
        "create_raw_items_detail_multi_import_reviews"
    )
    def test_detail_form_requires_at_least_one_file(
        self,
        multi_review_mock,
    ):
        self.login_accountant()

        response = self.client.post(
            reverse(
                "imports:raw_items_detail_upload"
            ),
            data={
                "period_start": "2026-04-04",
                "period_end": "2026-08-26",
            },
        )

        self.assertEqual(response.status_code, 200)
        multi_review_mock.assert_not_called()
        self.assertFalse(
            response.context[
                "items_detail_upload_form"
            ].is_valid()
        )

    def test_manager_cannot_upload_items_detail(self):
        self.client.force_login(self.manager)

        response = self.client.post(
            reverse(
                "imports:raw_items_detail_upload"
            ),
            data={},
        )

        self.assertEqual(response.status_code, 403)

    def test_accountant_home_renders_items_detail_panel(self):
        self.login_accountant()

        response = self.client.get(
            reverse("imports:accountant_home")
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "items_detail_upload_form",
            response.context,
        )
        self.assertContains(
            response,
            reverse(
                "imports:raw_items_detail_upload"
            ),
        )
        self.assertContains(
            response,
            'id="raw-items-detail-import"',
        )
        self.assertContains(
            response,
            'name="bifa_file"',
        )
        self.assertContains(
            response,
            'name="aio_file"',
        )

    @patch(
        "apps.imports.views."
        "create_raw_items_detail_multi_import_reviews"
    )
    def test_detail_results_render_all_derived_batches(
        self,
        multi_review_mock,
    ):
        self.login_accountant()

        delisky = SimpleNamespace(
            id=701,
            status="REVIEWED",
            brand=SimpleNamespace(code="DELISKY"),
            total_rows=23020,
            accepted_rows=23020,
            excluded_rows=0,
            warning_count=2,
            error_count=0,
        )
        nita = SimpleNamespace(
            id=702,
            status="REVIEWED",
            brand=SimpleNamespace(code="NITA"),
            total_rows=31998,
            accepted_rows=31998,
            excluded_rows=0,
            warning_count=586,
            error_count=0,
        )

        multi_review_mock.return_value = (
            SimpleNamespace(
                files=(
                    SimpleNamespace(
                        filename=(
                            "AIO_Items_DETAIL_"
                            "2026-04-04_to_2026-08-26.xlsx"
                        ),
                        succeeded=True,
                        batches=(delisky, nita),
                        error_code=None,
                        error_message=None,
                    ),
                ),
                succeeded_count=1,
                failed_count=0,
            )
        )

        response = self.client.post(
            reverse(
                "imports:raw_items_detail_upload"
            ),
            data={
                "period_start": "2026-04-04",
                "period_end": "2026-08-26",
                "aio_file": self.make_upload(
                    "AIO_Items_DETAIL_"
                    "2026-04-04_to_2026-08-26.xlsx"
                ),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "DELISKY")
        self.assertContains(response, "NITA")
        self.assertContains(
            response,
            reverse(
                "imports:batch_detail",
                args=[701],
            ),
        )
        self.assertContains(
            response,
            reverse(
                "imports:batch_detail",
                args=[702],
            ),
        )
