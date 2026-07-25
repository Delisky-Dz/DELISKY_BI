from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import (
    login_required,
    permission_required,
)
from django.db.models import Q
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.views.decorators.http import require_POST

from apps.imports.access import (
    accountant_required,
    can_access_accountant_area,
)

from .forms import (
    WorkerCapabilityForm,
    WorkerCategoryForm,
    WorkerForm,
    WorkerPositionPeriodForm,
)
from .models import (
    Worker,
    WorkerCapability,
    WorkerCategory,
    WorkerPositionPeriod,
)


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
        .prefetch_related(
            "default_capabilities",
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
            form.save_m2m()

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
            form.save_m2m()

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


@accountant_required
@permission_required(
    "workforce.view_workercapability",
    raise_exception=True,
)
def capability_list(request):
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

    capabilities = (
        WorkerCapability.objects
        .select_related(
            "updated_by",
        )
    )

    if query:
        capabilities = capabilities.filter(
            Q(name__icontains=query)
            | Q(code__icontains=query)
            | Q(description__icontains=query)
        )

    if status == STATUS_ACTIVE:
        capabilities = capabilities.filter(
            is_active=True
        )
    elif status == STATUS_INACTIVE:
        capabilities = capabilities.filter(
            is_active=False
        )

    capabilities = capabilities.order_by(
        "sort_order",
        "name",
    )

    all_capabilities = (
        WorkerCapability.objects.all()
    )

    return render(
        request,
        "workforce/capability_list.html",
        {
            "capabilities": capabilities,
            "query": query,
            "selected_status": status,
            "total_capabilities": (
                all_capabilities.count()
            ),
            "active_capabilities": (
                all_capabilities.filter(
                    is_active=True
                ).count()
            ),
            "system_capabilities": (
                all_capabilities.filter(
                    is_system=True
                ).count()
            ),
            "custom_capabilities": (
                all_capabilities.filter(
                    is_system=False
                ).count()
            ),
        },
    )


@accountant_required
@permission_required(
    "workforce.add_workercapability",
    raise_exception=True,
)
def capability_create(request):
    if request.method == "POST":
        form = WorkerCapabilityForm(
            request.POST
        )

        if form.is_valid():
            capability = form.save(
                commit=False
            )

            capability.created_by = (
                request.user
            )
            capability.updated_by = (
                request.user
            )

            capability.save()

            messages.success(
                request,
                (
                    "تمت إضافة قدرة "
                    f"{capability.name} "
                    "بنجاح."
                ),
            )

            return redirect(
                "workforce:capability_list"
            )
    else:
        form = WorkerCapabilityForm()

    return render(
        request,
        "workforce/capability_form.html",
        {
            "form": form,
            "capability": None,
            "form_mode": "create",
        },
    )


@accountant_required
@permission_required(
    "workforce.change_workercapability",
    raise_exception=True,
)
def capability_update(
    request,
    capability_id,
):
    capability = get_object_or_404(
        WorkerCapability,
        pk=capability_id,
    )

    if request.method == "POST":
        form = WorkerCapabilityForm(
            request.POST,
            instance=capability,
        )

        if form.is_valid():
            capability = form.save(
                commit=False
            )

            capability.updated_by = (
                request.user
            )

            capability.save()

            messages.success(
                request,
                (
                    "تم تحديث قدرة "
                    f"{capability.name} "
                    "بنجاح."
                ),
            )

            return redirect(
                "workforce:capability_list"
            )
    else:
        form = WorkerCapabilityForm(
            instance=capability
        )

    return render(
        request,
        "workforce/capability_form.html",
        {
            "form": form,
            "capability": capability,
            "form_mode": "update",
        },
    )


@require_POST
@accountant_required
@permission_required(
    "workforce.change_workercapability",
    raise_exception=True,
)
def capability_toggle_status(
    request,
    capability_id,
):
    capability = get_object_or_404(
        WorkerCapability,
        pk=capability_id,
    )

    capability.is_active = (
        not capability.is_active
    )
    capability.updated_by = (
        request.user
    )

    capability.save(
        update_fields=(
            "is_active",
            "updated_by",
            "updated_at",
        )
    )

    if capability.is_active:
        status_message = "تفعيل"
    else:
        status_message = "تعطيل"

    messages.success(
        request,
        (
            f"تم {status_message} "
            f"قدرة {capability.name}."
        ),
    )

    return redirect(
        "workforce:capability_list"
    )


@login_required
@permission_required(
    (
        "workforce.view_worker",
        "workforce.view_workerpositionperiod",
    ),
    raise_exception=True,
)
def worker_detail(
    request,
    worker_id,
):
    worker = get_object_or_404(
        Worker.objects.prefetch_related(
            "capabilities",
        ),
        pk=worker_id,
    )

    today = date.today()

    position_periods = list(
        WorkerPositionPeriod.objects
        .filter(worker=worker)
        .select_related(
            "category",
            "updated_by",
        )
        .order_by(
            "-start_date",
            "-pk",
        )
    )

    current_position = None
    upcoming_count = 0
    previous_count = 0

    for position in position_periods:
        if position.start_date > today:
            position.ui_status = "upcoming"
            upcoming_count += 1
        elif (
            position.end_date is None
            or position.end_date >= today
        ):
            position.ui_status = "current"
            current_position = position
        else:
            position.ui_status = "previous"
            previous_count += 1

    return render(
        request,
        "workforce/worker_detail.html",
        {
            "worker": worker,
            "position_periods": position_periods,
            "current_position": current_position,
            "upcoming_count": upcoming_count,
            "previous_count": previous_count,
            "can_access_worker_management": (
                can_access_accountant_area(
                    request.user
                )
            ),
        },
    )


@accountant_required
@permission_required(
    "workforce.add_workerpositionperiod",
    raise_exception=True,
)
def worker_position_create(
    request,
    worker_id,
):
    worker = get_object_or_404(
        Worker,
        pk=worker_id,
    )

    if request.method == "POST":
        form = WorkerPositionPeriodForm(
            request.POST,
            worker=worker,
        )

        if form.is_valid():
            position = form.save(
                commit=False
            )

            position.worker = worker
            position.created_by = request.user
            position.updated_by = request.user
            position.save()

            messages.success(
                request,
                (
                    "\u062a\u0645\u062a "
                    "\u0625\u0636\u0627\u0641\u0629 "
                    "\u0645\u0646\u0635\u0628 "
                    f"{position.category.name} "
                    "\u0625\u0644\u0649 "
                    "\u0633\u062c\u0644 "
                    f"{worker.full_name}."
                ),
            )

            return redirect(
                "workforce:worker_detail",
                worker_id=worker.pk,
            )
    else:
        form = WorkerPositionPeriodForm(
            worker=worker,
        )

    return render(
        request,
        "workforce/worker_position_form.html",
        {
            "form": form,
            "worker": worker,
            "position": None,
            "form_mode": "create",
        },
    )


@accountant_required
@permission_required(
    "workforce.change_workerpositionperiod",
    raise_exception=True,
)
def worker_position_update(
    request,
    worker_id,
    position_id,
):
    worker = get_object_or_404(
        Worker,
        pk=worker_id,
    )

    position = get_object_or_404(
        WorkerPositionPeriod,
        pk=position_id,
        worker=worker,
    )

    if request.method == "POST":
        form = WorkerPositionPeriodForm(
            request.POST,
            instance=position,
            worker=worker,
        )

        if form.is_valid():
            position = form.save(
                commit=False
            )

            position.worker = worker
            position.updated_by = request.user
            position.save()

            messages.success(
                request,
                (
                    "\u062a\u0645 "
                    "\u062a\u062d\u062f\u064a\u062b "
                    "\u0641\u062a\u0631\u0629 "
                    "\u0627\u0644\u0645\u0646\u0635\u0628 "
                    "\u0628\u0646\u062c\u0627\u062d."
                ),
            )

            return redirect(
                "workforce:worker_detail",
                worker_id=worker.pk,
            )
    else:
        form = WorkerPositionPeriodForm(
            instance=position,
            worker=worker,
        )

    return render(
        request,
        "workforce/worker_position_form.html",
        {
            "form": form,
            "worker": worker,
            "position": position,
            "form_mode": "update",
        },
    )


@require_POST
@accountant_required
@permission_required(
    "workforce.change_workerpositionperiod",
    raise_exception=True,
)
def worker_position_end(
    request,
    worker_id,
    position_id,
):
    worker = get_object_or_404(
        Worker,
        pk=worker_id,
    )

    position = get_object_or_404(
        WorkerPositionPeriod,
        pk=position_id,
        worker=worker,
    )

    if not position.is_current:
        messages.error(
            request,
            (
                "\u0644\u0627 \u064a\u0645\u0643\u0646 "
                "\u0625\u0646\u0647\u0627\u0621 "
                "\u0647\u0630\u0647 "
                "\u0627\u0644\u0641\u062a\u0631\u0629 "
                "\u0644\u0623\u0646\u0647\u0627 "
                "\u0644\u064a\u0633\u062a "
                "\u0627\u0644\u0645\u0646\u0635\u0628 "
                "\u0627\u0644\u062d\u0627\u0644\u064a."
            ),
        )

        return redirect(
            "workforce:worker_detail",
            worker_id=worker.pk,
        )

    position.end_date = date.today()
    position.updated_by = request.user

    position.save(
        update_fields=(
            "end_date",
            "updated_by",
            "updated_at",
        )
    )

    messages.success(
        request,
        (
            "\u062a\u0645 "
            "\u0625\u0646\u0647\u0627\u0621 "
            "\u0627\u0644\u0645\u0646\u0635\u0628 "
            "\u0627\u0644\u062d\u0627\u0644\u064a "
            "\u0628\u062a\u0627\u0631\u064a\u062e "
            "\u0627\u0644\u064a\u0648\u0645."
        ),
    )

    return redirect(
        "workforce:worker_detail",
        worker_id=worker.pk,
    )
