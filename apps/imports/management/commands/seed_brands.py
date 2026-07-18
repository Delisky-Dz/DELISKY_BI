from django.core.management.base import BaseCommand
from django.db import transaction

from apps.imports.models import DistributionBrand


OFFICIAL_BRANDS = (
    ("BIFA", "BIFA"),
    ("DELISKY", "DELISKY"),
    ("NITA", "NITA"),
)


class Command(BaseCommand):
    help = "Create or reactivate the official DELISKY BI distribution brands."

    @transaction.atomic
    def handle(self, *args, **options):
        for code, name in OFFICIAL_BRANDS:
            brand = DistributionBrand.objects.filter(
                code__iexact=code,
            ).first()

            if brand is None:
                DistributionBrand.objects.create(
                    code=code,
                    name=name,
                    is_active=True,
                )
                status = "created"
            elif not brand.is_active:
                brand.is_active = True
                brand.save(update_fields=["is_active", "updated_at"])
                status = "reactivated"
            else:
                status = "unchanged"

            self.stdout.write(
                self.style.SUCCESS(
                    f"{code}: {status}."
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                "DELISKY BI distribution brands configured successfully."
            )
        )
