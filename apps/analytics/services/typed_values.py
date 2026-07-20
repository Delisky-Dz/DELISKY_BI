from datetime import date, datetime
from decimal import Decimal
from typing import Any, Mapping

from apps.imports.services.value_normalizers import (
    ValueNormalizationError,
    normalize_lookup_text,
    normalize_text,
    parse_date_value,
    parse_datetime_value,
    parse_decimal_value,
)


class AnalyticalValueError(ValueError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        field_name: str,
        raw_value: Any = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.field_name = field_name
        self.raw_value = raw_value


def read_optional_text(
    data: Mapping[str, Any],
    field_name: str,
) -> str | None:
    return normalize_text(
        data.get(field_name)
    )


def read_required_text(
    data: Mapping[str, Any],
    field_name: str,
) -> str:
    raw_value = data.get(field_name)
    value = normalize_text(raw_value)

    if value is None:
        raise AnalyticalValueError(
            "missing_text",
            f"The {field_name} value is required.",
            field_name=field_name,
            raw_value=raw_value,
        )

    return value


def read_optional_lookup_text(
    data: Mapping[str, Any],
    field_name: str,
) -> str | None:
    return normalize_lookup_text(
        data.get(field_name)
    )


def read_required_lookup_text(
    data: Mapping[str, Any],
    field_name: str,
) -> str:
    raw_value = data.get(field_name)
    value = normalize_lookup_text(raw_value)

    if value is None:
        raise AnalyticalValueError(
            "missing_lookup_text",
            f"The normalized {field_name} value is required.",
            field_name=field_name,
            raw_value=raw_value,
        )

    return value


def read_optional_decimal(
    data: Mapping[str, Any],
    field_name: str,
) -> Decimal | None:
    raw_value = data.get(field_name)

    try:
        return parse_decimal_value(raw_value)
    except ValueNormalizationError as exc:
        raise AnalyticalValueError(
            "invalid_decimal",
            f"The {field_name} value is not a valid decimal.",
            field_name=field_name,
            raw_value=raw_value,
        ) from exc


def read_required_decimal(
    data: Mapping[str, Any],
    field_name: str,
) -> Decimal:
    value = read_optional_decimal(
        data,
        field_name,
    )

    if value is None:
        raise AnalyticalValueError(
            "missing_decimal",
            f"The {field_name} decimal value is required.",
            field_name=field_name,
            raw_value=data.get(field_name),
        )

    return value


def read_optional_date(
    data: Mapping[str, Any],
    field_name: str,
) -> date | None:
    raw_value = data.get(field_name)

    try:
        return parse_date_value(raw_value)
    except ValueNormalizationError as exc:
        raise AnalyticalValueError(
            "invalid_date",
            f"The {field_name} value is not a valid date.",
            field_name=field_name,
            raw_value=raw_value,
        ) from exc


def read_required_date(
    data: Mapping[str, Any],
    field_name: str,
) -> date:
    value = read_optional_date(
        data,
        field_name,
    )

    if value is None:
        raise AnalyticalValueError(
            "missing_date",
            f"The {field_name} date value is required.",
            field_name=field_name,
            raw_value=data.get(field_name),
        )

    return value


def read_optional_datetime(
    data: Mapping[str, Any],
    field_name: str,
) -> datetime | None:
    raw_value = data.get(field_name)

    try:
        return parse_datetime_value(raw_value)
    except ValueNormalizationError as exc:
        raise AnalyticalValueError(
            "invalid_datetime",
            f"The {field_name} value is not a valid datetime.",
            field_name=field_name,
            raw_value=raw_value,
        ) from exc


def read_required_datetime(
    data: Mapping[str, Any],
    field_name: str,
) -> datetime:
    value = read_optional_datetime(
        data,
        field_name,
    )

    if value is None:
        raise AnalyticalValueError(
            "missing_datetime",
            f"The {field_name} datetime value is required.",
            field_name=field_name,
            raw_value=data.get(field_name),
        )

    return value
