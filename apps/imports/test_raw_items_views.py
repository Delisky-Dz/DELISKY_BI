from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import (
    SimpleUploadedFile,
)
from django.test import TestCase
from django.urls import reverse


class RawItemsAccountantViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()

        accountant_group = Group.objects.create(
            name="Accountant"
        )

        cls.accountant = (
            user_model.objects.create_user(
                username="raw-items-accountant-view",
                password="test-pass-123",
                is_active=True,
            )
        )

        cls.accountant.groups.add(
            accountant_group
        )

        manager_group = Group.objects.create(
            name="Manager"
        )

        cls.manager = (
            user_model.objects.create_user(
                username="raw-items-manager-view",
                password="test-pass-123",
                is_active=True,
            )
        )

        cls.manager.groups.add(
            manager_group
        )

    def login_accountant(self):
        self.client.force_login(
            self.accountant
        )

    def make_upload(self, filename):
        return SimpleUploadedFile(
            filename,
            b"temporary-items-test-content",
            content_type=(
                "application/vnd.openxmlformats-"
                "officedocument.spreadsheetml.sheet"
            ),
        )

    @patch(
        "apps.imports.views."
        "create_raw_items_multi_import_reviews"
    )
    def test_valid_items_form_calls_multi_service(
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
                "imports:raw_items_upload"
            ),
            data={
                "period_start": "2026-08-01",
                "period_end": "2026-08-18",
                "bifa_files": [
                    self.make_upload(
                        "DCV-03 items.xlsx"
                    ),
                ],
                "aio_files": [
                    self.make_upload(
                        "VAN2-DELISKY items.xlsx"
                    ),
                ],
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        multi_review_mock.assert_called_once()

        requests = tuple(
            multi_review_mock.call_args.args[0]
        )

        self.assertEqual(
            len(requests),
            2,
        )

        self.assertEqual(
            requests[0].source_system_code,
            "BIFA_MILA",
        )
        self.assertEqual(
            requests[0].original_filename,
            "DCV-03 items.xlsx",
        )

        self.assertEqual(
            requests[1].source_system_code,
            "AIO_WEB",
        )
        self.assertEqual(
            requests[1].original_filename,
            "VAN2-DELISKY items.xlsx",
        )

        self.assertEqual(
            requests[0].period_start.isoformat(),
            "2026-08-01",
        )
        self.assertEqual(
            requests[0].period_end.isoformat(),
            "2026-08-18",
        )

        self.assertEqual(
            multi_review_mock.call_args.kwargs[
                "uploaded_by"
            ],
            self.accountant,
        )

    @patch(
        "apps.imports.views."
        "create_raw_items_multi_import_reviews"
    )
    def test_requires_at_least_one_items_file(
        self,
        multi_review_mock,
    ):
        self.login_accountant()

        response = self.client.post(
            reverse(
                "imports:raw_items_upload"
            ),
            data={
                "period_start": "2026-08-01",
                "period_end": "2026-08-18",
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )
        multi_review_mock.assert_not_called()

        self.assertFalse(
            response.context[
                "items_upload_form"
            ].is_valid()
        )

    def test_anonymous_items_upload_redirects(self):
        response = self.client.post(
            reverse(
                "imports:raw_items_upload"
            ),
            data={},
        )

        self.assertEqual(
            response.status_code,
            302,
        )

    def test_manager_cannot_upload_items(self):
        self.client.force_login(
            self.manager
        )

        response = self.client.post(
            reverse(
                "imports:raw_items_upload"
            ),
            data={},
        )

        self.assertEqual(
            response.status_code,
            403,
        )

    def test_accountant_home_renders_items_form(self):
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
            "items_upload_form",
            response.context,
        )

        self.assertContains(
            response,
            reverse(
                "imports:raw_items_upload"
            ),
        )

        self.assertContains(
            response,
            'id="raw-items-import"',
        )

        self.assertContains(
            response,
            'name="bifa_files"',
        )

        self.assertContains(
            response,
            'name="aio_files"',
        )

        self.assertContains(
            response,
            "multiple",
        )

    @patch(
        "apps.imports.views."
        "create_raw_items_multi_import_reviews"
    )
    def test_items_results_render_success_and_failure(
        self,
        multi_review_mock,
    ):
        self.login_accountant()

        batch = SimpleNamespace(
            id=501,
            status="REVIEWED",
            brand=SimpleNamespace(
                code="BIFA",
            ),
            total_rows=1565,
            accepted_rows=1565,
            excluded_rows=0,
            error_count=0,
        )

        multi_review_mock.return_value = (
            SimpleNamespace(
                files=(
                    SimpleNamespace(
                        filename=(
                            "DCV-03 items.xlsx"
                        ),
                        succeeded=True,
                        batch=batch,
                        error_code=None,
                        error_message=None,
                    ),
                    SimpleNamespace(
                        filename=(
                            "BAD items.xlsx"
                        ),
                        succeeded=False,
                        batch=None,
                        error_code=(
                            "source_truck_not_mapped"
                        ),
                        error_message=(
                            "Truck is not mapped."
                        ),
                    ),
                ),
                succeeded_count=1,
                failed_count=1,
            )
        )

        response = self.client.post(
            reverse(
                "imports:raw_items_upload"
            ),
            data={
                "period_start": "2026-08-01",
                "period_end": "2026-08-18",
                "bifa_files": [
                    self.make_upload(
                        "DCV-03 items.xlsx"
                    ),
                ],
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertContains(
            response,
            "DCV-03 items.xlsx",
        )
        self.assertContains(
            response,
            "BAD items.xlsx",
        )
        self.assertContains(
            response,
            "source_truck_not_mapped",
        )
        self.assertContains(
            response,
            reverse(
                "imports:batch_detail",
                args=[501],
            ),
        )
