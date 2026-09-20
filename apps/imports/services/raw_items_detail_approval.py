from dataclasses import dataclass
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.imports.models import (
    ImportBatch,
    ImportBatchStatus,
    ImportSourceSystem,
)

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


def _reviewed_replacement_batch_ids(
    batch: ImportBatch,
) -> tuple[int, ...] | None:
    summary = batch.review_summary or {}
    detail = summary.get("items_detail")

    if not isinstance(detail, dict):
        return None

    raw_ids = detail.get("replacement_batch_ids")
    if not isinstance(raw_ids, list):
        return None

    normalized: list[int] = []

    for value in raw_ids:
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or value <= 0
        ):
            return None

        normalized.append(value)

    if len(set(normalized)) != len(normalized):
        return None

    return tuple(normalized)


def _source_system_id_for_batch(
    batch_id: int,
) -> int | None:
    row = (
        ImportBatch.objects
        .filter(pk=batch_id)
        .values(
            "source_upload__source_system_id",
        )
        .first()
    )

    if row is None:
        raise ImportBatchApprovalError(
            "batch_not_found",
            "The requested ImportBatch does not exist.",
            details={"batch_id": batch_id},
        )

    return row[
        "source_upload__source_system_id"
    ]


def approve_items_detail_batch(
    batch: ImportBatch | int,
    *,
    approved_by: Any,
) -> ItemsDetailApprovalResult:
    """Approve one transaction-level Items brand batch atomically.

    Source-system scope is locked before any batch row so review/refresh and
    approval use the same lock order. The replacement plan is then recomputed
    and must still match the exact ids persisted at review time. Every covered
    approved legacy/detail batch is locked and superseded in the same
    transaction.
    """
    batch_id = (
        batch.pk
        if isinstance(batch, ImportBatch)
        else batch
    )

    if not batch_id:
        raise ImportBatchApprovalError(
            "unsaved_batch",
            (
                "The ImportBatch must be saved "
                "before approval."
            ),
        )

    if (
        approved_by is None
        or not getattr(approved_by, "pk", None)
    ):
        raise ImportBatchApprovalError(
            "invalid_approver",
            (
                "A saved user is required to "
                "approve the import batch."
            ),
        )

    if not getattr(
        approved_by,
        "is_active",
        False,
    ):
        raise ImportBatchApprovalError(
            "inactive_approver",
            (
                "An inactive user cannot approve "
                "the import batch."
            ),
        )

    with transaction.atomic():
        source_system_id = (
            _source_system_id_for_batch(
                batch_id
            )
        )

        locked_source_system = None

        if source_system_id is not None:
            locked_source_system = (
                ImportSourceSystem.objects
                .select_for_update()
                .get(pk=source_system_id)
            )

        target = (
            ImportBatch.objects
            .select_for_update()
            .select_related(
                "brand",
                "source_upload",
                "source_upload__source_system",
            )
            .get(pk=batch_id)
        )

        if (
            target.source_upload_id is not None
            and locked_source_system is not None
            and (
                target.source_upload.source_system_id
                != locked_source_system.pk
            )
        ):
            raise ImportBatchApprovalError(
                "source_scope_changed",
                (
                    "The Items detail source scope "
                    "changed during approval."
                ),
            )

        if (
            target.status
            != ImportBatchStatus.REVIEWED
        ):
            raise ImportBatchApprovalError(
                "batch_not_reviewed",
                (
                    "Only a successfully reviewed "
                    "transaction-level Items batch "
                    "can be approved."
                ),
                details={
                    "status": target.status
                },
            )

        if target.error_count:
            raise ImportBatchApprovalError(
                "batch_has_errors",
                (
                    "A batch containing blocking "
                    "errors cannot be approved."
                ),
            )

        if not target.content_sha256:
            raise ImportBatchApprovalError(
                "missing_content_hash",
                (
                    "The reviewed content hash "
                    "is missing."
                ),
            )

        if (
            target.report_type != "ITEMS"
            or target.source_upload_id is None
        ):
            raise ImportBatchApprovalError(
                "not_items_detail_batch",
                (
                    "This approval path requires a "
                    "source-backed ITEMS batch."
                ),
            )

        source_system = (
            locked_source_system
            or target.source_upload.source_system
        )

        covered_trucks = (
            detail_batch_covered_trucks(
                target
            )
        )

        if not covered_trucks:
            raise ImportBatchApprovalError(
                "not_items_detail_batch",
                (
                    "The batch review metadata does "
                    "not identify transaction-level "
                    "Items truck coverage."
                ),
            )

        reviewed_replacement_ids = (
            _reviewed_replacement_batch_ids(
                target
            )
        )

        if reviewed_replacement_ids is None:
            raise ImportBatchApprovalError(
                "missing_replacement_plan",
                (
                    "The reviewed Items detail batch "
                    "has no valid replacement-plan "
                    "snapshot. Review it again before "
                    "approval."
                ),
            )

        _validate_staged_rows(target)

        try:
            plan = (
                plan_items_detail_replacements(
                    source_system_code=(
                        source_system.code
                    ),
                    brand_code=target.brand.code,
                    covered_trucks=(
                        covered_trucks
                    ),
                    period_start=(
                        target.period_start
                    ),
                    period_end=(
                        target.period_end
                    ),
                    current_source_upload_id=(
                        target.source_upload_id
                    ),
                )
            )
        except RawItemsDetailReplacementError as exc:
            raise ImportBatchApprovalError(
                exc.code,
                exc.message,
                details=dict(exc.details),
            ) from exc

        replacement_ids = (
            plan.replacement_batch_ids
        )

        if (
            replacement_ids
            != reviewed_replacement_ids
        ):
            raise ImportBatchApprovalError(
                "replacement_plan_changed",
                (
                    "The Items replacement set "
                    "changed since review. Review "
                    "the batch again before "
                    "approving it."
                ),
                details={
                    (
                        "reviewed_replacement_"
                        "batch_ids"
                    ): list(
                        reviewed_replacement_ids
                    ),
                    (
                        "current_replacement_"
                        "batch_ids"
                    ): list(
                        replacement_ids
                    ),
                },
            )

        locked_replacements = list(
            ImportBatch.objects
            .select_for_update()
            .filter(
                pk__in=replacement_ids
            )
            .order_by("id")
        )

        if (
            tuple(
                replacement.pk
                for replacement
                in locked_replacements
            )
            != replacement_ids
        ):
            raise ImportBatchApprovalError(
                "replacement_plan_changed",
                (
                    "The Items replacement set "
                    "changed during approval; "
                    "retry review before approving."
                ),
            )

        for replaced in locked_replacements:
            if (
                replaced.status
                != ImportBatchStatus.APPROVED
            ):
                raise ImportBatchApprovalError(
                    (
                        "replacement_target_"
                        "not_approved"
                    ),
                    (
                        "Every Items detail "
                        "replacement target must "
                        "still be approved."
                    ),
                    details={
                        "batch_id": replaced.pk,
                        "status": replaced.status,
                    },
                )

            replaced.status = (
                ImportBatchStatus.SUPERSEDED
            )
            replaced.save(
                update_fields=[
                    "status",
                    "updated_at",
                ]
            )

        target.status = (
            ImportBatchStatus.APPROVED
        )
        target.approved_by = approved_by
        target.approved_at = timezone.now()
        target.save(
            update_fields=[
                "status",
                "approved_by",
                "approved_at",
                "updated_at",
            ]
        )

    return ItemsDetailApprovalResult(
        batch=target,
        superseded_batch_ids=(
            replacement_ids
        ),
    )
