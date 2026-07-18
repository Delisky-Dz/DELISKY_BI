from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.imports.services import (
    ExcelInspectionError,
    inspect_excel_file,
)


class Command(BaseCommand):
    help = (
        "Inspect an Excel workbook without saving "
        "any extracted data."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "file_path",
            help="Full or relative path to the .xlsx file.",
        )

    def handle(self, *args, **options):
        file_path = Path(options["file_path"]).expanduser()

        if not file_path.exists():
            raise CommandError(
                f"File does not exist: {file_path}"
            )

        if not file_path.is_file():
            raise CommandError(
                f"Path is not a file: {file_path}"
            )

        try:
            result = inspect_excel_file(file_path)
        except ExcelInspectionError as exc:
            self.stderr.write(
                self.style.ERROR(
                    f"Inspection failed [{exc.code}]: "
                    f"{exc.message}"
                )
            )

            if exc.details:
                self.stderr.write(
                    f"Details: {exc.details}"
                )

            raise CommandError(
                "Excel inspection did not complete."
            ) from exc

        self.stdout.write(
            self.style.SUCCESS(
                "Excel inspection completed successfully."
            )
        )

        self.stdout.write(
            f"Filename: {result.filename}"
        )
        self.stdout.write(
            f"File size: {result.file_size_bytes} bytes"
        )
        self.stdout.write(
            f"Worksheet count: {result.worksheet_count}"
        )

        for index, worksheet in enumerate(
            result.worksheets,
            start=1,
        ):
            self.stdout.write("")
            self.stdout.write(
                self.style.MIGRATE_HEADING(
                    f"Worksheet {index}: {worksheet.name}"
                )
            )
            self.stdout.write(
                f"Header row: {worksheet.header_row_number}"
            )
            self.stdout.write(
                f"Columns: {worksheet.column_count}"
            )
            self.stdout.write(
                f"Data rows: {worksheet.data_row_count}"
            )
            self.stdout.write(
                f"Blank rows: {worksheet.blank_row_count}"
            )
            self.stdout.write(
                f"Headers: {list(worksheet.headers)}"
            )
            self.stdout.write(
                "Empty header positions: "
                f"{list(worksheet.empty_header_positions)}"
            )
            self.stdout.write(
                "Duplicate headers: "
                f"{list(worksheet.duplicate_headers)}"
            )
