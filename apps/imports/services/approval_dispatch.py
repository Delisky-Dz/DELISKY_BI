from typing import Any

from django.db import transaction

from apps.imports.models import (
    ImportBatch,
    ImportSourceSystem,
)

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
        and bool(
            detail_batch_covered_trucks(
                batch
            )
        )
    )


def _load_target(
    batch_id: int,
) -> ImportBatch:
    return (
        ImportBatch.objects
        .select_related(
            "source_upload",
            "source_upload__source_system",
            "brand",
        )
        .get(pk=batch_id)
    )


def _source_system_id_for_source_items(
    batch_id: int,
) -> int | None:
    return (
        ImportBatch.objects
        .filter(
            pk=batch_id,
            report_type="ITEMS",
            source_upload__isnull=False,
        )
        .values_list(
            "source_upload__source_system_id",
            flat=True,
        )
        .first()
    )


def _dispatch_approval(
    target: ImportBatch,
    *,
    approved_by: Any,
):
    if is_items_detail_batch(target):
        return approve_items_detail_batch(
            target.pk,
            approved_by=approved_by,
        )

    return approve_import_batch(
        target.pk,
        approved_by=approved_by,
    )


def approve_reviewed_batch(
    batch: ImportBatch | int,
    *,
    approved_by: Any,
):
    """Route approval while serializing all source-backed Items flows.

    Legacy and transaction-detail Items can overlap the same source-system
    truck/period scope. Lock the source-system row before either approval
    service runs so a legacy approval cannot race a detail review/approval
    and create a replacement target that was not part of the reviewed plan.
    Non-Items and direct-file legacy flows keep their existing behaviour.
    """
    batch_id = (
        batch.pk
        if isinstance(batch, ImportBatch)
        else batch
    )

    if not batch_id:
        return approve_import_batch(
            batch_id,
            approved_by=approved_by,
        )

    source_system_id = (
        _source_system_id_for_source_items(
            batch_id
        )
    )

    if source_system_id is None:
        target = (
            batch
            if isinstance(batch, ImportBatch)
            else _load_target(batch_id)
        )

        return _dispatch_approval(
            target,
            approved_by=approved_by,
        )

    with transaction.atomic():
        ImportSourceSystem.objects.select_for_update().get(
            pk=source_system_id
        )

        target = _load_target(
            batch_id
        )

        return _dispatch_approval(
            target,
            approved_by=approved_by,
        )
