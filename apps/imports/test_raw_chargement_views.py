from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from apps.imports.models import (
    ImportSourceSystem,
)


class RawChargementAccountantViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()

        accountant_group = Group.objects.create(
            name="Accountant"
        )

        cls.accountant = user_model.objects.create_user(
            username="raw-accountant-view",
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
            username="raw-manager-view",
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

    @patch(
        "apps.imports.views."
        "create_raw_chargement_derived_multi_import_reviews"
    )
    def test_valid_raw_formset_calls_multi_file_service(
        self,
        multi_review_mock,
    ):
        self.login_accountant()

        multi_review_mock.return_value = SimpleNamespace(
            files=(),
            succeeded_count=1,
            failed_count=0,
        )

        source_file = SimpleUploadedFile(
            "raw_chargement.xlsx",
            b"temporary-test-content",
            content_type=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
        )

        response = self.client.post(
            reverse(
                "imports:raw_chargement_upload"
            ),
            data={
                "raw-TOTAL_FORMS": "1",
                "raw-INITIAL_FORMS": "0",
                "raw-MIN_NUM_FORMS": "1",
                "raw-MAX_NUM_FORMS": "20",

                "raw-0-source_system": (
                    self.source_system.pk
                ),
                "raw-0-period_start": (
                    "2026-03-07"
                ),
                "raw-0-period_end": (
                    "2026-03-11"
                ),
                "raw-0-source_file": source_file,
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

        request_item = requests[0]

        self.assertFalse(
            hasattr(
                request_item,
                "brand_code",
            )
        )
        self.assertEqual(
            request_item.source_system_code,
            "AIO_WEB",
        )
        self.assertEqual(
            request_item.period_start.isoformat(),
            "2026-03-07",
        )
        self.assertEqual(
            request_item.period_end.isoformat(),
            "2026-03-11",
        )
        self.assertEqual(
            request_item.original_filename,
            "raw_chargement.xlsx",
        )
        self.assertEqual(
            request_item.source.name,
            "raw_chargement.xlsx",
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
        "create_raw_chargement_derived_multi_import_reviews"
    )
    def test_invalid_raw_formset_does_not_call_service(
        self,
        multi_review_mock,
    ):
        self.login_accountant()

        response = self.client.post(
            reverse(
                "imports:raw_chargement_upload"
            ),
            data={
                "raw-TOTAL_FORMS": "1",
                "raw-INITIAL_FORMS": "0",
                "raw-MIN_NUM_FORMS": "1",
                "raw-MAX_NUM_FORMS": "20",

                "raw-0-source_system": (
                    self.source_system.pk
                ),
                "raw-0-period_start": (
                    "2026-03-07"
                ),
                "raw-0-period_end": (
                    "2026-03-11"
                ),
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        multi_review_mock.assert_not_called()

        formset = response.context[
            "raw_upload_formset"
        ]

        self.assertFalse(
            formset.is_valid()
        )
        self.assertIn(
            "source_file",
            formset.forms[0].errors,
        )

    def test_anonymous_raw_upload_redirects_to_login(self):
        response = self.client.post(
            reverse(
                "imports:raw_chargement_upload"
            ),
            data={},
        )

        self.assertEqual(
            response.status_code,
            302,
        )

    def test_manager_cannot_use_raw_upload_endpoint(self):
        self.client.force_login(
            self.manager
        )

        response = self.client.post(
            reverse(
                "imports:raw_chargement_upload"
            ),
            data={},
        )

        self.assertEqual(
            response.status_code,
            403,
        )

    def test_accountant_home_renders_raw_multi_file_form(self):
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
            "raw_upload_formset",
            response.context,
        )

        self.assertContains(
            response,
            'action="'
            + reverse(
                "imports:raw_chargement_upload"
            )
            + '"',
        )

        self.assertContains(
            response,
            'name="raw-TOTAL_FORMS"',
        )

        self.assertContains(
            response,
            'id="raw-form-list"',
        )

        self.assertContains(
            response,
            'id="raw-add-file"',
        )

    @patch(
        "apps.imports.views."
        "create_raw_chargement_derived_multi_import_reviews"
    )
    def test_mixed_raw_result_renders_all_derived_batches(
        self,
        multi_review_mock,
    ):
        self.login_accountant()

        delisky_batch = SimpleNamespace(
            id=101,
            brand=SimpleNamespace(
                code="DELISKY",
            ),
        )
        nita_batch = SimpleNamespace(
            id=202,
            brand=SimpleNamespace(
                code="NITA",
            ),
        )

        multi_review_mock.return_value = SimpleNamespace(
            files=(
                SimpleNamespace(
                    original_filename="mixed.xlsx",
                    succeeded=True,
                    batches=(
                        delisky_batch,
                        nita_batch,
                    ),
                    error_code=None,
                    error_message=None,
                ),
            ),
            succeeded_count=1,
            failed_count=0,
        )

        source_file = SimpleUploadedFile(
            "mixed.xlsx",
            b"temporary-test-content",
            content_type=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
        )

        response = self.client.post(
            reverse(
                "imports:raw_chargement_upload"
            ),
            data={
                "raw-TOTAL_FORMS": "1",
                "raw-INITIAL_FORMS": "0",
                "raw-MIN_NUM_FORMS": "1",
                "raw-MAX_NUM_FORMS": "20",
                "raw-0-source_system": (
                    self.source_system.pk
                ),
                "raw-0-period_start": "2026-03-07",
                "raw-0-period_end": "2026-03-11",
                "raw-0-source_file": source_file,
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertNotContains(
            response,
            'name="raw-0-brand"',
        )

        self.assertContains(
            response,
            reverse(
                "imports:batch_detail",
                args=[delisky_batch.id],
            ),
        )

        self.assertContains(
            response,
            reverse(
                "imports:batch_detail",
                args=[nita_batch.id],
            ),
        )

        rendered = response.content.decode("utf-8")

        self.assertRegex(
            rendered,
            "\u0641\u062a\u062d\\s+"
            "\u0645\u0631\u0627\u062c\u0639\u0629\\s+"
            "DELISKY",
        )
        self.assertRegex(
            rendered,
            "\u0641\u062a\u062d\\s+"
            "\u0645\u0631\u0627\u062c\u0639\u0629\\s+"
            "NITA",
        )
