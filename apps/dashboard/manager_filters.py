from urllib.parse import urlencode

from .forms import ManagerDashboardFilterForm


FILTER_QUERY_KEYS = (
    "period_start",
    "period_end",
    "brand",
    "run",
)


def filter_requested(request) -> bool:
    return any(
        key in request.GET
        for key in FILTER_QUERY_KEYS
    )


def build_filter_form(request):
    requested = filter_requested(request)

    form = ManagerDashboardFilterForm(
        data=(
            request.GET
            if requested
            else None
        ),
    )

    return requested, form


def selected_brand_id(form) -> int | None:
    selected_brand = form.cleaned_data["brand"]

    if selected_brand is None:
        return None

    return selected_brand.pk


def manager_filter_query(request) -> str:
    if not filter_requested(request):
        return ""

    values = []

    for key in FILTER_QUERY_KEYS:
        if key == "run":
            continue

        value = request.GET.get(key)

        if value not in (None, ""):
            values.append((key, value))

    values.append(("run", "1"))

    return urlencode(values)
