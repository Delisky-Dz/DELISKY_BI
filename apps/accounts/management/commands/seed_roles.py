from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand
from django.db import transaction


ROLE_SUPER_ADMIN = "Super Admin"
ROLE_ACCOUNTANT = "Accountant"
ROLE_MANAGER = "Manager"


MODEL_PERMISSIONS = {
    "workforce": {
        "worker": ("view", "add", "change", "delete"),
        "workercategory": (
            "view",
            "add",
            "change",
            "delete",
        ),
    },
    "fleet": {
        "truck": ("view", "add", "change", "delete"),
        "workertruckassignment": ("view", "add", "change", "delete"),
    },
    "imports": {
        "distributionbrand": ("view", "add", "change", "delete"),
        "importbatch": ("view", "add", "change", "delete"),
        "importrow": ("view",),
    },
}


def get_permissions(allowed_actions):
    permission_ids = []

    for app_label, models in MODEL_PERMISSIONS.items():
        for model_name, available_actions in models.items():
            for action in available_actions:
                if action not in allowed_actions:
                    continue

                codename = f"{action}_{model_name}"

                permission = Permission.objects.get(
                    content_type__app_label=app_label,
                    content_type__model=model_name,
                    codename=codename,
                )

                permission_ids.append(permission.pk)

    return Permission.objects.filter(pk__in=permission_ids)


class Command(BaseCommand):
    help = "Create or update DELISKY BI roles and permissions."

    @transaction.atomic
    def handle(self, *args, **options):
        role_definitions = {
            ROLE_SUPER_ADMIN: {
                "view",
                "add",
                "change",
                "delete",
            },
            ROLE_ACCOUNTANT: {
                "view",
                "add",
                "change",
            },
            ROLE_MANAGER: {
                "view",
            },
        }

        for role_name, allowed_actions in role_definitions.items():
            group, created = Group.objects.get_or_create(
                name=role_name,
            )

            permissions = get_permissions(allowed_actions)
            group.permissions.set(permissions)

            status = "created" if created else "updated"

            self.stdout.write(
                self.style.SUCCESS(
                    f"{role_name}: {status} "
                    f"with {permissions.count()} permissions."
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                "DELISKY BI roles configured successfully."
            )
        )
