from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum

from .truck_operational_status import (
    TruckOperationalStatus,
    TruckOperationalStatusResult,
)
from .worker_performance import (
    PerformanceDataQualitySummary,
    WorkerPerformanceResult,
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


def detect_operational_insights(
    *,
    operational_result: TruckOperationalStatusResult,
) -> tuple[ManagerInsight, ...]:
    """
    Build deterministic truck operational insights.

    ACTIVE trucks produce no attention insight. Non-active states
    are reported from their existing analytical evidence without
    inventing a performance score or arbitrary threshold.
    """
    insights: list[ManagerInsight] = []

    period_start = operational_result.requested_period_start
    period_end = operational_result.requested_period_end

    for state in operational_result.states:
        if state.status == TruckOperationalStatus.ACTIVE:
            continue

        entities = (
            InsightEntityRef(
                entity_type=InsightEntityType.BRAND,
                entity_id=state.brand_id,
            ),
            InsightEntityRef(
                entity_type=InsightEntityType.TRUCK,
                entity_id=state.truck_id,
            ),
        )

        evidence = (
            InsightEvidence(
                key="sales_activity_count",
                label="عدد أدلة نشاط المبيعات",
                value=state.sales_activity_count,
                source=(
                    "truck_operational_status.states."
                    "sales_activity_count"
                ),
                unit="records",
                period_start=period_start,
                period_end=period_end,
            ),
            InsightEvidence(
                key="sales_total",
                label="إجمالي المبيعات المرتبطة بالنشاط",
                value=state.sales_total,
                source=(
                    "truck_operational_status.states."
                    "sales_total"
                ),
                unit="DZD",
                period_start=period_start,
                period_end=period_end,
            ),
            InsightEvidence(
                key="authoritative_stopped_count",
                label="عدد أدلة التوقف المؤكدة",
                value=state.authoritative_stopped_count,
                source=(
                    "truck_operational_status.states."
                    "authoritative_stopped_count"
                ),
                unit="records",
                period_start=period_start,
                period_end=period_end,
            ),
            InsightEvidence(
                key="possible_stopped_count",
                label="عدد إشارات التوقف المحتملة",
                value=state.possible_stopped_count,
                source=(
                    "truck_operational_status.states."
                    "possible_stopped_count"
                ),
                unit="records",
                period_start=period_start,
                period_end=period_end,
            ),
        )

        limitation = (
            InsightLimitation(
                code="TRUCK_STATUS_NOT_WORKER_FAILURE",
                message=(
                    "حالة الشاحنة التشغيلية لا تعني "
                    "فشل البائع ولا يجب استخدامها "
                    "وحدها للحكم على أدائه."
                ),
            ),
        )

        if (
            state.status
            == TruckOperationalStatus.CONFIRMED_STOPPED
        ):
            insights.append(
                ManagerInsight(
                    code="TRUCK_CONFIRMED_STOPPED",
                    category=InsightCategory.OPERATIONS,
                    severity=InsightSeverity.WARNING,
                    confidence=InsightConfidence.HIGH,
                    title="توقف مؤكد لشاحنة توزيع",
                    summary=(
                        "توجد أدلة معتمدة تؤكد توقف "
                        "الشاحنة خلال الفترة التحليلية."
                    ),
                    period_start=period_start,
                    period_end=period_end,
                    evidence=evidence,
                    entities=entities,
                    limitations=limitation,
                )
            )
            continue

        if (
            state.status
            == TruckOperationalStatus.POSSIBLE_STOPPED
        ):
            insights.append(
                ManagerInsight(
                    code="TRUCK_POSSIBLE_STOPPED",
                    category=InsightCategory.OPERATIONS,
                    severity=InsightSeverity.ATTENTION,
                    confidence=InsightConfidence.MEDIUM,
                    title="توقف محتمل لشاحنة توزيع",
                    summary=(
                        "توجد إشارة إلى توقف الشاحنة، "
                        "لكن الدليل الحالي غير كافٍ "
                        "لاعتباره توقفًا مؤكدًا."
                    ),
                    period_start=period_start,
                    period_end=period_end,
                    evidence=evidence,
                    entities=entities,
                    limitations=limitation,
                )
            )
            continue

        if (
            state.status
            == TruckOperationalStatus.CONFLICTING_EVIDENCE
        ):
            insights.append(
                ManagerInsight(
                    code="TRUCK_OPERATIONAL_CONFLICT",
                    category=InsightCategory.OPERATIONS,
                    severity=InsightSeverity.WARNING,
                    confidence=InsightConfidence.HIGH,
                    title="تعارض في أدلة حالة الشاحنة",
                    summary=(
                        "توجد أدلة نشاط مبيعات وأدلة "
                        "توقف مؤكدة للشاحنة في نفس "
                        "الفترة التحليلية."
                    ),
                    period_start=period_start,
                    period_end=period_end,
                    evidence=evidence,
                    entities=entities,
                    limitations=(
                        *limitation,
                        InsightLimitation(
                            code="CONFLICTING_OPERATIONAL_EVIDENCE",
                            message=(
                                "يجب مراجعة الأدلة المتعارضة "
                                "قبل استخلاص حكم تشغيلي نهائي."
                            ),
                        ),
                    ),
                )
            )

    return tuple(insights)



def detect_worker_visit_insights(
    *,
    performance_result: WorkerPerformanceResult,
) -> tuple[ManagerInsight, ...]:
    """
    Compare measured workers against the weighted team
    non-visit rate for the same analytical period.

    This is a relative deterministic signal, not an arbitrary
    performance threshold and not proof of worker failure.
    """
    measured_workers = tuple(
        worker
        for worker in performance_result.workers
        if worker.has_visit_measurement
    )

    # A relative team comparison needs at least two measured
    # workers. Workers without visit measurement are not failures.
    if len(measured_workers) < 2:
        return ()

    team_pos_record_count = sum(
        worker.pos_record_count
        for worker in measured_workers
    )
    team_not_visited_record_count = sum(
        worker.not_visited_record_count
        for worker in measured_workers
    )

    if team_pos_record_count == 0:
        return ()

    team_non_visit_rate = (
        Decimal(team_not_visited_record_count)
        / Decimal(team_pos_record_count)
    )

    workers_above_team = tuple(
        sorted(
            (
                worker
                for worker in measured_workers
                if (
                    worker.non_visit_rate is not None
                    and worker.non_visit_rate
                    > team_non_visit_rate
                )
            ),
            key=lambda worker: (
                -worker.non_visit_rate,
                -worker.pos_record_count,
                worker.worker_id,
            ),
        )
    )

    if not workers_above_team:
        return ()

    evidence: list[InsightEvidence] = [
        InsightEvidence(
            key="team_pos_record_count",
            label="إجمالي سجلات PoS للفريق",
            value=team_pos_record_count,
            source="worker_performance.workers",
            unit="records",
            period_start=(
                performance_result.requested_period_start
            ),
            period_end=(
                performance_result.requested_period_end
            ),
        ),
        InsightEvidence(
            key="team_not_visited_record_count",
            label="إجمالي حالات عدم الزيارة للفريق",
            value=team_not_visited_record_count,
            source="worker_performance.workers",
            unit="records",
            period_start=(
                performance_result.requested_period_start
            ),
            period_end=(
                performance_result.requested_period_end
            ),
        ),
        InsightEvidence(
            key="team_non_visit_rate",
            label="معدل عدم الزيارة المجمع للفريق",
            value=team_non_visit_rate,
            source=(
                "manager_insights."
                "weighted_team_non_visit_rate"
            ),
            unit="ratio",
            period_start=(
                performance_result.requested_period_start
            ),
            period_end=(
                performance_result.requested_period_end
            ),
        ),
    ]

    for worker in workers_above_team:
        evidence.extend(
            (
                InsightEvidence(
                    key=(
                        f"worker_{worker.worker_id}_"
                        "pos_record_count"
                    ),
                    label=(
                        "عدد سجلات PoS "
                        f"للبائع {worker.worker_id}"
                    ),
                    value=worker.pos_record_count,
                    source="worker_performance.workers",
                    unit="records",
                    period_start=(
                        performance_result
                        .requested_period_start
                    ),
                    period_end=(
                        performance_result
                        .requested_period_end
                    ),
                ),
                InsightEvidence(
                    key=(
                        f"worker_{worker.worker_id}_"
                        "not_visited_record_count"
                    ),
                    label=(
                        "حالات عدم الزيارة "
                        f"للبائع {worker.worker_id}"
                    ),
                    value=(
                        worker.not_visited_record_count
                    ),
                    source="worker_performance.workers",
                    unit="records",
                    period_start=(
                        performance_result
                        .requested_period_start
                    ),
                    period_end=(
                        performance_result
                        .requested_period_end
                    ),
                ),
                InsightEvidence(
                    key=(
                        f"worker_{worker.worker_id}_"
                        "non_visit_rate"
                    ),
                    label=(
                        "معدل عدم الزيارة "
                        f"للبائع {worker.worker_id}"
                    ),
                    value=worker.non_visit_rate,
                    source=(
                        "worker_performance."
                        "non_visit_rate"
                    ),
                    unit="ratio",
                    period_start=(
                        performance_result
                        .requested_period_start
                    ),
                    period_end=(
                        performance_result
                        .requested_period_end
                    ),
                ),
            )
        )

    entities: list[InsightEntityRef] = []

    if performance_result.brand_id is not None:
        entities.append(
            InsightEntityRef(
                entity_type=InsightEntityType.BRAND,
                entity_id=performance_result.brand_id,
            )
        )

    entities.extend(
        InsightEntityRef(
            entity_type=InsightEntityType.WORKER,
            entity_id=worker.worker_id,
        )
        for worker in workers_above_team
    )

    return (
        ManagerInsight(
            code="WORKER_NON_VISIT_RATE_ABOVE_TEAM",
            category=InsightCategory.VISITS,
            severity=InsightSeverity.ATTENTION,
            confidence=InsightConfidence.HIGH,
            title="بائعون أعلى من معدل الفريق في عدم الزيارة",
            summary=(
                "توجد نتائج لبائعين "
                "لديهم معدل عدم زيارة "
                "أعلى من المعدل المجمع "
                "للفريق في نفس الفترة."
            ),
            period_start=(
                performance_result.requested_period_start
            ),
            period_end=(
                performance_result.requested_period_end
            ),
            evidence=tuple(evidence),
            entities=tuple(entities),
            limitations=(
                InsightLimitation(
                    code="RELATIVE_VISIT_SIGNAL_NOT_FAILURE",
                    message=(
                        "تجاوز معدل الفريق "
                        "إشارة نسبية للمتابعة "
                        "ولا يعني فشل البائع."
                    ),
                ),
                InsightLimitation(
                    code="VISIT_RATE_VOLUME_CONTEXT_REQUIRED",
                    message=(
                        "يجب قراءة نسبة عدم "
                        "الزيارة مع عدد سجلات "
                        "PoS المتاحة."
                    ),
                ),
                InsightLimitation(
                    code="VISIT_SIGNAL_NOT_CAUSAL",
                    message=(
                        "المقارنة لا تثبت "
                        "أن البائع هو سبب "
                        "عدم الزيارة دون "
                        "دراسة سياق الشاحنة "
                        "والمسار والزبائن."
                    ),
                ),
            ),
        ),
    )
