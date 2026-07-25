from django.db import migrations


CAPABILITIES = (
    {
        "code": "CAP-DRIVE",
        "name": "القيادة",
        "description": (
            "القدرة على قيادة شاحنات "
            "ومركبات التوزيع."
        ),
        "sort_order": 10,
        "worker_field": "can_drive",
        "category_field": "default_can_drive",
    },
    {
        "code": "CAP-SELL",
        "name": "البيع",
        "description": (
            "القدرة على البيع والتعامل "
            "مع الزبائن."
        ),
        "sort_order": 20,
        "worker_field": "can_sell",
        "category_field": "default_can_sell",
    },
    {
        "code": "CAP-WAREHOUSE",
        "name": "العمل في المخزن",
        "description": (
            "القدرة على تنفيذ مهام "
            "المخزن."
        ),
        "sort_order": 30,
        "worker_field": (
            "can_work_in_warehouse"
        ),
        "category_field": (
            "default_can_work_in_warehouse"
        ),
    },
    {
        "code": "CAP-DISTRIBUTION-ASSIST",
        "name": "مساعدة التوزيع",
        "description": (
            "القدرة على مساعدة طاقم "
            "التوزيع."
        ),
        "sort_order": 40,
        "worker_field": (
            "can_assist_distribution"
        ),
        "category_field": (
            "default_can_assist_distribution"
        ),
    },
    {
        "code": "CAP-TRAIN",
        "name": "تدريب العمال",
        "description": (
            "القدرة على مرافقة وتدريب "
            "عمال آخرين."
        ),
        "sort_order": 50,
        "worker_field": (
            "can_train_workers"
        ),
        "category_field": (
            "default_can_train_workers"
        ),
    },
)


def seed_and_migrate_capabilities(
    apps,
    schema_editor,
):
    Worker = apps.get_model(
        "workforce",
        "Worker",
    )
    WorkerCategory = apps.get_model(
        "workforce",
        "WorkerCategory",
    )
    WorkerCapability = apps.get_model(
        "workforce",
        "WorkerCapability",
    )

    database_alias = (
        schema_editor.connection.alias
    )

    worker_capabilities = {}
    category_capabilities = {}

    for definition in CAPABILITIES:
        capability, _ = (
            WorkerCapability.objects
            .using(database_alias)
            .update_or_create(
                code=definition["code"],
                defaults={
                    "name": definition["name"],
                    "description": (
                        definition["description"]
                    ),
                    "sort_order": (
                        definition["sort_order"]
                    ),
                    "is_active": True,
                    "is_system": True,
                },
            )
        )

        worker_capabilities[
            definition["worker_field"]
        ] = capability

        category_capabilities[
            definition["category_field"]
        ] = capability

    workers = (
        Worker.objects
        .using(database_alias)
        .all()
        .iterator()
    )

    for worker in workers:
        for (
            field_name,
            capability,
        ) in worker_capabilities.items():
            if getattr(
                worker,
                field_name,
                False,
            ):
                worker.capabilities.add(
                    capability
                )

    categories = (
        WorkerCategory.objects
        .using(database_alias)
        .all()
        .iterator()
    )

    for category in categories:
        for (
            field_name,
            capability,
        ) in category_capabilities.items():
            if getattr(
                category,
                field_name,
                False,
            ):
                category.default_capabilities.add(
                    capability
                )


def reverse_capability_migration(
    apps,
    schema_editor,
):
    Worker = apps.get_model(
        "workforce",
        "Worker",
    )
    WorkerCategory = apps.get_model(
        "workforce",
        "WorkerCategory",
    )
    WorkerCapability = apps.get_model(
        "workforce",
        "WorkerCapability",
    )

    database_alias = (
        schema_editor.connection.alias
    )

    codes = [
        definition["code"]
        for definition in CAPABILITIES
    ]

    capabilities_by_code = {
        capability.code: capability
        for capability in (
            WorkerCapability.objects
            .using(database_alias)
            .filter(code__in=codes)
        )
    }

    workers = (
        Worker.objects
        .using(database_alias)
        .all()
        .iterator()
    )

    for worker in workers:
        update_fields = []

        for definition in CAPABILITIES:
            capability = capabilities_by_code.get(
                definition["code"]
            )

            has_capability = False

            if capability is not None:
                has_capability = (
                    worker.capabilities
                    .filter(pk=capability.pk)
                    .exists()
                )

            setattr(
                worker,
                definition["worker_field"],
                has_capability,
            )

            update_fields.append(
                definition["worker_field"]
            )

        worker.save(
            update_fields=update_fields
        )

        if capabilities_by_code:
            worker.capabilities.remove(
                *capabilities_by_code.values()
            )

    categories = (
        WorkerCategory.objects
        .using(database_alias)
        .all()
        .iterator()
    )

    for category in categories:
        update_fields = []

        for definition in CAPABILITIES:
            capability = capabilities_by_code.get(
                definition["code"]
            )

            has_capability = False

            if capability is not None:
                has_capability = (
                    category
                    .default_capabilities
                    .filter(pk=capability.pk)
                    .exists()
                )

            setattr(
                category,
                definition["category_field"],
                has_capability,
            )

            update_fields.append(
                definition["category_field"]
            )

        category.save(
            update_fields=update_fields
        )

        if capabilities_by_code:
            category.default_capabilities.remove(
                *capabilities_by_code.values()
            )

    (
        WorkerCapability.objects
        .using(database_alias)
        .filter(
            code__in=codes,
            is_system=True,
        )
        .delete()
    )


class Migration(migrations.Migration):

    dependencies = [
        (
            "workforce",
            "0007_workercapability_"
            "worker_capabilities_and_more",
        ),
    ]

    operations = [
        migrations.RunPython(
            seed_and_migrate_capabilities,
            reverse_capability_migration,
        ),
    ]
