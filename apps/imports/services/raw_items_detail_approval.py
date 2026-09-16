from dataclasses import dataclass
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.imports.models import ImportBatch, ImportBatchStatus

from .batch_approval import (
    ImportBatchApprovalError,
    _validate_staged_rows,
)
from .raw_items_detail_replacement import (
    RawItemsDetailReplacementError,
    detail_batch_covered_trucks,
    plan_items_detail_replacements,
)


@dataclass(frozen=True, slots=True)
class ItemsDetailApprovalResult:
    batch: ImportBatch
    superseded_batch_ids: tuple[int, ...]


def approve_items_detail_batch(
    batch: ImportBatch | int,
    *,
    approved_by: Any,
) -> ItemsDetailApprovalResult:
    """Approve one transaction-level Items brand batch atomically.

    The replacement plan is recomputed while database rows are locked;
    every covered approved legacy/detail batch is superseded in the same
    transaction. This deliberately avoids the legacy single
    ``replaces_batch`` relation, which cannot represent a detail export
    replacing several per-truck batches.
    """
    batch_id = batch.pk if isinstance(batch, ImportBatch) else batch
    if not batch_id:
        raise ImportBatchApprovalError("unsaved_batch", "The ImportBatch must be saved before approval.")
    if approved_by is None or not getattr(approved_by, "pk", None):
        raise ImportBatchApprovalError("invalid_approver", "A saved user is required to approve the import batch.")
    if not getattr(approved_by, "is_active", False):
        raise ImportBatchApprovalError("inactive_approver", "An inactive user cannot approve the import batch.")

    with transaction.atomic():
        target = ImportBatch.objects.select_for_update().get(pk=batch_id)
        if target.status != ImportBatchStatus.REVIEWED:
            raise ImportBatchApprovalError(
                "batch_not_reviewed",
                "Only a successfully reviewed transaction-level Items batch can be approved.",
                details={"status": target.status},
            )
        if target.error_count:
            raise ImportBatchApprovalError("batch_has_errors", "A batch containing blocking errors cannot be approved.")
        if not target.content_sha256:
            raise ImportBatchApprovalError("missing_content_hash", "The reviewed content hash is missing.")
        if target.report_type != "ITEMS" or target.source_upload_id is None:
            raise ImportBatchApprovalError("not_items_detail_batch", "This approval path requires a source-backed ITEMS batch.")

        covered_trucks = detail_batch_covered_trucks(target)
        if not covered_trucks:
            raise ImportBatchApprovalError(
                "not_items_detail_batch",
                "The batch review metadata does not identify transaction-level Items truck coverage.",
            )

        _validate_staged_rows(target)

        try:
            plan = plan_items_detail_replacements(
                source_system_code=target.source_upload.source_system.code,
                brand_code=target.brand.code,
                covered_trucks=covered_trucks,
                period_start=target.period_start,
                period_end=target.period_end,
                current_source_upload_id=target.source_upload_id,
            )
        except RawItemsDetailReplacementError as exc:
            raise ImportBatchApprovalError(
                exc.code,
                exc.message,
                details=dict(exc.details),
            ) from exc

        replacement_ids = plan.replacement_batch_ids
        locked_replacements = list(
            ImportBatch.objects.select_for_update()
            .filter(pk__in=replacement_ids)
            .order_by("id")
        )
        if tuple(batch.pk for batch in locked_replacements) != replacement_ids:
            raise ImportBatchApprovalError(
                "replacement_plan_changed",
                "The Items replacement set changed during approval; retry review before approving.",
            )
        for replaced in locked_replacements:
            if replaced.status != ImportBatchStatus.APPROVED:
                raise ImportBatchApprovalError(
                    "replacement_target_not_approved",
                    "Every Items detail replacement target must still be approved.",
                    details={"batch_id": replaced.pk, "status": replaced.status},
                )
            replaced.status = ImportBatchStatus.SUPERSEDED
            replaced.save(update_fields=["status", "updated_at"])

        target.status = ImportBatchStatus.APPROVED
        target.approved_by = approved_by
        target.approved_at = timezone.now()
        target.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])

    return ItemsDetailApprovalResult(
        batch=target,
        superseded_batch_ids=replacement_ids,
    )
