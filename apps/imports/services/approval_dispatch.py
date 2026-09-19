from typing import Any

from apps.imports.models import ImportBatch

from .batch_approval import approve_import_batch
from .raw_items_detail_approval import (
    approve_items_detail_batch,
)
from .raw_items_detail_replacement import (
    detail_batch_covered_trucks,
)


def is_items_detail_batch(
    batch: ImportBatch,
) -> bool:
    return (
        batch.report_type == "ITEMS"
        and batch.source_upload_id is not None
        and bool(detail_batch_covered_trucks(batch))
    )


def approve_reviewed_batch(
    batch: ImportBatch | int,
    *,
    approved_by: Any,
):
    """Route approval to the correct service without changing legacy flows."""
    if isinstance(batch, ImportBatch):
        target = batch
    else:
        target = (
            ImportBatch.objects
            .select_related(
                "source_upload",
                "source_upload__source_system",
                "brand",
            )
            .get(pk=batch)
        )

    if is_items_detail_batch(target):
        return approve_items_detail_batch(
            target.pk,
            approved_by=approved_by,
        )

    return approve_import_batch(
        target.pk,
        approved_by=approved_by,
    )
