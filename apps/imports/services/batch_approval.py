import logging
from dataclasses import dataclass
from typing import Any

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.utils import timezone

from apps.imports.models import (
    ImportBatch,
    ImportBatchStatus,
    ImportRowStatus,
)


logger = logging.getLogger(__name__)


class ImportBatchApprovalError(Exception):
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
class ImportBatchApprovalResult:
    batch: ImportBatch
    superseded_batch_id: int | None
    deleted_source_filename: str


def _validation_details(
    exc: ValidationError,
) -> dict[str, Any]:
    if hasattr(exc, "message_dict"):
        return {
            field: [
                str(message)
                for message in messages
            ]
            for field, messages
            in exc.message_dict.items()
        }

    return {
        "errors": [
            str(message)
            for message in exc.messages
        ],
    }


def _delete_source_file(
    storage: Any,
    filename: str,
) -> None:
    if not filename:
        return

    try:
        storage.delete(filename)
    except Exception:
        logger.exception(
            "Could not delete approved import source file %s.",
            filename,
        )


def _validate_staged_rows(
    batch: ImportBatch,
) -> None:
    counts = batch.rows.aggregate(
        total=Count("id"),
        accepted=Count(
            "id",
            filter=Q(
                status=ImportRowStatus.ACCEPTED,
            ),
        ),
        excluded=Count(
            "id",
            filter=Q(
                status=ImportRowStatus.EXCLUDED,
            ),
        ),
        stopped=Count(
            "id",
            filter=Q(
                status=ImportRowStatus.STOPPED,
            ),
        ),
    )

    expected = {
        "total": batch.total_rows,
        "accepted": batch.accepted_rows,
        "excluded": batch.excluded_rows,
        "stopped": batch.stopped_rows,
    }

    actual = {
        "total": counts["total"] or 0,
        "accepted": counts["accepted"] or 0,
        "excluded": counts["excluded"] or 0,
        "stopped": counts["stopped"] or 0,
    }

    recognized_total = (
        actual["accepted"]
        + actual["excluded"]
        + actual["stopped"]
    )

    if actual["total"] != recognized_total:
        raise ImportBatchApprovalError(
            "unsupported_row_status",
            (
                "The batch contains rows with an "
                "unsupported staging status."
            ),
            details={
                "counts": actual,
            },
        )

    if actual != expected:
        raise ImportBatchApprovalError(
            "row_count_mismatch",
            (
                "The saved ImportRow counts do not "
                "match the reviewed batch totals."
            ),
            details={
                "expected": expected,
                "actual": actual,
            },
        )


