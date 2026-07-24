from .models import WorkerCategory


SYSTEM_CATEGORY_FIXTURES = (
    {
        "code": "SELLER",
        "name": (
            "\u0628\u0627\u0626\u0639 "
            "\u0645\u064a\u062f\u0627\u0646\u064a"
        ),
        "default_can_sell": True,
        "sort_order": 10,
    },
    {
        "code": "DRIVER",
        "name": "\u0633\u0627\u0626\u0642",
        "default_can_drive": True,
        "sort_order": 20,
    },
    {
        "code": "DRIVER_SELLER",
        "name": (
            "\u0633\u0627\u0626\u0642 "
            "\u0648\u0628\u0627\u0626\u0639"
        ),
        "default_can_drive": True,
        "default_can_sell": True,
        "sort_order": 30,
    },
    {
        "code": "WAREHOUSE_WORKER",
        "name": (
            "\u0639\u0627\u0645\u0644 "
            "\u0645\u062e\u0632\u0646"
        ),
        "default_can_work_in_warehouse": True,
        "sort_order": 40,
    },
    {
        "code": "DISTRIBUTION_ASSISTANT",
        "name": (
            "\u0645\u0633\u0627\u0639\u062f "
            "\u062a\u0648\u0632\u064a\u0639"
        ),
        "default_can_assist_distribution": True,
        "sort_order": 50,
    },
    {
        "code": "WAREHOUSE_SUPERVISOR",
        "name": (
            "\u0645\u0633\u0624\u0648\u0644 "
            "\u0645\u062e\u0632\u0646"
        ),
        "default_can_work_in_warehouse": True,
        "default_can_train_workers": True,
        "sort_order": 60,
    },
    {
        "code": "FIELD_SUPERVISOR",
        "name": (
            "\u0645\u0634\u0631\u0641 "
            "\u0645\u064a\u062f\u0627\u0646\u064a"
        ),
        "default_can_train_workers": True,
        "sort_order": 70,
    },
    {
        "code": "ACCOUNTANT",
        "name": "\u0645\u062d\u0627\u0633\u0628",
        "sort_order": 80,
    },
    {
        "code": "ADMINISTRATIVE",
        "name": "\u0625\u062f\u0627\u0631\u064a",
        "sort_order": 90,
    },
    {
        "code": "OTHER",
        "name": (
            "\u0645\u0646\u0635\u0628 "
            "\u0622\u062e\u0631"
        ),
        "sort_order": 100,
    },
)


CAPABILITY_FIELDS = (
    "default_can_drive",
    "default_can_sell",
    "default_can_work_in_warehouse",
    "default_can_assist_distribution",
    "default_can_train_workers",
)


def ensure_system_categories():
    for fixture in SYSTEM_CATEGORY_FIXTURES:
        defaults = {
            "name": fixture["name"],
            "description": "",
            "sort_order": fixture["sort_order"],
            "is_active": True,
            "is_system": True,
        }

        for field_name in CAPABILITY_FIELDS:
            defaults[field_name] = fixture.get(
                field_name,
                False,
            )

        WorkerCategory.objects.update_or_create(
            code=fixture["code"],
            defaults=defaults,
        )
