from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum


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
