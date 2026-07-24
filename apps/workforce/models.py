from django.conf import settings
from django.db import connection, models, transaction


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

    default_can_drive = models.BooleanField(
        "\u0627\u0644\u0642\u064a\u0627\u062f\u0629 "
        "\u0627\u0641\u062a\u0631\u0627\u0636\u064a\u064b\u0627",
        default=False,
    )
    default_can_sell = models.BooleanField(
        "\u0627\u0644\u0628\u064a\u0639 "
        "\u0627\u0641\u062a\u0631\u0627\u0636\u064a\u064b\u0627",
        default=False,
    )
    default_can_work_in_warehouse = (
        models.BooleanField(
            "\u0627\u0644\u0639\u0645\u0644 "
            "\u0641\u064a \u0627\u0644\u0645\u062e\u0632\u0646 "
            "\u0627\u0641\u062a\u0631\u0627\u0636\u064a\u064b\u0627",
            default=False,
        )
    )
    default_can_assist_distribution = (
        models.BooleanField(
            "\u0645\u0633\u0627\u0639\u062f\u0629 "
            "\u0627\u0644\u062a\u0648\u0632\u064a\u0639 "
            "\u0627\u0641\u062a\u0631\u0627\u0636\u064a\u064b\u0627",
            default=False,
        )
    )
    default_can_train_workers = (
        models.BooleanField(
            "\u062a\u062f\u0631\u064a\u0628 "
            "\u0627\u0644\u0639\u0645\u0627\u0644 "
            "\u0627\u0641\u062a\u0631\u0627\u0636\u064a\u064b\u0627",
            default=False,
        )
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
