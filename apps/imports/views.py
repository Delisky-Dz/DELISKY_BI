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

from apps.recruitment.models import (
    ApplicationStatus,
    JobApplication,
)

from .access import accountant_required
from .forms import (
    ImportUploadForm,
    RawChargementUploadFormSet,
    RawSalesUploadFormSet,
)
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
from .services.raw_chargement_derived_multi_review import (
    RawChargementDerivedImportRequest,
    create_raw_chargement_derived_multi_import_reviews,
)
from .services.raw_sales_multi_review import (
    RawSalesImportRequest,
    create_raw_sales_multi_import_reviews,
)


logger = logging.getLogger(__name__)


ACCOUNTANT_ISSUE_LABELS = {
    "date_outside_period": (
        "\u0627\u0644\u062a\u0627\u0631\u064a\u062e "
        "\u062e\u0627\u0631\u062c "
        "\u0627\u0644\u0641\u062a\u0631\u0629 "
        "\u0627\u0644\u0645\u062d\u062f\u062f\u0629"
    ),
    "truck_stopped_for_period": (
        "\u0627\u0644\u0634\u0627\u062d\u0646\u0629 "
        "\u0645\u062a\u0648\u0642\u0641\u0629 "
        "\u062e\u0644\u0627\u0644 "
        "\u0627\u0644\u0641\u062a\u0631\u0629"
    ),
}


OPERATIONAL_ISSUE_CODES = {
    "truck_stopped_for_period",
}


def _accountant_issue_label(code: str) -> str:
    normalized_code = str(code or "").strip()

    return ACCOUNTANT_ISSUE_LABELS.get(
        normalized_code,
        issue_message(normalized_code),
    )


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
    raw_upload_formset=None,
    raw_upload_result=None,
    sales_upload_formset=None,
    sales_upload_result=None,
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
        "recruitment_new_count": (
            JobApplication.objects.filter(
                status=ApplicationStatus.NEW,
            ).count()
        ),
        "service_error_details": (
            service_error_details or []
        ),
        "raw_upload_formset": (
            raw_upload_formset
            if raw_upload_formset is not None
            else RawChargementUploadFormSet(
                prefix="raw"
            )
        ),
        "raw_upload_result": raw_upload_result,
        "sales_upload_formset": (
            sales_upload_formset
            if sales_upload_formset is not None
            else RawSalesUploadFormSet(
                prefix="sales"
            )
        ),
        "sales_upload_result": sales_upload_result,
    }


def _present_service_errors(
    exc: ImportBatchReviewError,
) -> list[dict]:
    errors = exc.details.get("errors", [])

    return [
        {
            "stage": item.get("stage", ""),
            "code": item.get("code", ""),
            "message": _accountant_issue_label(
                item.get("code", "")
            ),
            "details": item.get("details", {}),
        }
        for item in errors
    ]


def _present_raw_value(value):
    if value is None or value == "":
        return "\u2014"

    if isinstance(value, bool):
        return (
            "\u0646\u0639\u0645"
            if value
            else "\u0644\u0627"
        )

    return value


def _present_problem_rows(batch) -> list[dict]:
    problem_rows = []

    reviewed_rows = batch.rows.order_by(
        "excel_row_number"
    )

    for row in reviewed_rows:
        raw_issues = (
            row.issues
            if isinstance(row.issues, list)
            else []
        )

        presented_issues = []

        for issue in raw_issues:
            if not isinstance(issue, dict):
                continue

            code = str(
                issue.get("code", "")
            )

            if code in OPERATIONAL_ISSUE_CODES:
                continue

            raw_value = issue.get(
                "raw_value"
            )

            presented_issues.append(
                {
                    "code": code,
                    "label": (
                        _accountant_issue_label(
                            code
                        )
                    ),
                    "severity": str(
                        issue.get(
                            "severity",
                            "WARNING",
                        )
                    ).upper(),
                    "field": str(
                        issue.get("field", "")
                    ),
                    "raw_value": (
                        _present_raw_value(
                            raw_value
                        )
                    ),
                    "has_raw_value": (
                        raw_value is not None
                        and raw_value != ""
                    ),
                }
            )

        if not presented_issues:
            continue

        raw_data = (
            row.raw_data
            if isinstance(row.raw_data, dict)
            else {}
        )

        raw_values = [
            {
                "field": str(field_name),
                "value": _present_raw_value(
                    value
                ),
            }
            for field_name, value
            in raw_data.items()
        ]

        problem_rows.append(
            {
                "excel_row_number": (
                    row.excel_row_number
                ),
                "status": row.status,
                "status_label": (
                    row.get_status_display()
                ),
                "issues": presented_issues,
                "issue_count": len(
                    presented_issues
                ),
                "has_error": any(
                    item["severity"] == "ERROR"
                    for item in presented_issues
                ),
                "raw_values": raw_values,
            }
        )

    return problem_rows


