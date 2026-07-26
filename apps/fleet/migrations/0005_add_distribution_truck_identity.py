import re

import django.db.models.deletion
from django.core.validators import (
    MaxValueValidator,
    MinValueValidator,
)
from django.db import migrations, models


TRUCK_CODE_PATTERN = re.compile(
    r"^(?P<brand>[A-Z0-9_-]+)\s+"
    r"(?P<route_type>PSLIV|PLIV|LIV)"
    r"(?P<number>\d+)$"
)


def populate_distribution_identity(apps, schema_editor):
    Truck = apps.get_model("fleet", "Truck")
    DistributionBrand = apps.get_model(
        "imports",
        "DistributionBrand",
    )

    for truck in Truck.objects.all().iterator():
        normalized_code = " ".join(
            (truck.internal_code or "")
            .strip()
            .upper()
            .split()
        )

        if not normalized_code:
            continue

        match = TRUCK_CODE_PATTERN.fullmatch(
            normalized_code
        )

        if match is None:
            raise RuntimeError(
                "تعذر تحليل رمز الشاحنة "
                f"{normalized_code!r}."
            )

        brand_code = match.group("brand")

        brand = DistributionBrand.objects.filter(
            code=brand_code
        ).first()

        if brand is None:
            raise RuntimeError(
                "لا توجد علامة توزيع مطابقة للرمز "
                f"{brand_code!r}."
            )

        truck.internal_code = normalized_code
        truck.distribution_brand_id = brand.pk
        truck.route_type = match.group("route_type")
        truck.route_number = int(
            match.group("number")
        )

        truck.save(
            update_fields=[
                "internal_code",
                "distribution_brand",
                "route_type",
                "route_number",
            ]
        )


def clear_distribution_identity(apps, schema_editor):
    Truck = apps.get_model("fleet", "Truck")

    Truck.objects.update(
        distribution_brand=None,
        route_type=None,
        route_number=None,
    )


class Migration(migrations.Migration):

    dependencies = [
        ("fleet", "0004_workertruckassignment"),
        ("imports", "0004_importrow"),
    ]

    operations = [
        migrations.AddField(
            model_name="truck",
            name="distribution_brand",
            field=models.ForeignKey(
                blank=True,
                help_text=(
                    "العلامة الرسمية مثل BIFA أو "
                    "DELISKY أو NITA."
                ),
                null=True,
                on_delete=(
                    django.db.models.deletion.PROTECT
                ),
                related_name="trucks",
                to="imports.distributionbrand",
                verbose_name="العلامة",
            ),
        ),
        migrations.AddField(
            model_name="truck",
            name="route_type",
            field=models.CharField(
                blank=True,
                choices=[
                    ("LIV", "LIV"),
                    ("PLIV", "PLIV"),
                    ("PSLIV", "PSLIV"),
                ],
                help_text=(
                    "نوع خط التوزيع مثل LIV أو "
                    "PLIV أو PSLIV."
                ),
                max_length=10,
                null=True,
                verbose_name="نوع التوزيع",
            ),
        ),
        migrations.AddField(
            model_name="truck",
            name="route_number",
            field=models.PositiveSmallIntegerField(
                blank=True,
                help_text=(
                    "الرقم التسلسلي داخل العلامة "
                    "ونوع التوزيع."
                ),
                null=True,
                validators=[
                    MinValueValidator(1),
                    MaxValueValidator(999),
                ],
                verbose_name="رقم خط التوزيع",
            ),
        ),
        migrations.RunPython(
            populate_distribution_identity,
            clear_distribution_identity,
        ),
    ]
