import math
import os
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta

from django.db import transaction
from django.utils import timezone

from .models import AskDeliskyRateLimit


ASK_DELISKY_MANAGER_SCOPE = "manager_ask"
MARKETING_HELPER_SCOPE = "marketing_helper"


class AskDeliskyRateLimitConfigurationError(
    RuntimeError
):
    """Ask DELISKY rate-limit configuration is invalid."""


@dataclass(frozen=True, slots=True)
class AskDeliskyRateLimitConfig:
    requests: int = 5
    window_seconds: int = 60

    def __post_init__(self) -> None:
        for name, value in (
            ("requests", self.requests),
            (
                "window_seconds",
                self.window_seconds,
            ),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value < 1
            ):
                raise ValueError(
                    f"{name} must be a positive integer."
                )


@dataclass(frozen=True, slots=True)
class AskDeliskyRateLimitResult:
    allowed: bool
    retry_after_seconds: int = 0


def _parse_positive_integer(
    *,
    raw_value: str,
    variable_name: str,
) -> int:
    try:
        value = int(raw_value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"{variable_name} must be an integer."
        ) from exc

    if value < 1:
        raise ValueError(
            f"{variable_name} must be positive."
        )

    return value


def load_ask_delisky_rate_limit_config(
    *,
    environ: Mapping[str, str] | None = None,
) -> AskDeliskyRateLimitConfig:
    source = (
        os.environ
        if environ is None
        else environ
    )

    try:
        requests = _parse_positive_integer(
            raw_value=source.get(
                "ASK_DELISKY_RATE_LIMIT_REQUESTS",
                "5",
            ),
            variable_name=(
                "ASK_DELISKY_RATE_LIMIT_REQUESTS"
            ),
        )

        window_seconds = _parse_positive_integer(
            raw_value=source.get(
                "ASK_DELISKY_RATE_LIMIT_WINDOW_SECONDS",
                "60",
            ),
            variable_name=(
                "ASK_DELISKY_RATE_LIMIT_WINDOW_SECONDS"
            ),
        )
    except ValueError as exc:
        raise AskDeliskyRateLimitConfigurationError(
            "Ask DELISKY rate-limit configuration "
            "is invalid."
        ) from exc

    return AskDeliskyRateLimitConfig(
        requests=requests,
        window_seconds=window_seconds,
    )


def check_ask_delisky_rate_limit(
    *,
    user,
    scope: str = ASK_DELISKY_MANAGER_SCOPE,
    now: datetime | None = None,
    environ: Mapping[str, str] | None = None,
) -> AskDeliskyRateLimitResult:
    if user.pk is None:
        raise ValueError(
            "Rate-limited user must be saved."
        )

    config = load_ask_delisky_rate_limit_config(
        environ=environ
    )

    current_time = (
        timezone.now()
        if now is None
        else now
    )

    with transaction.atomic():
        AskDeliskyRateLimit.objects.get_or_create(
            user=user,
            scope=scope,
            defaults={
                "window_started_at": current_time,
                "request_count": 0,
            },
        )

        bucket = (
            AskDeliskyRateLimit.objects
            .select_for_update()
            .get(
                user=user,
                scope=scope,
            )
        )

        window_end = (
            bucket.window_started_at
            + timedelta(
                seconds=config.window_seconds
            )
        )

        if current_time >= window_end:
            bucket.window_started_at = (
                current_time
            )
            bucket.request_count = 1
            bucket.save(
                update_fields=[
                    "window_started_at",
                    "request_count",
                    "updated_at",
                ]
            )

            return AskDeliskyRateLimitResult(
                allowed=True
            )

        if (
            bucket.request_count
            < config.requests
        ):
            bucket.request_count += 1
            bucket.save(
                update_fields=[
                    "request_count",
                    "updated_at",
                ]
            )

            return AskDeliskyRateLimitResult(
                allowed=True
            )

        remaining_seconds = (
            window_end - current_time
        ).total_seconds()

        return AskDeliskyRateLimitResult(
            allowed=False,
            retry_after_seconds=max(
                1,
                math.ceil(
                    remaining_seconds
                ),
            ),
        )
