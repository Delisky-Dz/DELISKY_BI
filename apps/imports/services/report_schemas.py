from dataclasses import dataclass
import unicodedata


REPORT_OPENING_STOCK = "OPENING_STOCK"
REPORT_CHARGEMENT = "CHARGEMENT"
REPORT_SALES = "SALES"
REPORT_ITEMS = "ITEMS"
REPORT_POS = "POS"


@dataclass(frozen=True, slots=True)
class ReportSchema:
    report_type: str
    required_headers: tuple[str, ...]
    expected_worksheet_count: int = 1

    @property
    def normalized_required_headers(self) -> tuple[str, ...]:
        return tuple(
            normalize_header(header)
            for header in self.required_headers
        )


def normalize_header(value: object) -> str:
    if value is None:
        return ""

    text = unicodedata.normalize(
        "NFKC",
        str(value),
    )

    text = (
        text.replace("\u00a0", " ")
        .replace("\u2018", "'")
        .replace("\u2019", "'")
    )

    text = " ".join(text.split())

    return text.casefold()


REPORT_SCHEMAS = {
    REPORT_OPENING_STOCK: ReportSchema(
        report_type=REPORT_OPENING_STOCK,
        required_headers=(
            "VAN",
            "Qt\u00e9",
            "Article",
        ),
    ),
    REPORT_CHARGEMENT: ReportSchema(
        report_type=REPORT_CHARGEMENT,
        required_headers=(
            "VAN",
            "Qt\u00e9",
            "Article",
        ),
    ),
    REPORT_SALES: ReportSchema(
        report_type=REPORT_SALES,
        required_headers=(
            "VAN",
            "Date&Heure",
            "Nom du client",
            "Total",
            "Region",
        ),
    ),
    REPORT_ITEMS: ReportSchema(
        report_type=REPORT_ITEMS,
        required_headers=(
            "VAN",
            "Article",
            "Qt\u00e9 vendue",
            "Client",
        ),
    ),
    REPORT_POS: ReportSchema(
        report_type=REPORT_POS,
        required_headers=(
            "VAN",
            "Nom du client",
            "Message d'ignoration",
            "Date",
            "Cause d'ignoration",
        ),
    ),
}


def get_report_schema(report_type: str) -> ReportSchema:
    try:
        return REPORT_SCHEMAS[report_type]
    except KeyError as exc:
        raise ValueError(
            f"Unsupported report type: {report_type}"
        ) from exc
