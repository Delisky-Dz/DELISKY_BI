from datetime import date

from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import (
    DateRangeField,
    RangeBoundary,
    RangeOperators,
)
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Func, Q

from apps.workforce.models import Worker


class DateRangeExpression(Func):
    function = "DATERANGE"
    output_field = DateRangeField()


class Truck(models.Model):
    class RouteType(models.TextChoices):
        LIV = "LIV", "LIV"
        PLIV = "PLIV", "PLIV"
        PSLIV = "PSLIV", "PSLIV"

    internal_code = models.CharField(
        "الرمز الداخلي",
        max_length=30,
        unique=True,
        null=True,
        blank=True,
        help_text="رمز اختياري وفريد للشاحنة داخل الشركة.",
    )
    distribution_brand = models.ForeignKey(
        "imports.DistributionBrand",
        verbose_name="العلامة",
        on_delete=models.PROTECT,
        related_name="trucks",
        null=True,
        blank=True,
        help_text="العلامة الرسمية مثل BIFA أو DELISKY أو NITA.",
    )
    route_type = models.CharField(
        "نوع التوزيع",
        max_length=10,
        choices=RouteType.choices,
        null=True,
        blank=True,
        help_text="نوع خط التوزيع مثل LIV أو PLIV أو PSLIV.",
    )
    route_number = models.PositiveSmallIntegerField(
        "رقم خط التوزيع",
        null=True,
        blank=True,
        validators=[
            MinValueValidator(1),
            MaxValueValidator(999),
        ],
        help_text="الرقم التسلسلي داخل العلامة ونوع التوزيع.",
    )
    registration_number = models.CharField(
        "رقم التسجيل",
        max_length=50,
        unique=True,
        help_text="رقم تسجيل الشاحنة كما هو موجود في الوثائق.",
    )
    brand = models.CharField(
        "العلامة",
        max_length=100,
    )
    model = models.CharField(
        "الطراز",
        max_length=100,
        blank=True,
    )
    manufacturing_year = models.PositiveSmallIntegerField(
        "سنة الصنع",
        null=True,
        blank=True,
        validators=[
            MinValueValidator(1900),
            MaxValueValidator(2100),
        ],
    )
    is_active = models.BooleanField(
        "نشطة",
        default=True,
        db_index=True,
        help_text="ألغِ التحديد لتعطيل الشاحنة دون حذف تاريخها.",
    )
    notes = models.TextField(
        "ملاحظات",
        blank=True,
    )
    created_at = models.DateTimeField(
        "تاريخ الإنشاء",
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        "آخر تعديل",
        auto_now=True,
    )

    class Meta:
        verbose_name = "شاحنة"
        verbose_name_plural = "الشاحنات"
        ordering = ["registration_number"]

        indexes = [
            models.Index(
                fields=["brand", "model"],
                name="truck_brand_model_idx",
            ),
        ]

        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(manufacturing_year__isnull=True)
                    | models.Q(
                        manufacturing_year__gte=1900,
                        manufacturing_year__lte=2100,
                    )
                ),
                name="truck_year_1900_2100",
            ),
        ]

    @staticmethod
    def build_internal_code(
        brand_code,
        route_type,
        route_number,
    ):
        brand_code = str(brand_code).strip().upper()
        route_type = str(route_type).strip().upper()
        route_number = int(route_number)

        return (
            f"{brand_code} "
            f"{route_type}{route_number:02d}"
        )

    def save(self, *args, **kwargs):
        if self.pk and not self._state.adding:
            original = type(self).objects.only(
                "internal_code",
                "distribution_brand_id",
                "route_type",
                "route_number",
            ).get(pk=self.pk)

            identity_changed = any(
                (
                    self.internal_code
                    != original.internal_code,
                    self.distribution_brand_id
                    != original.distribution_brand_id,
                    self.route_type
                    != original.route_type,
                    self.route_number
                    != original.route_number,
                )
            )

            if identity_changed:
                raise ValidationError(
                    "هوية رمز التوزيع ثابتة بعد الإنشاء. "
                    "عطّل الرمز القديم وأنشئ رمزًا جديدًا."
                )

        if (
            self.distribution_brand_id
            and self.route_type
            and self.route_number
        ):
            self.internal_code = self.build_internal_code(
                self.distribution_brand.code,
                self.route_type,
                self.route_number,
            )

        super().save(*args, **kwargs)

    def __str__(self):
        return (
            self.internal_code
            or self.registration_number
        )


