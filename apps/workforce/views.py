from django.contrib import messages
from django.contrib.auth.decorators import (
    permission_required,
)
from django.db.models import Q
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.views.decorators.http import require_POST

from apps.imports.access import accountant_required

from .forms import WorkerCategoryForm, WorkerForm
from .models import Worker, WorkerCategory


STATUS_ALL = "all"
STATUS_ACTIVE = "active"
STATUS_INACTIVE = "inactive"

VALID_STATUSES = {
    STATUS_ALL,
    STATUS_ACTIVE,
    STATUS_INACTIVE,
}


@accountant_required
@permission_required(
    "workforce.view_worker",
    raise_exception=True,
)
def worker_list(request):
    query = request.GET.get(
        "q",
        "",
    ).strip()

    status = request.GET.get(
        "status",
        STATUS_ALL,
    ).strip()

    if status not in VALID_STATUSES:
        status = STATUS_ALL

    workers = Worker.objects.all()

    if query:
        workers = workers.filter(
            Q(employee_code__icontains=query)
            | Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(phone__icontains=query)
        )

    if status == STATUS_ACTIVE:
        workers = workers.filter(
            is_active=True
        )
    elif status == STATUS_INACTIVE:
        workers = workers.filter(
            is_active=False
        )

    workers = workers.order_by(
        "last_name",
        "first_name",
    )

    all_workers = Worker.objects.all()

    context = {
        "workers": workers,
        "query": query,
        "selected_status": status,
        "total_workers": all_workers.count(),
        "active_workers": all_workers.filter(
            is_active=True
        ).count(),
        "inactive_workers": all_workers.filter(
            is_active=False
        ).count(),
    }

    return render(
        request,
        "workforce/worker_list.html",
        context,
    )


@accountant_required
@permission_required(
    "workforce.add_worker",
    raise_exception=True,
)
def worker_create(request):
    if request.method == "POST":
        form = WorkerForm(
            request.POST
        )

        if form.is_valid():
            worker = form.save()

            messages.success(
                request,
                (
                    "\u062a\u0645\u062a "
                    "\u0625\u0636\u0627\u0641\u0629 "
                    "\u0627\u0644\u0639\u0627\u0645\u0644 "
                    f"{worker.full_name} "
                    "\u0628\u0646\u062c\u0627\u062d."
                ),
            )

            return redirect(
                "workforce:worker_list"
            )
    else:
        form = WorkerForm()

    return render(
        request,
        "workforce/worker_form.html",
        {
            "form": form,
            "worker": None,
            "form_mode": "create",
        },
    )


@accountant_required
@permission_required(
    "workforce.change_worker",
    raise_exception=True,
)
def worker_update(request, worker_id):
    worker = get_object_or_404(
        Worker,
        pk=worker_id,
    )

    if request.method == "POST":
        form = WorkerForm(
            request.POST,
            instance=worker,
        )

        if form.is_valid():
            worker = form.save()

            messages.success(
                request,
                (
                    "\u062a\u0645 "
                    "\u062a\u062d\u062f\u064a\u062b "
                    "\u0628\u064a\u0627\u0646\u0627\u062a "
                    "\u0627\u0644\u0639\u0627\u0645\u0644 "
                    f"{worker.full_name} "
                    "\u0628\u0646\u062c\u0627\u062d."
                ),
            )

            return redirect(
                "workforce:worker_list"
            )
    else:
        form = WorkerForm(
            instance=worker
        )

    return render(
        request,
        "workforce/worker_form.html",
        {
            "form": form,
            "worker": worker,
            "form_mode": "update",
        },
    )


@require_POST
@accountant_required
@permission_required(
    "workforce.change_worker",
    raise_exception=True,
)
def worker_toggle_status(
    request,
    worker_id,
):
    worker = get_object_or_404(
        Worker,
        pk=worker_id,
    )

    worker.is_active = (
        not worker.is_active
    )

    worker.save(
        update_fields=(
            "is_active",
            "updated_at",
        )
    )

    if worker.is_active:
        status_message = (
            "\u062a\u0641\u0639\u064a\u0644"
        )
    else:
        status_message = (
            "\u062a\u0639\u0637\u064a\u0644"
        )

    messages.success(
        request,
        (
            f"\u062a\u0645 {status_message} "
            "\u0627\u0644\u0639\u0627\u0645\u0644 "
            f"{worker.full_name}."
        ),
    )

    return redirect(
        "workforce:worker_list"
    )


