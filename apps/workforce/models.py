from django.db import models


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

    def __str__(self):
        if self.employee_code:
            return f"{self.full_name} — {self.employee_code}"
        return self.full_name
