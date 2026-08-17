from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from django.core.files.base import ContentFile
from django.db import transaction

from apps.imports.models import (
    ImportSourceSystem,
    ImportSourceUpload,
)

from .batch_review import (
    ImportBatchReviewError,
    _read_source_bytes,
    _validate_user,
)


class ImportSourceUploadStoreError(Exception):
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
class ImportSourceUploadStoreResult:
    source_upload: ImportSourceUpload
    created: bool


def _get_active_source_system(
    source_system_code: str,
) -> ImportSourceSystem:
    normalized_code = str(
        source_system_code or ""
    ).strip().upper()

    if not normalized_code:
        raise ImportSourceUploadStoreError(
            "source_system_not_found",
            "Source system was not found.",
            details={
                "source_system_code": source_system_code,
            },
        )

    source_system = (
        ImportSourceSystem.objects
        .filter(code__iexact=normalized_code)
        .first()
    )

    if source_system is None:
        raise ImportSourceUploadStoreError(
            "source_system_not_found",
            "Source system was not found.",
            details={
                "source_system_code": normalized_code,
            },
        )

    if not source_system.is_active:
        raise ImportSourceUploadStoreError(
            "source_system_inactive",
            "Source system is inactive.",
            details={
                "source_system_id": source_system.pk,
                "source_system_code": source_system.code,
            },
        )

    return source_system


def create_import_source_upload(
    source: Any,
    *,
    source_system_code: str,
    uploaded_by: Any,
    worksheet_name: str = "",
    original_filename: str | None = None,
) -> ImportSourceUploadStoreResult:
    try:
        _validate_user(
            uploaded_by,
            "uploaded_by",
        )
        file_bytes = _read_source_bytes(source)
    except ImportBatchReviewError as exc:
        raise ImportSourceUploadStoreError(
            exc.code,
            exc.message,
            details=dict(exc.details),
        ) from exc

    if not file_bytes:
        raise ImportSourceUploadStoreError(
            "empty_file",
            "The raw Excel file is empty.",
        )

    source_system = _get_active_source_system(
        source_system_code
    )

    filename = (
        original_filename
        or getattr(source, "name", None)
        or ""
    )

    filename = str(filename).strip()

    if not filename:
        raise ImportSourceUploadStoreError(
            "original_filename_missing",
            "The original filename is required.",
        )

    file_hash = sha256(
        file_bytes
    ).hexdigest()

    existing = (
        ImportSourceUpload.objects
        .select_related("source_system")
        .filter(file_sha256=file_hash)
        .first()
    )

    if existing is not None:
        if existing.source_system_id != source_system.pk:
            raise ImportSourceUploadStoreError(
                "source_upload_system_mismatch",
                (
                    "The same raw file was already stored "
                    "for a different source system."
                ),
                details={
                    "existing_source_system_code": (
                        existing.source_system.code
                    ),
                    "requested_source_system_code": (
                        source_system.code
                    ),
                    "file_sha256": file_hash,
                },
            )

        return ImportSourceUploadStoreResult(
            source_upload=existing,
            created=False,
        )

    target = ImportSourceUpload(
        source_system=source_system,
        original_filename=filename,
        worksheet_name=str(
            worksheet_name or ""
        ).strip(),
        file_size_bytes=len(file_bytes),
        file_sha256=file_hash,
        uploaded_by=uploaded_by,
    )

    saved_file_name = ""

    try:
        with transaction.atomic():
            target.source_file.save(
                filename,
                ContentFile(file_bytes),
                save=False,
            )

            saved_file_name = (
                target.source_file.name
            )

            target.full_clean()
            target.save()

    except Exception:
        if saved_file_name:
            try:
                target.source_file.storage.delete(
                    saved_file_name
                )
            except Exception:
                pass

        raise

    return ImportSourceUploadStoreResult(
        source_upload=target,
        created=True,
    )
