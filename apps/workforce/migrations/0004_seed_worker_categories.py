from django.db import migrations


SYSTEM_CATEGORIES = (
    {
        "code": "SELLER",
        "name": "\u0628\u0627\u0626\u0639 \u0645\u064a\u062f\u0627\u0646\u064a",
        "description": (
            "\u0645\u0633\u0624\u0648\u0644 \u0639\u0646 "
            "\u0627\u0644\u0628\u064a\u0639 \u0627\u0644\u0645\u064a\u062f\u0627\u0646\u064a "
            "\u0648\u0632\u064a\u0627\u0631\u0629 \u0646\u0642\u0627\u0637 "
            "\u0627\u0644\u0628\u064a\u0639."
        ),
        "default_can_sell": True,
        "sort_order": 10,
    },
    {
        "code": "DRIVER",
        "name": "\u0633\u0627\u0626\u0642",
        "description": (
            "\u0645\u0633\u0624\u0648\u0644 \u0639\u0646 "
            "\u0642\u064a\u0627\u062f\u0629 \u0627\u0644\u0634\u0627\u062d\u0646\u0629."
        ),
        "default_can_drive": True,
        "sort_order": 20,
    },
    {
        "code": "DRIVER_SELLER",
        "name": "\u0633\u0627\u0626\u0642 \u0648\u0628\u0627\u0626\u0639",
        "description": (
            "\u064a\u062c\u0645\u0639 \u0628\u064a\u0646 "
            "\u0642\u064a\u0627\u062f\u0629 \u0627\u0644\u0634\u0627\u062d\u0646\u0629 "
            "\u0648\u0627\u0644\u0628\u064a\u0639 \u0627\u0644\u0645\u064a\u062f\u0627\u0646\u064a."
        ),
        "default_can_drive": True,
        "default_can_sell": True,
        "sort_order": 30,
    },
    {
        "code": "WAREHOUSE_WORKER",
        "name": "\u0639\u0627\u0645\u0644 \u0645\u062e\u0632\u0646",
        "description": (
            "\u064a\u0639\u0645\u0644 \u0641\u064a "
            "\u0627\u0644\u062a\u062d\u0636\u064a\u0631 "
            "\u0648\u0627\u0644\u062a\u0631\u062a\u064a\u0628 "
            "\u0648\u0627\u0644\u0645\u0646\u0627\u0648\u0644\u0629 "
            "\u062f\u0627\u062e\u0644 \u0627\u0644\u0645\u062e\u0632\u0646."
        ),
        "default_can_work_in_warehouse": True,
        "sort_order": 40,
    },
    {
        "code": "DISTRIBUTION_ASSISTANT",
        "name": "\u0645\u0633\u0627\u0639\u062f \u062a\u0648\u0632\u064a\u0639",
        "description": (
            "\u064a\u0631\u0627\u0641\u0642 \u0637\u0627\u0642\u0645 "
            "\u0627\u0644\u0634\u0627\u062d\u0646\u0629 "
            "\u0648\u064a\u0633\u0627\u0639\u062f \u0641\u064a "
            "\u0627\u0644\u062a\u062d\u0645\u064a\u0644 "
            "\u0648\u0627\u0644\u062a\u0641\u0631\u064a\u063a "
            "\u0648\u0627\u0644\u062a\u0648\u0632\u064a\u0639."
        ),
        "default_can_assist_distribution": True,
        "sort_order": 50,
    },
    {
        "code": "WAREHOUSE_SUPERVISOR",
        "name": "\u0645\u0633\u0624\u0648\u0644 \u0645\u062e\u0632\u0646",
        "description": (
            "\u0645\u0633\u0624\u0648\u0644 \u0639\u0646 "
            "\u062a\u0646\u0638\u064a\u0645 \u0627\u0644\u0645\u062e\u0632\u0646 "
            "\u0648\u0645\u062a\u0627\u0628\u0639\u0629 \u0627\u0644\u0639\u0645\u0627\u0644 "
            "\u0648\u0627\u0644\u0633\u0644\u0639."
        ),
        "default_can_work_in_warehouse": True,
        "default_can_train_workers": True,
        "sort_order": 60,
    },
    {
        "code": "FIELD_SUPERVISOR",
        "name": "\u0645\u0634\u0631\u0641 \u0645\u064a\u062f\u0627\u0646\u064a",
        "description": (
            "\u064a\u062a\u0627\u0628\u0639 \u0627\u0644\u0639\u0645\u0644 "
            "\u0627\u0644\u0645\u064a\u062f\u0627\u0646\u064a "
            "\u0648\u0637\u0648\u0627\u0642\u0645 \u0627\u0644\u0634\u0627\u062d\u0646\u0627\u062a."
        ),
        "default_can_train_workers": True,
        "sort_order": 70,
    },
    {
        "code": "ACCOUNTANT",
        "name": "\u0645\u062d\u0627\u0633\u0628",
        "description": (
            "\u0645\u0633\u0624\u0648\u0644 \u0639\u0646 "
            "\u0627\u0644\u0623\u0639\u0645\u0627\u0644 "
            "\u0627\u0644\u0645\u062d\u0627\u0633\u0628\u064a\u0629 "
            "\u0648\u0627\u0644\u0625\u062f\u0627\u0631\u064a\u0629."
        ),
        "sort_order": 80,
    },
    {
        "code": "ADMINISTRATIVE",
        "name": "\u0625\u062f\u0627\u0631\u064a",
        "description": (
            "\u0645\u0633\u0624\u0648\u0644 \u0639\u0646 "
            "\u0627\u0644\u0645\u0647\u0627\u0645 "
            "\u0627\u0644\u0625\u062f\u0627\u0631\u064a\u0629 "
            "\u0648\u0627\u0644\u062a\u0646\u0638\u064a\u0645\u064a\u0629."
        ),
        "sort_order": 90,
    },
    {
        "code": "OTHER",
        "name": "\u0645\u0646\u0635\u0628 \u0622\u062e\u0631",
        "description": (
            "\u064a\u0633\u062a\u0639\u0645\u0644 \u0645\u0624\u0642\u062a\u064b\u0627 "
            "\u0644\u0644\u062d\u0627\u0644\u0627\u062a "
            "\u063a\u064a\u0631 \u0627\u0644\u0645\u0635\u0646\u0641\u0629."
        ),
        "sort_order": 100,
    },
)


