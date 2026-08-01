from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum

from .truck_operational_status import (
    TruckOperationalStatus,
    TruckOperationalStatusResult,
)
from .worker_truck_mobility import (
    MobilityTransitionType,
    WorkerTruckMobilityComparison,
    WorkerTruckMobilityResult,
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


def _mobility_has_coverage_imbalance(
    comparison: WorkerTruckMobilityComparison,
) -> bool:
    sales_imbalance = (
        comparison.has_comparable_sales
        and (
            comparison.before.sales_measurement_day_count
            != comparison.after.sales_measurement_day_count
        )
    )
    visit_imbalance = (
        comparison.has_comparable_visits
        and (
            comparison.before.visit_measurement_day_count
            != comparison.after.visit_measurement_day_count
        )
    )

    return bool(
        sales_imbalance
        or visit_imbalance
    )


def _mobility_has_incomplete_coverage(
    comparison: WorkerTruckMobilityComparison,
) -> bool:
    sales_incomplete = (
        comparison.has_comparable_sales
        and (
            comparison.before.sales_measurement_day_count
            < comparison.before.working_day_count
            or comparison.after.sales_measurement_day_count
            < comparison.after.working_day_count
        )
    )
    visits_incomplete = (
        comparison.has_comparable_visits
        and (
            comparison.before.visit_measurement_day_count
            < comparison.before.working_day_count
            or comparison.after.visit_measurement_day_count
            < comparison.after.working_day_count
        )
    )

    return bool(
        sales_incomplete
        or visits_incomplete
    )



def _mobility_confidence(
    comparison: WorkerTruckMobilityComparison,
) -> InsightConfidence:
    has_gap = (
        comparison.gap_working_day_count > 0
    )
    has_incomplete_coverage = (
        _mobility_has_incomplete_coverage(
            comparison
        )
    )

    if has_gap and has_incomplete_coverage:
        return InsightConfidence.LOW

    if has_gap or has_incomplete_coverage:
        return InsightConfidence.MEDIUM

    return InsightConfidence.HIGH



def _mobility_entities(
    comparison: WorkerTruckMobilityComparison,
) -> tuple[InsightEntityRef, ...]:
    brand = InsightEntityRef(
        entity_type=InsightEntityType.BRAND,
        entity_id=comparison.brand_id,
    )

    if (
        comparison.transition_type
        == MobilityTransitionType.WORKER_CHANGED_TRUCK
    ):
        return (
            brand,
            InsightEntityRef(
                entity_type=InsightEntityType.WORKER,
                entity_id=comparison.before.worker_id,
            ),
            InsightEntityRef(
                entity_type=InsightEntityType.TRUCK,
                entity_id=comparison.before.truck_id,
            ),
            InsightEntityRef(
                entity_type=InsightEntityType.TRUCK,
                entity_id=comparison.after.truck_id,
            ),
        )

    return (
        brand,
        InsightEntityRef(
            entity_type=InsightEntityType.TRUCK,
            entity_id=comparison.before.truck_id,
        ),
        InsightEntityRef(
            entity_type=InsightEntityType.WORKER,
            entity_id=comparison.before.worker_id,
        ),
        InsightEntityRef(
            entity_type=InsightEntityType.WORKER,
            entity_id=comparison.after.worker_id,
        ),
    )


def _mobility_limitations(
    comparison: WorkerTruckMobilityComparison,
) -> tuple[InsightLimitation, ...]:
    limitations: list[InsightLimitation] = [
        InsightLimitation(
            code="MOBILITY_ASSOCIATION_NOT_CAUSATION",
            message=(
                "هذه مقارنة "
                "ارتباطية "
                "قبل/بعد ولا "
                "تثبت أن تغيير "
                "الشاحنة أو "
                "البائع هو سبب "
                "تغير النتائج."
            ),
        ),
        InsightLimitation(
            code="MOBILITY_CONTEXT_NOT_CONTROLLED",
            message=(
                "لا تتحكم "
                "المقارنة "
                "وحدها في "
                "اختلاف المسار "
                "والزبائن "
                "والطلب "
                "والتزويد "
                "وبقية السياق "
                "التشغيلي."
            ),
        ),
    ]

    if comparison.gap_working_day_count > 0:
        limitations.append(
            InsightLimitation(
                code="MOBILITY_WORKING_GAP_PRESENT",
                message=(
                    "توجد أيام "
                    "عمل فاصلة "
                    "بين التعيينين؛ "
                    "لذلك خُفِّضت "
                    "الثقة في "
                    "ربط التغير "
                    "بالتبديل "
                    "مباشرة."
                ),
            )
        )

    if _mobility_has_incomplete_coverage(
        comparison
    ):
        limitations.append(
            InsightLimitation(
                code=(
                    "MOBILITY_INCOMPLETE_"
                    "MEASUREMENT_COVERAGE"
                ),
                message=(
                    "البيانات "
                    "المقاسة "
                    "لا تغطي "
                    "كل أيام "
                    "العمل في "
                    "نافذة "
                    "المقارنة؛ "
                    "لذلك خُفِّضت "
                    "درجة "
                    "الثقة."
                ),
            )
        )

    if _mobility_has_coverage_imbalance(
        comparison
    ):
        limitations.append(
            InsightLimitation(
                code=(
                    "MOBILITY_MEASUREMENT_"
                    "COVERAGE_IMBALANCE"
                ),
                message=(
                    "عدد الأيام "
                    "التي ظهرت "
                    "فيها سجلات "
                    "القياس غير "
                    "متساوٍ بين "
                    "النافذتين؛ "
                    "وقد يعكس ذلك "
                    "اختلاف "
                    "النشاط أو "
                    "تغطية البيانات."
                ),
            )
        )

    return tuple(limitations)


def detect_mobility_insights(
    *,
    mobility_result: WorkerTruckMobilityResult,
) -> tuple[ManagerInsight, ...]:
    """
    Build deterministic before/after mobility signals.

    The detector reports measurable changes associated with a
    primary-seller assignment transition. It does not claim that
    the transition caused the result change and introduces no
    arbitrary performance threshold.
    """
    insights: list[ManagerInsight] = []

    for comparison in mobility_result.comparisons:
        sales_delta = (
            comparison.sales_total_delta
        )
        visit_rate_delta = (
            comparison.visit_success_rate_delta
        )

        has_sales_change = (
            sales_delta is not None
            and sales_delta != 0
        )
        has_visit_change = (
            visit_rate_delta is not None
            and visit_rate_delta != 0
        )

        if not (
            has_sales_change
            or has_visit_change
        ):
            continue

        evidence: list[InsightEvidence] = [
            InsightEvidence(
                key="change_date",
                label="تاريخ التغيير",
                value=comparison.change_date.isoformat(),
                source=(
                    "worker_truck_mobility."
                    "comparisons.change_date"
                ),
            ),
            InsightEvidence(
                key="gap_working_day_count",
                label="أيام العمل الفاصلة",
                value=(
                    comparison.gap_working_day_count
                ),
                source=(
                    "worker_truck_mobility.comparisons."
                    "gap_working_day_count"
                ),
                unit="working_days",
            ),
            InsightEvidence(
                key="before_working_day_count",
                label="أيام العمل قبل التغيير",
                value=comparison.before.working_day_count,
                source=(
                    "worker_truck_mobility.comparisons."
                    "before.working_day_count"
                ),
                unit="working_days",
                period_start=comparison.before.period_start,
                period_end=comparison.before.period_end,
            ),
            InsightEvidence(
                key="after_working_day_count",
                label="أيام العمل بعد التغيير",
                value=comparison.after.working_day_count,
                source=(
                    "worker_truck_mobility.comparisons."
                    "after.working_day_count"
                ),
                unit="working_days",
                period_start=comparison.after.period_start,
                period_end=comparison.after.period_end,
            ),
        ]

        if comparison.has_comparable_sales:
            evidence.extend(
                (
                    InsightEvidence(
                        key="before_sales_total",
                        label="إجمالي المبيعات قبل التغيير",
                        value=comparison.before.sales_total,
                        source=(
                            "worker_truck_mobility."
                            "comparisons.before.sales_total"
                        ),
                        unit="DZD",
                        period_start=(
                            comparison.before.period_start
                        ),
                        period_end=(
                            comparison.before.period_end
                        ),
                    ),
                    InsightEvidence(
                        key="after_sales_total",
                        label="إجمالي المبيعات بعد التغيير",
                        value=comparison.after.sales_total,
                        source=(
                            "worker_truck_mobility."
                            "comparisons.after.sales_total"
                        ),
                        unit="DZD",
                        period_start=(
                            comparison.after.period_start
                        ),
                        period_end=(
                            comparison.after.period_end
                        ),
                    ),
                    InsightEvidence(
                        key="sales_total_delta",
                        label="فرق إجمالي المبيعات",
                        value=sales_delta,
                        source=(
                            "worker_truck_mobility."
                            "comparisons.sales_total_delta"
                        ),
                        unit="DZD",
                        period_start=(
                            comparison.before.period_start
                        ),
                        period_end=(
                            comparison.after.period_end
                        ),
                    ),
                    InsightEvidence(
                        key=(
                            "before_sales_"
                            "measurement_day_count"
                        ),
                        label="أيام قياس المبيعات قبل التغيير",
                        value=(
                            comparison.before
                            .sales_measurement_day_count
                        ),
                        source=(
                            "worker_truck_mobility."
                            "comparisons.before."
                            "sales_measurement_day_count"
                        ),
                        unit="days",
                    ),
                    InsightEvidence(
                        key=(
                            "after_sales_"
                            "measurement_day_count"
                        ),
                        label="أيام قياس المبيعات بعد التغيير",
                        value=(
                            comparison.after
                            .sales_measurement_day_count
                        ),
                        source=(
                            "worker_truck_mobility."
                            "comparisons.after."
                            "sales_measurement_day_count"
                        ),
                        unit="days",
                    ),
                )
            )

        if comparison.has_comparable_visits:
            evidence.extend(
                (
                    InsightEvidence(
                        key="before_pos_record_count",
                        label="سجلات PoS قبل التغيير",
                        value=(
                            comparison.before
                            .pos_record_count
                        ),
                        source=(
                            "worker_truck_mobility."
                            "comparisons.before."
                            "pos_record_count"
                        ),
                        unit="records",
                        period_start=(
                            comparison.before.period_start
                        ),
                        period_end=(
                            comparison.before.period_end
                        ),
                    ),
                    InsightEvidence(
                        key="after_pos_record_count",
                        label="سجلات PoS بعد التغيير",
                        value=(
                            comparison.after
                            .pos_record_count
                        ),
                        source=(
                            "worker_truck_mobility."
                            "comparisons.after."
                            "pos_record_count"
                        ),
                        unit="records",
                        period_start=(
                            comparison.after.period_start
                        ),
                        period_end=(
                            comparison.after.period_end
                        ),
                    ),
                    InsightEvidence(
                        key=(
                            "before_visit_"
                            "measurement_day_count"
                        ),
                        label="أيام قياس الزيارات قبل التغيير",
                        value=(
                            comparison.before
                            .visit_measurement_day_count
                        ),
                        source=(
                            "worker_truck_mobility."
                            "comparisons.before."
                            "visit_measurement_day_count"
                        ),
                        unit="days",
                    ),
                    InsightEvidence(
                        key=(
                            "after_visit_"
                            "measurement_day_count"
                        ),
                        label="أيام قياس الزيارات بعد التغيير",
                        value=(
                            comparison.after
                            .visit_measurement_day_count
                        ),
                        source=(
                            "worker_truck_mobility."
                            "comparisons.after."
                            "visit_measurement_day_count"
                        ),
                        unit="days",
                    ),
                )
            )

            before_rate = (
                comparison.before.visit_success_rate
            )
            after_rate = (
                comparison.after.visit_success_rate
            )

            if (
                before_rate is not None
                and after_rate is not None
            ):
                evidence.extend(
                    (
                        InsightEvidence(
                            key=(
                                "before_visit_success_rate"
                            ),
                            label="معدل نجاح الزيارة قبل التغيير",
                            value=before_rate,
                            source=(
                                "worker_truck_mobility."
                                "comparisons.before."
                                "visit_success_rate"
                            ),
                            unit="ratio",
                        ),
                        InsightEvidence(
                            key=(
                                "after_visit_success_rate"
                            ),
                            label="معدل نجاح الزيارة بعد التغيير",
                            value=after_rate,
                            source=(
                                "worker_truck_mobility."
                                "comparisons.after."
                                "visit_success_rate"
                            ),
                            unit="ratio",
                        ),
                        InsightEvidence(
                            key=(
                                "visit_success_rate_delta"
                            ),
                            label="فرق معدل نجاح الزيارة",
                            value=visit_rate_delta,
                            source=(
                                "worker_truck_mobility."
                                "comparisons."
                                "visit_success_rate_delta"
                            ),
                            unit="ratio",
                        ),
                    )
                )

        if (
            comparison.transition_type
            == MobilityTransitionType.WORKER_CHANGED_TRUCK
        ):
            code = "WORKER_TRUCK_MOBILITY_SIGNAL"
            title = "انتقال بائع بين شاحنتين"
            summary = (
                "ارتبط انتقال "
                "البائع بين "
                "شاحنتين بتغير "
                "قابل للقياس "
                "في النتائج "
                "المتاحة قبل "
                "الانتقال "
                "وبعده."
            )
        else:
            code = "TRUCK_SELLER_MOBILITY_SIGNAL"
            title = "تغيير البائع الرئيسي للشاحنة"
            summary = (
                "ارتبط تغيير "
                "البائع "
                "الرئيسي "
                "على الشاحنة "
                "بتغير قابل "
                "للقياس في "
                "النتائج "
                "المتاحة قبل "
                "التغيير "
                "وبعده."
            )

        insights.append(
            ManagerInsight(
                code=code,
                category=InsightCategory.MOBILITY,
                severity=InsightSeverity.ATTENTION,
                confidence=_mobility_confidence(
                    comparison
                ),
                title=title,
                summary=summary,
                period_start=(
                    comparison.before.period_start
                ),
                period_end=(
                    comparison.after.period_end
                ),
                evidence=tuple(evidence),
                entities=_mobility_entities(
                    comparison
                ),
                limitations=_mobility_limitations(
                    comparison
                ),
            )
        )

    return tuple(insights)
