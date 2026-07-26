from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import (
    permission_required,
)
from django.db import IntegrityError, transaction
from django.db.models import Prefetch, Q
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.views.decorators.http import require_POST

from apps.imports.access import accountant_required

from .forms import (
    AssignmentEndForm,
    TruckForm,
    WorkerTruckAssignmentForm,
)
from .models import Truck, WorkerTruckAssignment


STATUS_ALL = "all"
STATUS_ACTIVE = "active"
STATUS_INACTIVE = "inactive"

VALID_STATUSES = {
    STATUS_ALL,
    STATUS_ACTIVE,
    STATUS_INACTIVE,
}


def _current_assignment_prefetch():
    today = date.today()

    return Prefetch(
        "worker_assignments",
        queryset=(
            WorkerTruckAssignment.objects
            .filter(
                start_date__lte=today,
            )
            .filter(
                Q(end_date__isnull=True)
                | Q(end_date__gte=today)
            )
            .select_related("worker")
            .order_by("-start_date")
        ),
        to_attr="current_assignments",
    )


@accountant_required
@permission_required(
    "fleet.view_truck",
    raise_exception=True,
)
def truck_list(request):
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

    trucks = Truck.objects.all()

    if query:
        trucks = trucks.filter(
            Q(internal_code__icontains=query)
            | Q(
                distribution_brand__code__icontains=query
            )
            | Q(route_type__icontains=query)
            | Q(registration_number__icontains=query)
            | Q(brand__icontains=query)
            | Q(model__icontains=query)
        )

    if status == STATUS_ACTIVE:
        trucks = trucks.filter(
            is_active=True
        )
    elif status == STATUS_INACTIVE:
        trucks = trucks.filter(
            is_active=False
        )

    trucks = list(
        trucks
        .select_related("distribution_brand")
        .prefetch_related(
            _current_assignment_prefetch()
        )
        .order_by("internal_code")
    )

    for truck in trucks:
        truck.current_assignment = (
            truck.current_assignments[0]
            if truck.current_assignments
            else None
        )

    today = date.today()

    assigned_truck_count = (
        WorkerTruckAssignment.objects
        .filter(start_date__lte=today)
        .filter(
            Q(end_date__isnull=True)
            | Q(end_date__gte=today)
        )
        .values("truck_id")
        .distinct()
        .count()
    )

    all_trucks = Truck.objects.all()

    context = {
        "trucks": trucks,
        "query": query,
        "selected_status": status,
        "total_trucks": all_trucks.count(),
        "active_trucks": all_trucks.filter(
            is_active=True
        ).count(),
        "inactive_trucks": all_trucks.filter(
            is_active=False
        ).count(),
        "assigned_truck_count": (
            assigned_truck_count
        ),
    }

    return render(
        request,
        "fleet/truck_list.html",
        context,
    )


@accountant_required
@permission_required(
    "fleet.add_truck",
    raise_exception=True,
)
def truck_create(request):
    if request.method == "POST":
        form = TruckForm(request.POST)

        if form.is_valid():
            truck = form.save()

            messages.success(
                request,
                (
                    "\u062a\u0645\u062a "
                    "\u0625\u0636\u0627\u0641\u0629 "
                    "\u0631\u0645\u0632 ""\u0627\u0644\u062a\u0648\u0632\u064a\u0639 "
                    f"{truck.internal_code} "
                    "\u0628\u0646\u062c\u0627\u062d."
                ),
            )

            return redirect(
                "fleet:truck_list"
            )
    else:
        form = TruckForm()

    return render(
        request,
        "fleet/truck_form.html",
        {
            "form": form,
            "truck": None,
            "form_mode": "create",
        },
    )


@accountant_required
@permission_required(
    "fleet.change_truck",
    raise_exception=True,
)
def truck_update(request, truck_id):
    truck = get_object_or_404(
        Truck,
        pk=truck_id,
    )

    if request.method == "POST":
        form = TruckForm(
            request.POST,
            instance=truck,
        )

        if form.is_valid():
            truck = form.save()

            messages.success(
                request,
                (
                    "\u062a\u0645 "
                    "\u062a\u062d\u062f\u064a\u062b "
                    "\u0628\u064a\u0627\u0646\u0627\u062a "
                    "\u0631\u0645\u0632 ""\u0627\u0644\u062a\u0648\u0632\u064a\u0639 "
                    f"{truck.internal_code} "
                    "\u0628\u0646\u062c\u0627\u062d."
                ),
            )

            return redirect(
                "fleet:truck_list"
            )
    else:
        form = TruckForm(
            instance=truck
        )

    return render(
        request,
        "fleet/truck_form.html",
        {
            "form": form,
            "truck": truck,
            "form_mode": "update",
        },
    )


