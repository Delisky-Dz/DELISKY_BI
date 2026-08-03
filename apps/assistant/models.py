"""Database models for the DELISKY assistant."""

from django.conf import settings
from django.db import models


class AskDeliskyRateLimit(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="+",
    )
    scope = models.CharField(
        max_length=64,
    )
    window_started_at = models.DateTimeField()
    request_count = models.PositiveIntegerField(
        default=0,
    )
    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "user",
                    "scope",
                ],
                name="ask_rate_user_scope_uniq",
            ),
        ]

    def __str__(self):
        return (
            f"{self.user_id}:"
            f"{self.scope}:"
            f"{self.request_count}"
        )



class AskDeliskyAuditScope(models.TextChoices):
    MANAGER_ASK = "manager_ask", "Ask DELISKY"
    MARKETING_HELPER = (
        "marketing_helper",
        "Marketing helper",
    )


class AskDeliskyAuditOutcome(models.TextChoices):
    SUCCESS = "SUCCESS", "Success"
    INVALID_REQUEST = "INVALID_REQUEST", "Invalid request"
    RATE_LIMITED = "RATE_LIMITED", "Rate limited"
    RATE_LIMIT_CONFIGURATION_ERROR = (
        "RATE_LIMIT_CONFIGURATION_ERROR",
        "Rate-limit configuration error",
    )
    PROVIDER_CONFIGURATION_ERROR = (
        "PROVIDER_CONFIGURATION_ERROR",
        "Provider configuration error",
    )
    PROVIDER_DISABLED = (
        "PROVIDER_DISABLED",
        "Provider disabled",
    )
    PROVIDER_UNAVAILABLE = (
        "PROVIDER_UNAVAILABLE",
        "Provider unavailable",
    )


class AskDeliskyAuditEvent(models.Model):
    scope = models.CharField(
        max_length=32,
        choices=AskDeliskyAuditScope.choices,
        default=AskDeliskyAuditScope.MANAGER_ASK,
        db_index=True,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
    )
    period_start = models.DateField(
        null=True,
        blank=True,
    )
    period_end = models.DateField(
        null=True,
        blank=True,
    )
    brand_id_value = models.PositiveBigIntegerField(
        null=True,
        blank=True,
        db_index=True,
    )
    outcome = models.CharField(
        max_length=40,
        choices=AskDeliskyAuditOutcome.choices,
        db_index=True,
    )
    http_status = models.PositiveSmallIntegerField()
    duration_ms = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    class Meta:
        ordering = [
            "-created_at",
            "-pk",
        ]

    def __str__(self):
        return (
            f"{self.created_at}:"
            f"{self.user_id}:"
            f"{self.outcome}"
        )
