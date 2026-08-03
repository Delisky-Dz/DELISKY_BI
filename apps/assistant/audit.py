from dataclasses import dataclass
from datetime import date

from apps.assistant.models import (
    AskDeliskyAuditEvent,
    AskDeliskyAuditScope,
)


@dataclass(frozen=True, slots=True)
class AskDeliskyAuditRecord:
    outcome: str
    http_status: int
    scope: str = AskDeliskyAuditScope.MANAGER_ASK
    duration_ms: int | None = None
    period_start: date | None = None
    period_end: date | None = None
    brand_id: int | None = None


def record_ask_delisky_audit_event(
    *,
    user,
    record: AskDeliskyAuditRecord,
) -> AskDeliskyAuditEvent:
    return AskDeliskyAuditEvent.objects.create(
        scope=record.scope,
        user=user,
        period_start=record.period_start,
        period_end=record.period_end,
        brand_id_value=record.brand_id,
        outcome=record.outcome,
        http_status=record.http_status,
        duration_ms=record.duration_ms,
    )