def seed_worker_categories(
    apps,
    schema_editor,
):
    WorkerCategory = apps.get_model(
        "workforce",
        "WorkerCategory",
    )

    database_alias = (
        schema_editor.connection.alias
    )

    capability_fields = (
        "default_can_drive",
        "default_can_sell",
        "default_can_work_in_warehouse",
        "default_can_assist_distribution",
        "default_can_train_workers",
    )

    for category in SYSTEM_CATEGORIES:
        defaults = {
            "name": category["name"],
            "description": (
                category["description"]
            ),
            "sort_order": (
                category["sort_order"]
            ),
            "is_active": True,
            "is_system": True,
        }

        for field_name in capability_fields:
            defaults[field_name] = (
                category.get(
                    field_name,
                    False,
                )
            )

        WorkerCategory.objects.using(
            database_alias
        ).update_or_create(
            code=category["code"],
            defaults=defaults,
        )


def remove_seeded_categories(
    apps,
    schema_editor,
):
    WorkerCategory = apps.get_model(
        "workforce",
        "WorkerCategory",
    )

    database_alias = (
        schema_editor.connection.alias
    )

    system_codes = [
        category["code"]
        for category in SYSTEM_CATEGORIES
    ]

    WorkerCategory.objects.using(
        database_alias
    ).filter(
        code__in=system_codes,
        is_system=True,
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        (
            "workforce",
            "0003_workercategory",
        ),
    ]

    operations = [
        migrations.RunPython(
            seed_worker_categories,
            remove_seeded_categories,
        ),
    ]