@require_POST
@accountant_required
@permission_required(
    "fleet.change_truck",
    raise_exception=True,
)
def truck_toggle_status(
    request,
    truck_id,
):
    truck = get_object_or_404(
        Truck,
        pk=truck_id,
    )

    truck.is_active = not truck.is_active

    truck.save(
        update_fields=(
            "is_active",
            "updated_at",
        )
    )

    if truck.is_active:
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
            "\u0631\u0645\u0632 ""\u0627\u0644\u062a\u0648\u0632\u064a\u0639 "
            f"{truck.internal_code}."
        ),
    )

    return redirect(
        "fleet:truck_list"
    )


ASSIGNMENT_STATUS_ALL = "all"
ASSIGNMENT_STATUS_CURRENT = "current"
ASSIGNMENT_STATUS_UPCOMING = "upcoming"
ASSIGNMENT_STATUS_ENDED = "ended"

VALID_ASSIGNMENT_STATUSES = {
    ASSIGNMENT_STATUS_ALL,
    ASSIGNMENT_STATUS_CURRENT,
    ASSIGNMENT_STATUS_UPCOMING,
    ASSIGNMENT_STATUS_ENDED,
}


def _current_assignment_condition(today):
    return (
        Q(start_date__lte=today)
        & (
            Q(end_date__isnull=True)
            | Q(end_date__gte=today)
        )
    )


def _save_assignment_form(form):
    try:
        with transaction.atomic():
            return form.save()
    except IntegrityError:
        form.add_error(
            None,
            (
                "\u062a\u0639\u0630\u0631 "
                "\u062d\u0641\u0638 "
                "\u0627\u0644\u062a\u0639\u064a\u064a\u0646. "
                "\u062a\u0623\u0643\u062f \u0645\u0646 "
                "\u0639\u062f\u0645 \u0648\u062c\u0648\u062f "
                "\u062a\u062f\u0627\u062e\u0644 "
                "\u0641\u064a \u0627\u0644\u0641\u062a\u0631\u0627\u062a."
            ),
        )

        return None


@accountant_required
@permission_required(
    "fleet.view_workertruckassignment",
    raise_exception=True,
)
def assignment_list(request):
    today = date.today()

    query = request.GET.get(
        "q",
        "",
    ).strip()

    status = request.GET.get(
        "status",
        ASSIGNMENT_STATUS_ALL,
    ).strip()

    if status not in VALID_ASSIGNMENT_STATUSES:
        status = ASSIGNMENT_STATUS_ALL

    assignments = (
        WorkerTruckAssignment.objects
        .select_related(
            "worker",
            "truck",
        )
    )

    if query:
        assignments = assignments.filter(
            Q(
                worker__first_name__icontains=query
            )
            | Q(
                worker__last_name__icontains=query
            )
            | Q(
                worker__employee_code__icontains=query
            )
            | Q(
                truck__internal_code__icontains=query
            )
            | Q(
                truck__registration_number__icontains=query
            )
        )

    current_condition = (
        _current_assignment_condition(today)
    )

    if (
        status
        == ASSIGNMENT_STATUS_CURRENT
    ):
        assignments = assignments.filter(
            current_condition
        )
    elif (
        status
        == ASSIGNMENT_STATUS_UPCOMING
    ):
        assignments = assignments.filter(
            start_date__gt=today
        )
    elif (
        status
        == ASSIGNMENT_STATUS_ENDED
    ):
        assignments = assignments.filter(
            end_date__lt=today
        )

    assignments = list(
        assignments.order_by(
            "-start_date",
            "truck__internal_code",
            "worker__last_name",
        )
    )

    for assignment in assignments:
        if assignment.start_date > today:
            assignment.status_key = (
                ASSIGNMENT_STATUS_UPCOMING
            )
        elif (
            assignment.end_date
            and assignment.end_date < today
        ):
            assignment.status_key = (
                ASSIGNMENT_STATUS_ENDED
            )
        else:
            assignment.status_key = (
                ASSIGNMENT_STATUS_CURRENT
            )

    all_assignments = (
        WorkerTruckAssignment.objects.all()
    )

    context = {
        "assignments": assignments,
        "query": query,
        "selected_status": status,
        "today": today,
        "total_assignments": (
            all_assignments.count()
        ),
        "current_assignments": (
            all_assignments
            .filter(current_condition)
            .count()
        ),
        "upcoming_assignments": (
            all_assignments
            .filter(start_date__gt=today)
            .count()
        ),
        "ended_assignments": (
            all_assignments
            .filter(end_date__lt=today)
            .count()
        ),
    }

    return render(
        request,
        "fleet/assignment_list.html",
        context,
    )