@accountant_required
@require_POST
def raw_chargement_upload(request):
    formset = RawChargementUploadFormSet(
        request.POST,
        request.FILES,
        prefix="raw",
    )

    if not formset.is_valid():
        return render(
            request,
            "imports/accountant_home.html",
            _home_context(
                raw_upload_formset=formset,
            ),
        )

    import_requests = []

    for form in formset.forms:
        cleaned_data = form.cleaned_data

        if cleaned_data.get("DELETE"):
            continue

        source_file = cleaned_data[
            "source_file"
        ]
        source_system = cleaned_data[
            "source_system"
        ]

        import_requests.append(
            RawChargementDerivedImportRequest(
                source=source_file,
                source_system_code=(
                    source_system.code
                ),
                period_start=cleaned_data[
                    "period_start"
                ],
                period_end=cleaned_data[
                    "period_end"
                ],
                original_filename=(
                    source_file.name
                ),
            )
        )

    result = (
        create_raw_chargement_derived_multi_import_reviews(
            tuple(import_requests),
            uploaded_by=request.user,
            reviewed_by=request.user,
        )
    )

    return render(
        request,
        "imports/accountant_home.html",
        _home_context(
            raw_upload_formset=(
                RawChargementUploadFormSet(
                    prefix="raw"
                )
            ),
            raw_upload_result=result,
        ),
    )


@accountant_required
@require_POST
def raw_sales_upload(request):
    formset = RawSalesUploadFormSet(
        request.POST,
        request.FILES,
        prefix="sales",
    )

    if not formset.is_valid():
        return render(
            request,
            "imports/accountant_home.html",
            _home_context(
                sales_upload_formset=formset,
            ),
        )

    import_requests = []

    for form in formset.forms:
        cleaned_data = form.cleaned_data

        if cleaned_data.get("DELETE"):
            continue

        source_file = cleaned_data[
            "source_file"
        ]
        source_system = cleaned_data[
            "source_system"
        ]

        import_requests.append(
            RawSalesImportRequest(
                source=source_file,
                source_system_code=(
                    source_system.code
                ),
                period_start=cleaned_data[
                    "period_start"
                ],
                period_end=cleaned_data[
                    "period_end"
                ],
                original_filename=(
                    source_file.name
                ),
            )
        )

    result = create_raw_sales_multi_import_reviews(
        tuple(import_requests),
        uploaded_by=request.user,
        reviewed_by=request.user,
    )

    return render(
        request,
        "imports/accountant_home.html",
        _home_context(
            sales_upload_formset=(
                RawSalesUploadFormSet(
                    prefix="sales"
                )
            ),
            sales_upload_result=result,
        ),
    )


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

    issue_groups = []

    for group in summary.get(
        "issue_groups",
        [],
    ):
        code = str(
            group.get("code", "")
        )

        issue_groups.append(
            {
                **group,
                "label": (
                    _accountant_issue_label(
                        code
                    )
                ),
                "display_severity": (
                    "INFO"
                    if code
                    in OPERATIONAL_ISSUE_CODES
                    else str(
                        group.get(
                            "severity",
                            "WARNING",
                        )
                    ).upper()
                ),
            }
        )

    problem_rows = _present_problem_rows(
        batch
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
            "problem_rows": problem_rows,
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
