from collections import Counter
from dataclasses import dataclass
from typing import Any

from django.db import transaction

from apps.imports.models import (
    ImportBatch,
    ImportSourceSystem,
    ImportSourceUpload,
)

from .batch_review import (
    MUTABLE_BATCH_STATUSES,
    _validate_user,
)
from .raw_items_detail_multi_brand_review import (
    RawItemsDetailDerivedReviewResult,
    persist_raw_items_detail_review,
)
from .raw_items_detail_review import (
    RawItemsDetailReviewResult,
    prepare_raw_items_detail_review,
)
from .source_upload_store import (
    create_import_source_upload,
)


class RawItemsDetailImportReviewError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


@dataclass(frozen=True, slots=True)
class RawItemsDetailImportReviewResult:
    source_upload: ImportSourceUpload
    review: RawItemsDetailReviewResult
    brand_results: tuple[
        RawItemsDetailDerivedReviewResult,
        ...,
    ]

    @property
    def batches(
        self,
    ) -> tuple[ImportBatch, ...]:
        return tuple(
            result.batch
            for result in self.brand_results
        )


def _source_audit_metadata(
    review: RawItemsDetailReviewResult,
) -> dict[str, Any]:
    excluded_counts = Counter(
        (
            row.source_code,
            row.reason,
        )
        for row in review.excluded_source_rows
    )

    return {
        "transaction_level": True,
        "period_start": (
            review.period_start.isoformat()
        ),
        "period_end": (
            review.period_end.isoformat()
        ),
        "adapted_row_count": len(
            review.adapted.rows
        ),
        "excluded_source_row_count": len(
            review.excluded_source_rows
        ),
        "excluded_source_groups": [
            {
                "source_code": (
                    source_code
                ),
                "reason": reason,
                "count": count,
            }
            for (
                source_code,
                reason,
            ), count in sorted(
                excluded_counts.items()
            )
        ],
        "source_truck_scope": (
            review.source_truck_scope
            .as_dict()
        ),
    }


def _existing_mutable_batches_by_brand(
    source_upload: ImportSourceUpload,
) -> dict[str, ImportBatch]:
    existing = list(
        source_upload.derived_batches
        .select_for_update()
        .select_related("brand")
        .order_by("pk")
    )

    if not existing:
        return {}

    invalid = [
        batch
        for batch in existing
        if (
            batch.report_type != "ITEMS"
            or batch.status
            not in MUTABLE_BATCH_STATUSES
        )
    ]

    if invalid:
        raise (
            RawItemsDetailImportReviewError(
                "source_upload_already_reviewed",
                (
                    "This transaction-level "
                    "Items source file already "
                    "has an immutable or non-Items "
                    "derived review."
                ),
                details={
                    "source_upload_id": (
                        source_upload.pk
                    ),
                    "existing_batches": [
                        {
                            "pk": batch.pk,
                            "brand__code": (
                                batch.brand.code
                            ),
                            "report_type": (
                                batch.report_type
                            ),
                            "status": batch.status,
                            "period_start": (
                                batch.period_start
                            ),
                            "period_end": (
                                batch.period_end
                            ),
                        }
                        for batch in existing
                    ],
                },
            )
        )

    by_brand: dict[
        str,
        ImportBatch,
    ] = {}

    for batch in existing:
        brand_code = str(
            batch.brand.code or ""
        ).strip().upper()

        if brand_code in by_brand:
            raise (
                RawItemsDetailImportReviewError(
                    (
                        "source_upload_"
                        "ambiguous_mutable_review"
                    ),
                    (
                        "This Items detail source "
                        "has more than one mutable "
                        "batch for the same brand "
                        "and cannot be refreshed "
                        "safely."
                    ),
                    details={
                        "source_upload_id": (
                            source_upload.pk
                        ),
                        "brand_code": (
                            brand_code
                        ),
                        "batch_ids": [
                            item.pk
                            for item in existing
                            if str(
                                item.brand.code
                                or ""
                            ).strip().upper()
                            == brand_code
                        ],
                    },
                )
            )

        by_brand[brand_code] = batch

    return by_brand


def create_raw_items_detail_import_review(
    source: Any,
    *,
    source_system_code: str,
    uploaded_by: Any,
    period_start: Any,
    period_end: Any,
    reviewed_by: Any | None = None,
    original_filename: (
        str | None
    ) = None,
) -> RawItemsDetailImportReviewResult:
    """Review and persist one transaction-level Items export atomically.

    Source-system scope is locked before the source upload and derived
    batches, matching the approval lock order and avoiding a refresh/approval
    deadlock. Re-uploading the same raw source may refresh mutable derived
    batches in place; approved or superseded history is never rewritten.
    """
    _validate_user(
        uploaded_by,
        "uploaded_by",
    )

    reviewer = (
        reviewed_by
        or uploaded_by
    )

    _validate_user(
        reviewer,
        "reviewed_by",
    )

    review = (
        prepare_raw_items_detail_review(
            source,
            source_system_code=(
                source_system_code
            ),
            period_start=period_start,
            period_end=period_end,
            original_filename=(
                original_filename
            ),
        )
    )

    source_upload_result = None

    try:
        with transaction.atomic():
            source_upload_result = (
                create_import_source_upload(
                    source,
                    source_system_code=(
                        source_system_code
                    ),
                    uploaded_by=uploaded_by,
                    worksheet_name=(
                        review.adapted
                        .worksheet_name
                    ),
                    original_filename=(
                        review.adapted.filename
                    ),
                )
            )

            source_system_id = (
                source_upload_result
                .source_upload
                .source_system_id
            )

            ImportSourceSystem.objects.select_for_update().get(
                pk=source_system_id
            )

            source_upload = (
                ImportSourceUpload.objects
                .select_for_update()
                .get(
                    pk=(
                        source_upload_result
                        .source_upload
                        .pk
                    )
                )
            )

            existing_batches_by_brand = (
                _existing_mutable_batches_by_brand(
                    source_upload
                )
            )

            audit_metadata = dict(
                source_upload.audit_metadata
                or {}
            )
            audit_metadata[
                "items_detail"
            ] = _source_audit_metadata(
                review
            )
            source_upload.audit_metadata = (
                audit_metadata
            )
            source_upload.save(
                update_fields=[
                    "audit_metadata",
                    "updated_at",
                ]
            )

            persisted = (
                persist_raw_items_detail_review(
                    source_upload=(
                        source_upload
                    ),
                    review=review,
                    uploaded_by=uploaded_by,
                    reviewer=reviewer,
                    existing_batches_by_brand=(
                        existing_batches_by_brand
                    ),
                )
            )

    except Exception:
        if (
            source_upload_result
            is not None
            and source_upload_result.created
        ):
            source_upload = (
                source_upload_result
                .source_upload
            )
            saved_file_name = (
                source_upload
                .source_file
                .name
            )

            if saved_file_name:
                try:
                    (
                        source_upload
                        .source_file
                        .storage
                        .delete(
                            saved_file_name
                        )
                    )
                except Exception:
                    pass

        raise

    return (
        RawItemsDetailImportReviewResult(
            source_upload=(
                persisted.source_upload
            ),
            review=review,
            brand_results=(
                persisted.brand_results
            ),
        )
    )