class WorkerTruckAssignment(models.Model):
    worker = models.ForeignKey(
        Worker,
        verbose_name="العامل",
        on_delete=models.PROTECT,
        related_name="truck_assignments",
    )
    truck = models.ForeignKey(
        Truck,
        verbose_name="الشاحنة",
        on_delete=models.PROTECT,
        related_name="worker_assignments",
    )
    start_date = models.DateField(
        "تاريخ بداية العمل",
        db_index=True,
    )
    end_date = models.DateField(
        "تاريخ نهاية العمل",
        null=True,
        blank=True,
        db_index=True,
        help_text="اتركه فارغًا إذا كان العامل ما زال يعمل مع الشاحنة.",
    )
    notes = models.TextField(
        "ملاحظات",
        blank=True,
    )
    created_at = models.DateTimeField(
        "تاريخ الإنشاء",
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        "آخر تعديل",
        auto_now=True,
    )

    class Meta:
        verbose_name = "تعيين عامل بشاحنة"
        verbose_name_plural = "تعيينات العمال بالشاحنات"
        ordering = ["-start_date", "truck", "worker"]

        indexes = [
            models.Index(
                fields=["truck", "start_date"],
                name="assignment_truck_start_idx",
            ),
            models.Index(
                fields=["worker", "start_date"],
                name="assignment_worker_start_idx",
            ),
        ]

        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(end_date__isnull=True)
                    | Q(end_date__gte=models.F("start_date"))
                ),
                name="assignment_end_not_before_start",
                violation_error_message=(
                    "تاريخ نهاية العمل لا يمكن أن يكون قبل تاريخ البداية."
                ),
            ),
            ExclusionConstraint(
                name="exclude_overlapping_truck_assignments",
                expressions=[
                    (
                        DateRangeExpression(
                            "start_date",
                            "end_date",
                            RangeBoundary(
                                inclusive_lower=True,
                                inclusive_upper=True,
                            ),
                        ),
                        RangeOperators.OVERLAPS,
                    ),
                    ("truck", RangeOperators.EQUAL),
                ],
                violation_error_message=(
                    "هذه الشاحنة مرتبطة بعامل آخر خلال جزء من هذه الفترة."
                ),
            ),
            ExclusionConstraint(
                name="exclude_overlapping_worker_assignments",
                expressions=[
                    (
                        DateRangeExpression(
                            "start_date",
                            "end_date",
                            RangeBoundary(
                                inclusive_lower=True,
                                inclusive_upper=True,
                            ),
                        ),
                        RangeOperators.OVERLAPS,
                    ),
                    ("worker", RangeOperators.EQUAL),
                ],
                violation_error_message=(
                    "هذا العامل مرتبط بشاحنة أخرى خلال جزء من هذه الفترة."
                ),
            ),
        ]

    @property
    def is_current(self):
        return self.end_date is None or self.end_date >= date.today()

    def clean(self):
        super().clean()

        errors = {}

        if (
            self.start_date
            and self.end_date
            and self.end_date < self.start_date
        ):
            errors["end_date"] = (
                "تاريخ نهاية العمل لا يمكن أن يكون قبل تاريخ البداية."
            )

        if not self.start_date:
            if errors:
                raise ValidationError(errors)
            return

        overlap_end = self.end_date or date.max

        possible_overlaps = WorkerTruckAssignment.objects.filter(
            start_date__lte=overlap_end,
        ).filter(
            Q(end_date__isnull=True)
            | Q(end_date__gte=self.start_date)
        )

        if self.pk:
            possible_overlaps = possible_overlaps.exclude(pk=self.pk)

        if (
            self.truck_id
            and possible_overlaps.filter(truck_id=self.truck_id).exists()
        ):
            errors["truck"] = (
                "هذه الشاحنة مرتبطة بعامل آخر خلال جزء من هذه الفترة."
            )

        if (
            self.worker_id
            and possible_overlaps.filter(worker_id=self.worker_id).exists()
        ):
            errors["worker"] = (
                "هذا العامل مرتبط بشاحنة أخرى خلال جزء من هذه الفترة."
            )

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        period_end = self.end_date or "مستمر"
        return (
            f"{self.worker.full_name} — "
            f"{self.truck.registration_number} — "
            f"{self.start_date} إلى {period_end}"
        )
