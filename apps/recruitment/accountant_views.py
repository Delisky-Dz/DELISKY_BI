from datetime import date
from pathlib import Path

from django.contrib import messages
from django.core.paginator import Paginator
from django.http import (
    FileResponse,
    Http404,
)
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.views.decorators.http import (
    require_POST,
)

from apps.imports.access import accountant_required

from .accountant_forms import ApplicationStatusForm
from .models import (
    ApplicationStatus,
    JobApplication,
)


def _new_application_count() -> int:
    return JobApplication.objects.filter(
        status=ApplicationStatus.NEW,
    ).count()


def _calculate_age(
    birth_date,
) -> int:
    today = date.today()

    return (
        today.year
        - birth_date.year
        - (
            (today.month, today.day)
            < (
                birth_date.month,
                birth_date.day,
            )
        )
    )


def _status_summary():
    counts = {
        value: 0
        for value, _label
        in ApplicationStatus.choices
    }

    rows = (
        JobApplication.objects
        .values_list(
            "status",
            flat=True,
        )
    )

    for status in rows:
        if status in counts:
            counts[status] += 1

    return counts


@accountant_required
def application_list(request):
    selected_status = str(
        request.GET.get(
            "status",
            "",
        )
    ).strip()

    valid_statuses = {
        value
        for value, _label
        in ApplicationStatus.choices
    }

    applications = (
        JobApplication.objects
        .select_related(
            "status_updated_by",
        )
        .all()
    )

    if selected_status in valid_statuses:
        applications = applications.filter(
            status=selected_status,
        )
    else:
        selected_status = ""

    paginator = Paginator(
        applications,
        25,
    )

    page = paginator.get_page(
        request.GET.get("page")
    )

    counts = _status_summary()

    status_tabs = [
        {
            "value": "",
            "label": "الكل",
            "count": sum(
                counts.values()
            ),
        },
        *[
            {
                "value": value,
                "label": label,
                "count": counts[value],
            }
            for value, label
            in ApplicationStatus.choices
        ],
    ]

    return render(
        request,
        "recruitment/accountant_list.html",
        {
            "page": page,
            "applications": page.object_list,
            "selected_status": (
                selected_status
            ),
            "status_tabs": status_tabs,
            "recruitment_new_count": (
                counts[
                    ApplicationStatus.NEW
                ]
            ),
        },
    )


@accountant_required
def application_detail(
    request,
    application_id: int,
):
    application = get_object_or_404(
        JobApplication.objects.select_related(
            "status_updated_by",
        ),
        pk=application_id,
    )

    return render(
        request,
        "recruitment/accountant_detail.html",
        {
            "application": application,
            "application_age": (
                _calculate_age(
                    application.birth_date
                )
            ),
            "status_form": (
                ApplicationStatusForm(
                    instance=application,
                )
            ),
            "recruitment_new_count": (
                _new_application_count()
            ),
        },
    )


@accountant_required
@require_POST
def update_application_status(
    request,
    application_id: int,
):
    application = get_object_or_404(
        JobApplication,
        pk=application_id,
    )

    form = ApplicationStatusForm(
        request.POST,
        instance=application,
    )

    if not form.is_valid():
        messages.error(
            request,
            "تعذر تحديث حالة طلب التوظيف.",
        )

        return redirect(
            "recruitment_accountant:detail",
            application_id=application.pk,
        )

    application = form.save(
        commit=False,
    )

    application.status_updated_by = (
        request.user
    )

    application.save(
        update_fields=[
            "status",
            "status_updated_by",
            "updated_at",
        ]
    )

    messages.success(
        request,
        "تم تحديث حالة طلب التوظيف.",
    )

    return redirect(
        "recruitment_accountant:detail",
        application_id=application.pk,
    )


@accountant_required
def download_cv(
    request,
    application_id: int,
):
    application = get_object_or_404(
        JobApplication,
        pk=application_id,
    )

    if not application.cv:
        raise Http404(
            "CV not available."
        )

    try:
        file_handle = (
            application.cv.open("rb")
        )
    except FileNotFoundError as exc:
        raise Http404(
            "CV file not found."
        ) from exc

    filename = Path(
        application.cv.name
    ).name

    return FileResponse(
        file_handle,
        as_attachment=True,
        filename=filename,
    )
