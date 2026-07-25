from datetime import date

from django.conf import settings
from django.contrib.postgres.constraints import (
    ExclusionConstraint,
)
from django.contrib.postgres.fields import (
    DateRangeField,
    RangeBoundary,
    RangeOperators,
)
from django.core.exceptions import ValidationError
from django.db import connection, models, transaction
from django.db.models import Func, Q


WORKER_CODE_PREFIX = "DW"
WORKER_CODE_SEQUENCE = (
    "workforce_worker_code_seq"
)


def generate_worker_code() -> str:
    if connection.vendor != "postgresql":
        raise RuntimeError(
            "Automatic worker codes require PostgreSQL."
        )

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT nextval(%s::regclass)",
            [WORKER_CODE_SEQUENCE],
        )

        sequence_value = cursor.fetchone()[0]

    return (
        f"{WORKER_CODE_PREFIX}-"
        f"{sequence_value:05d}"
    )



class WorkerCapability(models.Model):
    code = models.CharField(
        "الرمز التقني",
        max_length=40,
        unique=True,
        null=True,
        blank=True,
        editable=False,
        help_text=(
            "رمز ثابت تستعمله المنظومة "
            "ولا يتغير بعد إنشاء القدرة."
        ),
    )
    name = models.CharField(
        "اسم القدرة",
        max_length=100,
        unique=True,
    )
    description = models.TextField(
        "الوصف",
        blank=True,
    )
    sort_order = models.PositiveSmallIntegerField(
        "الترتيب",
        default=100,
        db_index=True,
        help_text=(
            "الرقم الأصغر يظهر أولًا."
        ),
    )
    is_active = models.BooleanField(
        "نشطة",
        default=True,
        db_index=True,
        help_text=(
            "عطّل القدرة بدل حذفها "
            "للحفاظ على ارتباطاتها."
        ),
    )
    is_system = models.BooleanField(
        "قدرة أساسية",
        default=False,
        editable=False,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="أنشأها",
        null=True,
        blank=True,
        editable=False,
        on_delete=models.SET_NULL,
        related_name=(
            "worker_capabilities_created"
        ),
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="آخر من عدلها",
        null=True,
        blank=True,
        editable=False,
        on_delete=models.SET_NULL,
        related_name=(
            "worker_capabilities_updated"
        ),
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
        verbose_name = "قدرة عامل"
        verbose_name_plural = "قدرات العمال"
        ordering = (
            "sort_order",
            "name",
        )
        indexes = [
            models.Index(
                fields=(
                    "is_active",
                    "sort_order",
                ),
                name=(
                    "worker_capability_state_idx"
                ),
            ),
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            original_code = (
                type(self)
                .objects
                .filter(pk=self.pk)
                .values_list(
                    "code",
                    flat=True,
                )
                .first()
            )

            if original_code:
                self.code = original_code

        self.name = self.name.strip()
        self.description = (
            self.description.strip()
        )

        if not self.code and not self.pk:
            with transaction.atomic():
                super().save(*args, **kwargs)

                self.code = (
                    f"CAP-{self.pk:05d}"
                )

                type(self).objects.filter(
                    pk=self.pk
                ).update(
                    code=self.code
                )

            return

        if not self.code and self.pk:
            self.code = (
                f"CAP-{self.pk:05d}"
            )

        super().save(*args, **kwargs)

    def __str__(self):
        if self.code:
            return (
                f"{self.name} — {self.code}"
            )

        return self.name


class WorkerCategory(models.Model):
    code = models.CharField(
        "\u0627\u0644\u0631\u0645\u0632 "
        "\u0627\u0644\u062a\u0642\u0646\u064a",
        max_length=40,
        unique=True,
        null=True,
        blank=True,
        editable=False,
        help_text=(
            "\u0631\u0645\u0632 \u062b\u0627\u0628\u062a "
            "\u064a\u0633\u062a\u0639\u0645\u0644\u0647 "
            "\u0627\u0644\u0646\u0638\u0627\u0645 "
            "\u0648\u0644\u0627 \u064a\u062a\u063a\u064a\u0631."
        ),
    )
    name = models.CharField(
        "\u0627\u0633\u0645 \u0627\u0644\u0635\u0646\u0641",
        max_length=100,
        unique=True,
    )
    description = models.TextField(
        "\u0627\u0644\u0648\u0635\u0641",
        blank=True,
    )

    default_capabilities = models.ManyToManyField(
        "WorkerCapability",
        verbose_name="القدرات الافتراضية",
        blank=True,
        related_name=(
            "default_for_categories"
        ),
        help_text=(
            "قدرات مقترحة لهذا الصنف، "
            "ولا تغيّر قدرات العامل تلقائيًا."
        ),
    )

    sort_order = models.PositiveSmallIntegerField(
        "\u0627\u0644\u062a\u0631\u062a\u064a\u0628",
        default=100,
        db_index=True,
    )
    is_active = models.BooleanField(
        "\u0646\u0634\u0637",
        default=True,
        db_index=True,
        help_text=(
            "\u0639\u0637\u0651\u0644 \u0627\u0644\u0635\u0646\u0641 "
            "\u0628\u062f\u0644 \u062d\u0630\u0641\u0647 "
            "\u0644\u0644\u062d\u0641\u0627\u0638 "
            "\u0639\u0644\u0649 \u0627\u0644\u062a\u0627\u0631\u064a\u062e."
        ),
    )
    is_system = models.BooleanField(
        "\u0635\u0646\u0641 \u0623\u0633\u0627\u0633\u064a",
        default=False,
        editable=False,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=(
            "\u0623\u0646\u0634\u0623\u0647"
        ),
        null=True,
        blank=True,
        editable=False,
        on_delete=models.SET_NULL,
        related_name=(
            "worker_categories_created"
        ),
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=(
            "\u0622\u062e\u0631 \u0645\u0646 "
            "\u0639\u062f\u0644\u0647"
        ),
        null=True,
        blank=True,
        editable=False,
        on_delete=models.SET_NULL,
        related_name=(
            "worker_categories_updated"
        ),
    )

    created_at = models.DateTimeField(
        "\u062a\u0627\u0631\u064a\u062e "
        "\u0627\u0644\u0625\u0646\u0634\u0627\u0621",
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        "\u0622\u062e\u0631 \u062a\u0639\u062f\u064a\u0644",
        auto_now=True,
    )

    class Meta:
        verbose_name = (
            "\u0635\u0646\u0641 \u0639\u0627\u0645\u0644"
        )
        verbose_name_plural = (
            "\u0623\u0635\u0646\u0627\u0641 "
            "\u0627\u0644\u0639\u0645\u0627\u0644"
        )
        ordering = (
            "sort_order",
            "name",
        )
        indexes = [
            models.Index(
                fields=(
                    "is_active",
                    "sort_order",
                ),
                name=(
                    "worker_category_state_idx"
                ),
            ),
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            original_code = (
                type(self)
                .objects
                .filter(pk=self.pk)
                .values_list(
                    "code",
                    flat=True,
                )
                .first()
            )

            if original_code:
                self.code = original_code

        self.name = self.name.strip()
        self.description = (
            self.description.strip()
        )

        if not self.code and not self.pk:
            with transaction.atomic():
                super().save(*args, **kwargs)

                self.code = (
                    f"WC-{self.pk:05d}"
                )

                type(self).objects.filter(
                    pk=self.pk
                ).update(
                    code=self.code
                )

            return

        if not self.code and self.pk:
            self.code = (
                f"WC-{self.pk:05d}"
            )

        super().save(*args, **kwargs)

    def __str__(self):
        if self.code:
            return (
                f"{self.name} \u2014 {self.code}"
            )

        return self.name


class Worker(models.Model):
    employee_code = models.CharField(
        "الرقم الداخلي",
        max_length=30,
        unique=True,
        null=True,
        blank=True,
        help_text="رقم اختياري وفريد للعامل داخل الشركة.",
    )
    first_name = models.CharField(
        "الاسم",
        max_length=100,
    )
    last_name = models.CharField(
        "اللقب",
        max_length=100,
    )
    phone = models.CharField(
        "رقم الهاتف",
        max_length=30,
        blank=True,
    )

    capabilities = models.ManyToManyField(
        "WorkerCapability",
        verbose_name="قدرات العامل",
        blank=True,
        related_name="workers",
        help_text=(
            "القدرات الفعلية الخاصة بالعامل، "
            "وهي مستقلة عن منصبه الرسمي."
        ),
    )

    is_active = models.BooleanField(
        "نشط",
        default=True,
        db_index=True,
        help_text="ألغِ التحديد لتعطيل العامل دون حذف سجله.",
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
        verbose_name = "عامل"
        verbose_name_plural = "العمال"
        ordering = ["last_name", "first_name"]
        indexes = [
            models.Index(
                fields=["last_name", "first_name"],
                name="worker_name_idx",
            ),
        ]

    @property
    def full_name(self):
        return f"{self.last_name} {self.first_name}".strip()

    def save(self, *args, **kwargs):
        if self.pk:
            original_code = (
                type(self)
                .objects
                .filter(pk=self.pk)
                .values_list(
                    "employee_code",
                    flat=True,
                )
                .first()
            )

            if original_code:
                self.employee_code = (
                    original_code
                )

        elif not self.employee_code:
            self.employee_code = (
                generate_worker_code()
            )

        super().save(*args, **kwargs)

    def __str__(self):
        if self.employee_code:
            return f"{self.full_name} — {self.employee_code}"
        return self.full_name


class WorkerPositionPeriod(models.Model):
    worker = models.ForeignKey(
        Worker,
        verbose_name="\u0627\u0644\u0639\u0627\u0645\u0644",
        on_delete=models.PROTECT,
        related_name="position_periods",
    )
    category = models.ForeignKey(
        WorkerCategory,
        verbose_name=(
            "\u0635\u0646\u0641 "
            "\u0627\u0644\u0645\u0646\u0635\u0628"
        ),
        on_delete=models.PROTECT,
        related_name="worker_position_periods",
    )
    start_date = models.DateField(
        "\u062a\u0627\u0631\u064a\u062e "
        "\u0628\u062f\u0627\u064a\u0629 "
        "\u0627\u0644\u0645\u0646\u0635\u0628",
        db_index=True,
    )
    end_date = models.DateField(
        "\u062a\u0627\u0631\u064a\u062e "
        "\u0646\u0647\u0627\u064a\u0629 "
        "\u0627\u0644\u0645\u0646\u0635\u0628",
        null=True,
        blank=True,
        db_index=True,
        help_text=(
            "\u0627\u062a\u0631\u0643\u0647 "
            "\u0641\u0627\u0631\u063a\u064b\u0627 "
            "\u0625\u0630\u0627 \u0643\u0627\u0646 "
            "\u0627\u0644\u0639\u0627\u0645\u0644 "
            "\u0645\u0627 \u0632\u0627\u0644 "
            "\u0641\u064a \u0647\u0630\u0627 "
            "\u0627\u0644\u0645\u0646\u0635\u0628."
        ),
    )
    notes = models.TextField(
        "\u0645\u0644\u0627\u062d\u0638\u0627\u062a",
        blank=True,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=(
            "\u0623\u0646\u0634\u0623\u0647"
        ),
        null=True,
        blank=True,
        editable=False,
        on_delete=models.SET_NULL,
        related_name=(
            "worker_position_periods_created"
        ),
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=(
            "\u0622\u062e\u0631 \u0645\u0646 "
            "\u0639\u062f\u0644\u0647"
        ),
        null=True,
        blank=True,
        editable=False,
        on_delete=models.SET_NULL,
        related_name=(
            "worker_position_periods_updated"
        ),
    )

    created_at = models.DateTimeField(
        "\u062a\u0627\u0631\u064a\u062e "
        "\u0627\u0644\u0625\u0646\u0634\u0627\u0621",
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        "\u0622\u062e\u0631 \u062a\u0639\u062f\u064a\u0644",
        auto_now=True,
    )

    class Meta:
        verbose_name = (
            "\u0641\u062a\u0631\u0629 "
            "\u0645\u0646\u0635\u0628 "
            "\u0639\u0627\u0645\u0644"
        )
        verbose_name_plural = (
            "\u062a\u0627\u0631\u064a\u062e "
            "\u0645\u0646\u0627\u0635\u0628 "
            "\u0627\u0644\u0639\u0645\u0627\u0644"
        )
        ordering = (
            "-start_date",
            "worker",
            "category",
        )

        indexes = [
            models.Index(
                fields=(
                    "worker",
                    "start_date",
                ),
                name=(
                    "worker_position_start_idx"
                ),
            ),
            models.Index(
                fields=(
                    "category",
                    "start_date",
                ),
                name=(
                    "position_category_start_idx"
                ),
            ),
        ]

        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(end_date__isnull=True)
                    | Q(
                        end_date__gte=models.F(
                            "start_date"
                        )
                    )
                ),
                name=(
                    "worker_position_end_after_start"
                ),
                violation_error_message=(
                    "\u062a\u0627\u0631\u064a\u062e "
                    "\u0646\u0647\u0627\u064a\u0629 "
                    "\u0627\u0644\u0645\u0646\u0635\u0628 "
                    "\u0644\u0627 \u064a\u0645\u0643\u0646 "
                    "\u0623\u0646 \u064a\u0643\u0648\u0646 "
                    "\u0642\u0628\u0644 "
                    "\u062a\u0627\u0631\u064a\u062e "
                    "\u0627\u0644\u0628\u062f\u0627\u064a\u0629."
                ),
            ),
            ExclusionConstraint(
                name=(
                    "exclude_overlapping_worker_positions"
                ),
                expressions=[
                    (
                        Func(
                            "start_date",
                            "end_date",
                            RangeBoundary(
                                inclusive_lower=True,
                                inclusive_upper=True,
                            ),
                            function="DATERANGE",
                            output_field=DateRangeField(),
                        ),
                        RangeOperators.OVERLAPS,
                    ),
                    (
                        "worker",
                        RangeOperators.EQUAL,
                    ),
                ],
                violation_error_message=(
                    "\u0647\u0630\u0627 "
                    "\u0627\u0644\u0639\u0627\u0645\u0644 "
                    "\u0645\u0631\u062a\u0628\u0637 "
                    "\u0628\u0645\u0646\u0635\u0628 "
                    "\u0622\u062e\u0631 \u062e\u0644\u0627\u0644 "
                    "\u062c\u0632\u0621 \u0645\u0646 "
                    "\u0647\u0630\u0647 "
                    "\u0627\u0644\u0641\u062a\u0631\u0629."
                ),
            ),
        ]

    @property
    def is_current(self):
        today = date.today()

        return (
            self.start_date <= today
            and (
                self.end_date is None
                or self.end_date >= today
            )
        )

    def clean(self):
        super().clean()

        errors = {}

        if (
            self.start_date
            and self.end_date
            and self.end_date < self.start_date
        ):
            errors["end_date"] = (
                "\u062a\u0627\u0631\u064a\u062e "
                "\u0646\u0647\u0627\u064a\u0629 "
                "\u0627\u0644\u0645\u0646\u0635\u0628 "
                "\u0644\u0627 \u064a\u0645\u0643\u0646 "
                "\u0623\u0646 \u064a\u0643\u0648\u0646 "
                "\u0642\u0628\u0644 "
                "\u062a\u0627\u0631\u064a\u062e "
                "\u0627\u0644\u0628\u062f\u0627\u064a\u0629."
            )

        if not self.start_date:
            if errors:
                raise ValidationError(errors)
            return

        overlap_end = (
            self.end_date or date.max
        )

        possible_overlaps = (
            WorkerPositionPeriod.objects
            .filter(
                start_date__lte=overlap_end,
            )
            .filter(
                Q(end_date__isnull=True)
                | Q(
                    end_date__gte=self.start_date
                )
            )
        )

        if self.pk:
            possible_overlaps = (
                possible_overlaps.exclude(
                    pk=self.pk
                )
            )

        if (
            self.worker_id
            and possible_overlaps.filter(
                worker_id=self.worker_id
            ).exists()
        ):
            errors["worker"] = (
                "\u0647\u0630\u0627 "
                "\u0627\u0644\u0639\u0627\u0645\u0644 "
                "\u0644\u062f\u064a\u0647 "
                "\u0645\u0646\u0635\u0628 \u0622\u062e\u0631 "
                "\u062e\u0644\u0627\u0644 \u062c\u0632\u0621 "
                "\u0645\u0646 \u0647\u0630\u0647 "
                "\u0627\u0644\u0641\u062a\u0631\u0629."
            )

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        period_end = (
            self.end_date
            or "\u0645\u0633\u062a\u0645\u0631"
        )

        return (
            f"{self.worker.full_name} \u2014 "
            f"{self.category.name} \u2014 "
            f"{self.start_date} "
            f"\u0625\u0644\u0649 {period_end}"
        )