@accountant_required
@permission_required(
    "workforce.view_workercategory",
    raise_exception=True,
)
def category_list(request):
    query = request.GET.get(
        "q",
        "",
    ).strip()

    status = request.GET.get(
        "status",
        STATUS_ALL,
    ).strip()

    if status not in VALID_STATUSES:
        status = STATUS_ALL

    categories = (
        WorkerCategory.objects
        .select_related(
            "updated_by",
        )
    )

    if query:
        categories = categories.filter(
            Q(name__icontains=query)
            | Q(code__icontains=query)
            | Q(description__icontains=query)
        )

    if status == STATUS_ACTIVE:
        categories = categories.filter(
            is_active=True
        )
    elif status == STATUS_INACTIVE:
        categories = categories.filter(
            is_active=False
        )

    categories = categories.order_by(
        "sort_order",
        "name",
    )

    all_categories = (
        WorkerCategory.objects.all()
    )

    context = {
        "categories": categories,
        "query": query,
        "selected_status": status,
        "total_categories": (
            all_categories.count()
        ),
        "active_categories": (
            all_categories.filter(
                is_active=True
            ).count()
        ),
        "system_categories": (
            all_categories.filter(
                is_system=True
            ).count()
        ),
        "custom_categories": (
            all_categories.filter(
                is_system=False
            ).count()
        ),
    }

    return render(
        request,
        "workforce/category_list.html",
        context,
    )


@accountant_required
@permission_required(
    "workforce.add_workercategory",
    raise_exception=True,
)
def category_create(request):
    if request.method == "POST":
        form = WorkerCategoryForm(
            request.POST
        )

        if form.is_valid():
            category = form.save(
                commit=False
            )

            category.created_by = (
                request.user
            )
            category.updated_by = (
                request.user
            )

            category.save()

            messages.success(
                request,
                (
                    "\u062a\u0645\u062a \u0625\u0636\u0627\u0641\u0629 "
                    "\u0635\u0646\u0641 \u0627\u0644\u0639\u0645\u0627\u0644 "
                    f"{category.name} "
                    "\u0628\u0646\u062c\u0627\u062d."
                ),
            )

            return redirect(
                "workforce:category_list"
            )
    else:
        form = WorkerCategoryForm()

    return render(
        request,
        "workforce/category_form.html",
        {
            "form": form,
            "category": None,
            "form_mode": "create",
        },
    )


@accountant_required
@permission_required(
    "workforce.change_workercategory",
    raise_exception=True,
)
def category_update(
    request,
    category_id,
):
    category = get_object_or_404(
        WorkerCategory,
        pk=category_id,
    )

    if request.method == "POST":
        form = WorkerCategoryForm(
            request.POST,
            instance=category,
        )

        if form.is_valid():
            category = form.save(
                commit=False
            )

            category.updated_by = (
                request.user
            )

            category.save()

            messages.success(
                request,
                (
                    "\u062a\u0645 \u062a\u062d\u062f\u064a\u062b "
                    "\u0635\u0646\u0641 \u0627\u0644\u0639\u0645\u0627\u0644 "
                    f"{category.name} "
                    "\u0628\u0646\u062c\u0627\u062d."
                ),
            )

            return redirect(
                "workforce:category_list"
            )
    else:
        form = WorkerCategoryForm(
            instance=category
        )

    return render(
        request,
        "workforce/category_form.html",
        {
            "form": form,
            "category": category,
            "form_mode": "update",
        },
    )


@require_POST
@accountant_required
@permission_required(
    "workforce.change_workercategory",
    raise_exception=True,
)
def category_toggle_status(
    request,
    category_id,
):
    category = get_object_or_404(
        WorkerCategory,
        pk=category_id,
    )

    category.is_active = (
        not category.is_active
    )

    category.updated_by = (
        request.user
    )

    category.save(
        update_fields=(
            "is_active",
            "updated_by",
            "updated_at",
        )
    )

    if category.is_active:
        status_message = (
            "\u062a\u0641\u0639\u064a\u0644"
        )
    else:
        status_message = (
            "\u062a\u0639\u0637\u064a\u0644"
        )

    messages.success(
        request,
        (
            f"\u062a\u0645 {status_message} "
            "\u0635\u0646\u0641 "
            f"{category.name}."
        ),
    )

    return redirect(
        "workforce:category_list"
    )
