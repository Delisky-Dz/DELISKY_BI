from django.db import connection, models


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
