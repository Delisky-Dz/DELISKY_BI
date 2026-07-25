from .models import (
    WorkerCapability,
    WorkerCategory,
)


SYSTEM_CAPABILITIES = (
    (
        "CAP-DRIVE",
        "القيادة",
        10,
    ),
    (
        "CAP-SELL",
        "البيع",
        20,
    ),
    (
        "CAP-WAREHOUSE",
        "العمل في المخزن",
        30,
    ),
    (
        "CAP-DISTRIBUTION-ASSIST",
        "مساعدة التوزيع",
        40,
    ),
    (
        "CAP-TRAIN",
        "تدريب العمال",
        50,
    ),
)


SYSTEM_CATEGORIES = (
    (
        "SELLER",
        "بائع ميداني",
        10,
        (
            "CAP-SELL",
        ),
    ),
    (
        "DRIVER",
        "سائق",
        20,
        (
            "CAP-DRIVE",
        ),
    ),
    (
        "DRIVER_SELLER",
        "سائق وبائع",
        30,
        (
            "CAP-DRIVE",
            "CAP-SELL",
        ),
    ),
    (
        "WAREHOUSE_WORKER",
        "عامل مخزن",
        40,
        (
            "CAP-WAREHOUSE",
        ),
    ),
    (
        "DISTRIBUTION_ASSISTANT",
        "مساعد توزيع",
        50,
        (
            "CAP-DISTRIBUTION-ASSIST",
        ),
    ),
    (
        "WAREHOUSE_SUPERVISOR",
        "مسؤول مخزن",
        60,
        (
            "CAP-WAREHOUSE",
            "CAP-TRAIN",
        ),
    ),
    (
        "FIELD_SUPERVISOR",
        "مشرف ميداني",
        70,
        (
            "CAP-TRAIN",
        ),
    ),
    (
        "ACCOUNTANT",
        "محاسب",
        80,
        (),
    ),
    (
        "ADMINISTRATIVE",
        "إداري",
        90,
        (),
    ),
    (
        "OTHER",
        "منصب آخر",
        100,
        (),
    ),
)


def ensure_system_capabilities():
    capabilities_by_code = {}

    for (
        code,
        name,
        sort_order,
    ) in SYSTEM_CAPABILITIES:
        capability, _ = (
            WorkerCapability.objects
            .update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "sort_order": sort_order,
                    "is_active": True,
                    "is_system": True,
                },
            )
        )

        capabilities_by_code[
            code
        ] = capability

    return capabilities_by_code


def ensure_system_categories():
    capabilities_by_code = (
        ensure_system_capabilities()
    )

    categories = []

    for (
        code,
        name,
        sort_order,
        capability_codes,
    ) in SYSTEM_CATEGORIES:
        category, _ = (
            WorkerCategory.objects
            .update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "sort_order": sort_order,
                    "is_active": True,
                    "is_system": True,
                },
            )
        )

        category.default_capabilities.set(
            [
                capabilities_by_code[
                    capability_code
                ]
                for capability_code
                in capability_codes
            ]
        )

        categories.append(
            category
        )

    return tuple(categories)
