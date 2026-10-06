import logging

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.views.decorators.http import (
    require_http_methods,
    require_POST,
    require_GET,
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
    RawItemsDetailUploadForm,
    RawItemsUploadForm,
    RawOpeningStockUploadForm,
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
from .services.approval_dispatch import (
    approve_reviewed_batch,
)
from .services.batch_approval import (
    ImportBatchApprovalError,
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
from .services.raw_items_detail_multi_review import (
    RawItemsDetailImportRequest,
    create_raw_items_detail_multi_import_reviews,
)
from .services.raw_items_multi_review import (
    RawItemsImportRequest,
    create_raw_items_multi_import_reviews,
)
from .services.raw_opening_stock_multi_review import (
    RawOpeningStockImportRequest,
    create_raw_opening_stock_multi_import_reviews,
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


def _home_context() -> dict:
    # Keep the landing page independent of upload forms and import history.
    return {
        "accountant_section": "home",
        "recruitment_new_count": JobApplication.objects.filter(
            status=ApplicationStatus.NEW,
        ).count(),
    }


def _upload_context(section, **values) -> dict:
    titles = {
        "opening_stock": "Opening Stock — المخزون الافتتاحي",
        "chargement": "Chargement — التحميل",
        "items_detail": "Items Detail — تفاصيل الأصناف",
        "items": "Items — الأصناف",
        "sales": "Sales — المبيعات",
        "standard": "استيراد الملفات الموحّدة",
    }
    return {
        "accountant_section": section,
        "section_title": titles[section],
        "section_partial": f"imports/partials/{section}_upload.html",
        **values,
    }


@accountant_required
@require_GET
def batch_list(request):
    batches = ImportBatch.objects.select_related(
        "brand", "uploaded_by", "reviewed_by", "approved_by",
    ).all()
    page = Paginator(batches, 20).get_page(request.GET.get("page"))
    counts = _status_counts()
    return render(request, "imports/accountant_batches.html", {
        "accountant_section": "batches",
        "recent_batches": page.object_list,
        "page_obj": page,
        "status_counts": counts,
        "batch_total": sum(counts.values()),
    })


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
@require_http_methods(["GET", "POST"])
def raw_chargement_upload(request):
    if request.method == "GET":
        return render(request, "imports/accountant_upload.html", _upload_context(
            "chargement", raw_upload_formset=RawChargementUploadFormSet(prefix="raw"),
        ))

    formset = RawChargementUploadFormSet(
        request.POST,
        request.FILES,
        prefix="raw",
    )

    if not formset.is_valid():
        return render(
            request,
            "imports/accountant_upload.html",
            _upload_context(
                "chargement",
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
        "imports/accountant_upload.html",
        _upload_context(
            "chargement",
            raw_upload_formset=(
                RawChargementUploadFormSet(
                    prefix="raw"
                )
            ),
            raw_upload_result=result,
        ),
    )


@accountant_required
@require_http_methods(["GET", "POST"])
def raw_sales_upload(request):
    if request.method == "GET":
        return render(request, "imports/accountant_upload.html", _upload_context(
            "sales", sales_upload_formset=RawSalesUploadFormSet(prefix="sales"),
        ))

    formset = RawSalesUploadFormSet(
        request.POST,
        request.FILES,
        prefix="sales",
    )

    if not formset.is_valid():
        return render(
            request,
            "imports/accountant_upload.html",
            _upload_context(
                "sales",
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
        "imports/accountant_upload.html",
        _upload_context(
            "sales",
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
def raw_opening_stock_upload(request):
    if request.method == "GET":
        return render(request, "imports/accountant_upload.html", _upload_context(
            "opening_stock", opening_stock_upload_form=RawOpeningStockUploadForm(),
        ))

    form = RawOpeningStockUploadForm(
        request.POST,
        request.FILES,
    )

    if not form.is_valid():
        return render(
            request,
            "imports/accountant_upload.html",
            _upload_context(
                "opening_stock",
                opening_stock_upload_form=form,
            ),
        )

    stock_date = form.cleaned_data[
        "stock_date"
    ]

    import_requests = []

    for source_file in form.cleaned_data[
        "bifa_files"
    ]:
        source_file.seek(0)

        import_requests.append(
            RawOpeningStockImportRequest(
                source=source_file,
                source_system_code="BIFA_MILA",
                stock_date=stock_date,
                original_filename=(
                    source_file.name
                ),
            )
        )

    for source_file in form.cleaned_data[
        "aio_files"
    ]:
        source_file.seek(0)

        import_requests.append(
            RawOpeningStockImportRequest(
                source=source_file,
                source_system_code="AIO_WEB",
                stock_date=stock_date,
                original_filename=(
                    source_file.name
                ),
            )
        )

    result = (
        create_raw_opening_stock_multi_import_reviews(
            tuple(import_requests),
            uploaded_by=request.user,
            reviewed_by=request.user,
        )
    )

    return render(
        request,
        "imports/accountant_upload.html",
        _upload_context(
            "opening_stock",
            opening_stock_upload_form=(
                RawOpeningStockUploadForm()
            ),
            opening_stock_upload_result=result,
        ),
    )


@accountant_required
@require_http_methods(["GET", "POST"])
def raw_items_detail_upload(request):
    if request.method == "GET":
        return render(request, "imports/accountant_upload.html", _upload_context(
            "items_detail", items_detail_upload_form=RawItemsDetailUploadForm(),
        ))

    form = RawItemsDetailUploadForm(
        request.POST,
        request.FILES,
    )

    if not form.is_valid():
        return render(
            request,
            "imports/accountant_upload.html",
            _upload_context(
                "items_detail",
                items_detail_upload_form=form,
            ),
        )

    period_start = form.cleaned_data[
        "period_start"
    ]
    period_end = form.cleaned_data[
        "period_end"
    ]

    import_requests = []

    for field_name, source_system_code in (
        ("bifa_file", "BIFA_MILA"),
        ("aio_file", "AIO_WEB"),
    ):
        source_file = form.cleaned_data.get(
            field_name
        )

        if source_file is None:
            continue

        source_file.seek(0)

        import_requests.append(
            RawItemsDetailImportRequest(
                source=source_file,
                source_system_code=(
                    source_system_code
                ),
                period_start=period_start,
                period_end=period_end,
                original_filename=(
                    source_file.name
                ),
            )
        )

    result = (
        create_raw_items_detail_multi_import_reviews(
            tuple(import_requests),
            uploaded_by=request.user,
            reviewed_by=request.user,
        )
    )

    return render(
        request,
        "imports/accountant_upload.html",
        _upload_context(
            "items_detail",
            items_detail_upload_form=(
                RawItemsDetailUploadForm()
            ),
            items_detail_upload_result=result,
        ),
    )


@accountant_required
@require_http_methods(["GET", "POST"])
def raw_items_upload(request):
    if request.method == "GET":
        return render(request, "imports/accountant_upload.html", _upload_context(
            "items", items_upload_form=RawItemsUploadForm(),
        ))

    form = RawItemsUploadForm(
        request.POST,
        request.FILES,
    )

    if not form.is_valid():
        return render(
            request,
            "imports/accountant_upload.html",
            _upload_context(
                "items",
                items_upload_form=form,
            ),
        )

    period_start = form.cleaned_data[
        "period_start"
    ]
    period_end = form.cleaned_data[
        "period_end"
    ]

    import_requests = []

    for source_file in form.cleaned_data[
        "bifa_files"
    ]:
        source_file.seek(0)

        import_requests.append(
            RawItemsImportRequest(
                source=source_file,
                source_system_code="BIFA_MILA",
                period_start=period_start,
                period_end=period_end,
                original_filename=(
                    source_file.name
                ),
            )
        )

    for source_file in form.cleaned_data[
        "aio_files"
    ]:
        source_file.seek(0)

        import_requests.append(
            RawItemsImportRequest(
                source=source_file,
                source_system_code="AIO_WEB",
                period_start=period_start,
                period_end=period_end,
                original_filename=(
                    source_file.name
                ),
            )
        )

    result = (
        create_raw_items_multi_import_reviews(
            tuple(import_requests),
            uploaded_by=request.user,
            reviewed_by=request.user,
        )
    )

    return render(
        request,
        "imports/accountant_upload.html",
        _upload_context(
            "items",
            items_upload_form=RawItemsUploadForm(),
            items_upload_result=result,
        ),
    )


@accountant_required
@require_http_methods(["GET", "POST"])
def accountant_home(request):
    if request.method == "POST":
        # Preserve the original canonical import POST endpoint.
        return standard_upload(request)
    return render(request, "imports/accountant_home.html", _home_context())


@accountant_required
@require_http_methods(["GET", "POST"])
def standard_upload(request):
    if request.method == "GET":
        return render(request, "imports/accountant_upload.html", _upload_context(
            "standard", upload_form=ImportUploadForm(),
        ))

    upload_form = ImportUploadForm(
        request.POST,
        request.FILES,
    )

    if not upload_form.is_valid():
        return render(
            request,
            "imports/accountant_upload.html",
            _upload_context(
                "standard",
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
            "imports/accountant_upload.html",
            _upload_context(
                "standard",
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
            "imports/accountant_upload.html",
            _upload_context(
                "standard",
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
            "source_upload",
            "source_upload__source_system",
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

    items_detail = summary.get(
        "items_detail"
    )
    if not isinstance(items_detail, dict):
        items_detail = None

    detail_replacement_batches = []

    if items_detail is not None:
        replacement_ids = items_detail.get(
            "replacement_batch_ids",
            [],
        )

        if isinstance(
            replacement_ids,
            (list, tuple),
        ):
            valid_ids = [
                value
                for value in replacement_ids
                if (
                    isinstance(value, int)
                    and not isinstance(value, bool)
                    and value > 0
                )
            ]

            if valid_ids:
                replacements_by_id = {
                    candidate.pk: candidate
                    for candidate in (
                        ImportBatch.objects
                        .select_related("brand")
                        .filter(pk__in=valid_ids)
                    )
                }

                detail_replacement_batches = [
                    replacements_by_id[batch_id]
                    for batch_id in valid_ids
                    if batch_id in replacements_by_id
                ]

    source_audit = {}

    if batch.source_upload_id:
        raw_audit = (
            batch.source_upload.audit_metadata
            or {}
        )
        candidate_audit = raw_audit.get(
            "items_detail",
            {},
        )
        if isinstance(candidate_audit, dict):
            source_audit = candidate_audit

    source_file_sha256 = (
        batch.file_sha256
        or (
            batch.source_upload.file_sha256
            if batch.source_upload_id
            else ""
        )
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
            "items_detail": items_detail,
            "detail_replacement_batches": (
                detail_replacement_batches
            ),
            "items_detail_source_audit": (
                source_audit
            ),
            "source_file_sha256": (
                source_file_sha256
            ),
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
        result = approve_reviewed_batch(
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