@accountant_required
@permission_required(
    "fleet.add_workertruckassignment",
    raise_exception=True,
)
def assignment_create(request):
    if request.method == "POST":
        form = WorkerTruckAssignmentForm(
            request.POST
        )

        if form.is_valid():
            assignment = (
                _save_assignment_form(form)
            )

            if assignment:
                messages.success(
                    request,
                    (
                        "\u062a\u0645 \u0631\u0628\u0637 "
                        f"{assignment.worker.full_name} "
                        "\u0628\u0627\u0644\u0634\u0627\u062d\u0646\u0629 "
                        f"{assignment.truck.internal_code} "
                        "\u0628\u0646\u062c\u0627\u062d."
                    ),
                )

                return redirect(
                    "fleet:assignment_list"
                )
    else:
        form = WorkerTruckAssignmentForm(
            initial={
                "start_date": date.today(),
            }
        )

    return render(
        request,
        "fleet/assignment_form.html",
        {
            "form": form,
            "assignment": None,
            "form_mode": "create",
        },
    )


@accountant_required
@permission_required(
    "fleet.change_workertruckassignment",
    raise_exception=True,
)
def assignment_update(
    request,
    assignment_id,
):
    assignment = get_object_or_404(
        WorkerTruckAssignment.objects
        .select_related(
            "worker",
            "truck",
        ),
        pk=assignment_id,
    )

    if request.method == "POST":
        form = WorkerTruckAssignmentForm(
            request.POST,
            instance=assignment,
        )

        if form.is_valid():
            saved_assignment = (
                _save_assignment_form(form)
            )

            if saved_assignment:
                messages.success(
                    request,
                    (
                        "\u062a\u0645 "
                        "\u062a\u062d\u062f\u064a\u062b "
                        "\u0627\u0644\u062a\u0639\u064a\u064a\u0646 "
                        "\u0628\u0646\u062c\u0627\u062d."
                    ),
                )

                return redirect(
                    "fleet:assignment_list"
                )
    else:
        form = WorkerTruckAssignmentForm(
            instance=assignment
        )

    return render(
        request,
        "fleet/assignment_form.html",
        {
            "form": form,
            "assignment": assignment,
            "form_mode": "update",
        },
    )


@accountant_required
@permission_required(
    "fleet.change_workertruckassignment",
    raise_exception=True,
)
def assignment_end(
    request,
    assignment_id,
):
    assignment = get_object_or_404(
        WorkerTruckAssignment.objects
        .select_related(
            "worker",
            "truck",
        ),
        pk=assignment_id,
    )

    if request.method == "POST":
        form = AssignmentEndForm(
            request.POST,
            instance=assignment,
        )

        if form.is_valid():
            saved_assignment = (
                _save_assignment_form(form)
            )

            if saved_assignment:
                messages.success(
                    request,
                    (
                        "\u062a\u0645 "
                        "\u0625\u0646\u0647\u0627\u0621 "
                        "\u0627\u0644\u062a\u0639\u064a\u064a\u0646 "
                        "\u0628\u062a\u0627\u0631\u064a\u062e "
                        f"{saved_assignment.end_date}."
                    ),
                )

                return redirect(
                    "fleet:assignment_list"
                )
    else:
        suggested_end_date = max(
            date.today(),
            assignment.start_date,
        )

        form = AssignmentEndForm(
            instance=assignment,
            initial={
                "end_date": (
                    suggested_end_date
                ),
            },
        )

    return render(
        request,
        "fleet/assignment_end.html",
        {
            "form": form,
            "assignment": assignment,
        },
    )
