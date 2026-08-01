from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum

from .worker_performance import (
    PerformanceDataQualitySummary,
)


InsightValue = Decimal | int | str | bool


class InsightSeverity(StrEnum):
    INFO = "INFO"
    ATTENTION = "ATTENTION"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class InsightConfidence(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class InsightCategory(StrEnum):
    SALES = "SALES"
    VISITS = "VISITS"
    CLIENTS = "CLIENTS"
    PRODUCTS = "PRODUCTS"
    OPERATIONS = "OPERATIONS"
    WORKERS = "WORKERS"
    MOBILITY = "MOBILITY"
    DATA_QUALITY = "DATA_QUALITY"


class InsightEntityType(StrEnum):
    BRAND = "BRAND"
    WORKER = "WORKER"
    TRUCK = "TRUCK"
    CLIENT = "CLIENT"
    PRODUCT = "PRODUCT"


@dataclass(frozen=True, slots=True)
class InsightEntityRef:
    entity_type: InsightEntityType
    entity_id: int | str
    label: str = ""

    def __post_init__(self) -> None:
        if isinstance(self.entity_id, str):
            if not self.entity_id.strip():
                raise ValueError(
                    "entity_id cannot be empty."
                )


@dataclass(frozen=True, slots=True)
class InsightEvidence:
    key: str
    label: str
    value: InsightValue
    source: str
    unit: str = ""
    period_start: date | None = None
    period_end: date | None = None

    def __post_init__(self) -> None:
        if not self.key.strip():
            raise ValueError(
                "evidence key cannot be empty."
            )

        if not self.label.strip():
            raise ValueError(
                "evidence label cannot be empty."
            )

        if not self.source.strip():
            raise ValueError(
                "evidence source cannot be empty."
            )

        if (
            self.period_start is not None
            and self.period_end is not None
            and self.period_end < self.period_start
        ):
            raise ValueError(
                "evidence period_end cannot be before "
                "period_start."
            )


@dataclass(frozen=True, slots=True)
class InsightLimitation:
    code: str
    message: str

    def __post_init__(self) -> None:
        if not self.code.strip():
            raise ValueError(
                "limitation code cannot be empty."
            )

        if not self.message.strip():
            raise ValueError(
                "limitation message cannot be empty."
            )


@dataclass(frozen=True, slots=True)
class ManagerInsight:
    code: str
    category: InsightCategory
    severity: InsightSeverity
    confidence: InsightConfidence
    title: str
    summary: str

    period_start: date | None
    period_end: date | None

    evidence: tuple[InsightEvidence, ...]
    entities: tuple[InsightEntityRef, ...] = ()
    limitations: tuple[InsightLimitation, ...] = ()

    def __post_init__(self) -> None:
        if not self.code.strip():
            raise ValueError(
                "insight code cannot be empty."
            )

        if not self.title.strip():
            raise ValueError(
                "insight title cannot be empty."
            )

        if not self.summary.strip():
            raise ValueError(
                "insight summary cannot be empty."
            )

        if not self.evidence:
            raise ValueError(
                "an insight must contain evidence."
            )

        if (
            self.period_start is not None
            and self.period_end is not None
            and self.period_end < self.period_start
        ):
            raise ValueError(
                "period_end cannot be before period_start."
            )

    @property
    def has_limitations(self) -> bool:
        return bool(self.limitations)


def detect_data_quality_insights(
    *,
    data_quality: PerformanceDataQualitySummary,
    period_start: date | None = None,
    period_end: date | None = None,
) -> tuple[ManagerInsight, ...]:
    """
    Build deterministic data-quality insights.

    Counts come directly from existing analytics. No arbitrary
    score or count threshold is introduced here.
    """
    if (
        period_start is not None
        and period_end is not None
        and period_end < period_start
    ):
        raise ValueError(
            "period_end cannot be before period_start."
        )

    insights: list[ManagerInsight] = []

    attribution_sources = (
        (
            "sales_attribution_issues",
            "مشاكل إسناد المبيعات",
            data_quality.sales_attribution_issue_count,
            (
                "worker_performance.data_quality."
                "sales_attribution_issue_count"
            ),
        ),
        (
            "pos_attribution_issues",
            "مشاكل إسناد الزيارات",
            data_quality.pos_attribution_issue_count,
            (
                "worker_performance.data_quality."
                "pos_attribution_issue_count"
            ),
        ),
        (
            "items_attribution_issues",
            "مشاكل إسناد المنتجات",
            data_quality.items_attribution_issue_count,
            (
                "worker_performance.data_quality."
                "items_attribution_issue_count"
            ),
        ),
        (
            "opening_stock_attribution_issues",
            "مشاكل إسناد الرصيد الافتتاحي",
            data_quality.opening_stock_attribution_issue_count,
            (
                "worker_performance.data_quality."
                "opening_stock_attribution_issue_count"
            ),
        ),
        (
            "chargement_attribution_issues",
            "مشاكل إسناد التحميل",
            data_quality.chargement_attribution_issue_count,
            (
                "worker_performance.data_quality."
                "chargement_attribution_issue_count"
            ),
        ),
        (
            "operational_attribution_issues",
            "مشاكل إسناد الحالة التشغيلية",
            data_quality.operational_attribution_issue_count,
            (
                "worker_performance.data_quality."
                "operational_attribution_issue_count"
            ),
        ),
    )

    attribution_evidence = tuple(
        InsightEvidence(
            key=key,
            label=label,
            value=count,
            source=source,
            unit="records",
            period_start=period_start,
            period_end=period_end,
        )
        for key, label, count, source in attribution_sources
        if count > 0
    )

    if attribution_evidence:
        insights.append(
            ManagerInsight(
                code="DATA_ATTRIBUTION_ISSUES",
                category=InsightCategory.DATA_QUALITY,
                severity=InsightSeverity.WARNING,
                confidence=InsightConfidence.HIGH,
                title="مشاكل في إسناد بعض البيانات",
                summary=(
                    "توجد سجلات معتمدة "
                    "لم يمكن إسنادها "
                    "بثقة إلى الكيان "
                    "التحليلي المطلوب."
                ),
                period_start=period_start,
                period_end=period_end,
                evidence=attribution_evidence,
                limitations=(
                    InsightLimitation(
                        code="ATTRIBUTION_NOT_PERFORMANCE_FAILURE",
                        message=(
                            "مشكلة الإسناد "
                            "هي قيد على جودة "
                            "التحليل ولا تعني "
                            "فشل البائع أو الشاحنة."
                        ),
                    ),
                ),
            )
        )

    warning_sources = (
        (
            "pos_numeric_message_warnings",
            "رسائل PoS الرقمية",
            data_quality.pos_numeric_message_warning_count,
            (
                "worker_performance.data_quality."
                "pos_numeric_message_warning_count"
            ),
        ),
        (
            "pos_duplicate_same_day_warnings",
            "تكرار PoS لنفس الزبون في نفس اليوم",
            data_quality.pos_duplicate_same_day_warning_count,
            (
                "worker_performance.data_quality."
                "pos_duplicate_same_day_warning_count"
            ),
        ),
    )

    warning_evidence = tuple(
        InsightEvidence(
            key=key,
            label=label,
            value=count,
            source=source,
            unit="records",
            period_start=period_start,
            period_end=period_end,
        )
        for key, label, count, source in warning_sources
        if count > 0
    )

    if warning_evidence:
        insights.append(
            ManagerInsight(
                code="POS_DATA_WARNINGS",
                category=InsightCategory.DATA_QUALITY,
                severity=InsightSeverity.ATTENTION,
                confidence=InsightConfidence.HIGH,
                title="تحذيرات في بيانات الزيارات",
                summary=(
                    "توجد حالات PoS "
                    "تحتاج الانتباه "
                    "عند تفسير مؤشرات "
                    "الزيارة."
                ),
                period_start=period_start,
                period_end=period_end,
                evidence=warning_evidence,
                limitations=(
                    InsightLimitation(
                        code="POS_WARNING_NOT_AUTOMATIC_EXCLUSION",
                        message=(
                            "هذه التحذيرات "
                            "لا تعني تلقائيًا "
                            "حذف السجل أو "
                            "اعتباره عدم زيارة."
                        ),
                    ),
                ),
            )
        )

    return tuple(insights)
