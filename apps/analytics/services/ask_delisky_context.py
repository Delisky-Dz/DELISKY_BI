from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from .manager_dashboard import ManagerDashboardSummary
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
class AskDeliskySummary:
    total_sales: str
    sale_record_count: int
    positive_sale_record_count: int
    zero_total_record_count: int
    average_sale_value: str | None
    average_positive_sale_value: str | None
    worker_count: int
    measured_sales_worker_count: int
    pos_record_count: int
    visited_record_count: int
    not_visited_record_count: int
    visit_success_ratio: str | None
    non_visit_ratio: str | None
    distinct_brand_client_count: int
    worker_not_sold_product_count: int
    truck_not_sold_product_count: int
    worker_negative_gap_product_count: int
    truck_negative_gap_product_count: int
    confirmed_stopped_truck_count: int
    possible_stopped_truck_count: int
    conflicting_truck_state_count: int

    def to_payload(self) -> dict[str, object]:
        return {
            "sales": {
                "total": self.total_sales,
                "currency": "DZD",
                "record_count": self.sale_record_count,
                "positive_record_count": (
                    self.positive_sale_record_count
                ),
                "zero_total_record_count": (
                    self.zero_total_record_count
                ),
                "average_record_value": (
                    self.average_sale_value
                ),
                "average_positive_record_value": (
                    self.average_positive_sale_value
                ),
            },
            "workers": {
                "count": self.worker_count,
                "measured_sales_count": (
                    self.measured_sales_worker_count
                ),
            },
            "visits": {
                "record_count": self.pos_record_count,
                "visited_record_count": (
                    self.visited_record_count
                ),
                "not_visited_record_count": (
                    self.not_visited_record_count
                ),
                "success_ratio": (
                    self.visit_success_ratio
                ),
                "non_visit_ratio": self.non_visit_ratio,
                "distinct_brand_client_count": (
                    self.distinct_brand_client_count
                ),
            },
            "products": {
                "worker_not_sold_count": (
                    self.worker_not_sold_product_count
                ),
                "truck_not_sold_count": (
                    self.truck_not_sold_product_count
                ),
                "worker_negative_gap_count": (
                    self.worker_negative_gap_product_count
                ),
                "truck_negative_gap_count": (
                    self.truck_negative_gap_product_count
                ),
            },
            "trucks": {
                "confirmed_stopped_count": (
                    self.confirmed_stopped_truck_count
                ),
                "possible_stopped_count": (
                    self.possible_stopped_truck_count
                ),
                "conflicting_state_count": (
                    self.conflicting_truck_state_count
                ),
            },
        }


@dataclass(frozen=True, slots=True)
class AskDeliskyContext:
    schema_version: str
    requested_period_start: str | None
    requested_period_end: str | None
    brand_id: int | None
    insights: tuple[AskDeliskyInsight, ...]
    summary: AskDeliskySummary | None = None

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
            "summary": (
                self.summary.to_payload()
                if self.summary is not None
                else None
            ),
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


def _serialize_optional_decimal(
    value: Decimal | None,
) -> str | None:
    if value is None:
        return None

    return format(value, "f")


def _convert_summary(
    summary: ManagerDashboardSummary | None,
) -> AskDeliskySummary | None:
    if summary is None:
        return None

    return AskDeliskySummary(
        total_sales=format(summary.total_sales, "f"),
        sale_record_count=summary.sale_record_count,
        positive_sale_record_count=(
            summary.positive_sale_record_count
        ),
        zero_total_record_count=(
            summary.zero_total_record_count
        ),
        average_sale_value=_serialize_optional_decimal(
            summary.average_sale_value
        ),
        average_positive_sale_value=(
            _serialize_optional_decimal(
                summary.average_positive_sale_value
            )
        ),
        worker_count=summary.worker_count,
        measured_sales_worker_count=(
            summary.measured_sales_worker_count
        ),
        pos_record_count=summary.pos_record_count,
        visited_record_count=(
            summary.visited_record_count
        ),
        not_visited_record_count=(
            summary.not_visited_record_count
        ),
        visit_success_ratio=(
            _serialize_optional_decimal(
                summary.visit_success_rate
            )
        ),
        non_visit_ratio=(
            _serialize_optional_decimal(
                summary.non_visit_rate
            )
        ),
        distinct_brand_client_count=(
            summary.distinct_brand_client_count
        ),
        worker_not_sold_product_count=(
            summary.worker_not_sold_product_count
        ),
        truck_not_sold_product_count=(
            summary.truck_not_sold_product_count
        ),
        worker_negative_gap_product_count=(
            summary.worker_negative_gap_product_count
        ),
        truck_negative_gap_product_count=(
            summary.truck_negative_gap_product_count
        ),
        confirmed_stopped_truck_count=(
            summary.confirmed_stopped_truck_count
        ),
        possible_stopped_truck_count=(
            summary.possible_stopped_truck_count
        ),
        conflicting_truck_state_count=(
            summary.conflicting_truck_state_count
        ),
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
        schema_version="2",
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
        summary=_convert_summary(
            insights_result.summary
        ),
    )
