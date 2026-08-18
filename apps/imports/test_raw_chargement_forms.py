from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils.datastructures import MultiValueDict

from apps.imports.forms import (
    RawChargementUploadForm,
    RawChargementUploadFormSet,
)
from apps.imports.models import (
    ImportSourceSystem,
)


class RawChargementUploadFormTests(TestCase):
    def setUp(self):
        self.aio = ImportSourceSystem.objects.create(
            code="AIO_WEB",
            name="AIO-WEB",
            is_active=True,
        )

        self.inactive_source = ImportSourceSystem.objects.create(
            code="OLD_SYSTEM",
            name="Old System",
            is_active=False,
        )

    def make_file(self, name="chargement.xlsx"):
        return SimpleUploadedFile(
            name,
            b"test-content",
            content_type=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
        )

    def test_accepts_valid_raw_chargement_metadata(self):
        form = RawChargementUploadForm(
            data={
                "source_system": self.aio.pk,
                "period_start": "2026-03-07",
                "period_end": "2026-03-11",
            },
            files={
                "source_file": self.make_file(),
            },
        )

        self.assertTrue(
            form.is_valid(),
            form.errors.as_json(),
        )

        self.assertEqual(
            form.cleaned_data["source_system"],
            self.aio,
        )
        self.assertEqual(
            form.cleaned_data["period_start"].isoformat(),
            "2026-03-07",
        )
        self.assertEqual(
            form.cleaned_data["period_end"].isoformat(),
            "2026-03-11",
        )

    def test_only_active_source_systems_are_available(self):
        form = RawChargementUploadForm()

        self.assertNotIn(
            "brand",
            form.fields,
        )

        self.assertEqual(
            list(
                form.fields["source_system"]
                .queryset
                .values_list("code", flat=True)
            ),
            ["AIO_WEB"],
        )

    def test_rejects_period_end_before_period_start(self):
        form = RawChargementUploadForm(
            data={
                "source_system": self.aio.pk,
                "period_start": "2026-03-11",
                "period_end": "2026-03-07",
            },
            files={
                "source_file": self.make_file(),
            },
        )

        self.assertFalse(form.is_valid())

        self.assertIn(
            "__all__",
            form.errors,
        )

    def test_rejects_non_xlsx_file(self):
        form = RawChargementUploadForm(
            data={
                "source_system": self.aio.pk,
                "period_start": "2026-03-07",
                "period_end": "2026-03-11",
            },
            files={
                "source_file": self.make_file(
                    "chargement.csv"
                ),
            },
        )

        self.assertFalse(form.is_valid())

        self.assertIn(
            "source_file",
            form.errors,
        )

    def test_formset_accepts_two_files_with_independent_metadata(self):
        bifa_system = ImportSourceSystem.objects.create(
            code="BIFA_MILA",
            name="BIFA MILA",
            is_active=True,
        )

        formset = RawChargementUploadFormSet(
            data={
                "raw-TOTAL_FORMS": "2",
                "raw-INITIAL_FORMS": "0",
                "raw-MIN_NUM_FORMS": "1",
                "raw-MAX_NUM_FORMS": "20",

                "raw-0-source_system": self.aio.pk,
                "raw-0-period_start": "2026-03-07",
                "raw-0-period_end": "2026-03-11",

                "raw-1-source_system": bifa_system.pk,
                "raw-1-period_start": "2026-03-14",
                "raw-1-period_end": "2026-03-18",
            },
            files=MultiValueDict(
                {
                    "raw-0-source_file": [
                        self.make_file(
                            "delisky.xlsx"
                        )
                    ],
                    "raw-1-source_file": [
                        self.make_file(
                            "nita.xlsx"
                        )
                    ],
                }
            ),
            prefix="raw",
        )

        self.assertTrue(
            formset.is_valid(),
            formset.errors,
        )

        self.assertEqual(
            len(formset.forms),
            2,
        )

        first = formset.forms[0].cleaned_data
        second = formset.forms[1].cleaned_data

        self.assertEqual(
            first["source_system"],
            self.aio,
        )
        self.assertEqual(
            first["period_start"].isoformat(),
            "2026-03-07",
        )
        self.assertEqual(
            first["period_end"].isoformat(),
            "2026-03-11",
        )

        self.assertEqual(
            second["source_system"],
            bifa_system,
        )
        self.assertEqual(
            second["period_start"].isoformat(),
            "2026-03-14",
        )
        self.assertEqual(
            second["period_end"].isoformat(),
            "2026-03-18",
        )

    def test_formset_rejects_more_than_twenty_files(self):
        data = {
            "raw-TOTAL_FORMS": "21",
            "raw-INITIAL_FORMS": "0",
            "raw-MIN_NUM_FORMS": "1",
            "raw-MAX_NUM_FORMS": "20",
        }

        files = MultiValueDict()

        for index in range(21):
            prefix = f"raw-{index}"

            data[f"{prefix}-source_system"] = (
                self.aio.pk
            )
            data[f"{prefix}-period_start"] = (
                "2026-03-07"
            )
            data[f"{prefix}-period_end"] = (
                "2026-03-11"
            )

            files.setlist(
                f"{prefix}-source_file",
                [
                    self.make_file(
                        f"chargement_{index}.xlsx"
                    )
                ],
            )

        formset = RawChargementUploadFormSet(
            data=data,
            files=files,
            prefix="raw",
        )

        self.assertFalse(
            formset.is_valid()
        )

        self.assertTrue(
            formset.non_form_errors()
        )


    def test_raw_form_does_not_require_brand_selection(self):
        form = RawChargementUploadForm(
            data={
                "source_system": self.aio.pk,
                "period_start": "2026-03-07",
                "period_end": "2026-03-11",
            },
            files={
                "source_file": self.make_file(),
            },
        )

        self.assertNotIn(
            "brand",
            form.fields,
        )

        self.assertTrue(
            form.is_valid(),
            form.errors.as_json(),
        )
