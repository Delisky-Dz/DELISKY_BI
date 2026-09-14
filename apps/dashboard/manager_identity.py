def worker_display_identity(
    worker_id: int,
    worker,
) -> tuple[str, str | None]:
    """
    Return a truthful display identity for manager analytics.

    Generic analytical workers represent a distribution route,
    not a real employee. They are therefore displayed as the route
    code instead of a fabricated personal name.
    """
    if worker is None:
        return f"المسار رقم {worker_id}", None

    employee_code = str(
        getattr(worker, "employee_code", "") or ""
    ).strip()

    if employee_code.startswith("GEN-"):
        route_label = " ".join(
            employee_code.split("-")[1:]
        )
        return route_label, "مسار توزيع"

    full_name = str(
        getattr(worker, "full_name", "") or ""
    ).strip()

    if full_name:
        return full_name, employee_code or None

    if employee_code:
        return employee_code, None

    return f"البائع رقم {worker_id}", None
