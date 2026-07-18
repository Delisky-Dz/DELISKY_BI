from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from typing import Any
import math
import re
import unicodedata

from openpyxl.utils.datetime import (
    CALENDAR_WINDOWS_1900,
    from_excel,
)


DECIMAL_PATTERN = re.compile(
    r"^[+-]?\d+(?:[.,]\d+)?$"
)

DATETIME_FORMATS = (
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%d/%m/%Y",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d",
)


class ValueNormalizationError(ValueError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        value: Any = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.value = value


def is_blank_value(value: Any) -> bool:
    if value is None:
        return True

    if isinstance(value, str):
        return not value.strip()

    return False


def normalize_text(value: Any) -> str | None:
    if is_blank_value(value):
        return None

    text = unicodedata.normalize(
        "NFKC",
        str(value),
    )

    text = (
        text.replace("\u00a0", " ")
        .replace("\u2007", " ")
        .replace("\u202f", " ")
        .replace("\u2018", "'")
        .replace("\u2019", "'")
    )

    text = " ".join(text.split())

    return text or None


def normalize_lookup_text(value: Any) -> str | None:
    text = normalize_text(value)

    if text is None:
        return None

    return text.casefold()


def parse_decimal_value(
    value: Any,
) -> Decimal | None:
    if is_blank_value(value):
        return None

    if isinstance(value, bool):
        raise ValueNormalizationError(
            "invalid_number",
            "Boolean values are not valid numbers.",
            value=value,
        )

    if isinstance(value, Decimal):
        return value

    if isinstance(value, int):
        return Decimal(value)

    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueNormalizationError(
                "invalid_number",
                "The numeric value is not finite.",
                value=value,
            )

        return Decimal(str(value))

    text = normalize_text(value)

    if text is None:
        return None

    compact = (
        text.replace(" ", "")
        .replace("\u00a0", "")
    )

    if not DECIMAL_PATTERN.fullmatch(compact):
        raise ValueNormalizationError(
            "invalid_number",
            "The value is not a supported numeric format.",
            value=value,
        )

    compact = compact.replace(",", ".")

    try:
        return Decimal(compact)
    except InvalidOperation as exc:
        raise ValueNormalizationError(
            "invalid_number",
            "The value could not be converted to a number.",
            value=value,
        ) from exc


def _datetime_from_excel_number(
    value: Any,
) -> datetime:
    try:
        converted = from_excel(
            float(value),
            epoch=CALENDAR_WINDOWS_1900,
        )
    except (
        OverflowError,
        TypeError,
        ValueError,
    ) as exc:
        raise ValueNormalizationError(
            "invalid_datetime",
            "The Excel date number is invalid.",
            value=value,
        ) from exc

    if isinstance(converted, datetime):
        return converted

    if isinstance(converted, date):
        return datetime.combine(
            converted,
            time.min,
        )

    raise ValueNormalizationError(
        "invalid_datetime",
        "The Excel value does not contain a valid date.",
        value=value,
    )


def parse_datetime_value(
    value: Any,
) -> datetime | None:
    if is_blank_value(value):
        return None

    if isinstance(value, bool):
        raise ValueNormalizationError(
            "invalid_datetime",
            "Boolean values are not valid dates.",
            value=value,
        )

    if isinstance(value, datetime):
        return value.replace(tzinfo=None)

    if isinstance(value, date):
        return datetime.combine(
            value,
            time.min,
        )

    if isinstance(
        value,
        (int, float, Decimal),
    ):
        return _datetime_from_excel_number(value)

    text = normalize_text(value)

    if text is None:
        return None

    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        parsed = None

    if parsed is not None:
        return parsed.replace(tzinfo=None)

    for date_format in DATETIME_FORMATS:
        try:
            return datetime.strptime(
                text,
                date_format,
            )
        except ValueError:
            continue

    raise ValueNormalizationError(
        "invalid_datetime",
        "The value is not a supported date or datetime.",
        value=value,
    )


def parse_date_value(
    value: Any,
) -> date | None:
    parsed = parse_datetime_value(value)

    if parsed is None:
        return None

    return parsed.date()
