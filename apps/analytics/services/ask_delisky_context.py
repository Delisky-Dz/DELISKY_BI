from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from .manager_insights import (
    InsightEvidence,
    InsightEntityRef,
    InsightLimitation,
    ManagerInsight,
)
from .manager_insights_orchestrator import (
    ManagerInsightsResult,
)


AskDeliskyValue = int | str | bool
AskDeliskyEntityId = int | str


@dataclass(frozen=True, slots=True)
class AskDeliskyEvidence:
    key: str
    label: str
    value: AskDeliskyValue
    unit: str
    period_start: str | None
    period_end: str | None

    def to_payload(self) -> dict[str, object]:
        return {
            "key": self.key,
            "label": self.label,
            "value": self.value,
            "unit": self.unit,
            "period_start": self.period_start,
            "period_end": self.period_end,
        }


@dataclass(frozen=True, slots=True)
class AskDeliskyEntity:
    entity_type: str
    entity_id: AskDeliskyEntityId
    label: str

    def to_payload(self) -> dict[str, object]:
        return {
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "label": self.label,
        }


@dataclass(frozen=True, slots=True)
class AskDeliskyLimitation:
    code: str
    message: str

    def to_payload(self) -> dict[str, str]:
        return {
            "code": self.code,
            "message": self.message,
        }


@dataclass(frozen=True, slots=True)
class AskDeliskyInsight:
    code: str
    category: str
    severity: str
    confidence: str
    title: str
    summary: str
    period_start: str | None
    period_end: str | None
    evidence: tuple[AskDeliskyEvidence, ...]
    entities: tuple[AskDeliskyEntity, ...]
    limitations: tuple[AskDeliskyLimitation, ...]

    def to_payload(self) -> dict[str, object]:
        return {
            "code": self.code,
            "category": self.category,
            "severity": self.severity,
            "confidence": self.confidence,
            "title": self.title,
            "summary": self.summary,
            "period_start": self.period_start,
            "period_end": self.period_end,
            "evidence": [
                item.to_payload()
                for item in self.evidence
            ],
            "entities": [
                item.to_payload()
                for item in self.entities
            ],
            "limitations": [
                item.to_payload()
                for item in self.limitations
            ],
        }


@dataclass(frozen=True, slots=True)
class AskDeliskyContext:
    schema_version: str
    requested_period_start: str | None
    requested_period_end: str | None
    brand_id: int | None
    insights: tuple[AskDeliskyInsight, ...]

    @property
    def insight_count(self) -> int:
        return len(self.insights)

    @property
    def has_insights(self) -> bool:
        return bool(self.insights)

    def to_payload(self) -> dict[str, object]:
        """
        Return the provider-safe analytical payload.

        The payload intentionally contains only the deterministic
        insight contract. Internal evidence source paths, ORM
        objects, raw import rows and application configuration are
        not exposed.
        """
        return {
            "schema_version": self.schema_version,
            "scope": {
                "period_start": self.requested_period_start,
                "period_end": self.requested_period_end,
                "brand_id": self.brand_id,
            },
            "insights": [
                insight.to_payload()
                for insight in self.insights
            ],
        }


def _serialize_brand_id(
    value: int | None,
) -> int | None:
    if value is None:
        return None

    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(
            "Ask DELISKY brand_id must be an integer or None."
        )

    return value


def _serialize_entity_id(
    value: int | str,
) -> AskDeliskyEntityId:
    if isinstance(value, bool):
        raise TypeError(
            "Ask DELISKY entity_id cannot be boolean."
        )

    if isinstance(value, int):
        return value

    if isinstance(value, str):
        if not value.strip():
            raise ValueError(
                "Ask DELISKY entity_id cannot be empty."
            )

        return value

    raise TypeError(
        "Unsupported Ask DELISKY entity_id type."
    )


def _serialize_date(
    value: date | None,
) -> str | None:
    if value is None:
        return None

    return value.isoformat()


def _serialize_value(
    value: Decimal | int | str | bool,
) -> AskDeliskyValue:
    # bool must be checked before int because bool subclasses int.
    if isinstance(value, bool):
        return value

    if isinstance(value, int):
        return value

    if isinstance(value, Decimal):
        # Keep decimal precision deterministic and avoid binary
        # floating-point conversion in the provider payload.
        return format(value, "f")

    if isinstance(value, str):
        return value

    raise TypeError(
        "Unsupported Ask DELISKY evidence value type."
    )


def _convert_evidence(
    evidence: InsightEvidence,
) -> AskDeliskyEvidence:
    return AskDeliskyEvidence(
        key=evidence.key,
        label=evidence.label,
        value=_serialize_value(evidence.value),
        unit=evidence.unit,
        period_start=_serialize_date(
            evidence.period_start
        ),
        period_end=_serialize_date(
            evidence.period_end
        ),
    )


def _convert_entity(
    entity: InsightEntityRef,
) -> AskDeliskyEntity:
    return AskDeliskyEntity(
        entity_type=entity.entity_type.value,
        entity_id=_serialize_entity_id(
            entity.entity_id
        ),
        label=entity.label,
    )


def _convert_limitation(
    limitation: InsightLimitation,
) -> AskDeliskyLimitation:
    return AskDeliskyLimitation(
        code=limitation.code,
        message=limitation.message,
    )


def _convert_insight(
    insight: ManagerInsight,
) -> AskDeliskyInsight:
    return AskDeliskyInsight(
        code=insight.code,
        category=insight.category.value,
        severity=insight.severity.value,
        confidence=insight.confidence.value,
        title=insight.title,
        summary=insight.summary,
        period_start=_serialize_date(
            insight.period_start
        ),
        period_end=_serialize_date(
            insight.period_end
        ),
        evidence=tuple(
            _convert_evidence(item)
            for item in insight.evidence
        ),
        entities=tuple(
            _convert_entity(item)
            for item in insight.entities
        ),
        limitations=tuple(
            _convert_limitation(item)
            for item in insight.limitations
        ),
    )


def build_ask_delisky_context(
    *,
    insights_result: ManagerInsightsResult,
) -> AskDeliskyContext:
    """
    Convert deterministic manager insights into the minimum
    provider-safe context allowed for Ask DELISKY.

    This function performs no database access and sends no data to
    any external or local language-model provider.
    """
    return AskDeliskyContext(
        schema_version="1",
        requested_period_start=_serialize_date(
            insights_result.requested_period_start
        ),
        requested_period_end=_serialize_date(
            insights_result.requested_period_end
        ),
        brand_id=_serialize_brand_id(
            insights_result.brand_id
        ),
        insights=tuple(
            _convert_insight(insight)
            for insight in insights_result.insights
        ),
    )
