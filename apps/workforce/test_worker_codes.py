import re

from django.test import TestCase

from .models import Worker


class WorkerAutomaticCodeTests(TestCase):
    def create_worker(
        self,
        number,
        **extra_fields,
    ):
        values = {
            "first_name": f"Name{number}",
            "last_name": f"Family{number}",
        }

        values.update(extra_fields)

        return Worker.objects.create(
            **values
        )

    def test_blank_code_is_generated(self):
        worker = self.create_worker(1)

        self.assertRegex(
            worker.employee_code,
            r"^DW-\d{5}$",
        )

    def test_generated_codes_are_sequential(self):
        first_worker = self.create_worker(1)
        second_worker = self.create_worker(2)

        first_number = int(
            first_worker.employee_code.split(
                "-"
            )[1]
        )

        second_number = int(
            second_worker.employee_code.split(
                "-"
            )[1]
        )

        self.assertEqual(
            second_number,
            first_number + 1,
        )

    def test_generated_code_stays_unchanged(self):
        worker = self.create_worker(1)

        original_code = worker.employee_code

        worker.employee_code = "DW-99999"
        worker.phone = "0550000000"
        worker.save()

        worker.refresh_from_db()

        self.assertEqual(
            worker.employee_code,
            original_code,
        )

    def test_legacy_code_is_preserved_on_create(self):
        worker = self.create_worker(
            1,
            employee_code="LEGACY-15",
        )

        self.assertEqual(
            worker.employee_code,
            "LEGACY-15",
        )

    def test_generated_code_format_has_five_digits(self):
        worker = self.create_worker(1)

        match = re.fullmatch(
            r"DW-(\d{5})",
            worker.employee_code,
        )

        self.assertIsNotNone(match)
