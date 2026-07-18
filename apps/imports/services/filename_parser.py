from dataclasses import dataclass
from datetime import date
from pathlib import Path
import re


REPORT_NAME_TO_TYPE = {
    "openingstock": "OPENING_STOCK",
    "chargement": "CHARGEMENT",
    "sales": "SALES",
    "items": "ITEMS",
    "pos": "POS",
}


FILENAME_PATTERN = re.compile(
    r"^(?P<report>"
    r"OpeningStock|Chargement|Sales|Items|PoS"
    r")_"
    r"(?P<brand>[A-Za-z0-9][A-Za-z0-9_-]*?)_"
    r"(?P<period_start>\d{4}-\d{2}-\d{2})"
    r"(?:_(?P<period_end>\d{4}-\d{2}-\d{2}))?"
    r"\.xlsx$",
    flags=re.IGNORECASE,
)


class ImportFilenameError(ValueError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: dict | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


@dataclass(frozen=True, slots=True)
class ParsedImportFilename:
    filename: str
    report_type: str
    brand_code: str
    period_start: date
    period_end: date


def _parse_iso_date(
    value: str,
    *,
    field_name: str,
) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ImportFilenameError(
            "invalid_date",
            "The filename contains an invalid date.",
            details={
                "field": field_name,
                "value": value,
            },
        ) from exc


def parse_import_filename(
    filename: str | Path,
) -> ParsedImportFilename:
    basename = Path(str(filename)).name
    match = FILENAME_PATTERN.fullmatch(basename)

    if match is None:
        raise ImportFilenameError(
            "invalid_filename_format",
            (
                "The filename does not match the official "
                "DELISKY BI import format."
            ),
            details={
                "filename": basename,
            },
        )

    report_name = match.group("report")
    report_type = REPORT_NAME_TO_TYPE[
        report_name.casefold()
    ]

    brand_code = match.group("brand").upper()
    period_start = _parse_iso_date(
        match.group("period_start"),
        field_name="period_start",
    )

    period_end_text = match.group("period_end")

    if report_type == "OPENING_STOCK":
        if period_end_text is not None:
            raise ImportFilenameError(
                "unexpected_period_end",
                (
                    "OpeningStock filenames must contain "
                    "one date only."
                ),
                details={
                    "filename": basename,
                },
            )

        period_end = period_start
    else:
        if period_end_text is None:
            raise ImportFilenameError(
                "missing_period_end",
                (
                    "This report filename must contain "
                    "a start date and an end date."
                ),
                details={
                    "filename": basename,
                    "report_type": report_type,
                },
            )

        period_end = _parse_iso_date(
            period_end_text,
            field_name="period_end",
        )

    if period_end < period_start:
        raise ImportFilenameError(
            "invalid_period",
            (
                "The filename period end cannot be "
                "earlier than its start."
            ),
            details={
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
            },
        )

    return ParsedImportFilename(
        filename=basename,
        report_type=report_type,
        brand_code=brand_code,
        period_start=period_start,
        period_end=period_end,
    )
