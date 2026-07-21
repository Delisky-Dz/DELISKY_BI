import logging

from django.contrib import messages
from django.db.models import Count
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.views.decorators.http import (
    require_http_methods,
    require_POST,
)

from .access import accountant_required
from .forms import ImportUploadForm
from .models import (
    ImportBatch,
    ImportBatchStatus,
)
from .presenters import (
    approval_error_message,
    issue_message,
    review_error_message,
)
from .services.batch_approval import (
    ImportBatchApprovalError,
    approve_import_batch,
)
from .services.batch_review import (
    ImportBatchReviewError,
    create_or_update_import_review,
)


logger = logging.getLogger(__name__)


def _status_counts() -> dict[str, int]:
    counts = {
        value: 0
        for value, _label
        in ImportBatchStatus.choices
    }

    rows = (
        ImportBatch.objects
        .values("status")
        .annotate(total=Count("id"))
    )

    for row in rows:
        counts[row["status"]] = row["total"]

    return counts


def _home_context(
    *,
    upload_form: ImportUploadForm | None = None,
    service_error_details: list[dict] | None = None,
) -> dict:
    recent_batches = (
        ImportBatch.objects
        .select_related(
            "brand",
            "uploaded_by",
            "reviewed_by",
            "approved_by",
        )
        .all()[:20]
    )

    counts = _status_counts()

    return {
        "upload_form": (
            upload_form
            if upload_form is not None
            else ImportUploadForm()
        ),
        "recent_batches": recent_batches,
        "status_counts": counts,
        "batch_total": sum(counts.values()),
        "service_error_details": (
            service_error_details or []
        ),
    }


def _present_service_errors(
    exc: ImportBatchReviewError,
) -> list[dict]:
    errors = exc.details.get("errors", [])

    return [
        {
            "stage": item.get("stage", ""),
            "code": item.get("code", ""),
            "message": issue_message(
                item.get("code", "")
            ),
            "details": item.get("details", {}),
        }
        for item in errors
    ]


@accountant_required
@require_http_methods(["GET", "POST"])
def accountant_home(request):
    if request.method == "GET":
        return render(
            request,
            "imports/accountant_home.html",
            _home_context(),
        )

    upload_form = ImportUploadForm(
        request.POST,
        request.FILES,
    )

    if not upload_form.is_valid():
        return render(
            request,
            "imports/accountant_home.html",
            _home_context(
                upload_form=upload_form,
            ),
        )

    source_file = upload_form.cleaned_data[
        "source_file"
    ]

    try:
        result = create_or_update_import_review(
            source_file,
            uploaded_by=request.user,
            reviewed_by=request.user,
            original_filename=source_file.name,
        )
    except ImportBatchReviewError as exc:
        upload_form.add_error(
            None,
            review_error_message(exc),
        )

        return render(
            request,
            "imports/accountant_home.html",
            _home_context(
                upload_form=upload_form,
                service_error_details=(
                    _present_service_errors(exc)
                ),
            ),
        )
    except Exception:
        logger.exception(
            "Unexpected accountant import review failure."
        )

        upload_form.add_error(
            None,
            (
                "\u062d\u062f\u062b \u062e\u0637\u0623 "
                "\u063a\u064a\u0631 \u0645\u062a\u0648\u0642\u0639 "
                "\u0623\u062b\u0646\u0627\u0621 "
                "\u0645\u0631\u0627\u062c\u0639\u0629 \u0627\u0644\u0645\u0644\u0641."
            ),
        )

        return render(
            request,
            "imports/accountant_home.html",
            _home_context(
                upload_form=upload_form,
            ),
        )

    messages.success(
        request,
        (
            "\u062a\u0645 \u0641\u062d\u0635 "
            "\u0627\u0644\u0645\u0644\u0641 \u0648\u0625\u0646\u0634\u0627\u0621 "
            "\u0645\u0644\u062e\u0635 \u0627\u0644\u0645\u0631\u0627\u062c\u0639\u0629."
        ),
    )

    return redirect(
        "imports:batch_detail",
        batch_id=result.batch.pk,
    )


@accountant_required
def batch_detail(request, batch_id: int):
    batch = get_object_or_404(
        ImportBatch.objects.select_related(
            "brand",
            "uploaded_by",
            "reviewed_by",
            "approved_by",
            "replaces_batch",
        ),
        pk=batch_id,
    )

    summary = batch.review_summary or {}

    issue_groups = [
        {
            **group,
            "label": issue_message(
                group.get("code", "")
            ),
        }
        for group in summary.get(
            "issue_groups",
            [],
        )
    ]

    rows = list(
        batch.rows
        .order_by("excel_row_number")[:100]
    )

    can_approve = (
        batch.status
        == ImportBatchStatus.REVIEWED
        and batch.error_count == 0
    )

    return render(
        request,
        "imports/batch_detail.html",
        {
            "batch": batch,
            "summary": summary,
            "issue_groups": issue_groups,
            "rows": rows,
            "can_approve": can_approve,
        },
    )


@accountant_required
@require_POST
def approve_batch(request, batch_id: int):
    batch = get_object_or_404(
        ImportBatch,
        pk=batch_id,
    )

    try:
        result = approve_import_batch(
            batch.pk,
            approved_by=request.user,
        )
    except ImportBatchApprovalError as exc:
        messages.error(
            request,
            approval_error_message(exc),
        )
    except Exception:
        logger.exception(
            "Unexpected accountant import approval failure."
        )

        messages.error(
            request,
            (
                "\u062d\u062f\u062b \u062e\u0637\u0623 "
                "\u063a\u064a\u0631 \u0645\u062a\u0648\u0642\u0639 "
                "\u0623\u062b\u0646\u0627\u0621 "
                "\u0627\u0639\u062a\u0645\u0627\u062f \u0627\u0644\u062f\u0641\u0639\u0629."
            ),
        )
    else:
        messages.success(
            request,
            (
                "\u062a\u0645 \u0627\u0639\u062a\u0645\u0627\u062f "
                "\u0627\u0644\u062f\u0641\u0639\u0629 \u0628\u0646\u062c\u0627\u062d."
            ),
        )

        batch_id = result.batch.pk

    return redirect(
        "imports:batch_detail",
        batch_id=batch_id,
    )