def approve_import_batch(
    batch: ImportBatch | int,
    *,
    approved_by: Any,
) -> ImportBatchApprovalResult:
    batch_id = (
        batch.pk
        if isinstance(batch, ImportBatch)
        else batch
    )

    if not batch_id:
        raise ImportBatchApprovalError(
            "unsaved_batch",
            (
                "The ImportBatch must already exist "
                "before it can be approved."
            ),
        )

    if (
        approved_by is None
        or not getattr(approved_by, "pk", None)
    ):
        raise ImportBatchApprovalError(
            "invalid_approver",
            (
                "A saved user is required to approve "
                "the import batch."
            ),
        )

    if not getattr(approved_by, "is_active", False):
        raise ImportBatchApprovalError(
            "inactive_approver",
            (
                "An inactive user cannot approve "
                "an import batch."
            ),
        )

    try:
        with transaction.atomic():
            locked_batch = (
                ImportBatch.objects
                .select_for_update()
                .get(pk=batch_id)
            )

            if (
                locked_batch.status
                == ImportBatchStatus.APPROVED
            ):
                raise ImportBatchApprovalError(
                    "already_approved",
                    (
                        "This import batch has already "
                        "been approved."
                    ),
                )

            if (
                locked_batch.status
                != ImportBatchStatus.REVIEWED
            ):
                raise ImportBatchApprovalError(
                    "batch_not_reviewed",
                    (
                        "Only a successfully reviewed "
                        "batch can be approved."
                    ),
                    details={
                        "status": locked_batch.status,
                    },
                )

            if locked_batch.error_count:
                raise ImportBatchApprovalError(
                    "batch_has_errors",
                    (
                        "A batch containing blocking "
                        "errors cannot be approved."
                    ),
                    details={
                        "error_count": (
                            locked_batch.error_count
                        ),
                    },
                )

            if not locked_batch.content_sha256:
                raise ImportBatchApprovalError(
                    "missing_content_hash",
                    (
                        "The reviewed content hash is "
                        "missing."
                    ),
                )

            _validate_staged_rows(locked_batch)

            superseded_batch = None

            if locked_batch.replaces_batch_id:
                superseded_batch = (
                    ImportBatch.objects
                    .select_for_update()
                    .get(
                        pk=(
                            locked_batch
                            .replaces_batch_id
                        )
                    )
                )

                if (
                    superseded_batch.status
                    != ImportBatchStatus.APPROVED
                ):
                    raise ImportBatchApprovalError(
                        "replacement_target_not_approved",
                        (
                            "The batch being replaced "
                            "must currently be approved."
                        ),
                        details={
                            "status": (
                                superseded_batch.status
                            ),
                        },
                    )

                if (
                    superseded_batch.brand_id
                    != locked_batch.brand_id
                    or (
                        superseded_batch.report_type
                        != locked_batch.report_type
                    )
                    or (
                        superseded_batch.period_start
                        != locked_batch.period_start
                    )
                    or (
                        superseded_batch.period_end
                        != locked_batch.period_end
                    )
                ):
                    raise ImportBatchApprovalError(
                        "replacement_scope_mismatch",
                        (
                            "The replacement batch must "
                            "match the original brand, "
                            "report type and period."
                        ),
                    )

                superseded_batch.status = (
                    ImportBatchStatus.SUPERSEDED
                )

                try:
                    superseded_batch.full_clean()
                except ValidationError as exc:
                    raise ImportBatchApprovalError(
                        "invalid_replacement_target",
                        (
                            "The replaced batch could not "
                            "be superseded safely."
                        ),
                        details=_validation_details(exc),
                    ) from exc

                superseded_batch.save(
                    update_fields=[
                        "status",
                        "updated_at",
                    ]
                )

                locked_batch.replaces_batch = (
                    superseded_batch
                )

            source_filename = (
                locked_batch.source_file.name
                if locked_batch.source_file
                else ""
            )

            source_storage = (
                locked_batch.source_file.storage
                if source_filename
                else None
            )

            locked_batch.status = (
                ImportBatchStatus.APPROVED
            )
            locked_batch.approved_by = approved_by
            locked_batch.approved_at = timezone.now()
            locked_batch.source_file = ""

            try:
                locked_batch.full_clean()
            except ValidationError as exc:
                raise ImportBatchApprovalError(
                    "invalid_approval",
                    (
                        "The batch could not be approved "
                        "because its data is invalid or "
                        "duplicates approved data."
                    ),
                    details=_validation_details(exc),
                ) from exc

            locked_batch.save(
                update_fields=[
                    "status",
                    "approved_by",
                    "approved_at",
                    "source_file",
                    "opening_month",
                    "updated_at",
                ]
            )

            if source_storage and source_filename:
                transaction.on_commit(
                    lambda: _delete_source_file(
                        source_storage,
                        source_filename,
                    )
                )

            result = ImportBatchApprovalResult(
                batch=locked_batch,
                superseded_batch_id=(
                    superseded_batch.pk
                    if superseded_batch
                    else None
                ),
                deleted_source_filename=(
                    source_filename
                ),
            )

    except ImportBatch.DoesNotExist as exc:
        raise ImportBatchApprovalError(
            "batch_not_found",
            "The requested ImportBatch does not exist.",
            details={
                "batch_id": batch_id,
            },
        ) from exc
    except IntegrityError as exc:
        raise ImportBatchApprovalError(
            "approval_conflict",
            (
                "The batch conflicts with data that "
                "was already approved."
            ),
        ) from exc

    return result
